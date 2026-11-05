"""Risk-of-ruin Monte Carlo validated against closed forms."""

import math

import numpy as np
import pytest

from occheck.risk import (
    edge_per_trade,
    gamblers_ruin_probability,
    kelly_fraction,
    risk_report,
    simulate,
)


def test_kelly_and_edge():
    assert kelly_fraction(0.6, 1.0) == pytest.approx(0.2)
    assert kelly_fraction(0.5, 2.0) == pytest.approx(0.25)
    assert edge_per_trade(0.6, 1.0) == pytest.approx(0.2)
    assert kelly_fraction(0.4, 1.0) < 0


def test_gamblers_ruin_closed_form_known_values():
    assert gamblers_ruin_probability(0.5, 5, 10) == pytest.approx(0.5)
    # p=0.45, start 10 units, target 20: ((11/9)^10 - (11/9)^20) / (1 - (11/9)^20)
    r = 0.55 / 0.45
    assert gamblers_ruin_probability(0.45, 10, 20) == pytest.approx((r**10 - r**20) / (1 - r**20))


@pytest.mark.parametrize("p,start,target", [(0.5, 5, 10), (0.48, 10, 20), (0.55, 4, 12)])
def test_fixed_bet_monte_carlo_matches_gamblers_ruin(p, start, target):
    # Bet 1/start of equity each trade -> start units; absorb at target/start.
    res = simulate(
        p, payoff=1.0, f=1 / start, trades=4000, paths=20_000, mode="fixed",
        stop_at=target / start, seed=1, record_band=False,
    )  # fmt: skip
    exact = gamblers_ruin_probability(p, start, target)
    se = math.sqrt(exact * (1 - exact) / res.paths)
    assert res.prob_ruin + res.prob_target == pytest.approx(1.0, abs=1e-3)  # all absorbed
    assert abs(res.prob_ruin - exact) < 3 * se


def test_fraction_mode_mean_matches_analytic_expectation():
    p, b, f, n = 0.55, 1.2, 0.05, 50
    res = simulate(p, b, f, trades=n, paths=50_000, ruin_level=-1.0, seed=2, record_band=False)
    # E[final] = (1 + f*(p*b - (1-p)))^n for fixed-fraction betting.
    expected = (1 + f * (p * b - (1 - p))) ** n
    rng = np.random.default_rng(2)
    wins = rng.random((50_000, n)) < p
    finals = np.prod(np.where(wins, 1 + f * b, 1 - f), axis=1)
    se = finals.std() / math.sqrt(finals.size)
    assert finals.mean() == pytest.approx(expected, abs=4 * se)
    assert res.final_percentiles[50] == pytest.approx(np.percentile(finals, 50), rel=1e-9)


def test_more_risk_means_more_drawdowns():
    lo = simulate(0.55, 1.0, 0.02, trades=200, paths=5000)
    hi = simulate(0.55, 1.0, 0.25, trades=200, paths=5000)
    assert hi.prob_drawdown > lo.prob_drawdown
    assert hi.final_percentiles[5] < lo.final_percentiles[5]


def test_band_shape_and_validation():
    res = simulate(0.5, 1.5, 0.1, trades=30, paths=200)
    assert set(res.band) == {5, 25, 50, 75, 95}
    assert res.band_x == list(range(31))  # <= 50 trades: every trade
    assert all(len(v) == 31 for v in res.band.values())
    assert res.band[5][0] == res.band[95][0] == 1.0
    with pytest.raises(ValueError):
        simulate(1.5, 1.0, 0.1)
    with pytest.raises(ValueError):
        simulate(0.5, 1.0, 0.0)


def test_risk_report_inputs_and_kelly_ratio():
    r = risk_report(win_rate=60, avg_win=100, avg_loss=100, risk_pct=10, trades=50)
    assert r["payoff"] == pytest.approx(1.0) and r["kelly"] == pytest.approx(0.2)
    assert r["risk_vs_kelly"] == pytest.approx(0.5)
    assert 0 <= r["prob_drawdown"] <= 1 and len(r["band"][50]) == len(r["band_x"]) == 51
    assert risk_report(40, 100, 100, 5)["risk_vs_kelly"] is None  # negative edge
    with pytest.raises(ValueError):
        risk_report(50, 100, 0, 5)
