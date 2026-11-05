"""Merger-arbitrage spread math.

Pure functions, no I/O. All prices are per target share unless noted.

Conventions
-----------
- Deal value  V = cash + ratio * acquirer_price
- Gross spread S = V - target_price
- Carry over the holding period (per target share):
    + target dividends received
    - ratio * acquirer dividends owed on the short leg
    - borrow fee on the short leg: fee_rate * ratio * acquirer_price * days / 365
    - round-trip trading costs
- Net spread Sn = S + carry
- Capital at risk is the long target position (target_price per share). Margin
  financing and the use of short-sale proceeds are ignored.
- If the deal breaks, the target is assumed to fall to ``fallback_price``.
  For stock deals the short acquirer leg's P&L on a break is unknown (acquirers
  often rise when a deal dies), so it is ignored here; this understates or
  overstates the break loss depending on how the acquirer reacts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

DAYS_PER_YEAR = 365.0


@dataclass(frozen=True)
class Deal:
    """Inputs describing one pending acquisition.

    Attributes:
        target_price: Current market price of the target.
        fallback_price: Where you expect the target to trade if the deal breaks.
        days_to_close: Expected calendar days until the deal closes.
        cash: Cash paid per target share.
        ratio: Acquirer shares paid per target share (0 for all-cash deals).
        acquirer_price: Current acquirer price (needed when ratio > 0).
        target_dividends: Target dividends you expect to receive before close.
        acquirer_dividends: Acquirer dividends per acquirer share you would owe
            on the short leg before close.
        borrow_fee_rate: Annual borrow fee on the short leg, as a fraction.
        trading_costs: Round-trip commissions/fees per target share.
    """

    target_price: float
    fallback_price: float
    days_to_close: float
    cash: float = 0.0
    ratio: float = 0.0
    acquirer_price: float = 0.0
    target_dividends: float = 0.0
    acquirer_dividends: float = 0.0
    borrow_fee_rate: float = 0.0
    trading_costs: float = 0.0

    def __post_init__(self) -> None:
        if self.target_price <= 0:
            raise ValueError("target_price must be positive")
        if self.days_to_close <= 0:
            raise ValueError("days_to_close must be positive")
        if self.ratio < 0 or self.cash < 0:
            raise ValueError("cash and ratio must be non-negative")
        if self.ratio > 0 and self.acquirer_price <= 0:
            raise ValueError("acquirer_price must be positive for stock deals")
        if self.cash == 0 and self.ratio == 0:
            raise ValueError("deal must pay cash, stock, or both")


@dataclass(frozen=True)
class Analysis:
    """Results for one deal. Money amounts are per target share."""

    deal_value: float
    gross_spread: float
    carry: float
    borrow_cost: float
    net_spread: float
    gross_return: float
    net_return: float
    annualized_net_return: float
    loss_if_break: float
    implied_probability: float
    breakeven_probability: float
    hedge_shares_per_target: float
    notes: list[str] = field(default_factory=list)


def deal_value(deal: Deal) -> float:
    """Value of the consideration per target share at current acquirer price."""
    return deal.cash + deal.ratio * deal.acquirer_price


def borrow_cost(deal: Deal, days: float | None = None) -> float:
    """Borrow fee on the short acquirer leg per target share over ``days``."""
    d = deal.days_to_close if days is None else days
    return deal.borrow_fee_rate * deal.ratio * deal.acquirer_price * d / DAYS_PER_YEAR


def carry(deal: Deal, days: float | None = None) -> float:
    """Dividends received minus dividends owed, borrow and trading costs."""
    return (
        deal.target_dividends
        - deal.ratio * deal.acquirer_dividends
        - borrow_cost(deal, days)
        - deal.trading_costs
    )


def annualize(period_return: float, days: float) -> float:
    """Compound a holding-period return to an annual rate.

    Returns -1.0 for a total loss and raises for impossible returns below -100%.
    """
    if days <= 0:
        raise ValueError("days must be positive")
    if period_return < -1:
        raise ValueError("period_return below -100% is not possible")
    if period_return == -1:
        return -1.0
    return (1.0 + period_return) ** (DAYS_PER_YEAR / days) - 1.0


def implied_probability(price: float, payoff_if_close: float, fallback: float) -> float:
    """Probability p solving p*payoff_if_close + (1-p)*fallback = price.

    This is the risk-neutral reading of the spread with zero discounting, the
    standard back-of-envelope used by arb desks. The result is not clipped,
    so values outside [0, 1] signal inconsistent inputs (e.g. fallback above
    the current price, or a target trading above the offer).
    """
    if payoff_if_close == fallback:
        raise ValueError("payoff_if_close must differ from fallback")
    return (price - fallback) / (payoff_if_close - fallback)


def analyze(deal: Deal) -> Analysis:
    """Compute spread, returns, implied odds and break-even odds for a deal."""
    v = deal_value(deal)
    s = v - deal.target_price
    c = carry(deal)
    sn = s + c
    t = deal.target_price
    loss = deal.fallback_price - t  # negative number when the target would fall

    notes: list[str] = []
    if s < 0:
        notes.append(
            "Negative spread: target trades above the offer. The market may be "
            "expecting a higher bid, or the inputs are stale."
        )
    if deal.fallback_price >= t:
        notes.append(
            "Fallback price is at or above the current price, so a break would "
            "not lose money and the implied probability is not meaningful."
        )
    if deal.ratio > 0:
        notes.append(
            "Stock deal: the offer value moves with the acquirer. Short "
            f"{deal.ratio:g} acquirer shares per target share to lock the spread."
        )

    ip = implied_probability(t, v, deal.fallback_price) if v != deal.fallback_price else math.nan
    be = (
        implied_probability(t, t + sn, deal.fallback_price)
        if t + sn != deal.fallback_price
        else math.nan
    )

    return Analysis(
        deal_value=v,
        gross_spread=s,
        carry=c,
        borrow_cost=borrow_cost(deal),
        net_spread=sn,
        gross_return=s / t,
        net_return=sn / t,
        annualized_net_return=annualize(sn / t, deal.days_to_close) if sn / t >= -1 else -1.0,
        loss_if_break=loss,
        implied_probability=ip,
        breakeven_probability=be,
        hedge_shares_per_target=deal.ratio,
        notes=notes,
    )


def expected_return(deal: Deal, probability_close: float) -> float:
    """Expected holding-period return given your own probability the deal closes.

    Assumes the break, if any, happens at the expected close date and that
    carry is earned/paid only when the deal closes (a simplification).
    """
    if not 0.0 <= probability_close <= 1.0:
        raise ValueError("probability_close must be in [0, 1]")
    a = analyze(deal)
    ev = probability_close * a.net_spread + (1.0 - probability_close) * a.loss_if_break
    return ev / deal.target_price


def delay_table(deal: Deal, extra_days: tuple[float, ...] = (0, 90, 180, 365)) -> list[dict]:
    """Annualized net return if the close slips by each number of extra days.

    Borrow cost scales with time; dividends and trading costs are held fixed
    (in reality a long delay usually adds dividends on both legs).
    """
    rows = []
    for extra in extra_days:
        d = deal.days_to_close + extra
        sn = deal_value(deal) - deal.target_price + carry(deal, d)
        r = sn / deal.target_price
        rows.append(
            {
                "days": d,
                "net_return": r,
                "annualized": annualize(r, d) if r >= -1 else -1.0,
            }
        )
    return rows


def position_size(deal: Deal, account_size: float, max_loss_fraction: float) -> dict:
    """Shares to buy so a deal break loses at most ``max_loss_fraction`` of the account.

    This is a risk-budget calculation, not a recommendation. It ignores the
    short leg's P&L on a break and any gap below the fallback price.
    """
    if account_size <= 0 or not 0 < max_loss_fraction <= 1:
        raise ValueError("account_size > 0 and 0 < max_loss_fraction <= 1 required")
    per_share_loss = deal.target_price - deal.fallback_price
    if per_share_loss <= 0:
        raise ValueError("fallback must be below target price to size by break loss")
    shares = math.floor(account_size * max_loss_fraction / per_share_loss)
    return {
        "target_shares": shares,
        "acquirer_shares_short": round(shares * deal.ratio),
        "capital": shares * deal.target_price,
        "loss_if_break": shares * per_share_loss,
    }
