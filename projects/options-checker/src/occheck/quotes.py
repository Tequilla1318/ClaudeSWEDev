"""Cboe delayed option quotes, for prefilling the pre-trade checker (localhost only).

Cboe publishes a free, roughly 15-minute delayed option chain per symbol at
``cdn-api.cboe.com/api/global/delayed_quotes/options/<SYMBOL>.json``. It isn't a
documented API, so this module validates what comes back and fails with a clear
message. Like the other data in this project it is fetched on the user's own
machine by ``occheck serve`` and never republished. Browsers can't fetch it
directly (no CORS headers), so on GitHub Pages the checker stays manual-entry.
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from dataclasses import dataclass
from datetime import date

from occheck.data import USER_AGENT

URL = "https://cdn-api.cboe.com/api/global/delayed_quotes/options/{}.json"
INDEXES = {"SPX", "XSP", "NDX", "RUT", "VIX", "DJX", "OEX", "MRUT"}  # Cboe prefixes these with "_"
_OCC = re.compile(r"^(?P<root>[A-Z0-9.]+?)(?P<ymd>\d{6})(?P<right>[CP])(?P<strike>\d{8})$")


class QuoteError(ValueError):
    """The quote feed returned something unusable. The message says what."""


@dataclass(frozen=True)
class OptionQuote:
    """One listed option's delayed quote."""

    root: str
    expiry: date
    right: str
    strike: float
    bid: float
    ask: float
    iv: float
    delta: float
    open_interest: float
    volume: float


@dataclass(frozen=True)
class Chain:
    """A symbol's delayed chain."""

    symbol: str
    timestamp: str
    spot: float
    iv30: float | None
    options: list[OptionQuote]


def feed_symbol(symbol: str) -> str:
    """Cboe's file name for a ticker: indexes get a leading underscore (SPX -> _SPX)."""
    s = symbol.strip().upper().lstrip("_^")
    if not re.fullmatch(r"[A-Z0-9.]{1,8}", s):
        raise QuoteError(f"{symbol!r} doesn't look like a ticker")
    return f"_{s}" if s in INDEXES else s


def parse_occ(code: str) -> tuple[str, date, str, float]:
    """Split an OCC symbol like ``AAPL270115P00365000`` into (root, expiry, right, strike)."""
    m = _OCC.match(code.replace(" ", ""))
    if not m:
        raise QuoteError(f"unrecognized option symbol {code!r}")
    ymd = m["ymd"]
    expiry = date(2000 + int(ymd[:2]), int(ymd[2:4]), int(ymd[4:]))
    return m["root"], expiry, m["right"], int(m["strike"]) / 1000.0


def load_chain(text: str) -> Chain:
    """Parse Cboe's delayed-quote JSON."""
    try:
        doc = json.loads(text)
        d = doc["data"]
        spot = float(d["current_price"])
        rows = d["options"]
    except (ValueError, KeyError, TypeError) as exc:
        raise QuoteError(f"not a Cboe delayed-quote file ({exc})") from exc
    opts = []
    for row in rows:
        try:
            root, expiry, right, strike = parse_occ(row["option"])
        except (QuoteError, KeyError):
            continue
        opts.append(
            OptionQuote(
                root=root,
                expiry=expiry,
                right=right,
                strike=strike,
                bid=float(row.get("bid") or 0.0),
                ask=float(row.get("ask") or 0.0),
                iv=float(row.get("iv") or 0.0),
                delta=float(row.get("delta") or 0.0),
                open_interest=float(row.get("open_interest") or 0.0),
                volume=float(row.get("volume") or 0.0),
            )
        )
    if not opts:
        raise QuoteError("the quote file has no options")
    iv30 = d.get("iv30")
    return Chain(
        symbol=str(d.get("symbol") or ""),
        timestamp=str(doc.get("timestamp") or ""),
        spot=spot,
        iv30=float(iv30) if iv30 not in (None, "") else None,
        options=opts,
    )


def summary(chain: Chain) -> dict:
    """Spot, timestamp and the expiries on offer (what the page shows first)."""
    exps = sorted({o.expiry for o in chain.options})
    return {
        "symbol": chain.symbol,
        "timestamp": chain.timestamp,
        "spot": chain.spot,
        "iv30": chain.iv30,
        "expiries": [e.isoformat() for e in exps],
    }


def expiry_rows(chain: Chain, expiry: date) -> list[dict]:
    """Quotes for one expiry, sorted by right then strike, with zero-ask rows dropped."""
    rows = [o for o in chain.options if o.expiry == expiry and o.ask > 0]
    rows.sort(key=lambda o: (o.right, o.strike))
    return [
        {
            "right": o.right,
            "strike": o.strike,
            "bid": o.bid,
            "ask": o.ask,
            "iv": o.iv,
            "delta": o.delta,
            "oi": o.open_interest,
            "root": o.root,
        }
        for o in rows
    ]


_CACHE: dict[str, tuple[float, Chain]] = {}


def fetch_chain(symbol: str, max_age_s: float = 300.0, timeout: float = 30.0) -> Chain:
    """Download (or reuse a 5-minute cached copy of) a symbol's chain. Localhost only."""
    key = feed_symbol(symbol)
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < max_age_s:
        return hit[1]
    req = urllib.request.Request(URL.format(key), headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed https URL
            text = resp.read().decode("utf-8")
    except OSError as exc:
        raise QuoteError(f"couldn't reach Cboe for {key}: {exc}") from exc
    chain = load_chain(text)
    _CACHE[key] = (time.time(), chain)
    return chain
