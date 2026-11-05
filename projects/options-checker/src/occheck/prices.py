"""Daily stock prices (via yfinance, localhost only) and the metrics that need them.

* :func:`pgr_plr` — Odean's (1998) disposition measure: on each day you sold stock,
  count every position as a realized or paper gain or loss, then compare the
  proportion of gains realized (PGR) with the proportion of losses realized (PLR).
* :func:`realized_vol` — annualized close-to-close volatility, for the checker.

yfinance reads Yahoo Finance's public pages. It's an optional dependency
(``pip install "occheck[local]"``) used only by ``occheck serve`` on the user's own
machine; browsers can't reach Yahoo directly and nothing is republished.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date

from occheck.trades import Trade

YAHOO_SYMBOLS = {"SPX": "^GSPC", "NDX": "^NDX", "RUT": "^RUT", "VIX": "^VIX", "DJX": "^DJI"}

Prices = dict[str, dict[date, float]]  # symbol -> {day: close}


class PriceError(ValueError):
    """Prices couldn't be fetched or parsed. The message says why."""


def realized_vol(closes: list[float], window: int = 21) -> float | None:
    """Annualized volatility of the last ``window`` daily log returns (252 trading days)."""
    if len(closes) < window + 1:
        return None
    tail = closes[-(window + 1) :]
    rets = [math.log(b / a) for a, b in zip(tail[:-1], tail[1:], strict=True) if a > 0 and b > 0]
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var * 252.0)


def _close_on(series: dict[date, float], day: date) -> float | None:
    """Close on ``day``, or the latest close before it."""
    if day in series:
        return series[day]
    earlier = [d for d in series if d <= day]
    return series[max(earlier)] if earlier else None


def pgr_plr(trades: list[Trade], prices: Prices) -> dict[str, float | int | None]:
    """Odean's proportion of gains realized (PGR) and of losses realized (PLR), stocks only.

    On each day with at least one stock sale, every stock held at the start of that day
    counts once: a *realized* gain or loss if it was sold that day (sale price vs average
    cost), otherwise a *paper* gain or loss if that day's close is above or below its
    average cost. Positions with no price that day are skipped. Ties count as neither.
    """
    stock = sorted((t for t in trades if t.asset_class == "STK"), key=lambda t: t.when)
    qty: dict[str, float] = defaultdict(float)
    cost: dict[str, float] = defaultdict(float)  # average cost per share
    by_day: dict[date, list[Trade]] = defaultdict(list)
    for t in stock:
        by_day[t.when.date()].append(t)
    rg = rl = pg = pl = 0
    skipped = 0
    for day in sorted(by_day):
        day_trades = by_day[day]
        sells = {t.symbol: t for t in day_trades if t.quantity < 0 and qty[t.symbol] > 0}
        if sells:
            for sym, q in list(qty.items()):
                if q <= 0:
                    continue
                if sym in sells:
                    px = sells[sym].price
                    rg += px > cost[sym]
                    rl += px < cost[sym]
                else:
                    close = _close_on(prices.get(sym, {}), day)
                    if close is None:
                        skipped += 1
                        continue
                    pg += close > cost[sym]
                    pl += close < cost[sym]
        for t in day_trades:  # then apply the day's trades to holdings
            if t.quantity > 0:
                total = qty[t.symbol] + t.quantity
                cost[t.symbol] = (cost[t.symbol] * qty[t.symbol] + t.price * t.quantity) / total
                qty[t.symbol] = total
            else:
                qty[t.symbol] = max(qty[t.symbol] + t.quantity, 0.0)
    pgr = rg / (rg + pg) if rg + pg else None
    plr = rl / (rl + pl) if rl + pl else None
    return {
        "realized_gains": rg,
        "paper_gains": pg,
        "realized_losses": rl,
        "paper_losses": pl,
        "pgr": pgr,
        "plr": plr,
        "ratio": pgr / plr if pgr is not None and plr else None,
        "skipped_no_price": skipped,
    }


def yfinance_closes(symbol: str, start: date, end: date) -> dict[date, float]:
    """Daily closes from Yahoo Finance via yfinance (localhost only; optional dependency)."""
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise PriceError('price history needs yfinance: pip install "occheck[local]"') from exc
    ysym = YAHOO_SYMBOLS.get(symbol.upper(), symbol.upper())
    try:
        hist = yf.Ticker(ysym).history(
            start=start.isoformat(), end=end.isoformat(), auto_adjust=False
        )
    except Exception as exc:  # yfinance raises many types on network/HTML changes
        raise PriceError(f"yfinance failed for {ysym}: {exc}") from exc
    if hist is None or hist.empty:
        raise PriceError(f"no prices from Yahoo for {ysym}")
    return {ts.date(): float(c) for ts, c in hist["Close"].items()}
