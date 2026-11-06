"""Collect historical merger deals and their outcomes from EDGAR (slow; responses are cached).

    SEC_USER_AGENT="Name email" python -m mergerarb.backtest.collect \\
        --start 2011-11-01 --end 2026-10-31 --out deals_hist.jsonl

Writes one JSON line per deal group, including skipped groups and the reason,
so the backtest can report how much of the universe it actually used.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from mergerarb.backtest.history import deal_outcome, pick_prices, price_statements
from mergerarb.extract import extract_terms, html_to_text
from mergerarb.scan import SPAC_SIC, clean_name, market_today, match_ticker
from mergerarb.sources import ARCHIVES, EFTS, SUBMISSIONS, TICKERS, Hit, parse_hits, sec_user_agent

FORMS = ("SC TO-T", "PREM14A", "DEFM14A")
READ_BYTES = 900_000
GROUP_DAYS = 400


class Limiter:
    """Thread-safe minimum spacing between requests."""

    def __init__(self, per_second: float):
        self.gap = 1.0 / per_second
        self.lock = threading.Lock()
        self.next = 0.0

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            t = max(now, self.next)
            self.next = t + self.gap
        if t > now:
            time.sleep(t - now)


class Fetcher:
    """Disk-cached GET with per-host rate limits, reading at most ``limit`` bytes."""

    def __init__(self, cache: Path):
        self.cache = cache
        cache.mkdir(parents=True, exist_ok=True)
        self.sec = Limiter(6)
        self.yahoo = Limiter(2)
        self.ua = sec_user_agent()

    def get(self, url: str, limit: int | None = None, retries: int = 3) -> str | None:
        """Text of ``url`` or None on 404 / persistent failure."""
        import hashlib

        p = self.cache / hashlib.sha256(url.encode()).hexdigest()[:32]
        if p.exists():
            body = p.read_text()
            return None if body == "\x00404" else body
        is_yahoo = "yahoo.com" in url
        ua = "Mozilla/5.0 (merger-arb research)" if is_yahoo else self.ua
        for attempt in range(retries):
            (self.yahoo if is_yahoo else self.sec).wait()
            try:
                req = urllib.request.Request(url, headers={"User-Agent": ua})
                with urllib.request.urlopen(req, timeout=60) as r:
                    raw = r.read(limit) if limit else r.read()
                body = raw.decode("utf-8", "replace")
                p.write_text(body)
                return body
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    p.write_text("\x00404")
                    return None
                time.sleep(2 * (attempt + 1))
            except Exception:  # noqa: BLE001 - network hiccup; retry
                time.sleep(2 * (attempt + 1))
        return None


@dataclass
class HistDeal:
    """One deal group in the historical universe."""

    target: str
    cik: int
    form: str
    filed: str
    filing_url: str
    group_forms: list[str]
    ticker: str | None = None
    acquirer: str | None = None
    acquirer_ticker: str | None = None
    cash: float = 0.0
    ratio: float = 0.0
    has_cvr: bool = False
    has_election: bool = False
    entry_date: str | None = None
    entry_price: float | None = None
    unaffected_price: float | None = None
    outcome: str | None = None
    outcome_date: str | None = None
    outcome_evidence: str = ""
    exit_price_break: float | None = None
    exit_basis: str | None = None
    acq_entry_price: float | None = None
    acq_exit_price: float | None = None
    last_filing: str | None = None
    expected_close: str | None = None
    skip: str | None = None
    notes: list[str] = field(default_factory=list)


def search_all(f: Fetcher, form: str, start: date, end: date, log) -> list[Hit]:
    """Every filing of ``form`` between start and end, paged year by year."""
    hits: list[Hit] = []
    y0 = start
    while y0 <= end:
        y1 = min(end, date(y0.year, 12, 31))
        offset = 0
        while True:
            q = urllib.parse.urlencode(
                {
                    "forms": form,
                    "dateRange": "custom",
                    "startdt": y0.isoformat(),
                    "enddt": y1.isoformat(),
                    "from": offset,
                }
            )
            body = f.get(f"{EFTS}?{q}")
            if not body:
                break
            payload = json.loads(body)
            page = parse_hits(payload)
            hits.extend(page)
            offset += len(page)
            total = payload.get("hits", {}).get("total", {}).get("value", 0)
            if not page or offset >= total or offset >= 9900:
                break
        log(f"  {form} {y0.year}: {offset}")
        y0 = date(y0.year + 1, 1, 1)
    return hits


def group_hits(hits: list[Hit]) -> list[list[Hit]]:
    """Group original filings by target, splitting groups more than 400 days apart."""
    by_cik: dict[int, list[Hit]] = {}
    for h in hits:
        if "/A" in h.form or not h.ciks or SPAC_SIC in h.sics:
            continue
        by_cik.setdefault(h.ciks[0], []).append(h)
    groups = []
    for hs in by_cik.values():
        hs.sort(key=lambda h: h.file_date)
        cur: list[Hit] = []
        for h in hs:
            if cur and (h.file_date - cur[0].file_date).days > GROUP_DAYS:
                groups.append(cur)
                cur = []
            cur.append(h)
        groups.append(cur)
    return groups


def submissions_events(f: Fetcher, cik: int, since: date) -> tuple[dict, list, list, list]:
    """Company profile plus (forms, dates, items) reaching back to ``since``."""
    body = f.get(SUBMISSIONS.format(cik=cik))
    if not body:
        return {}, [], [], []
    sub = json.loads(body)
    forms, dates, items = [], [], []

    def add(block: dict) -> None:
        forms.extend(block.get("form", []))
        dates.extend(date.fromisoformat(d) for d in block.get("filingDate", []))
        items.extend(block.get("items", [""] * len(block.get("form", []))))

    add(sub.get("filings", {}).get("recent", {}))
    for extra in sub.get("filings", {}).get("files", []):
        if date.fromisoformat(extra["filingTo"]) >= since:
            b = f.get(f"https://data.sec.gov/submissions/{extra['name']}")
            if b:
                add(json.loads(b))
    return sub, forms, dates, items


_yahoo_cache: dict[str, list[tuple[date, float]] | None] = {}
_yahoo_lock = threading.Lock()


def yahoo_closes(f: Fetcher, symbol: str) -> list[tuple[date, float]] | None:
    """Daily closes 2010-01-01 to today (split-adjusted, not dividend-adjusted)."""
    with _yahoo_lock:
        if symbol in _yahoo_cache:
            return _yahoo_cache[symbol]
    sym = urllib.parse.quote(symbol.replace(".", "-"))
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
        f"?period1=1262304000&period2={int(time.time()) // 86400 * 86400}&interval=1d"
    )
    body = f.get(url)
    out = None
    if body:
        try:
            r = json.loads(body)["chart"]["result"][0]
            out = [
                (datetime.fromtimestamp(t, UTC).date(), float(c))
                for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"], strict=False)
                if c is not None
            ]
        except (KeyError, IndexError, TypeError, ValueError):
            out = None
    with _yahoo_lock:
        _yahoo_cache[symbol] = out or None
    return out or None


def close_on_or_after(series: list[tuple[date, float]], d: date, max_gap: int = 10):
    """First close on/after ``d`` within ``max_gap`` days."""
    for day, c in series:
        if d <= day <= d + timedelta(days=max_gap):
            return day, c
        if day > d + timedelta(days=max_gap):
            break
    return None


def process_group(f: Fetcher, group: list[Hit], tickers: list[dict], today: date) -> HistDeal:
    """Build one HistDeal: terms, entry/unaffected prices, outcome, exit prices."""
    # Entry is the earliest filing so deals that break early are still counted.
    order = sorted(group, key=lambda h: h.file_date)
    first = order[0]
    name = clean_name(first.names[0]) if first.names else f"CIK {first.ciks[0]}"
    d = HistDeal(
        target=name,
        cik=first.ciks[0],
        form=first.form,
        filed=first.file_date.isoformat(),
        filing_url=first.url,
        group_forms=sorted({h.form for h in group}),
    )
    terms = entry = unaff = None
    for h in order:  # first filing with usable terms and an entry price
        raw = f.get(h.url, READ_BYTES)
        if not raw:
            continue
        text = html_to_text(raw)
        if h.form == "SC TO-T":
            idx = f.get(f"{ARCHIVES}/{h.ciks[0]}/{h.adsh.replace('-', '')}/index.json")
            if idx:
                items = json.loads(idx).get("directory", {}).get("item", [])
                docs = [
                    i
                    for i in items
                    if i.get("name", "").lower().endswith((".htm", ".html"))
                    and i["name"] != h.filename
                ]
                if docs:
                    best = max(
                        docs,
                        key=lambda i: (
                            int(i.get("size") or 0) if str(i.get("size") or "0").isdigit() else 0
                        ),
                    )
                    ex = f.get(
                        f"{ARCHIVES}/{h.ciks[0]}/{h.adsh.replace('-', '')}/{best['name']}",
                        READ_BYTES,
                    )
                    if ex:
                        text += " " + html_to_text(ex)
        t = extract_terms(text, after=h.file_date, target_name=name)
        if not (t.cash or t.ratio):
            continue
        acq = (
            clean_name(h.names[1]) if h.form == "SC TO-T" and len(h.names) > 1 else t.acquirer_name
        )
        value = t.cash if (t.cash and not t.ratio) else None
        e, u = pick_prices(price_statements(text, name, acq), h.file_date, value)
        if terms is None:
            terms, d.form, d.filed, d.filing_url, d.acquirer = (
                t,
                h.form,
                h.file_date.isoformat(),
                h.url,
                acq,
            )
            unaff = u
        if e:
            entry = e
            if h is not order[0]:
                d.notes.append(f"entry price from later {h.form} filed {h.file_date}")
                d.form, d.filed, d.filing_url = h.form, h.file_date.isoformat(), h.url
            unaff = unaff or u
            break
    if terms is None:
        d.skip = "no terms found"
        return d
    d.cash, d.ratio = terms.cash or 0.0, terms.ratio or 0.0
    if terms.expected_close:
        d.expected_close = terms.expected_close.isoformat()
    d.has_cvr, d.has_election = terms.has_cvr, terms.has_election
    if d.cash and d.ratio and terms.has_election:
        d.skip = "cash/stock election"
        return d
    if entry is None:
        d.skip = "no entry price in filing text"
        return d
    d.entry_date, d.entry_price = entry.day.isoformat(), entry.price
    d.unaffected_price = unaff.price if unaff else None

    sub, forms, dates, items = submissions_events(f, d.cik, entry.day)
    tk = sub.get("tickers") or []
    d.ticker = tk[0] if tk else None
    filed = date.fromisoformat(d.filed)
    last = max(dates) if dates else None
    d.last_filing = last.isoformat() if last else None
    oc = deal_outcome(forms, dates, items, filed)
    d.outcome, d.outcome_evidence = oc.status, oc.evidence
    d.outcome_date = oc.day.isoformat() if oc.day else None
    exp = date.fromisoformat(d.expected_close) if d.expected_close else None

    def stopped_filing_close() -> date | None:
        """Close date for a target that lost its ticker and stopped filing."""
        if d.ticker or last is None:
            return None
        day = max(last, exp) if exp else last
        return day if filed < day <= filed + timedelta(days=540) else None

    if oc.status == "broke" and not d.ticker and last and last <= oc.day + timedelta(days=180):
        # An item 1.02 report near the company's final filings is a closing, not a break.
        d.outcome = "closed"
        d.notes.append("termination 8-K was part of the closing (company stopped filing)")
    elif oc.status == "open":
        inferred = stopped_filing_close()
        if inferred and inferred <= today:
            d.outcome, d.outcome_date = "closed", inferred.isoformat()
            d.outcome_evidence = "company stopped filing and has no ticker"
        elif (today - filed).days > 900:
            series = yahoo_closes(f, d.ticker) if d.ticker else None
            at = filed + timedelta(days=365)
            px = close_on_or_after(series, at) if series else None
            if not px:
                d.skip = "outcome unknown"
                return d
            d.outcome, d.outcome_date = "broke", px[0].isoformat()
            d.exit_price_break, d.exit_basis = px[1], "still trading a year later"
            d.notes.append("no closing in filings and still listed; treated as broken")
    if d.outcome == "broke" and d.exit_price_break is None:
        series = yahoo_closes(f, d.ticker) if d.ticker else None
        px = close_on_or_after(series, oc.day + timedelta(days=1)) if series and oc.day else None
        if px:
            d.exit_price_break, d.exit_basis = px[1], "market price after break"
        elif d.unaffected_price:
            d.exit_price_break, d.exit_basis = d.unaffected_price, "unaffected price from filing"
        else:
            d.exit_price_break, d.exit_basis = (
                round(0.7 * d.entry_price, 4),
                "70% of entry (no price)",
            )
    elif d.outcome == "open":
        series = yahoo_closes(f, d.ticker) if d.ticker else None
        if series:
            d.exit_price_break, d.exit_basis = series[-1][1], f"marked to market {series[-1][0]}"
        else:
            d.exit_price_break, d.exit_basis = d.entry_price, "marked at entry (no price)"

    if d.ratio:
        d.acquirer_ticker = match_ticker(d.acquirer, tickers) if d.acquirer else None
        series = yahoo_closes(f, d.acquirer_ticker) if d.acquirer_ticker else None
        if not series:
            d.skip = "stock deal: no acquirer price history"
            return d
        a0 = close_on_or_after(series, entry.day, 5)
        end_day = date.fromisoformat(d.outcome_date) if d.outcome_date else series[-1][0]
        a1 = close_on_or_after(series, end_day) or (series[-1] if d.outcome == "open" else None)
        if not (a0 and a1):
            d.skip = "stock deal: acquirer price missing on entry or exit date"
            return d
        d.acq_entry_price, d.acq_exit_price = a0[1], a1[1]
        value = d.cash + d.ratio * a0[1]
        if not 0.5 * value <= d.entry_price <= 1.3 * value:
            d.skip = "entry price far from deal value (likely misread)"
    return d


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=date.fromisoformat, default=date(2011, 11, 1))
    ap.add_argument("--end", type=date.fromisoformat, default=date(2026, 10, 31))
    ap.add_argument("--out", type=Path, default=Path("deals_hist.jsonl"))
    ap.add_argument("--cache", type=Path, default=Path.home() / ".cache" / "mergerarb-hist")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args(argv)

    def log(m: str) -> None:
        print(m, file=sys.stderr, flush=True)

    f = Fetcher(a.cache)
    hits = []
    for form in FORMS:
        hits += search_all(f, form, a.start, a.end, log)
    groups = group_hits(hits)
    log(f"{len(hits)} filings -> {len(groups)} deal groups")
    tickers = list(json.loads(f.get(TICKERS)).values())
    todo = groups  # reruns are cheap: every response is cached on disk
    today = market_today()
    t0 = time.time()
    n = 0
    with a.out.open("w") as out, ThreadPoolExecutor(a.workers) as pool:
        futs = {pool.submit(process_group, f, g, tickers, today): g for g in todo}
        for fut in as_completed(futs):
            try:
                rec = fut.result()
            except Exception as e:  # noqa: BLE001 - keep going; record the failure
                g = futs[fut]
                rec = HistDeal(
                    clean_name(g[0].names[0]) if g[0].names else "?",
                    g[0].ciks[0],
                    g[0].form,
                    g[0].file_date.isoformat(),
                    g[0].url,
                    [],
                    skip=f"error: {e}",
                )
            out.write(json.dumps(asdict(rec)) + "\n")
            out.flush()
            n += 1
            if n % 100 == 0:
                log(f"{n}/{len(todo)} groups, {time.time() - t0:.0f}s")
    log("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
