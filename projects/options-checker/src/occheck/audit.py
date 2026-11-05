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
    """Traded notional per year, and annual turnover when account value is known.

    ``annual_turnover`` follows Barber & Odean (2000): the average of buy and sell
    turnover, i.e. half of all traded notional, divided by account value. Their average
    household turned over 0.8x a year; the most active fifth, 1.15x or more.

    Flex Trades exports don't include account equity, so ``account_value`` comes from
    the user. Annualized over the span between the first and last trade (minimum 30
    days, so a short file isn't extrapolated wildly).
    """
    if not trades:
        return {"notional_per_year": 0.0, "annual_turnover": None, "span_days": 0.0}
    times = [t.when for t in trades]
    span = max((max(times) - min(times)).total_seconds() / 86400.0, 30.0)
    per_year = sum(t.notional for t in trades) * 365.0 / span
    annual = per_year / 2.0 / account_value if account_value else None
    return {"notional_per_year": per_year, "annual_turnover": annual, "span_days": span}


@dataclass(frozen=True)
class Thresholds:
    """Cut-offs for the bias metrics. Defaults are documented in docs/decisions.md."""

    lottery_max_premium: float = 0.50  # per-share option price
    lottery_max_dte: int = 7
    lottery_watch: float = 0.05  # share of long-option premium spent on lottery-type options
    lottery_flag: float = 0.25
    zero_dte_flag: float = 0.25  # share of option trades opened on expiry day (any = watch)
    disposition_ratio_flag: float = 1.2  # losers held this many times longer than winners
    high_win_rate: float = 0.6
    concentration_flag: float = 0.05  # single loss as a share of account value
    turnover_watch: float = 0.8  # annual turnover, Barber & Odean definition
    turnover_flag: float = 1.15
    commission_watch: float = 0.10  # commissions as a share of gross profits
    commission_flag: float = 0.25
    min_samples: int = 5


def _median(xs: list[float]) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    mid = len(s) // 2
    return s[mid] if len(s) % 2 else 0.5 * (s[mid - 1] + s[mid])


def expectancy(round_trips: list[RoundTrip]) -> dict[str, float | int | None]:
    """Win rate next to what an average trade actually earns (after commissions)."""
    nets = [rt.net_pnl for rt in round_trips]
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x <= 0]
    n = len(nets)
    avg_win = sum(wins) / len(wins) if wins else None
    avg_loss = sum(losses) / len(losses) if losses else None
    return {
        "n": n,
        "win_rate": len(wins) / n if n else None,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "expectancy": sum(nets) / n if n else None,
        "largest_loss": min(nets) if nets else None,
        "wins_to_cover_largest_loss": (
            -min(nets) / avg_win if nets and avg_win and min(nets) < 0 else None
        ),
    }


def disposition(round_trips: list[RoundTrip]) -> dict[str, float | int | None]:
    """Median holding time of winners vs losers (Odean's disposition effect, holding-time form).

    A ratio above 1 means losing positions were held longer than winning ones.
    """
    win_days = [rt.holding_days for rt in round_trips if rt.net_pnl > 0]
    loss_days = [rt.holding_days for rt in round_trips if rt.net_pnl <= 0]
    mw, ml = _median(win_days), _median(loss_days)
    return {
        "n_winners": len(win_days),
        "n_losers": len(loss_days),
        "median_days_winners": mw,
        "median_days_losers": ml,
        "ratio": ml / mw if mw and ml is not None and mw > 0 else None,
    }


def lottery(round_trips: list[RoundTrip], th: Thresholds) -> dict[str, float | int | None]:
    """Spending on cheap, short-dated long options, and same-day (0DTE) trading."""
    longs = [rt for rt in round_trips if rt.asset_class == "OPT" and rt.direction == "long"]
    opts = [rt for rt in round_trips if rt.asset_class == "OPT"]
    lotto = [
        rt
        for rt in longs
        if rt.open_price < th.lottery_max_premium
        and rt.dte_at_open is not None
        and rt.dte_at_open <= th.lottery_max_dte
    ]
    paid = sum(rt.open_premium for rt in longs)
    lotto_paid = sum(rt.open_premium for rt in lotto)
    zero = [rt for rt in opts if rt.dte_at_open == 0]
    return {
        "long_premium_paid": paid,
        "lottery_premium_paid": lotto_paid,
        "lottery_share": lotto_paid / paid if paid else None,
        "lottery_n": len(lotto),
        "lottery_net_pnl": sum(rt.net_pnl for rt in lotto),
        "zero_dte_share": len(zero) / len(opts) if opts else None,
        "zero_dte_net_pnl": sum(rt.net_pnl for rt in zero),
    }


def buyer_seller(round_trips: list[RoundTrip]) -> dict[str, dict[str, float | int]]:
    """Option results split by long (buyer) vs short (seller) positions."""
    out: dict[str, dict[str, float | int]] = {}
    for side in ("long", "short"):
        rts = [rt for rt in round_trips if rt.asset_class == "OPT" and rt.direction == side]
        out["buyer" if side == "long" else "seller"] = {
            "n": len(rts),
            "premium": sum(rt.open_premium for rt in rts),
            "net_pnl": sum(rt.net_pnl for rt in rts),
        }
    return out


def concentration(
    round_trips: list[RoundTrip], account_value: float | None
) -> dict[str, float | str | None]:
    """Largest single loss, as a share of account value (if known) and of all losses."""
    losers = [rt for rt in round_trips if rt.net_pnl < 0]
    if not losers:
        return {
            "largest_loss": None,
            "symbol": None,
            "share_of_account": None,
            "share_of_losses": None,
        }
    worst = min(losers, key=lambda rt: rt.net_pnl)
    total_losses = sum(rt.net_pnl for rt in losers)
    return {
        "largest_loss": worst.net_pnl,
        "symbol": worst.symbol,
        "share_of_account": -worst.net_pnl / account_value if account_value else None,
        "share_of_losses": worst.net_pnl / total_losses,
    }
