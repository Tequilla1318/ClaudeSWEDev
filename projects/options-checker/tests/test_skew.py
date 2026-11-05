"""Smile shape and the VIX/ATM replication integral."""

import numpy as np
import pytest

from occheck.backtest.skew import smile_vol, vix_over_atm


def test_smile_shape():
    atm, s, t = 0.15, 100.0, 30 / 365
    assert float(smile_vol(atm, s, s, t, 0.1)) == pytest.approx(atm)  # ATM unchanged
    k_otm = s * np.exp(-1.0 * atm * np.sqrt(t))  # one standard deviation below spot
    assert float(smile_vol(atm, s, k_otm, t, 0.1)) == pytest.approx(atm * 1.1)
    assert float(smile_vol(atm, s, 1.0, t, 0.1)) == pytest.approx(atm * 3.0)  # clipped
    assert float(smile_vol(atm, s, 80.0, t, 0.0)) == atm  # flat


def test_scale_free_in_z():
    # Same z at a different vol level gives the same vol multiple.
    for atm in (0.1, 0.3):
        k = 100 * np.exp(-0.5 * atm * np.sqrt(0.1))
        assert float(smile_vol(atm, 100, k, 0.1, 0.2)) / atm == pytest.approx(1.1)


def test_vix_over_atm_integral():
    assert vix_over_atm(0.0) == 1.0
    # A flat smile at 15% must reproduce 15%: check the integral itself via beta ~ 0.
    assert vix_over_atm(1e-9) == pytest.approx(1.0, abs=2e-4)
    vals = [vix_over_atm(b) for b in (0.1, 0.2, 0.3)]
    assert vals == sorted(vals) and vals[1] == pytest.approx(1 / 0.925, abs=0.005)
