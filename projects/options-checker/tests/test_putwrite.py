"""Synthetic put-write: calendar, analytic cases, and (opt-in) the real PUT index."""

import os

import numpy as np
import pytest

from occheck import data
from occheck.backtest.putwrite import (
    cagr,
    compare_to_index,
    max_drawdown,
    month_end_returns,
    monthly_expirations,
    put_write,
)
from occheck.pricing import bs_price


def _weekdays(start, end):
    d = np.arange(np.datetime64(start), np.datetime64(end), dtype="datetime64[D]")
    return d[((d.astype(np.int64) + 3) % 7) < 5]


def test_third_fridays_and_holiday():
    d = _weekdays("2008-01-01", "2008-05-01")
    d = d[d != np.datetime64("2008-03-21")]  # Good Friday 2008 = 3rd Friday, market closed
    got = [str(x) for x in d[monthly_expirations(d)]]
    assert got == ["2008-01-18", "2008-02-15", "2008-03-20", "2008-04-18"]


def test_zero_vol_flat_market_earns_tbill_only():
    d = _weekdays("2020-01-01", "2020-07-01")
    n = len(d)
    res = put_write(d, np.full(n, 3000.0), np.zeros(n), np.full(n, 3.6), atm_vol_ratio=1.0)
    days = (res.dates[-1] - res.dates[0]).astype(int)
    gaps = np.diff(res.dates).astype(int)
    expected = np.prod(1 + 0.036 * gaps / 360)
    assert res.equity[-1] == pytest.approx(expected, rel=1e-12)
    assert days > 120


def test_one_month_matches_hand_calculation():
    d = _weekdays("2021-01-15", "2021-02-20")  # rolls 2021-01-15 and 2021-02-19
    n = len(d)
    spx = np.full(n, 4000.0)
    spx[-1] = 3800.0  # expiry close 5% below the strike
    vix, rate = np.full(n, 20.0), np.zeros(n)
    res = put_write(d, spx, vix, rate, atm_vol_ratio=1.0)
    t = (np.datetime64("2021-02-19") - np.datetime64("2021-01-15")).astype(int) / 365
    premium = bs_price(4000, 4000, t, 0.0, 0.20, "P")
    expected = 1 + premium / 4000 - (4000 - 3800) / 4000
    end = list(res.dates).index(np.datetime64("2021-02-19"))
    assert res.equity[end] == pytest.approx(expected, rel=1e-12)


def test_costs_reduce_returns():
    d = _weekdays("2021-01-01", "2021-12-31")
    n = len(d)
    args = (d, np.full(n, 4000.0), np.full(n, 20.0), np.full(n, 1.0))
    assert put_write(*args, cost_frac=0.1).equity[-1] < put_write(*args).equity[-1]


def test_stats_helpers():
    d = _weekdays("2020-01-01", "2022-01-01")
    v = np.linspace(1.0, 1.21, len(d))
    assert cagr(d, v) == pytest.approx(0.1, abs=0.002)
    assert max_drawdown(np.array([1.0, 2.0, 1.0, 3.0])) == pytest.approx(0.5)
    m, r = month_end_returns(d, v)
    assert len(m) == 23 and np.all(r > 0)


def test_compare_identical_series():
    d = _weekdays("2021-01-01", "2023-01-01")
    n = len(d)
    rng = np.random.default_rng(0)
    spx = 4000 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    res = put_write(d, spx, np.full(n, 20.0), np.full(n, 1.0))
    c = compare_to_index(res, res.dates, res.equity * 250.0)
    assert c["monthly_corr"] == pytest.approx(1.0) and c["cagr_diff"] == pytest.approx(0.0)


@pytest.mark.skipif(not os.environ.get("OCCHECK_LIVE"), reason="network test")
def test_gate_against_real_put_index(tmp_path):
    load = lambda k: data.load_csv(data.download(k, tmp_path).read_text())  # noqa: E731
    spx, vix, tb, put = (load(k) for k in ("SPX", "VIX", "DTB3", "PUT"))
    dates, (s, v, r) = data.align(spx, vix, tb)
    m = dates >= np.datetime64("2007-06-01")
    c = compare_to_index(put_write(dates[m], s[m], v[m], r[m]), put.dates, put.values)
    assert c["monthly_corr"] >= 0.9 and abs(c["cagr_diff"]) <= 0.015


@pytest.mark.skipif(not os.environ.get("OCCHECK_LIVE"), reason="network test")
def test_skew_gate_against_real_puty_index(tmp_path):
    from occheck.backtest.skew import DEFAULT_BETA

    load = lambda k: data.load_csv(data.download(k, tmp_path).read_text())  # noqa: E731
    spx, vix, tb, puty = (load(k) for k in ("SPX", "VIX", "DTB3", "PUTY"))
    dates, (s, v, r) = data.align(spx, vix, tb)
    for lo, hi in (("1990-01-01", "2007-12-31"), ("2008-01-01", "2099-12-31")):
        m = (dates >= np.datetime64(lo)) & (dates <= np.datetime64(hi))
        res = put_write(dates[m], s[m], v[m], r[m], moneyness=0.98, skew_beta=DEFAULT_BETA)
        c = compare_to_index(res, puty.dates, puty.values)
        assert c["monthly_corr"] >= 0.9 and abs(c["cagr_diff"]) <= 0.015
