"""FIFO matching of trades into round trips (open → close) per instrument.

A round trip is a quantity opened by one trade and closed by a later one. Trades
are matched first-in, first-out within each instrument (:attr:`Trade.contract_key`).
A closing trade larger than the open position closes it and opens the remainder in
the other direction (a position flip).

Commissions are allocated per unit: an opening trade's commission is spread over
its quantity, and each round trip carries its share of both the opening and the
closing commission.

Expiries, assignments and exercises close the option at the price the broker
reports (usually 0). An assignment's resulting stock position is a separate
round trip opened at the strike, as brokers record it ("broker" view).

:func:`wheel_view` re-expresses assigned short options the way wheel traders track
them: a put's premium lowers the cost basis of the shares it puts you into, and a
covered call's premium raises the sale price of the shares called away. Total P&L is
unchanged; only how it is split between round trips changes.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from typing import Literal

from occheck.trades import Trade

CloseReason = Literal["closed", "expired", "assigned", "exercised"]


@dataclass(frozen=True)
class RoundTrip:
    """A matched open/close of ``quantity`` units of one instrument."""

    symbol: str
    underlying: str
    asset_class: str
    direction: Literal["long", "short"]
    quantity: float
    multiplier: float
    open_time: datetime
    close_time: datetime
    open_price: float
    close_price: float
    commission: float
    close_reason: CloseReason
    right: str | None = None
    strike: float | None = None
    expiry: date | None = None
    open_trade_id: str = ""
    close_trade_id: str = ""
    wheel_premium: float = 0.0  # option P&L folded into this stock round trip (wheel view)

    @property
    def gross_pnl(self) -> float:
        """P&L before commissions."""
        sign = 1.0 if self.direction == "long" else -1.0
        return sign * (self.close_price - self.open_price) * self.quantity * self.multiplier

    @property
    def net_pnl(self) -> float:
        """P&L after this round trip's share of commissions."""
        return self.gross_pnl - self.commission

    @property
    def holding_days(self) -> float:
        """Calendar days between open and close (fractional)."""
        return (self.close_time - self.open_time).total_seconds() / 86400.0

    @property
    def open_premium(self) -> float:
        """Absolute value paid or received at the open (options: premium)."""
        return self.open_price * self.quantity * self.multiplier

    @property
    def dte_at_open(self) -> int | None:
        """Calendar days to expiry when the position was opened (options only)."""
        if self.expiry is None:
            return None
        return (self.expiry - self.open_time.date()).days


@dataclass
class _Lot:
    trade: Trade
    remaining: float  # signed
    commission_per_unit: float


@dataclass
class MatchResult:
    """Round trips plus positions still open at the end of the file."""

    round_trips: list[RoundTrip]
    open_lots: list[tuple[Trade, float]] = field(default_factory=list)


def _reason(trade: Trade) -> CloseReason:
    for code, reason in (
        ("EXPIRED", "expired"),
        ("ASSIGNED", "assigned"),
        ("EXERCISED", "exercised"),
    ):
        if code in trade.codes:
            return reason  # type: ignore[return-value]
    return "closed"


def match_round_trips(trades: list[Trade]) -> MatchResult:
    """Match trades FIFO into round trips. ``trades`` need not be sorted."""
    books: dict[tuple, deque[_Lot]] = {}
    out: list[RoundTrip] = []
    eps = 1e-9
    for t in sorted(trades, key=lambda x: (x.when, x.trade_id)):
        if abs(t.quantity) < eps:
            continue
        book = books.setdefault(t.contract_key, deque())
        close_comm_per_unit = t.commission / abs(t.quantity)
        left = t.quantity
        while book and abs(left) > eps and (book[0].remaining > 0) != (left > 0):
            lot = book[0]
            qty = min(abs(left), abs(lot.remaining))
            o = lot.trade
            out.append(
                RoundTrip(
                    symbol=o.symbol,
                    underlying=o.underlying,
                    asset_class=o.asset_class,
                    direction="long" if lot.remaining > 0 else "short",
                    quantity=qty,
                    multiplier=o.multiplier,
                    open_time=o.when,
                    close_time=t.when,
                    open_price=o.price,
                    close_price=t.price,
                    commission=qty * (lot.commission_per_unit + close_comm_per_unit),
                    close_reason=_reason(t),
                    right=o.right,
                    strike=o.strike,
                    expiry=o.expiry,
                    open_trade_id=o.trade_id,
                    close_trade_id=t.trade_id,
                )
            )
            step = qty if lot.remaining > 0 else -qty
            lot.remaining -= step
            left += step
            if abs(lot.remaining) < eps:
                book.popleft()
        if abs(left) > eps:
            book.append(_Lot(t, left, t.commission / abs(t.quantity)))
    open_lots = [(lot.trade, lot.remaining) for book in books.values() for lot in book]
    return MatchResult(round_trips=out, open_lots=open_lots)


def wheel_view(round_trips: list[RoundTrip], trades: list[Trade]) -> list[RoundTrip]:
    """Fold assigned short options into the stock round trips they created or closed.

    * Short put assigned: its gross P&L is spread over the shares bought on assignment
      (lowering their open price) and the round trip starts when the put was sold.
    * Short call assigned: its gross P&L is spread over the shares called away
      (raising their close price).

    Each option's commission moves with it. Assigned options whose shares are still
    open at the end of the file stay as separate round trips.
    """
    assigned_stock = {
        t.trade_id: t for t in trades if t.asset_class == "STK" and "ASSIGNED" in t.codes
    }
    out = list(round_trips)
    for rt in round_trips:
        if not (
            rt.asset_class == "OPT" and rt.direction == "short" and rt.close_reason == "assigned"
        ):
            continue
        if rt.right == "P":
            linked = [
                (i, s)
                for i, s in enumerate(out)
                if s.open_trade_id in assigned_stock
                and s.underlying == rt.underlying
                and s.open_time == rt.close_time
                and s.direction == "long"
            ]
        else:
            linked = [
                (i, s)
                for i, s in enumerate(out)
                if s.close_trade_id in assigned_stock
                and s.underlying == rt.underlying
                and s.close_time == rt.close_time
                and s.direction == "long"
            ]
        shares = sum(s.quantity * s.multiplier for _, s in linked)
        if not linked or shares <= 0:
            continue
        per_share = rt.gross_pnl / shares
        for i, s in linked:
            weight = s.quantity * s.multiplier / shares
            if rt.right == "P":
                out[i] = replace(
                    s,
                    open_price=s.open_price - per_share,
                    open_time=min(s.open_time, rt.open_time),
                    commission=s.commission + rt.commission * weight,
                    wheel_premium=s.wheel_premium + rt.gross_pnl * weight,
                )
            else:
                out[i] = replace(
                    s,
                    close_price=s.close_price + per_share,
                    commission=s.commission + rt.commission * weight,
                    wheel_premium=s.wheel_premium + rt.gross_pnl * weight,
                )
        out = [x for x in out if x is not rt]
    return out
