"""A one-parameter SPX volatility smile for synthetic options.

Implied vol for strike ``K`` is

    sigma(K) = sigma_atm * clip(1 - beta * z, 0.5, 3),   z = ln(K / S) / (sigma_atm * sqrt(T))

so out-of-the-money puts (z < 0) trade above at-the-money vol: the SPX skew. Measuring
moneyness in standard deviations (z) keeps the shape the same at any vol level and
maturity. ATM vol itself stays 0.9 x VIX, the level validated against the Cboe PUT
index. ``beta`` = 0.10 is the default; how it was chosen (and two rejected
alternatives) is in docs/validation/skew-calibration.md.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from numpy.typing import ArrayLike, NDArray

from occheck.pricing import bs_price

CLIP = (0.5, 3.0)
DEFAULT_BETA = 0.10


def smile_vol(
    atm: ArrayLike, s: ArrayLike, k: ArrayLike, tau: ArrayLike, beta: float
) -> NDArray[np.float64]:
    """Implied vol at strike ``k`` given ATM vol, spot, time to expiry (years) and slope."""
    atm, s, k, tau = (np.asarray(a, dtype=float) for a in (atm, s, k, tau))
    if beta == 0:
        return np.broadcast_to(atm, np.broadcast(atm, s, k, tau).shape).astype(float)
    t = np.maximum(tau, 1.0 / 365.0)
    z = np.log(k / s) / (atm * np.sqrt(t))
    return atm * np.clip(1.0 - beta * z, *CLIP)


@lru_cache(maxsize=64)
def vix_over_atm(beta: float, t: float = 30.0 / 365.0) -> float:
    """Variance-swap (VIX-style) vol divided by ATM vol for slope ``beta``.

    By the replication integral sigma_VS^2 = (2/T) * integral Q(K)/K^2 dK over OTM
    options (Cboe VIX methodology), at zero rates. Used in the calibration report to
    show how much of the VIX/ATM gap the skew alone explains.
    """
    if beta == 0:
        return 1.0
    atm = 0.15
    k = np.linspace(0.2, 2.5, 40_001)
    vol = smile_vol(atm, 1.0, k, t, beta)
    q = np.where(k < 1.0, bs_price(1.0, k, t, 0.0, vol, "P"), bs_price(1.0, k, t, 0.0, vol, "C"))
    return float(np.sqrt(2.0 / t * np.trapezoid(q / k**2, k)) / atm)
