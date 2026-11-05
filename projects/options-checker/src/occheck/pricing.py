"""Black-Scholes-Merton pricing, Greeks and implied volatility.

European options on an underlying with continuous dividend yield ``q``.
All inputs accept scalars or numpy arrays (broadcast together); outputs match.

Units: ``t`` in years, ``r``/``q``/``sigma`` as decimals per year (0.05 = 5%).
Vega and rho are per 1.00 change (divide by 100 for "per vol point").
Theta is per year (divide by 365 for per calendar day).

Only numpy is used at runtime so the module loads quickly in Pyodide; the
normal CDF uses ``math.erf``.
"""

from __future__ import annotations

import math
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

Right = Literal["C", "P"]

_SQRT2 = math.sqrt(2.0)
_INV_SQRT_2PI = 1.0 / math.sqrt(2.0 * math.pi)
_erf = np.frompyfunc(math.erf, 1, 1)


def norm_cdf(x: ArrayLike) -> NDArray[np.float64]:
    """Standard normal cumulative distribution function."""
    x = np.asarray(x, dtype=float)
    return 0.5 * (1.0 + np.asarray(_erf(x / _SQRT2), dtype=float))


def norm_pdf(x: ArrayLike) -> NDArray[np.float64]:
    """Standard normal probability density function."""
    x = np.asarray(x, dtype=float)
    return _INV_SQRT_2PI * np.exp(-0.5 * x * x)


def _sign(right: Right) -> float:
    if right == "C":
        return 1.0
    if right == "P":
        return -1.0
    raise ValueError(f"right must be 'C' or 'P', got {right!r}")


def _d1_d2(s, k, t, r, q, sigma):
    vol_t = sigma * np.sqrt(t)
    with np.errstate(divide="ignore", invalid="ignore"):
        d1 = (np.log(s / k) + (r - q + 0.5 * sigma * sigma) * t) / vol_t
    return d1, d1 - vol_t


def _scalar_or_array(x: NDArray[np.float64]) -> float | NDArray[np.float64]:
    return float(x) if np.ndim(x) == 0 else x


def bs_price(
    s: ArrayLike,
    k: ArrayLike,
    t: ArrayLike,
    r: ArrayLike,
    sigma: ArrayLike,
    right: Right,
    q: ArrayLike = 0.0,
) -> float | NDArray[np.float64]:
    """Black-Scholes-Merton price of a European call ("C") or put ("P").

    At ``t == 0`` or ``sigma == 0`` the price is the discounted intrinsic value of
    the forward, which is the limit of the formula.
    """
    w = _sign(right)
    s, k, t, r, q, sigma = (np.asarray(a, dtype=float) for a in (s, k, t, r, q, sigma))
    s, k, t, r, q, sigma = np.broadcast_arrays(s, k, t, r, q, sigma)
    df_r, df_q = np.exp(-r * t), np.exp(-q * t)
    degenerate = (t <= 0) | (sigma <= 0)
    d1, d2 = _d1_d2(s, k, np.where(degenerate, 1.0, t), r, q, np.where(degenerate, 1.0, sigma))
    live = w * (s * df_q * norm_cdf(w * d1) - k * df_r * norm_cdf(w * d2))
    limit = np.maximum(w * (s * df_q - k * df_r), 0.0)
    return _scalar_or_array(np.where(degenerate, limit, live))


def bs_greeks(
    s: ArrayLike,
    k: ArrayLike,
    t: ArrayLike,
    r: ArrayLike,
    sigma: ArrayLike,
    right: Right,
    q: ArrayLike = 0.0,
) -> dict[str, float | NDArray[np.float64]]:
    """Delta, gamma, vega, theta and rho for a European option (``t > 0``, ``sigma > 0``).

    Returns a dict with keys ``delta``, ``gamma``, ``vega``, ``theta``, ``rho``.
    """
    w = _sign(right)
    s, k, t, r, q, sigma = (np.asarray(a, dtype=float) for a in (s, k, t, r, q, sigma))
    if np.any(t <= 0) or np.any(sigma <= 0):
        raise ValueError("Greeks need t > 0 and sigma > 0")
    d1, d2 = _d1_d2(s, k, t, r, q, sigma)
    df_r, df_q = np.exp(-r * t), np.exp(-q * t)
    pdf = norm_pdf(d1)
    sqrt_t = np.sqrt(t)
    greeks = {
        "delta": w * df_q * norm_cdf(w * d1),
        "gamma": df_q * pdf / (s * sigma * sqrt_t),
        "vega": s * df_q * pdf * sqrt_t,
        "theta": (
            -s * df_q * pdf * sigma / (2.0 * sqrt_t)
            - w * r * k * df_r * norm_cdf(w * d2)
            + w * q * s * df_q * norm_cdf(w * d1)
        ),
        "rho": w * k * t * df_r * norm_cdf(w * d2),
    }
    return {name: _scalar_or_array(np.asarray(v, dtype=float)) for name, v in greeks.items()}


def implied_vol(
    price: float,
    s: float,
    k: float,
    t: float,
    r: float,
    right: Right,
    q: float = 0.0,
    *,
    tol: float = 1e-10,
    lo: float = 1e-6,
    hi: float = 5.0,
    max_iter: int = 200,
) -> float:
    """Implied volatility that reproduces ``price``, by safeguarded Newton iteration.

    Newton steps on vega, falling back to bisection whenever a step would leave the
    bracket ``[lo, hi]``. Raises ``ValueError`` if ``price`` is outside the no-arbitrage
    bounds or the bracket.
    """
    if t <= 0:
        raise ValueError("implied vol needs t > 0")
    w = _sign(right)
    df_r, df_q = math.exp(-r * t), math.exp(-q * t)
    lower = max(w * (s * df_q - k * df_r), 0.0)
    upper = s * df_q if w > 0 else k * df_r
    if not lower - 1e-12 <= price <= upper + 1e-12:
        raise ValueError(f"price {price} outside no-arbitrage bounds [{lower:.6g}, {upper:.6g}]")
    if price - lower <= 1e-9:
        raise ValueError("option has no time value; implied vol is undefined")

    def f(vol: float) -> float:
        return float(bs_price(s, k, t, r, vol, right, q)) - price

    f_lo, f_hi = f(lo), f(hi)
    if f_lo > 0 or f_hi < 0:
        raise ValueError("implied vol outside search bracket")
    vol = 0.2 if lo < 0.2 < hi else 0.5 * (lo + hi)
    for _ in range(max_iter):
        diff = f(vol)
        if abs(diff) < tol:
            return vol
        if diff > 0:
            hi = vol
        else:
            lo = vol
        vega = float(bs_greeks(s, k, t, r, vol, right, q)["vega"])
        step = vol - diff / vega if vega > 1e-14 else -1.0
        vol = step if lo < step < hi else 0.5 * (lo + hi)
        if hi - lo < 1e-15:
            return vol
    return vol
