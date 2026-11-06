"""Cross-sectional stock momentum, long-short, for a Canadian (Ontario) investor.

The strategy the source video describes, in its standard academic form
(Jegadeesh & Titman 1993; the 12-1 signal used by Fama-French "Mom"):

- Universe: S&P 500 members on each rebalance date (point-in-time membership
  from github.com/fja05680/sp500), so stocks are only eligible while they were
  actually in the index.
- Signal: total return from 12 months ago to 1 month ago (the latest month is
  skipped, because one-month returns tend to reverse).
- Each month-end: buy the top 10% equally weighted and short the bottom 10%
  equally weighted, each side sized to 100% of equity (dollar-neutral, 2x gross).
- Costs: IBKR Fixed commissions per order, SEC/FINRA fees on sales and short
  sales, slippage, and a borrow fee on the short side.
- Tax (non-registered, a short book can't sit in a TFSA): every sale or cover
  realizes a gain in CAD (average cost per stock, exchange rate on each trade
  date), gains on the USD cash pool are realized when it is converted, taxed
  yearly at the capital-gains rate with losses carried forward, or every gain
  at the ordinary rate if the CRA treats it as business income.

Known biases: Yahoo Finance has no prices for companies that were later
delisted or renamed, so those members can't be ranked or held. The share of
members priced each month is reported. Missing bankruptcies would have been
profitable shorts; missing takeovers would have hurt shorts and helped longs.
Dividends are inside the adjusted prices and so are taxed as capital gains
here (in reality a long's dividends are income and a short's are a deduction;
the two roughly cancel in a dollar-neutral book).
"""

from __future__ import annotations

import csv
import io
import json
import time
import urllib.parse
import zipfile
from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from mergerarb.backtest.costs import BORROW_FEE, Bracket, IbkrFixed, fx_cost
from mergerarb.backtest.sim import Series

MEMBERS_URL = (
    "https://raw.githubusercontent.com/fja05680/sp500/master/"
    "S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv"
)
UMD_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_CSV.zip"


# --- data ------------------------------------------------------------------------


def parse_members(text: str) -> list[tuple[date, frozenset[str]]]:
    """Point-in-time membership rows: (date, tickers), oldest first."""
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        rows.append((date.fromisoformat(r["date"]), frozenset(r["tickers"].split(","))))
    return sorted(rows)


def members_on(rows: list[tuple[date, frozenset[str]]], day: date) -> frozenset[str]:
    """Index members on ``day`` (the latest row on or before it)."""
    i = bisect_right([d for d, _ in rows], day) - 1
    return rows[max(i, 0)][1]


def parse_umd(raw_zip: bytes) -> dict[tuple[int, int], float]:
    """Fama-French monthly momentum factor (decimal returns) keyed by (year, month)."""
    z = zipfile.ZipFile(io.BytesIO(raw_zip))
    out = {}
    for line in z.read(z.namelist()[0]).decode("latin1").splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 2 and len(parts[0]) == 6 and parts[0].isdigit():
            v = float(parts[1])
            if v > -99:
                out[(int(parts[0][:4]), int(parts[0][4:]))] = v / 100
        elif len(parts) == 2 and len(parts[0]) == 4 and parts[0].isdigit():
            break  # annual section starts
    return out


def yahoo_symbol(ticker: str) -> str:
    """Index-file ticker to Yahoo symbol (BRK.B -> BRK-B)."""
    return ticker.replace(".", "-")


def fetch_adjusted(fetcher, ticker: str, start: date, end: date) -> list[tuple[date, float]] | None:
    """Daily dividend-and-split-adjusted closes from Yahoo, or None if it has none."""
    p1 = int(datetime(start.year, start.month, start.day, tzinfo=UTC).timestamp())
    p2 = int(datetime(end.year, end.month, end.day, tzinfo=UTC).timestamp()) + 86400 * 5
    sym = urllib.parse.quote(yahoo_symbol(ticker))
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}"
        f"&period2={p2}&interval=1d&events=div%2Csplit"
    )
    body = fetcher.get(url)
    if not body:
        return None
    try:
        r = json.loads(body)["chart"]["result"][0]
        adj = r["indicators"]["adjclose"][0]["adjclose"]
        return [
            (datetime.fromtimestamp(t, UTC).date(), float(c))
            for t, c in zip(r["timestamp"], adj, strict=False)
            if c is not None and c > 0
        ]
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def month_ends(start: date, end: date) -> list[date]:
    """Last calendar day of each month from ``start``'s month to ``end``'s."""
    out, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        nxt = date(y + (m == 12), m % 12 + 1, 1)
        out.append(min(nxt - timedelta(days=1), end))
        y, m = nxt.year, nxt.month
    return out


class PriceBook:
    """Adjusted closes for many stocks, looked up on or just before a date."""

    def __init__(self, series: dict[str, list[tuple[date, float]]]):
        self.days = {t: [d for d, _ in s] for t, s in series.items()}
        self.vals = {t: [v for _, v in s] for t, s in series.items()}

    def at(self, ticker: str, day: date, max_stale: int = 7) -> float | None:
        """Close on or before ``day``, if one exists within ``max_stale`` days."""
        ds = self.days.get(ticker)
        if not ds:
            return None
        i = bisect_right(ds, day) - 1
        if i < 0 or (day - ds[i]).days > max_stale:
            return None
        return self.vals[ticker][i]


def momentum_scores(prices: PriceBook, tickers: frozenset[str], day: date) -> dict[str, float]:
    """12-1 momentum for every ticker with prices 12 and 1 months back and today."""
    t12 = day - timedelta(days=365)
    t1 = day - timedelta(days=30)
    out = {}
    for t in tickers:
        p12, p1, p0 = prices.at(t, t12), prices.at(t, t1), prices.at(t, day)
        if p12 and p1 and p0:
            out[t] = p1 / p12 - 1
    return out


def pick_legs(scores: dict[str, float], fraction: float = 0.10) -> tuple[list[str], list[str]]:
    """Top and bottom ``fraction`` of tickers by score (ties broken by ticker)."""
    ranked = sorted(scores, key=lambda t: (scores[t], t))
    n = max(1, int(len(ranked) * fraction))
    return ranked[-n:], ranked[:n]


# --- simulation --------------------------------------------------------------------


@dataclass
class MomConfig:
    """Momentum book settings."""

    start: date
    end: date
    capital_cad: float = 100_000.0
    fraction: float = 0.10
    gross_per_side: float = 1.0  # each leg sized to this multiple of equity
    account: str = "nonreg"  # "nonreg" or "pretax"
    regime: str = "capital"
    bracket: Bracket | None = None
    ibkr: IbkrFixed = field(default_factory=lambda: IbkrFixed(slippage=0.0005))
    borrow_fee: float = BORROW_FEE


@dataclass
class MomResult:
    """Output of a momentum run."""

    nav_cad: list[tuple[date, float]]
    final_cad: float
    taxes_cad: float
    fees_usd: float
    turnover: float  # average one-way traded value per month / equity
    coverage: list[tuple[date, float]]  # share of index members priced
    leg_returns: list[tuple[date, float]]  # gross long-minus-short return per month (USD)
    years: dict[int, dict] = field(default_factory=dict)


def simulate_momentum(
    members: list[tuple[date, frozenset[str]]],
    prices: PriceBook,
    fx: Series,
    cfg: MomConfig,
) -> MomResult:
    """Run the monthly long-short book."""
    ib = cfg.ibkr
    taxed = cfg.account == "nonreg"
    r0 = fx.at(cfg.start)
    cash = cfg.capital_cad / r0
    cash -= fx_cost(cash)
    acb_fx = cfg.capital_cad / cash  # CAD per USD of the cash pool
    pos: dict[str, float] = {}  # shares; negative = short
    acb_cad: dict[str, float] = {}  # CAD cost (long) or CAD proceeds (short), whole position
    year = {"cg": 0.0, "fx": 0.0}
    carry = taxes = fees = traded = 0.0
    nav, cov, legs = [], [], []
    years: dict[int, dict] = {}
    months = month_ends(cfg.start, cfg.end)
    n_months = 0

    def pool(delta_usd: float, rate: float) -> None:
        """Move USD in (+) or out (-) of the cash pool, realizing FX on outflows."""
        nonlocal cash, acb_fx
        if delta_usd >= 0:
            total = cash + delta_usd
            acb_fx = (cash * acb_fx + delta_usd * rate) / total if total > 0 and cash > 0 else rate
            cash = total
        else:
            year["fx"] += -delta_usd * (rate - acb_fx)
            cash += delta_usd

    def trade(t: str, new_shares: float, px: float, rate: float) -> None:
        """Change a position to ``new_shares``, booking costs and realized CAD gains."""
        nonlocal fees, traded
        old = pos.get(t, 0.0)
        delta = new_shares - old
        if abs(delta) < 1e-9:
            return
        qty = abs(delta)
        traded += qty * px
        # Closing part of the position (toward zero) realizes a gain on that part.
        closing = min(qty, abs(old)) if old * delta < 0 else 0.0
        if closing:
            frac = closing / abs(old)
            basis = acb_cad.get(t, 0.0) * frac
            if old > 0:  # selling a long
                proceeds = closing * px - ib.sell_cost(closing, px)
                year["cg"] += proceeds * rate - basis
                pool(proceeds, rate)
                fees += ib.sell_cost(closing, px)
            else:  # covering a short
                cost = closing * px + ib.buy_cost(closing, px)
                year["cg"] += basis - cost * rate
                pool(-cost, rate)
                fees += ib.buy_cost(closing, px)
            acb_cad[t] = acb_cad.get(t, 0.0) - basis
        opening = qty - closing
        if opening:
            side = 1 if delta > 0 else -1
            if side > 0:  # buying long
                cost = opening * px + ib.buy_cost(opening, px)
                pool(-cost, rate)
                acb_cad[t] = acb_cad.get(t, 0.0) + cost * rate
                fees += ib.buy_cost(opening, px)
            else:  # selling short: proceeds go into the pool as collateral
                proceeds = opening * px - ib.sell_cost(opening, px)
                pool(proceeds, rate)
                acb_cad[t] = acb_cad.get(t, 0.0) + proceeds * rate
                fees += ib.sell_cost(opening, px)
        if abs(new_shares) < 1e-9:
            pos.pop(t, None)
            acb_cad.pop(t, None)
        else:
            pos[t] = new_shares

    def equity_usd(day: date) -> float:
        total = cash
        for t, n in pos.items():
            px = prices.at(t, day, max_stale=40)
            total += n * (px if px else 0.0)
        return total

    def pay_tax(day: date, final: bool = False) -> None:
        nonlocal carry, taxes
        b = cfg.bracket
        g = year["cg"] + year["fx"]
        if cfg.regime == "business":
            tax = g * b.ordinary
        else:
            if g < 0:
                carry += -g
                g = 0.0
            else:
                use = min(carry, g)
                carry -= use
                g -= use
            tax = g * b.capital_gains
        years[day.year] = {"gains_cad": year["cg"], "fx_cad": year["fx"], "tax_cad": tax}
        year.update(cg=0.0, fx=0.0)
        taxes += tax
        if not final:
            rate = fx.at(day)
            pool(-(tax / rate) - fx_cost(abs(tax) / rate), rate)

    prev_long_val = prev_short_val = None
    prev_day = None
    for day in months:
        rate = fx.at(day)
        # Gross leg return over the month just ended (before this rebalance).
        if prev_day is not None and prev_long_val:
            lv = sum(n * (prices.at(t, day, 40) or 0) for t, n in pos.items() if n > 0)
            sv = sum(-n * (prices.at(t, day, 40) or 0) for t, n in pos.items() if n < 0)
            legs.append((day, lv / prev_long_val - sv / prev_short_val))
        # Borrow fee for the month on the short side.
        short_val = sum(-n * (prices.at(t, day, 40) or 0) for t, n in pos.items() if n < 0)
        if prev_day is not None and short_val:
            fee = cfg.borrow_fee * short_val * (day - prev_day).days / 365
            pool(-fee, rate)
            fees += fee
        # Year-end tax before rebalancing in December.
        if taxed and prev_day is not None and day.month == 12:
            pay_tax(day)
        if day >= cfg.end:
            break
        mem = members_on(members, day)
        scores = momentum_scores(prices, mem, day)
        cov.append((day, len(scores) / max(len(mem), 1)))
        longs, shorts = pick_legs(scores, cfg.fraction)
        eq = equity_usd(day)
        nav.append((day, eq * rate))
        n_months += 1
        side = cfg.gross_per_side * eq
        target = {t: side / len(longs) / prices.at(t, day) for t in longs}
        target.update({t: -side / len(shorts) / prices.at(t, day) for t in shorts})
        for t in list(pos):
            if t not in target:
                px = prices.at(t, day, max_stale=40)
                if px:
                    trade(t, 0.0, px, rate)
                else:
                    pos.pop(t)  # no price at all: written off at zero (rare)
                    acb_cad.pop(t, None)
        for t, n in target.items():
            trade(t, n, prices.at(t, day), rate)
        prev_long_val = sum(n * prices.at(t, day) for t, n in pos.items() if n > 0)
        prev_short_val = sum(-n * prices.at(t, day) for t, n in pos.items() if n < 0)
        prev_day = day

    # Liquidate at the end.
    end = cfg.end
    rate = fx.at(end)
    for t in list(pos):
        px = prices.at(t, end, max_stale=40)
        trade(t, 0.0, px if px else 0.0, rate)
    year["fx"] += cash * (rate - acb_fx)
    cad = cash * rate - fx_cost(cash) * rate
    fees += fx_cost(cash)
    final_tax = 0.0
    if taxed:
        before = taxes
        pay_tax(end, final=True)
        final_tax = taxes - before
    final = cad - final_tax
    nav.append((end, final))
    first_eq = cfg.capital_cad / r0
    return MomResult(
        nav, final, taxes, fees, traded / 2 / max(n_months, 1) / first_eq, cov, legs, years
    )


def load_prices(fetcher, members, start: date, end: date, log=print) -> PriceBook:
    """Yahoo adjusted closes for every ticker that was in the index during the window."""
    tickers = sorted(
        {t for d, ts in members if start - timedelta(days=400) <= d <= end for t in ts}
    )
    series, missing = {}, 0
    t0 = time.time()
    for i, t in enumerate(tickers):
        s = fetch_adjusted(fetcher, t, start - timedelta(days=420), end)
        if s:
            series[t] = s
        else:
            missing += 1
        if (i + 1) % 100 == 0:
            log(f"  prices {i + 1}/{len(tickers)} ({missing} missing) {time.time() - t0:.0f}s")
    log(f"prices for {len(series)} of {len(tickers)} tickers")
    return PriceBook(series)
