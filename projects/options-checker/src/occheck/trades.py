"""Broker-neutral trade model shared by parsers and the auditor."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

AssetClass = Literal["STK", "OPT"]
OpenClose = Literal["O", "C"]


@dataclass(frozen=True)
class Trade:
    """One execution (or book entry such as an expiry or assignment).

    ``quantity`` is signed: positive buys, negative sells, in shares or contracts.
    ``commission`` is a cost and always ``>= 0`` (fees included).
    ``codes`` holds broker event codes normalized to: ``"EXPIRED"``,
    ``"ASSIGNED"``, ``"EXERCISED"``.
    """

    trade_id: str
    when: datetime
    symbol: str
    underlying: str
    asset_class: AssetClass
    quantity: float
    price: float
    multiplier: float
    commission: float
    currency: str = "USD"
    right: Literal["C", "P"] | None = None
    strike: float | None = None
    expiry: date | None = None
    open_close: OpenClose | None = None
    codes: frozenset[str] = field(default_factory=frozenset)

    @property
    def is_option(self) -> bool:
        """True for option trades."""
        return self.asset_class == "OPT"

    @property
    def contract_key(self) -> tuple:
        """Identity of the instrument, used to match opens with closes."""
        if self.is_option:
            return ("OPT", self.underlying, self.right, self.strike, self.expiry, self.multiplier)
        return ("STK", self.symbol)

    @property
    def notional(self) -> float:
        """Absolute traded value: |quantity| x price x multiplier."""
        return abs(self.quantity) * self.price * self.multiplier

    @property
    def cash_flow(self) -> float:
        """Cash in (+) or out (-) from the trade itself, before commission."""
        return -self.quantity * self.price * self.multiplier

    @property
    def dte(self) -> int | None:
        """Calendar days from trade date to expiry, for options."""
        if self.expiry is None:
            return None
        return (self.expiry - self.when.date()).days
