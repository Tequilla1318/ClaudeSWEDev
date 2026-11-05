"""Find pending US merger deals on EDGAR and price them.

Pipeline:
1. Search EDGAR for recent tender offers (SC TO-T) and merger proxies
   (PREM14A, DEFM14A). Skip amendments and blank-check companies (SPACs).
2. For each target, read its EDGAR filing history: drop deals whose target has
   already delisted (Form 25 / 15), find the announcement 8-K (item 1.01), and
   flag a later termination 8-K (item 1.02).
3. Extract cash per share, exchange ratio and expected close from the filing.
4. Price target and acquirer; use the close before the announcement as the
   default break price.

Run:  SEC_USER_AGENT="Name email" python -m mergerarb.scan --out deals.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from mergerarb.core import Deal, analyze
from mergerarb.extract import extract_terms, html_to_text
from mergerarb.sources import (
    Hit,
    Http,
    SourceError,
    company_tickers,
    filing_text,
    largest_exhibit,
    price_history,
    search_filings,
    submissions,
)

FORMS = {"SC TO-T": 120, "DEFM14A": 270, "PREM14A": 200}  # form -> look-back days
FORM_RANK = {"SC TO-T": 0, "DEFM14A": 1, "PREM14A": 2}
DELIST_FORMS = {"25", "25-NSE", "15-12B", "15-12G", "15F-12B", "15F-12G"}
SPAC_SIC = "6770"
DEFAULT_DAYS = {"SC TO-T": 30, "DEFM14A": 120, "PREM14A": 180}


@dataclass
class DealRecord:
    """One deal as shown in the deal list."""

    target: str
    target_cik: int
    target_ticker: str | None
    acquirer: str | None = None
    acquirer_ticker: str | None = None
    kind: str | None = None
    cash: float = 0.0
    ratio: float = 0.0
    target_price: float | None = None
    price_date: str | None = None
    acquirer_price: float | None = None
    announced: str | None = None
    break_price: float | None = None
    expected_close: str | None = None
    close_basis: str | None = None
    days_to_close: int | None = None
    filing_form: str = ""
    filing_date: str = ""
    filing_url: str = ""
    flags: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    review: str | None = None
    analysis: dict | None = None


def clean_name(display_name: str) -> str:
    """'Pacira BioSciences, Inc.  (PCRX)  (CIK 0001396814)' -> 'Pacira BioSciences, Inc.'"""
    return re.sub(r"\s*\((?:CIK [0-9]+|[A-Z0-9.,\- ]+)\)", "", display_name).strip()


def pick_candidates(hits: list[Hit]) -> list[Hit]:
    """One filing per target: the latest original filing of the most useful form.

    Tender offers win over proxies (they state price and expiry plainly), and a
    definitive proxy wins over a preliminary one.
    """
    best: dict[int, Hit] = {}
    for h in hits:
        if "/A" in h.form or not h.ciks or SPAC_SIC in h.sics:
            continue
        cik = h.ciks[0]
        cur = best.get(cik)
        key = (FORM_RANK.get(h.form, 9), -h.file_date.toordinal())
        if cur is None or key < (FORM_RANK.get(cur.form, 9), -cur.file_date.toordinal()):
            best[cik] = h
    return sorted(best.values(), key=lambda h: h.file_date, reverse=True)


@dataclass(frozen=True)
class Status:
    """What a company's filing history says about a deal."""

    delisted: bool
    terminated: bool
    announced: date | None
    ticker: str | None


def status_from_submissions(sub: dict, filed: date, lookback_days: int = 270) -> Status:
    """Read delisting, termination and announcement signals from EDGAR submissions."""
    recent = sub.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = [date.fromisoformat(d) for d in recent.get("filingDate", [])]
    items = recent.get("items", [""] * len(forms))
    delisted = terminated = False
    announced = None
    earliest = filed - timedelta(days=lookback_days)
    for f, d, it in zip(forms, dates, items, strict=False):
        it = it or ""
        if f in DELIST_FORMS and d >= filed:
            delisted = True
        if f == "8-K" and "1.02" in it and d > filed:
            terminated = True
        if (
            f == "8-K"
            and "1.01" in it
            and earliest <= d <= filed
            and (announced is None or d > announced)
        ):
            announced = d
    tickers = sub.get("tickers") or []
    return Status(delisted, terminated, announced, tickers[0] if tickers else None)


def _norm(s: str) -> str:
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    s = re.sub(r"\b(inc|corp|corporation|co|company|ltd|plc|holdings?|group|the|n v|s a)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def match_ticker(name: str, tickers: list[dict]) -> str | None:
    """Best-effort ticker for a company name from the SEC ticker list."""
    n = _norm(name)
    if not n:
        return None
    exact = [t for t in tickers if _norm(t["title"]) == n]
    if exact:
        return exact[0]["ticker"]
    prefix = [t for t in tickers if _norm(t["title"]).startswith(n + " ")]
    return prefix[0]["ticker"] if len(prefix) == 1 else None


def days_until(d: date, today: date) -> int:
    """Calendar days from ``today`` to ``d``, at least 1."""
    return max(1, (d - today).days)


def build_record(
    hit: Hit,
    status: Status,
    text: str,
    today: date,
    acquirer_ticker_hint: str | None,
    tickers: list[dict],
) -> DealRecord:
    """Combine a filing, its company history and extracted terms into a record (no prices)."""
    terms = extract_terms(text, after=today)
    rec = DealRecord(
        target=clean_name(hit.names[0]) if hit.names else f"CIK {hit.ciks[0]}",
        target_cik=hit.ciks[0],
        target_ticker=status.ticker,
        filing_form=hit.form,
        filing_date=hit.file_date.isoformat(),
        filing_url=hit.url,
        evidence=terms.evidence,
    )
    if hit.form == "SC TO-T" and len(hit.names) > 1:
        rec.acquirer = clean_name(hit.names[1])
        rec.acquirer_ticker = acquirer_ticker_hint
    elif terms.acquirer_name:
        rec.acquirer = terms.acquirer_name
        rec.acquirer_ticker = match_ticker(terms.acquirer_name, tickers)

    rec.cash = terms.cash or 0.0
    rec.ratio = terms.ratio or 0.0
    if rec.cash and rec.ratio:
        rec.kind = "cash+stock"
    elif rec.ratio:
        rec.kind = "stock"
    elif rec.cash:
        rec.kind = "cash"

    if status.announced:
        rec.announced = status.announced.isoformat()
    if terms.expected_close and terms.expected_close > today:
        rec.expected_close = terms.expected_close.isoformat()
        rec.close_basis = terms.close_basis
        rec.days_to_close = days_until(terms.expected_close, today)
    else:
        rec.days_to_close = DEFAULT_DAYS.get(hit.form, 120)
        rec.expected_close = (today + timedelta(days=rec.days_to_close)).isoformat()
        rec.close_basis = "default guess"
        rec.flags.append("Close date not found in the filing; using a default guess.")

    if terms.has_cvr:
        rec.flags.append("Includes a contingent value right (CVR) not counted in the spread.")
    if terms.has_ticking_fee:
        rec.flags.append("Has a ticking fee: the price rises if closing is delayed.")
    if status.terminated:
        rec.flags.append("A later 8-K reports a terminated agreement. Check the deal is still on.")

    if rec.kind is None:
        rec.review = "No cash price or exchange ratio found in the filing."
    elif terms.has_election and rec.kind == "cash+stock":
        rec.review = "Holders choose cash or stock (an election), so the terms can't be summed."
    elif rec.ratio and not rec.acquirer_ticker:
        rec.review = "Stock deal, but the acquirer's ticker couldn't be matched."
    elif rec.acquirer and _norm(rec.acquirer) and _norm(rec.acquirer) in _norm(rec.target):
        rec.review = "The filer looks like the acquirer, not the target."
    return rec


def price_record(rec: DealRecord, http: Http, today: date) -> None:
    """Fill prices, break price and spread analysis in place."""
    if rec.review:
        return
    if not rec.target_ticker:
        rec.review = "Target has no ticker on EDGAR."
        return
    try:
        th = price_history(http, rec.target_ticker)
    except SourceError:
        rec.review = f"No price data for {rec.target_ticker}."
        return
    d, p = th.last()
    if (today - d).days > 7:
        rec.review = f"Last price is from {d}; the stock may have stopped trading."
        return
    rec.target_price, rec.price_date = round(p, 4), d.isoformat()
    if rec.announced:
        before = th.close_before(date.fromisoformat(rec.announced))
        if before:
            rec.break_price = round(before[1], 4)
    if rec.break_price is None:
        rec.break_price = round(0.75 * p, 4)
        rec.flags.append("Pre-announcement price not found; break price set to 75% of today's.")
    elif rec.break_price >= p:
        rec.flags.append(
            "Target trades at or below its pre-announcement price, so that price is a poor "
            "break-price guess. Set your own."
        )
    if rec.ratio:
        try:
            rec.acquirer_price = round(price_history(http, rec.acquirer_ticker).last()[1], 4)
        except SourceError:
            rec.review = f"No price data for acquirer {rec.acquirer_ticker}."
            return
    deal = Deal(
        target_price=rec.target_price,
        fallback_price=rec.break_price,
        days_to_close=rec.days_to_close,
        cash=rec.cash,
        ratio=rec.ratio,
        acquirer_price=rec.acquirer_price or 0.0,
    )
    a = analyze(deal)
    if abs(a.gross_spread) > 0.5 * rec.target_price:
        rec.review = "Price is far from the extracted offer; the terms are probably wrong."
        return
    rec.analysis = {
        "deal_value": a.deal_value,
        "gross_spread": a.gross_spread,
        "net_return": a.net_return,
        "annualized": a.annualized_net_return,
        "implied_probability": a.implied_probability,
    }


def scan(http: Http, today: date, log=print) -> dict:
    """Run the full pipeline and return the deals payload."""
    hits: list[Hit] = []
    for form, back in FORMS.items():
        got = search_filings(http, form, today - timedelta(days=back), today)
        log(f"{form}: {len(got)} filings")
        hits.extend(got)
    cands = pick_candidates(hits)
    log(f"{len(cands)} candidate targets")
    tickers = company_tickers(http)
    records, closed = [], 0
    for h in cands:
        try:
            st = status_from_submissions(submissions(http, h.ciks[0]), h.file_date)
            if st.delisted:
                closed += 1
                continue
            hint = None
            if h.form == "SC TO-T" and len(h.ciks) > 1:
                hint = status_from_submissions(submissions(http, h.ciks[1]), h.file_date).ticker
            text = html_to_text(filing_text(http, h))[:150_000]
            if h.form == "SC TO-T":
                exhibit = largest_exhibit(http, h)
                if exhibit:
                    text += " " + html_to_text(exhibit)[:150_000]
            rec = build_record(h, st, text, today, hint, tickers)
            price_record(rec, http, today)
        except SourceError as e:
            log(f"skip {h.names[:1]}: {e}")
            continue
        records.append(rec)
    listed = [r for r in records if r.analysis]
    listed.sort(key=lambda r: r.analysis["annualized"], reverse=True)
    review = [r for r in records if not r.analysis]
    log(f"{len(listed)} priced, {len(review)} need review, {closed} already closed")
    return {
        "generated": today.isoformat(),
        "deals": [asdict(r) for r in listed],
        "review": [asdict(r) for r in review],
        "closed_skipped": closed,
    }


def market_today() -> date:
    """Today's date in New York, where US markets trade."""
    return datetime.now(ZoneInfo("America/New_York")).date()


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=Path("deals.json"))
    ap.add_argument("--cache", type=Path, default=Path.home() / ".cache" / "mergerarb")
    args = ap.parse_args(argv)
    try:
        payload = scan(Http(args.cache), market_today(), log=lambda m: print(m, file=sys.stderr))
    except SourceError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    args.out.write_text(json.dumps(payload, indent=1))
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
