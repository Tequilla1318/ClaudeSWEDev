"""Network access: SEC EDGAR and free daily prices.

EDGAR requires every automated request to declare who is making it, with a
contact email, in the User-Agent header. Set it in the environment:

    export SEC_USER_AGENT="Your Name your.email@example.com"

The SEC's fair-access limit is 10 requests per second; this client stays well
under it. Daily prices come from Yahoo Finance's public chart endpoint, which
is free but unofficial and can change without notice.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

EFTS = "https://efts.sec.gov/LATEST/search-index"
ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
TICKERS = "https://www.sec.gov/files/company_tickers.json"
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=2y&interval=1d"


class SourceError(RuntimeError):
    """A data source could not be reached or returned something unusable."""


class Http:
    """Small HTTP client with polite rate limiting and an optional disk cache.

    Filing documents never change once filed, so they are cached forever.
    Search results, submissions and prices are cached for ``ttl`` seconds.
    """

    def __init__(self, cache_dir: Path | None = None, ttl: float = 6 * 3600, pause: float = 0.15):
        self.cache_dir = cache_dir
        self.ttl = ttl
        self.pause = pause
        self._last = 0.0
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, url: str) -> Path | None:
        if not self.cache_dir:
            return None
        return self.cache_dir / hashlib.sha256(url.encode()).hexdigest()[:32]

    def get(self, url: str, user_agent: str, immutable: bool = False) -> str:
        """GET ``url`` as text, using the cache when fresh."""
        p = self._cache_path(url)
        if p and p.exists() and (immutable or time.time() - p.stat().st_mtime < self.ttl):
            return p.read_text()
        wait = self.pause - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(
            url, headers={"User-Agent": user_agent, "Accept-Encoding": "identity"}
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read().decode("utf-8", "replace")
        except Exception as e:
            raise SourceError(f"{url}: {e}") from e
        finally:
            self._last = time.monotonic()
        if p:
            p.write_text(body)
        return body


def sec_user_agent() -> str:
    """The User-Agent the SEC requires, from ``SEC_USER_AGENT``."""
    ua = os.environ.get("SEC_USER_AGENT", "").strip()
    if "@" not in ua:
        raise SourceError(
            "Set SEC_USER_AGENT to a name and contact email, e.g. "
            '"Jane Doe jane@example.com". The SEC rejects requests without one.'
        )
    return ua


@dataclass(frozen=True)
class Hit:
    """One filing returned by EDGAR full-text search."""

    adsh: str
    filename: str
    form: str
    file_date: date
    ciks: tuple[int, ...]
    names: tuple[str, ...]
    sics: tuple[str, ...]

    @property
    def url(self) -> str:
        """Link to the filing's primary document."""
        return f"{ARCHIVES}/{self.ciks[0]}/{self.adsh.replace('-', '')}/{self.filename}"

    @property
    def index_url(self) -> str:
        """Link to the filing's index page on EDGAR."""
        return f"{ARCHIVES}/{self.ciks[0]}/{self.adsh.replace('-', '')}/{self.adsh}-index.htm"


def parse_hits(payload: dict) -> list[Hit]:
    """Turn an EDGAR full-text-search response into ``Hit`` records."""
    out = []
    for h in payload.get("hits", {}).get("hits", []):
        s = h["_source"]
        adsh, _, fn = h["_id"].partition(":")
        out.append(
            Hit(
                adsh=adsh,
                filename=fn,
                form=s.get("form", ""),
                file_date=date.fromisoformat(s["file_date"]),
                ciks=tuple(int(c) for c in s.get("ciks", [])),
                names=tuple(s.get("display_names", [])),
                sics=tuple(s.get("sics", []) or []),
            )
        )
    return out


def search_filings(http: Http, form: str, start: date, end: date, max_hits: int = 400) -> list[Hit]:
    """All filings of one form type filed between ``start`` and ``end``."""
    ua = sec_user_agent()
    hits: list[Hit] = []
    offset = 0
    while offset < max_hits:
        q = urllib.parse.urlencode(
            {
                "forms": form,
                "dateRange": "custom",
                "startdt": start.isoformat(),
                "enddt": end.isoformat(),
                "from": offset,
            }
        )
        payload = json.loads(http.get(f"{EFTS}?{q}", ua))
        page = parse_hits(payload)
        hits.extend(page)
        total = payload.get("hits", {}).get("total", {}).get("value", 0)
        offset += len(page)
        if not page or offset >= total:
            break
    return hits


def submissions(http: Http, cik: int) -> dict:
    """A company's EDGAR profile and recent filings."""
    return json.loads(http.get(SUBMISSIONS.format(cik=cik), sec_user_agent()))


def filing_text(http: Http, hit: Hit) -> str:
    """Raw HTML of a filing's primary document."""
    return http.get(hit.url, sec_user_agent(), immutable=True)


def largest_exhibit(http: Http, hit: Hit) -> str | None:
    """Raw HTML of the biggest other .htm document in the filing, if any.

    A tender-offer filing's cover document is short; the Offer to Purchase,
    which states the expiry date, is a separate and usually the largest exhibit.
    """
    base = f"{ARCHIVES}/{hit.ciks[0]}/{hit.adsh.replace('-', '')}"
    listing = json.loads(http.get(f"{base}/index.json", sec_user_agent(), immutable=True))
    items = listing.get("directory", {}).get("item", [])
    docs = [
        i
        for i in items
        if i.get("name", "").lower().endswith((".htm", ".html"))
        and i["name"] != hit.filename
        and "index" not in i["name"].lower()
    ]
    if not docs:
        return None

    def size(i: dict) -> int:
        try:
            return int(i.get("size") or 0)
        except ValueError:
            return 0

    best = max(docs, key=size)
    return http.get(f"{base}/{best['name']}", sec_user_agent(), immutable=True)


def company_tickers(http: Http) -> list[dict]:
    """SEC's list of companies with tickers: dicts with cik_str, ticker, title."""
    return list(json.loads(http.get(TICKERS, sec_user_agent())).values())


@dataclass(frozen=True)
class PriceHistory:
    """Daily closes for one symbol, oldest first."""

    symbol: str
    dates: tuple[date, ...]
    closes: tuple[float, ...]

    def last(self) -> tuple[date, float]:
        """Most recent close."""
        return self.dates[-1], self.closes[-1]

    def close_before(self, day: date) -> tuple[date, float] | None:
        """Last close strictly before ``day``."""
        best = None
        for d, c in zip(self.dates, self.closes, strict=True):
            if d < day:
                best = (d, c)
            else:
                break
        return best


def parse_yahoo(symbol: str, payload: dict) -> PriceHistory:
    """Parse a Yahoo chart response, dropping days with no close."""
    try:
        r = payload["chart"]["result"][0]
        ts = r["timestamp"]
        closes = r["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError) as e:
        raise SourceError(f"no price data for {symbol}") from e
    pairs = [
        (datetime.fromtimestamp(t, UTC).date(), float(c))
        for t, c in zip(ts, closes, strict=False)
        if c is not None
    ]
    if not pairs:
        raise SourceError(f"no price data for {symbol}")
    return PriceHistory(symbol, tuple(d for d, _ in pairs), tuple(c for _, c in pairs))


def price_history(http: Http, symbol: str) -> PriceHistory:
    """Two years of daily closes from Yahoo Finance."""
    sym = urllib.parse.quote(symbol.replace(".", "-"))
    body = http.get(YAHOO.format(sym=sym), "Mozilla/5.0 (merger-arb research tool)")
    return parse_yahoo(symbol, json.loads(body))
