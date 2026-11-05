"""Synthetic replication of the Cboe S&P 500 PutWrite index (PUT).

PUT's published rules, simplified here: on each monthly SPX expiration (third
Friday), sell one-month at-the-money SPX puts, fully cash-secured. The collateral
earns Treasury-bill interest, and the puts are held to expiry.

There is no free history of SPX option prices, so the puts are priced with
Black-Scholes:

* underlying: SPX close;
* volatility: VIX close x ``atm_vol_ratio`` (default 0.9). VIX measures 30-day
  variance across all strikes, including expensive out-of-the-money puts, so it sits
  above at-the-money implied vol. 0.9 was fitted on 2007-2016 and held out of sample
  on 2017-2026; see docs/validation/put-replication.md;
* rate: 3-month T-bill (DTB3), which also accrues on the cash, act/360;
* expiry settlement: SPX close on the expiration date. The real index settles at
  that morning's opening print (SOQ), so this is one source of tracking error.

The point is to measure how far this model is from the real index (S9) before any
rule results built on it are trusted (S10).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from occheck.pricing import bs_price


def monthly_expirations(dates: NDArray[np.datetime64]) -> NDArray[np.int64]:
    """Indices into ``dates`` of each month's third Friday (or the trading day before).

    A month is included only if ``dates`` covers its third Friday.
    """
    months = dates.astype("datetime64[M]")
    out: list[int] = []
    for m in np.unique(months):
        first = m.astype("datetime64[D]")
        # numpy weekday: 1970-01-01 was a Thursday, so (day + 3) % 7 == 0 is Monday.
        dow = (first.astype(np.int64) + 3) % 7
        first_friday = first + np.timedelta64(int((4 - dow) % 7), "D")
        third_friday = first_friday + np.timedelta64(14, "D")
        if third_friday < dates[0] or third_friday > dates[-1]:
            continue
        idx = int(np.searchsorted(dates, third_friday, side="right") - 1)
        if dates[idx].astype("datetime64[M]") == m:
            out.append(idx)
    return np.array(out, dtype=np.int64)


@dataclass(frozen=True)
class PutWriteResult:
    """Daily equity of the synthetic strategy (starts at 1.0 on the first roll)."""

    dates: NDArray[np.datetime64]
    equity: NDArray[np.float64]
    rolls: NDArray[np.int64]  # indices into ``dates`` of each roll


def put_write(
    dates: NDArray[np.datetime64],
    spx: NDArray[np.float64],
    vix: NDArray[np.float64],
    rate_pct: NDArray[np.float64],
    atm_vol_ratio: float = 0.9,
    cost_frac: float = 0.0,
) -> PutWriteResult:
    """Run the synthetic monthly ATM put-write on aligned daily arrays.

    ``rate_pct`` is the T-bill rate in percent a year. ``cost_frac`` is the share of
    each sold put's premium lost to the bid-ask spread (0 to replicate the index,
    which has no trading costs).
    """
    rolls = monthly_expirations(dates)
    if len(rolls) < 2:
        raise ValueError("need at least two monthly expirations in the data")
    first, last = int(rolls[0]), int(rolls[-1])
    r = rate_pct / 100.0
    equity = np.full(len(dates), np.nan)
    cash = 1.0
    equity[first] = 1.0
    for a, b in zip(rolls[:-1], rolls[1:], strict=True):
        k = spx[a]
        n = cash / k  # puts per unit of equity: fully cash-secured
        t_exp = (dates[b] - dates[a]).astype(int) / 365.0
        premium = bs_price(spx[a], k, t_exp, r[a], vix[a] / 100.0 * atm_vol_ratio, "P")
        cash += n * premium * (1.0 - cost_frac)
        days = np.arange(a + 1, b + 1)
        gap = np.diff(dates[a : b + 1]).astype(int)
        growth = np.cumprod(1.0 + r[a:b] * gap / 360.0)  # act/360 accrual, prior day's rate
        cash_path = cash * growth
        tau = (dates[b] - dates[days]).astype(int) / 365.0
        puts = bs_price(spx[days], k, tau, r[days], vix[days] / 100.0 * atm_vol_ratio, "P")
        equity[days] = cash_path - n * puts
        cash = float(equity[b])  # settle the expiring put, re-collateralize
    keep = slice(first, last + 1)
    return PutWriteResult(dates[keep], equity[keep], rolls - first)


def month_end_returns(
    dates: NDArray[np.datetime64], values: NDArray[np.float64]
) -> tuple[NDArray[np.datetime64], NDArray[np.float64]]:
    """Month-end-to-month-end simple returns (the last observation in each month)."""
    months = dates.astype("datetime64[M]")
    last = np.concatenate([months[1:] != months[:-1], [True]])
    m, v = months[last], values[last]
    return m[1:], v[1:] / v[:-1] - 1.0


def cagr(dates: NDArray[np.datetime64], values: NDArray[np.float64]) -> float:
    """Compound annual growth rate between the first and last observation."""
    years = (dates[-1] - dates[0]).astype(int) / 365.25
    return float((values[-1] / values[0]) ** (1.0 / years) - 1.0)


def max_drawdown(values: NDArray[np.float64]) -> float:
    """Largest peak-to-trough fall, as a positive fraction."""
    peak = np.maximum.accumulate(values)
    return float(np.max(1.0 - values / peak))


def compare_to_index(
    synth: PutWriteResult, idx_dates: NDArray[np.datetime64], idx_values: NDArray[np.float64]
) -> dict[str, float]:
    """Tracking statistics of the synthetic strategy vs the real index on common dates."""
    common, ia, ib = np.intersect1d(synth.dates, idx_dates, return_indices=True)
    s_vals, i_vals = synth.equity[ia], idx_values[ib]
    _, rs = month_end_returns(common, s_vals)
    _, ri = month_end_returns(common, i_vals)
    diff = rs - ri
    return {
        "start": str(common[0]),
        "end": str(common[-1]),
        "months": float(len(rs)),
        "monthly_corr": float(np.corrcoef(rs, ri)[0, 1]),
        "cagr_synth": cagr(common, s_vals),
        "cagr_index": cagr(common, i_vals),
        "cagr_diff": cagr(common, s_vals) - cagr(common, i_vals),
        "tracking_error": float(np.std(diff, ddof=1) * np.sqrt(12)),
        "mean_monthly_diff": float(np.mean(diff)),
        "max_dd_synth": max_drawdown(s_vals),
        "max_dd_index": max_drawdown(i_vals),
        "vol_synth": float(np.std(rs, ddof=1) * np.sqrt(12)),
        "vol_index": float(np.std(ri, ddof=1) * np.sqrt(12)),
    }
