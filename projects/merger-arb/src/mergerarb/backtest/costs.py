"""IBKR trading costs and Ontario tax rates used by the backtest.

Sources (checked 2026-11-05):
- IBKR Fixed pricing, US stocks: USD 0.005/share, min USD 1.00, max 1% of trade
  value; SEC fee USD 0.0000206 x sale value; FINRA TAF on shares sold (USD 0.000166
  per share normally; a fee holiday applies Oct-Dec 2026, ignored here).
  https://www.interactivebrokers.ca/en/index.php?f=49637
- IBKR FX conversion: 0.20 bp of value, min USD 2.00.
  https://www.interactivebrokers.ca/en/trading/us-stock-trading-costs-for-canadian-resi.php
- IBKR interest on USD cash: benchmark minus 0.5% on balances over USD 10,000.
  https://www.interactivebrokers.ca/en/general/about/mediaRelations/3-23-23.php
- 2026 Ontario combined marginal rates (Richter):
  https://www.richter.ca/2026-ontario-income-tax-tables/
- Capital-gains inclusion stays at 50% (the 2/3 increase was cancelled in 2025).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IbkrFixed:
    """IBKR Pro Fixed pricing for US stocks, in USD."""

    per_share: float = 0.005
    minimum: float = 1.00
    max_fraction: float = 0.01
    sec_fee_rate: float = 0.0000206  # on sale value
    finra_taf_per_share: float = 0.000166  # on shares sold
    finra_taf_max: float = 8.30
    slippage: float = 0.0005  # half-spread paid on each trade, as a fraction of value

    def commission(self, shares: float, price: float) -> float:
        """Commission for one order."""
        value = shares * price
        return max(self.minimum, min(self.per_share * shares, self.max_fraction * value))

    def buy_cost(self, shares: float, price: float) -> float:
        """Total cost beyond ``shares * price`` for a purchase (or a buy-to-cover)."""
        return self.commission(shares, price) + self.slippage * shares * price

    def sell_cost(self, shares: float, price: float) -> float:
        """Total cost deducted from proceeds of a sale (or a short sale)."""
        return (
            self.commission(shares, price)
            + self.sec_fee_rate * shares * price
            + min(self.finra_taf_max, self.finra_taf_per_share * shares)
            + self.slippage * shares * price
        )


def fx_cost(usd_value: float) -> float:
    """IBKR currency-conversion commission in USD."""
    return max(2.0, 0.00002 * abs(usd_value))


@dataclass(frozen=True)
class Bracket:
    """2026 Ontario combined marginal rates for one income level."""

    name: str
    ordinary: float
    capital_gains: float
    eligible_dividends: float


BRACKETS = {
    "60k": Bracket("About $60k income", 0.2965, 0.1483, 0.0639),
    "100k": Bracket("About $100k income", 0.3148, 0.1574, 0.0892),
    "250k": Bracket("$250k+ (top bracket)", 0.5353, 0.2676, 0.3934),
}

US_WITHHOLDING = 0.15  # treaty rate on US dividends paid to Canadian residents
BORROW_FEE = 0.005  # annual fee to borrow easy-to-borrow acquirer shares
CASH_SPREAD = 0.005  # IBKR pays benchmark minus this on USD cash
CASH_FREE_TIER = 10_000.0  # first USD 10k earns nothing
