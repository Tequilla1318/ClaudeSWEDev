"""Portfolio simulation: a systematic merger-arb book for a Canadian (Ontario) investor.

Rules (fixed in advance, applied to every deal the same way):
- Enter on the day the deal's first usable filing appears, at the closing price the
  filing states for its most recent practicable date.
- Only enter if the stock trades below the offer value by more than 0% and at
  most 40% (above 40% is almost always a misread or a distressed situation).
- Each position is 5% of the book (cash + positions at cost), if cash allows.
- Cash deals: buy the target. Stock deals: also short the exchange ratio of
  acquirer shares (non-registered only; a TFSA can't short).
- Hold to the outcome: cash-out on closing; sell at the post-break price if the
  deal dies; mark open deals at the end.
- The book is held in USD. Idle cash earns IBKR's rate (benchmark minus 0.5%)
  on balances over USD 10k, using the 13-week T-bill as the benchmark.

Positions are carried at cost until they resolve, because daily prices for
acquired companies are no longer available. That hides interim swings, so this
book's volatility and drawdowns understate reality; the fund cross-check shows
what a marked-to-market arb portfolio looked like.

Tax (non-registered) is computed in CAD with Bank-of-Canada-style daily rates:
each deal's gain uses the exchange rate on its entry and exit dates, and gains
or losses on the USD cash pool itself are realized when USD is converted
(average-cost basis), as CRA requires for foreign currency.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from datetime import date, timedelta

from mergerarb.backtest.costs import (
    BORROW_FEE,
    CASH_FREE_TIER,
    CASH_SPREAD,
    Bracket,
    IbkrFixed,
    fx_cost,
)


class Series:
    """Step series: value on or before a date (forward-filled)."""

    def __init__(self, points: list[tuple[date, float]]):
        pts = sorted(points)
        self.days = [d for d, _ in pts]
        self.vals = [v for _, v in pts]

    def at(self, d: date) -> float:
        """Last value on or before ``d`` (first value if ``d`` is earlier)."""
        i = bisect.bisect_right(self.days, d) - 1
        return self.vals[max(i, 0)]


@dataclass(frozen=True)
class SimDeal:
    """A deal ready to simulate. Prices in USD per target share."""

    name: str
    entry: date
    exit: date
    outcome: str  # closed / broke / open
    t0: float
    cash: float
    ratio: float
    a0: float
    a1: float
    exit_price: float | None  # target price on a break, or the mark for open deals

    @property
    def value0(self) -> float:
        """Offer value per target share at entry."""
        return self.cash + self.ratio * self.a0

    @property
    def spread(self) -> float:
        """Gross spread at entry as a fraction of the price paid."""
        return self.value0 / self.t0 - 1


def to_sim_deals(rows: list[dict], end: date) -> tuple[list[SimDeal], dict[str, int]]:
    """Turn collected rows into SimDeals; returns the deals and counts of why rows were dropped."""
    out, dropped = [], {}

    def drop(reason: str) -> None:
        dropped[reason] = dropped.get(reason, 0) + 1

    for r in rows:
        if r.get("skip"):
            drop(r["skip"])
            continue
        entry = date.fromisoformat(r["filed"])
        if entry > end:
            drop("after end date")
            continue
        status = r["outcome"]
        ex = date.fromisoformat(r["outcome_date"]) if r.get("outcome_date") else end
        if status == "closed" and ex > end:
            status, ex = "closed", end  # pays out at the end of the window
        if status != "closed" and ex > end:
            status, ex = "open", end
        if ex <= entry:
            drop("outcome before entry")
            continue
        d = SimDeal(
            name=r["target"],
            entry=entry,
            exit=ex,
            outcome=status,
            t0=r["entry_price"],
            cash=r["cash"],
            ratio=r["ratio"],
            a0=r.get("acq_entry_price") or 0.0,
            a1=r.get("acq_exit_price") or 0.0,
            exit_price=r.get("exit_price_break"),
        )
        if d.t0 < 1.0:
            drop("price under $1")
            continue
        if not 0 < d.spread <= 0.40:
            drop("spread outside 0-40%")
            continue
        if d.outcome != "closed" and d.exit_price is None:
            drop("no exit price")
            continue
        out.append(d)
    return sorted(out, key=lambda d: d.entry), dropped


@dataclass
class Position:
    deal: SimDeal
    shares: int
    short: int
    cost_usd: float  # cash paid for the long leg incl. costs
    short_proceeds_usd: float  # net proceeds of the short sale (held as collateral)
    fx_entry: float


@dataclass
class Trade:
    """One completed deal in the simulation, for reporting."""

    name: str
    entry: date
    exit: date
    outcome: str
    stock_deal: bool
    usd_pnl: float
    usd_return: float
    cad_gain: float


@dataclass
class Config:
    """Simulation settings."""

    start: date
    end: date
    capital_cad: float = 100_000.0
    position_fraction: float = 0.05
    account: str = "tfsa"  # "tfsa" or "nonreg"
    regime: str = "capital"  # "capital" gains or "business" income (non-reg only)
    bracket: Bracket | None = None
    ibkr: IbkrFixed = field(default_factory=IbkrFixed)
    allow_stock_deals: bool | None = None  # default: only outside a TFSA


@dataclass
class Result:
    """Simulation output."""

    nav_cad: list[tuple[date, float]]
    final_cad: float
    trades: list[Trade]
    taxes_cad: float
    interest_cad: float
    fees_usd: float
    skipped_no_cash: int
    years: dict[int, dict] = field(default_factory=dict)
    avg_invested: float = 0.0  # time-average share of the book in open deals
    avg_positions: float = 0.0


def simulate(deals: list[SimDeal], fx: Series, tbill: Series, cfg: Config) -> Result:
    """Run the book day by day from ``cfg.start`` to ``cfg.end``."""
    ib = cfg.ibkr
    taxed = cfg.account == "nonreg"
    if taxed and cfg.bracket is None:
        raise ValueError("a non-registered account needs a tax bracket")
    stock_ok = cfg.allow_stock_deals if cfg.allow_stock_deals is not None else taxed
    universe = [d for d in deals if cfg.start <= d.entry <= cfg.end and (stock_ok or d.ratio == 0)]

    fx0 = fx.at(cfg.start)
    usd = cfg.capital_cad / fx0
    usd -= fx_cost(usd)
    acb = cfg.capital_cad / usd  # CAD per USD in the pool
    fees = fx_cost(cfg.capital_cad / fx0)
    open_pos: list[Position] = []
    trades: list[Trade] = []
    nav: list[tuple[date, float]] = []
    year = {"cg": 0.0, "fx": 0.0, "interest": 0.0}
    carry_loss = 0.0
    taxes = interest_total = 0.0
    skipped = 0
    years: dict[int, dict] = {}
    by_entry: dict[date, list[SimDeal]] = {}
    for d in universe:
        by_entry.setdefault(d.entry, []).append(d)

    def pool_in(amount_usd: float, rate: float) -> None:
        nonlocal usd, acb
        if amount_usd <= 0:
            usd += amount_usd
            return
        total = usd + amount_usd
        if total > 0 and usd > 0:
            acb = (usd * acb + amount_usd * rate) / total
        elif total > 0:
            acb = rate
        usd = total

    def pool_out(amount_usd: float, rate: float) -> None:
        """Spend USD from the pool; realize the FX gain on it (CRA treatment)."""
        nonlocal usd
        year["fx"] += amount_usd * (rate - acb)
        usd -= amount_usd

    def close(p: Position, day: date, mark: bool = False) -> None:
        nonlocal fees
        d = p.deal
        r = fx.at(day)
        if d.outcome == "closed" and not mark:
            got = d.cash * p.shares  # cash consideration; acquirer shares cover the short
            residual = d.ratio * p.shares - p.short  # rounding of the hedge, valued at exit
            cover = 0.0
            got += residual * d.a1
        else:
            px = d.exit_price if d.exit_price is not None else d.t0
            got = px * p.shares - ib.sell_cost(p.shares, px)
            cover = p.short * d.a1 + (ib.buy_cost(p.short, d.a1) if p.short else 0.0)
            fees += ib.sell_cost(p.shares, px) + (ib.buy_cost(p.short, d.a1) if p.short else 0.0)
        borrow = BORROW_FEE * p.short * d.a0 * (day - d.entry).days / 365
        fees += borrow
        net_short = p.short_proceeds_usd - cover - borrow
        long_gain_cad = got * r - p.cost_usd * p.fx_entry
        short_gain_cad = p.short_proceeds_usd * p.fx_entry - (cover + borrow) * r
        cad_gain = long_gain_cad + short_gain_cad
        year["cg"] += cad_gain
        pool_in(got + net_short, r)
        pnl = got + net_short - p.cost_usd
        trades.append(
            Trade(
                d.name,
                d.entry,
                day,
                "open" if mark else d.outcome,
                p.short > 0,
                pnl,
                pnl / p.cost_usd,
                cad_gain,
            )
        )

    def pay_tax(day: date, final: bool = False) -> None:
        nonlocal carry_loss, taxes
        b = cfg.bracket
        cg = year["cg"] + year["fx"]
        if cfg.regime == "business":
            tax = cg * b.ordinary
        else:
            if cg < 0:
                carry_loss += -cg
                cg = 0.0
            else:
                use = min(carry_loss, cg)
                carry_loss -= use
                cg -= use
            tax = cg * b.capital_gains
        tax += year["interest"] * b.ordinary
        years[day.year] = {
            "gains_cad": year["cg"],
            "fx_cad": year["fx"],
            "interest_cad": year["interest"],
            "tax_cad": tax,
        }
        year.update(cg=0.0, fx=0.0, interest=0.0)
        taxes += tax
        if final:
            return
        r = fx.at(day)
        if tax > 0:
            need = tax / r
            pool_out(need + fx_cost(need), r)
        elif tax < 0:
            pool_in(-tax / r - fx_cost(-tax / r), r)

    inv_sum = pos_sum = 0.0
    n_days = 0
    day = cfg.start
    while day <= cfg.end:
        r = fx.at(day)
        # 1) resolve deals
        for p in [p for p in open_pos if p.deal.exit <= day]:
            close(p, day)
            open_pos.remove(p)
        # 2) interest on idle cash
        rate = max(0.0, tbill.at(day) - CASH_SPREAD)
        accrued = max(0.0, usd - CASH_FREE_TIER) * rate / 365
        if accrued:
            pool_in(accrued, r)
            year["interest"] += accrued * r
            interest_total += accrued * r
        # 3) new deals
        for d in by_entry.get(day, []):
            book = usd + sum(p.cost_usd for p in open_pos)
            budget = min(cfg.position_fraction * book, usd)
            shares = int(budget // (d.t0 * (1 + ib.slippage) + 0.01))
            if shares * d.t0 < 1_000:
                skipped += 1
                continue
            cost = shares * d.t0 + ib.buy_cost(shares, d.t0)
            short = round(d.ratio * shares)
            proceeds = 0.0
            if short:
                proceeds = short * d.a0 - ib.sell_cost(short, d.a0)
                fees += ib.sell_cost(short, d.a0)
            fees += ib.buy_cost(shares, d.t0)
            pool_out(cost, r)
            open_pos.append(Position(d, shares, short, cost, proceeds, r))
        # 4) year-end tax
        if taxed and day.month == 12 and day.day == 31:
            pay_tax(day)
        invested = sum(p.cost_usd for p in open_pos)
        inv_sum += invested / max(usd + invested, 1e-9)
        pos_sum += len(open_pos)
        n_days += 1
        nav.append((day, (usd + invested) * r))
        day += timedelta(days=1)

    # Liquidate at the end: mark open deals, convert everything to CAD.
    end = cfg.end
    for p in open_pos:
        close(p, end, mark=True)
    r = fx.at(end)
    cad = usd * r - fx_cost(usd) * r
    fees += fx_cost(usd)
    year["fx"] += usd * (r - acb)
    final_tax = 0.0
    if taxed:
        before = taxes
        pay_tax(end, final=True)
        final_tax = taxes - before
    final = cad - final_tax
    nav.append((end, final))
    return Result(
        nav,
        final,
        trades,
        taxes,
        interest_total,
        fees,
        skipped,
        years,
        inv_sum / max(n_days, 1),
        pos_sum / max(n_days, 1),
    )
