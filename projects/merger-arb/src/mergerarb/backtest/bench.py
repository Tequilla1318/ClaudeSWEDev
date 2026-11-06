"""Buy-and-hold index benchmarks for a Canadian investor, with dividends and tax.

- S&P 500 via SPY (USD). US dividends have 15% withheld. In a TFSA that 15% is
  lost; in a non-registered account the dividend is taxed at the ordinary rate
  and the 15% is credited against it (foreign tax credit), so the total tax is
  the ordinary rate.
- TSX via XIC.TO (CAD). Distributions are treated as eligible Canadian
  dividends (taxed at the eligible-dividend rate outside a TFSA). In reality a
  slice is foreign income or return of capital; this is a simplification.
- Dividends are reinvested on the pay date after tax; nothing is sold until the
  end, when the whole position is sold and the capital gain (in CAD, using
  exchange rates on each purchase and on the sale) is taxed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from mergerarb.backtest.costs import US_WITHHOLDING, Bracket, IbkrFixed, fx_cost
from mergerarb.backtest.sim import Series


@dataclass
class BenchResult:
    """Output of a buy-and-hold run."""

    nav_cad: list[tuple[date, float]]  # value before the final sale's tax
    final_pre_sale_cad: float
    final_cad: float  # after selling everything and paying capital-gains tax
    dividend_tax_cad: float
    sale_tax_cad: float


def buy_and_hold(
    prices: Series,
    dividends: list[tuple[date, float]],
    fx: Series | None,
    start: date,
    end: date,
    capital_cad: float = 100_000.0,
    account: str = "tfsa",
    bracket: Bracket | None = None,
    us_listed: bool = True,
    ibkr: IbkrFixed | None = None,
) -> BenchResult:
    """Simulate buying ``capital_cad`` of one fund and holding it.

    ``prices`` are closes in the fund's own currency (not dividend-adjusted);
    ``fx`` is USD->CAD for US-listed funds and None for CAD funds.
    """
    ib = ibkr or IbkrFixed(slippage=0.0001)
    rate = (lambda d: fx.at(d)) if (us_listed and fx) else (lambda d: 1.0)
    taxed = account == "nonreg"
    r0 = rate(start)
    cash = capital_cad / r0 - (fx_cost(capital_cad / r0) if us_listed else 0.0)
    p0 = prices.at(start)
    shares = int(cash // (p0 * (1 + ib.slippage)))
    cost = shares * p0 + ib.buy_cost(shares, p0)
    cash -= cost
    acb_cad = cost * r0
    div_tax = 0.0
    divs = {d: amt for d, amt in dividends if start < d <= end}
    nav = []
    day = start
    while day <= end:
        if day in divs:
            gross = divs[day] * shares
            withheld = US_WITHHOLDING * gross if us_listed else 0.0
            net = gross - withheld
            if taxed:
                cad = gross * rate(day)
                if us_listed:
                    extra = max(0.0, bracket.ordinary * cad - withheld * rate(day))
                else:
                    extra = bracket.eligible_dividends * cad
                div_tax += extra + (withheld * rate(day) if us_listed else 0.0)
                net -= extra / rate(day)
            cash += net
            px = prices.at(day)
            n = int(cash // (px * (1 + ib.slippage)))
            if n > 0 and n * px > 200:
                c = n * px + ib.buy_cost(n, px)
                cash -= c
                shares += n
                acb_cad += c * rate(day)
        if day.weekday() < 5 or day == end:
            nav.append((day, (shares * prices.at(day) + cash) * rate(day)))
        day += timedelta(days=1)
    px = prices.at(end)
    proceeds = shares * px - ib.sell_cost(shares, px)
    pre = (shares * px + cash) * rate(end)
    gain = proceeds * rate(end) - acb_cad
    sale_tax = max(0.0, gain) * bracket.capital_gains if taxed else 0.0
    total_cash = proceeds + cash
    final = (
        total_cash * rate(end) - (fx_cost(total_cash) * rate(end) if us_listed else 0.0) - sale_tax
    )
    nav.append((end, final))  # last point: after selling and paying tax, as for the arb book
    return BenchResult(nav, pre, final, div_tax, sale_tax)


def total_return_series(
    adjclose: Series, fx: Series | None, start: date, end: date, capital_cad: float = 100_000.0
) -> list[tuple[date, float]]:
    """Value of ``capital_cad`` in a fund using its dividend-adjusted closes (pre-tax)."""
    rate = (lambda d: fx.at(d)) if fx else (lambda d: 1.0)
    units = capital_cad / rate(start) / adjclose.at(start)
    out = []
    day = start
    while day <= end:
        if day.weekday() < 5:
            out.append((day, units * adjclose.at(day) * rate(day)))
        day += timedelta(days=1)
    return out
