"""Merger-arbitrage spread calculator."""

from mergerarb.core import (
    Analysis,
    Deal,
    analyze,
    annualize,
    delay_table,
    expected_return,
    implied_probability,
    position_size,
)

__all__ = [
    "Analysis",
    "Deal",
    "analyze",
    "annualize",
    "delay_table",
    "expected_return",
    "implied_probability",
    "position_size",
]
