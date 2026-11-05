"""Trade-log audit metrics: what trading cost, and how much was traded.

Every metric is computed from the user's own trades. Nothing here needs market data.
"""

from __future__ import annotations

from dataclasses import dataclass

from occheck.roundtrips import RoundTrip
from occheck.trades import Trade


@dataclass(frozen=True)
class CostSummary:
    """Realized P&L and what commissions took out of it."""

    round_trips: int
    gross_pnl: float
    commission: float
    net_pnl: float
    traded_notional: float
    commission_bps_of_notional: float
    commission_share_of_gross: float | None
    commission_share_of_gross_profit: float | None


def cost_summary(trades: list[Trade], round_trips: list[RoundTrip]) -> CostSummary:
    """Summarize realized P&L and commission drag.

    ``commission_share_of_gross`` is commissions / gross P&L and is ``None`` when
    gross P&L is not positive (a share of a loss is not meaningful).
    ``commission_share_of_gross_profit`` divides by the sum of winning trades' gross
    P&L, which stays meaningful for losing accounts. All commissions in the file
    count, including those on positions still open.
    """
    gross = sum(rt.gross_pnl for rt in round_trips)
    commission = sum(t.commission for t in trades)
    notional = sum(t.notional for t in trades)
    profits = sum(rt.gross_pnl for rt in round_trips if rt.gross_pnl > 0)
    return CostSummary(
        round_trips=len(round_trips),
        gross_pnl=gross,
        commission=commission,
        net_pnl=gross - sum(rt.commission for rt in round_trips),
        traded_notional=notional,
        commission_bps_of_notional=commission / notional * 1e4 if notional else 0.0,
        commission_share_of_gross=commission / gross if gross > 0 else None,
        commission_share_of_gross_profit=commission / profits if profits > 0 else None,
    )


def turnover(trades: list[Trade], account_value: float | None) -> dict[str, float | None]:
    """Traded notional per year, and as a multiple of account value when it is known.

    Flex Trades exports don't include account equity, so ``account_value`` comes from
    the user. Annualized over the span between the first and last trade (minimum 30
    days, so a short file isn't extrapolated wildly).
    """
    if not trades:
        return {"notional_per_year": 0.0, "annual_turnover": None, "span_days": 0.0}
    times = [t.when for t in trades]
    span = max((max(times) - min(times)).total_seconds() / 86400.0, 30.0)
    per_year = sum(t.notional for t in trades) * 365.0 / span
    annual = per_year / account_value if account_value else None
    return {"notional_per_year": per_year, "annual_turnover": annual, "span_days": span}
