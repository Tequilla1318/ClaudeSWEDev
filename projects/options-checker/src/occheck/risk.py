"""Position sizing and risk of ruin, by Monte Carlo with closed-form checks.

Model: a sequence of independent trades. Each trade wins with probability ``p`` and
then gains ``payoff`` times the amount risked, or loses the amount risked.

* ``mode="fraction"``: risk a fixed fraction ``f`` of *current* equity per trade
  (equity can shrink toward zero but never reaches it).
* ``mode="fixed"``: risk a fixed dollar amount, ``f`` x starting equity, per trade
  (a random walk that can hit zero: classic gambler's ruin).

Equity is in units of starting equity (1.0 = where you started).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray


def kelly_fraction(p: float, payoff: float) -> float:
    """Kelly-optimal fraction to risk per trade: p - (1 - p) / payoff (can be negative)."""
    return p - (1.0 - p) / payoff


def edge_per_trade(p: float, payoff: float) -> float:
    """Expected profit per trade, in units of the amount risked."""
    return p * payoff - (1.0 - p)


def gamblers_ruin_probability(p: float, start_units: int, target_units: int) -> float:
    """Probability of hitting 0 before ``target_units`` in a ±1-unit random walk.

    Closed form (e.g. Feller, *An Introduction to Probability Theory*, Vol. 1, XIV.2).
    """
    q = 1.0 - p
    if abs(p - q) < 1e-12:
        return 1.0 - start_units / target_units
    r = q / p
    return (r**start_units - r**target_units) / (1.0 - r**target_units)


@dataclass(frozen=True)
class RiskResult:
    """Summary of simulated equity paths."""

    paths: int
    trades: int
    kelly: float
    edge: float
    prob_drawdown: float  # P(max drawdown from peak >= drawdown_level at any point)
    prob_ruin: float  # P(equity <= ruin_level at any point)
    prob_target: float  # P(equity reached stop_at before ruin), 0 if no target
    final_percentiles: dict[int, float]
    band: dict[int, list[float]]  # percentile -> equity at each trade index in band_x
    band_x: list[int]


def simulate(
    p: float,
    payoff: float,
    f: float,
    trades: int = 200,
    paths: int = 10_000,
    mode: Literal["fraction", "fixed"] = "fraction",
    drawdown_level: float = 0.5,
    ruin_level: float = 0.0,
    stop_at: float | None = None,
    seed: int | None = 0,
    record_band: bool = True,
) -> RiskResult:
    """Simulate equity paths and summarize drawdown and ruin risk.

    ``ruin_level`` is in units of starting equity (0.0 = account wiped out; for
    ``mode="fraction"`` use e.g. 0.2, since equity never reaches exactly zero).
    ``stop_at`` (optional) absorbs paths that reach that equity multiple.
    Paths that hit ruin stay at the ruin level for the rest of the run.
    ``record_band=False`` skips the per-trade percentile band (saves memory on long runs).
    """
    if not 0.0 <= p <= 1.0:
        raise ValueError("win probability p must be between 0 and 1")
    if payoff <= 0 or not 0 < f <= 1:
        raise ValueError("payoff must be > 0 and f in (0, 1]")
    rng = np.random.default_rng(seed)
    wins = rng.random((paths, trades)) < p
    eq = np.ones(paths)
    peak = np.ones(paths)
    max_dd = np.zeros(paths)
    ruined = np.zeros(paths, dtype=bool)
    hit_target = np.zeros(paths, dtype=bool)
    history: NDArray[np.float64] | None = np.empty((trades + 1, paths)) if record_band else None
    if history is not None:
        history[0] = eq
    for i in range(trades):
        live = ~(ruined | hit_target)
        if mode == "fraction":
            step = np.where(wins[:, i], f * payoff, -f) * eq
        else:
            step = np.where(wins[:, i], f * payoff, -f)
        eq = np.where(live, eq + step, eq)
        newly_ruined = live & (eq <= ruin_level + 1e-12)
        eq = np.where(newly_ruined, ruin_level, eq)
        ruined |= newly_ruined
        if stop_at is not None:
            hit_target |= live & ~ruined & (eq >= stop_at - 1e-12)
        peak = np.maximum(peak, eq)
        max_dd = np.maximum(max_dd, 1.0 - eq / peak)
        if history is not None:
            history[i + 1] = eq
    pct = (5, 25, 50, 75, 95)
    band: dict[int, list[float]] = {}
    band_x: list[int] = []
    if history is not None:
        # ~50 evenly spaced points keep the chart readable; percentiles of a discrete
        # outcome lattice zigzag trade-to-trade otherwise.
        idx = np.unique(np.linspace(0, trades, min(trades, 50) + 1).round().astype(int))
        band_x = idx.tolist()
        band = {q: np.percentile(history[idx], q, axis=1).round(6).tolist() for q in pct}
    return RiskResult(
        paths=paths,
        trades=trades,
        kelly=kelly_fraction(p, payoff),
        edge=edge_per_trade(p, payoff),
        prob_drawdown=float(np.mean(max_dd >= drawdown_level - 1e-12)),
        prob_ruin=float(np.mean(ruined)),
        prob_target=float(np.mean(hit_target)),
        final_percentiles={q: float(np.percentile(eq, q)) for q in pct},
        band=band,
        band_x=band_x,
    )


def risk_report(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    risk_pct: float,
    trades: int = 200,
    drawdown_pct: float = 50.0,
) -> dict:
    """JSON-friendly calculator output for the web page (percent inputs, dollars for P&L)."""
    if avg_loss <= 0 or avg_win <= 0:
        raise ValueError("average win and average loss must both be positive amounts")
    p, payoff, f = win_rate / 100.0, avg_win / avg_loss, risk_pct / 100.0
    res = simulate(p, payoff, f, trades=trades, drawdown_level=drawdown_pct / 100.0, ruin_level=0.2)
    return {
        "payoff": payoff,
        "edge": res.edge,
        "kelly": res.kelly,
        "risk_vs_kelly": f / res.kelly if res.kelly > 0 else None,
        "prob_drawdown": res.prob_drawdown,
        "prob_ruin": res.prob_ruin,
        "final_percentiles": res.final_percentiles,
        "band": res.band,
        "band_x": res.band_x,
        "paths": res.paths,
        "trades": res.trades,
        "drawdown_pct": drawdown_pct,
    }
