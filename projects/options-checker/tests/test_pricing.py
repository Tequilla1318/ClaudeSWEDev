"""Validation of the Black-Scholes core against published values and scipy."""

import math

import numpy as np
import pytest
from scipy.stats import norm

from occheck.pricing import bs_greeks, bs_price, implied_vol, norm_cdf


def _scipy_bs(s, k, t, r, sigma, right, q=0.0):
    d1 = (math.log(s / k) + (r - q + 0.5 * sigma**2) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)
    if right == "C":
        return s * math.exp(-q * t) * norm.cdf(d1) - k * math.exp(-r * t) * norm.cdf(d2)
    return k * math.exp(-r * t) * norm.cdf(-d2) - s * math.exp(-q * t) * norm.cdf(-d1)


def test_hull_worked_example():
    # Hull, Options, Futures and Other Derivatives: S=42, K=40, r=10%, sigma=20%, T=0.5.
    assert bs_price(42, 40, 0.5, 0.10, 0.20, "C") == pytest.approx(4.76, abs=0.01)
    assert bs_price(42, 40, 0.5, 0.10, 0.20, "P") == pytest.approx(0.81, abs=0.01)


def test_norm_cdf_matches_scipy():
    x = np.linspace(-8, 8, 161)
    np.testing.assert_allclose(norm_cdf(x), norm.cdf(x), atol=1e-15)


GRID = [
    (s, k, t, r, sig, q)
    for s in (50.0, 100.0)
    for k in (80.0, 100.0, 120.0)
    for t in (0.02, 0.5, 2.0)
    for r in (0.0, 0.05)
    for sig in (0.1, 0.4)
    for q in (0.0, 0.02)
]


@pytest.mark.parametrize("s,k,t,r,sig,q", GRID)
def test_matches_scipy_and_parity(s, k, t, r, sig, q):
    c = bs_price(s, k, t, r, sig, "C", q)
    p = bs_price(s, k, t, r, sig, "P", q)
    assert c == pytest.approx(_scipy_bs(s, k, t, r, sig, "C", q), abs=1e-10)
    assert p == pytest.approx(_scipy_bs(s, k, t, r, sig, "P", q), abs=1e-10)
    assert c - p == pytest.approx(s * math.exp(-q * t) - k * math.exp(-r * t), abs=1e-10)


@pytest.mark.parametrize("right", ["C", "P"])
@pytest.mark.parametrize("s,k,t,r,sig,q", GRID[::7])
def test_greeks_match_finite_differences(right, s, k, t, r, sig, q):
    g = bs_greeks(s, k, t, r, sig, right, q)
    h = 1e-4

    def px(**kw):
        a = {"s": s, "k": k, "t": t, "r": r, "sigma": sig, "q": q} | kw
        return bs_price(a["s"], a["k"], a["t"], a["r"], a["sigma"], right, a["q"])

    fd_delta = (px(s=s + h) - px(s=s - h)) / (2 * h)
    fd_gamma = (px(s=s + h) - 2 * px() + px(s=s - h)) / h**2
    fd_vega = (px(sigma=sig + h) - px(sigma=sig - h)) / (2 * h)
    fd_rho = (px(r=r + h) - px(r=r - h)) / (2 * h)
    fd_theta = -(px(t=t + h) - px(t=t - h)) / (2 * h)  # theta = -dV/dT
    assert g["delta"] == pytest.approx(fd_delta, abs=1e-4)
    assert g["gamma"] == pytest.approx(fd_gamma, abs=1e-3)  # second difference is noisier
    assert g["vega"] == pytest.approx(fd_vega, abs=1e-4)
    assert g["rho"] == pytest.approx(fd_rho, abs=1e-4)
    assert g["theta"] == pytest.approx(fd_theta, rel=1e-5, abs=1e-4)  # O(h^2) error at short t


@pytest.mark.parametrize("right", ["C", "P"])
@pytest.mark.parametrize("s,k,t,r,sig,q", GRID)
def test_implied_vol_round_trip(right, s, k, t, r, sig, q):
    price = bs_price(s, k, t, r, sig, right, q)
    w = 1 if right == "C" else -1
    time_value = price - max(w * (s * math.exp(-q * t) - k * math.exp(-r * t)), 0.0)
    if time_value <= 1e-9:
        # Deep ITM/OTM and short-dated: price carries no vol information.
        with pytest.raises(ValueError):
            implied_vol(price, s, k, t, r, right, q)
        return
    if time_value < 1e-6:
        pytest.skip("time value too small for a 1e-6 vol tolerance")
    assert implied_vol(price, s, k, t, r, right, q) == pytest.approx(sig, abs=1e-6)


def test_vectorized_inputs():
    k = np.array([90.0, 100.0, 110.0])
    out = bs_price(100.0, k, 0.25, 0.03, 0.2, "C")
    assert out.shape == (3,)
    for ki, oi in zip(k, out, strict=True):
        assert oi == pytest.approx(bs_price(100.0, ki, 0.25, 0.03, 0.2, "C"))


def test_expiry_and_zero_vol_limits():
    assert bs_price(105, 100, 0.0, 0.05, 0.2, "C") == pytest.approx(5.0)
    assert bs_price(95, 100, 0.0, 0.05, 0.2, "P") == pytest.approx(5.0)
    assert bs_price(95, 100, 0.0, 0.05, 0.2, "C") == 0.0
    # sigma=0: discounted forward intrinsic
    assert bs_price(100, 100, 1.0, 0.05, 0.0, "C") == pytest.approx(100 - 100 * math.exp(-0.05))


def test_implied_vol_rejects_arbitrage_prices():
    with pytest.raises(ValueError):
        implied_vol(0.5, 100, 80, 0.5, 0.0, "C")  # below intrinsic of 20
    with pytest.raises(ValueError):
        implied_vol(150.0, 100, 80, 0.5, 0.0, "C")  # above spot


def test_bad_right_rejected():
    with pytest.raises(ValueError):
        bs_price(100, 100, 1, 0, 0.2, "X")
