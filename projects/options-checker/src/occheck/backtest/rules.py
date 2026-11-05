"""Rule-based short-put backtest on synthetic SPX options.

The strategy sells cash-secured (or levered) SPX puts by forum-style rules:

* open at a target delta (e.g. 0.30) with a target days-to-expiry (e.g. 45);
* close early at a take-profit (e.g. 50% of the premium kept);
* close at a management DTE (e.g. 21 days left), or hold to expiry;
* optional stop-loss at a multiple of the premium received;
* re-open the next position the same day;
* pay a bid-ask cost, as a share of the option price, on every open and close.

Options are priced with :func:`occheck.pricing.bs_price`. ATM vol = VIX x ``atm_vol_ratio``
(validated against the Cboe PUT index); strikes away from the money follow the
one-parameter smile in :mod:`occheck.backtest.skew` (validated against the 2%-OTM PUTY
index; docs/validation/skew-calibration.md). Today's real SPX smile is steeper than the
historical fit, so far-OTM premiums may still be understated in today's markets.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np
from numpy.typing import NDArray

from occheck.backtest.putwrite import cagr, max_drawdown, month_end_returns, monthly_expirations
from occheck.backtest.skew import DEFAULT_BETA, smile_vol
from occheck.pricing import bs_price, norm_cdf

STRESS_PERIODS: tuple[tuple[str, str, str], ...] = (
    ("1998 LTCM / Russia", "1998-07-17", "1998-10-08"),
    ("2008 financial crisis", "2008-09-01", "2009-03-09"),
    ("2011 US downgrade", "2011-07-22", "2011-10-03"),
    ("Feb 2018 volatility spike", "2018-01-26", "2018-02-08"),
    ("Mar 2020 Covid crash", "2020-02-19", "2020-03-23"),
    ("2022 bear market", "2022-01-03", "2022-10-12"),
)


@dataclass(frozen=True)
class Rules:
    """Short-put rules. Defaults follow the common r/thetagang guide (see research review)."""

    delta: float | None = 0.30  # absolute put delta at open; None = strike exactly at spot
    dte: int = 45  # calendar days to expiry at open (ignored when monthly=True)
    monthly: bool = False  # open/expire on third Fridays, like the Cboe PUT index
    take_profit: float | None = 0.50  # close when this share of premium is captured
    manage_dte: int | None = 21  # close when this many days remain
    stop_loss: float | None = None  # close if the put costs this multiple of premium
    leverage: float = 1.0  # strike notional / equity; 1.0 = fully cash-secured
    cost_frac: float = 0.03  # bid-ask cost per side, as a share of the option price
    atm_vol_ratio: float = 0.9
    skew_beta: float = DEFAULT_BETA  # smile slope for OTM strikes; 0 = flat vol


@dataclass(frozen=True)
class Trade:
    """One opened-and-closed short put, per unit of equity at open."""

    open_date: str
    close_date: str
    strike_pct: float  # strike / spot at open
    premium_pct: float  # premium / spot at open
    pnl_pct: float  # P&L as a share of equity at open, after costs
    reason: str


def _ppf(prob: float) -> float:
    """Inverse standard normal CDF by bisection (no scipy at runtime)."""
    lo, hi = -10.0, 10.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if float(norm_cdf(mid)) < prob:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def strike_for_put_delta(s: float, t: float, r: float, sigma: float, delta: float) -> float:
    """Strike whose Black-Scholes put delta equals ``-delta`` (``0 < delta < 1``)."""
    if not 0.0 < delta < 1.0:
        raise ValueError("delta must be between 0 and 1")
    d1 = -_ppf(delta)  # put delta = N(d1) - 1 = -delta
    return s * math.exp(-(d1 * sigma * math.sqrt(t) - (r + 0.5 * sigma * sigma) * t))


def strike_for_put_delta_smile(
    s: float, t: float, r: float, atm: float, delta: float, beta: float
) -> float:
    """Like :func:`strike_for_put_delta`, with each strike priced at its own smile vol.

    Fixed-point iteration: price at the vol of the current strike guess, re-solve.
    """
    k = strike_for_put_delta(s, t, r, atm, delta)
    for _ in range(50):
        vol = float(smile_vol(atm, s, k, t, beta))
        k_new = strike_for_put_delta(s, t, r, vol, delta)
        if abs(k_new - k) < 1e-9 * s:
            return k_new
        k = k_new
    return k


@dataclass(frozen=True)
class BacktestResult:
    """Daily equity plus the trade list."""

    dates: NDArray[np.datetime64]
    equity: NDArray[np.float64]
    trades: list[Trade]


def run_short_puts(
    dates: NDArray[np.datetime64],
    spx: NDArray[np.float64],
    vix: NDArray[np.float64],
    rate_pct: NDArray[np.float64],
    rules: Rules | None = None,
) -> BacktestResult:
    """Backtest ``rules`` on aligned daily arrays. Equity starts at 1.0."""
    rules = rules or Rules()
    n_days = len(dates)
    vol = vix / 100.0 * rules.atm_vol_ratio
    r = rate_pct / 100.0
    day_num = dates.astype("datetime64[D]").astype(np.int64)
    equity = np.empty(n_days)
    equity[0] = 1.0
    cash, i, trades = 1.0, 0, []
    expiries = monthly_expirations(dates) if rules.monthly else None
    if expiries is not None:
        if len(expiries) < 2:
            raise ValueError("need at least two monthly expirations in the data")
        i = int(expiries[0])
        equity[: i + 1] = 1.0
    while i < n_days - 1:
        if expiries is not None:
            nxt = expiries[expiries > i]
            if not len(nxt):
                break
            last = int(nxt[0])
            expiry_day = int(day_num[last])
        else:
            expiry_day = day_num[i] + rules.dte
            last = int(np.searchsorted(day_num, expiry_day, side="right") - 1)
        if last <= i:
            break
        t0 = (expiry_day - day_num[i]) / 365.0
        if rules.delta is None:
            k = float(spx[i])
        else:
            k = strike_for_put_delta_smile(spx[i], t0, r[i], vol[i], rules.delta, rules.skew_beta)
        prem = float(
            bs_price(spx[i], k, t0, r[i], smile_vol(vol[i], spx[i], k, t0, rules.skew_beta), "P")
        )
        contracts = rules.leverage * cash / k
        start_cash = cash
        cash += contracts * prem * (1.0 - rules.cost_frac)
        days = np.arange(i + 1, last + 1)
        tau = (expiry_day - day_num[days]) / 365.0
        vols = smile_vol(vol[days], spx[days], k, tau, rules.skew_beta)
        px = np.asarray(bs_price(spx[days], k, tau, r[days], vols, "P"), dtype=float)
        gap = (day_num[days] - day_num[days - 1]).astype(float)
        cash_path = cash * np.cumprod(1.0 + r[days - 1] * gap / 360.0)
        reason = np.full(len(days), "", dtype=object)
        if rules.take_profit is not None:
            reason[px <= prem * (1.0 - rules.take_profit)] = "take profit"
        if rules.stop_loss is not None:
            reason[(reason == "") & (px >= prem * rules.stop_loss)] = "stop loss"
        if rules.manage_dte is not None:
            reason[(reason == "") & (expiry_day - day_num[days] <= rules.manage_dte)] = "managed"
        hit = np.flatnonzero(reason != "")
        j = int(hit[0]) if len(hit) else len(days) - 1
        why = str(reason[j]) if len(hit) else "expired"
        close_px = px[j]
        cost = 0.0 if why == "expired" else contracts * close_px * rules.cost_frac
        equity[days[:j]] = cash_path[:j] - contracts * px[:j]
        cash = float(cash_path[j] - contracts * close_px - cost)
        equity[days[j]] = cash
        trades.append(
            Trade(
                open_date=str(dates[i]),
                close_date=str(dates[days[j]]),
                strike_pct=k / spx[i],
                premium_pct=prem / spx[i],
                pnl_pct=cash / start_cash - 1.0,
                reason=why,
            )
        )
        if cash <= 0:  # levered account wiped out
            equity[days[j] :] = 0.0
            i = n_days
            break
        i = int(days[j])
    end = i if i < n_days else n_days - 1
    first = int(expiries[0]) if expiries is not None else 0
    return BacktestResult(dates[first : end + 1], equity[first : end + 1], trades)


def _window_return(dates, values, lo: str, hi: str) -> float | None:
    m = (dates >= np.datetime64(lo)) & (dates <= np.datetime64(hi))
    if m.sum() < 2:
        return None
    v = values[m]
    return float(v[-1] / v[0] - 1.0)


def _window_drawdown(dates, values, lo: str, hi: str) -> float | None:
    m = (dates >= np.datetime64(lo)) & (dates <= np.datetime64(hi))
    return max_drawdown(values[m]) if m.sum() >= 2 else None


def summarize(
    result: BacktestResult, spx_dates: NDArray[np.datetime64], spx: NDArray[np.float64]
) -> dict:
    """Headline stats, stress-period table and chart series, JSON-friendly."""
    d, eq = result.dates, result.equity
    alive = eq > 0
    sel = (spx_dates >= d[0]) & (spx_dates <= d[-1])
    sd, sv = spx_dates[sel], spx[sel]
    _, mr = month_end_returns(d[alive], eq[alive]) if alive.sum() > 40 else (None, np.array([0.0]))
    pnls = np.array([t.pnl_pct for t in result.trades]) if result.trades else np.array([0.0])
    step = max(1, len(d) // 600)
    common, ia, ib = np.intersect1d(d[::step], sd, return_indices=True)
    stress = []
    for name, lo, hi in STRESS_PERIODS:
        if np.datetime64(lo) < d[0] or np.datetime64(hi) > d[-1]:
            continue
        stress.append(
            {
                "name": name,
                "from": lo,
                "to": hi,
                "strategy": _window_return(d, eq, lo, hi),
                "strategy_drawdown": _window_drawdown(d, eq, lo, hi),
                "spx": _window_return(sd, sv, lo, hi),
            }
        )
    reasons: dict[str, int] = {}
    for t in result.trades:
        reasons[t.reason] = reasons.get(t.reason, 0) + 1
    wiped = bool(eq[-1] <= 0)
    return {
        "start": str(d[0]),
        "end": str(d[-1]),
        "wiped_out": wiped,
        "strategy": {
            "cagr": None if wiped else cagr(d, eq),
            "max_drawdown": max_drawdown(np.maximum(eq, 1e-12)),
            "worst_month": float(mr.min()),
            "vol": float(np.std(mr, ddof=1) * math.sqrt(12)) if len(mr) > 2 else None,
        },
        "spx": {
            "cagr": cagr(sd, sv),
            "max_drawdown": max_drawdown(sv),
            "worst_month": float(month_end_returns(sd, sv)[1].min()),
        },
        "trades": {
            "count": len(result.trades),
            "win_rate": float(np.mean(pnls > 0)),
            "avg_pnl": float(pnls.mean()),
            "worst": float(pnls.min()),
            "best": float(pnls.max()),
            "close_reasons": reasons,
        },
        "stress": stress,
        "chart": {
            "dates": [str(x) for x in common],
            "strategy": [round(float(x), 6) for x in eq[::step][ia]],
            "spx": [round(float(x / sv[0]), 6) for x in sv[ib]],
        },
    }


def backtest_report(spx_text: str, vix_text: str, dtb3_text: str, **rule_args) -> dict:
    """Parse the three CSVs, run the rules and summarize (entry point for the web page)."""
    from occheck import data

    spx = data.load_csv(spx_text)
    vix = data.load_csv(vix_text)
    tb = data.load_csv(dtb3_text)
    for s, want in ((spx, "SPX"), (vix, "VIX"), (tb, "DTB3")):
        if s.kind != want:
            raise data.DataFormatError(f"expected the {want} file, got {s.kind}")
    rules = Rules(**rule_args)
    dates, (s, v, r) = data.align(spx, vix, tb)
    out = summarize(run_short_puts(dates, s, v, r, rules), dates, s)
    out["rules"] = asdict(rules)
    return out
