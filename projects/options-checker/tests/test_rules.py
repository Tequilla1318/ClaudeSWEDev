"""Rule engine: exact cases, consistency with the validated put-write, and summaries."""

import os

import numpy as np
import pytest

from occheck import data
from occheck.backtest.putwrite import compare_to_index, put_write
from occheck.backtest.rules import (
    Rules,
    backtest_report,
    run_short_puts,
    strike_for_put_delta,
    summarize,
)
from occheck.pricing import bs_greeks, bs_price


def _days(start, end):
    d = np.arange(np.datetime64(start), np.datetime64(end), dtype="datetime64[D]")
    return d[((d.astype(np.int64) + 3) % 7) < 5]


@pytest.mark.parametrize("delta", [0.05, 0.16, 0.30, 0.50, 0.70])
def test_strike_for_delta_round_trip(delta):
    k = strike_for_put_delta(4000.0, 45 / 365, 0.04, 0.18, delta)
    assert bs_greeks(4000.0, k, 45 / 365, 0.04, 0.18, "P")["delta"] == pytest.approx(
        -delta, abs=1e-9
    )


def test_hold_to_expiry_single_trade_exact():
    d = _days("2021-03-01", "2021-04-20")
    n = len(d)
    spx = np.full(n, 4000.0)
    rules = Rules(delta=None, dte=30, take_profit=None, manage_dte=None, cost_frac=0.02)
    spx[d >= np.datetime64("2021-03-30")] = 3900.0
    res = run_short_puts(d, spx, np.full(n, 20.0), np.zeros(n), rules)
    t = res.trades[0]
    prem = float(bs_price(4000.0, 4000.0, 30 / 365, 0.0, 0.18, "P"))
    expected = prem * 0.98 / 4000 - 100 / 4000  # premium after cost, minus payoff at expiry
    assert t.reason == "expired" and t.close_date == "2021-03-31"
    assert t.pnl_pct == pytest.approx(expected, rel=1e-12)


def test_take_profit_and_manage_dte_trigger():
    d = _days("2021-01-04", "2021-04-30")
    n = len(d)
    vix = np.full(n, 25.0)
    vix[5:] = 1.0  # vol collapses after the first week: put value falls below 50%
    res = run_short_puts(d, np.full(n, 4000.0), vix, np.zeros(n), Rules())
    assert res.trades[0].reason == "take profit"
    assert res.trades[0].close_date == str(d[5])
    flat = run_short_puts(d, np.full(n, 4000.0), np.full(n, 20.0), np.zeros(n),
                          Rules(take_profit=None, manage_dte=21))  # fmt: skip
    first = flat.trades[0]
    held = (np.datetime64(first.close_date) - np.datetime64(first.open_date)).astype(int)
    assert first.reason == "managed" and 45 - held <= 21


def test_monthly_atm_mode_equals_validated_put_write():
    d = _days("2015-01-01", "2019-12-31")
    n = len(d)
    rng = np.random.default_rng(3)
    spx = 2000 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, n)))
    vix = 15 + 5 * np.abs(np.sin(np.arange(n) / 40))
    rate = np.full(n, 1.5)
    rules = Rules(delta=None, monthly=True, take_profit=None, manage_dte=None, cost_frac=0.0)
    a = run_short_puts(d, spx, vix, rate, rules)
    b = put_write(d, spx, vix, rate)
    assert np.array_equal(a.dates, b.dates)
    np.testing.assert_allclose(a.equity, b.equity, rtol=1e-12)


def test_leverage_can_wipe_out_and_summary_says_so():
    d = _days("2020-01-02", "2020-06-30")
    n = len(d)
    spx = np.full(n, 3000.0)
    spx[20:] = 1200.0  # a 60% crash
    res = run_short_puts(d, spx, np.full(n, 20.0), np.zeros(n), Rules(leverage=3.0, delta=0.5))
    assert res.equity[-1] == 0.0
    s = summarize(res, d, spx)
    assert s["wiped_out"] and s["strategy"]["cagr"] is None


def test_summary_shape():
    d = _days("2019-06-01", "2021-06-01")
    n = len(d)
    rng = np.random.default_rng(1)
    spx = 3000 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    res = run_short_puts(d, spx, np.full(n, 20.0), np.full(n, 1.0))
    s = summarize(res, d, spx)
    assert [x["name"] for x in s["stress"]] == ["Mar 2020 Covid crash"]
    assert len(s["chart"]["dates"]) == len(s["chart"]["strategy"]) == len(s["chart"]["spx"])
    assert 0 <= s["trades"]["win_rate"] <= 1 and s["trades"]["count"] == len(res.trades)


def test_backtest_report_checks_file_kinds():
    spx = "DATE,SPX\n01/03/2000,1455\n"
    with pytest.raises(data.DataFormatError, match="expected the VIX file"):
        backtest_report(spx, spx, spx)


@pytest.mark.skipif(not os.environ.get("OCCHECK_LIVE"), reason="network test")
def test_monthly_atm_engine_tracks_real_put_index(tmp_path):
    load = lambda k: data.load_csv(data.download(k, tmp_path).read_text())  # noqa: E731
    spx, vix, tb, put = (load(k) for k in ("SPX", "VIX", "DTB3", "PUT"))
    d, (s, v, r) = data.align(spx, vix, tb)
    m = d >= np.datetime64("2007-06-01")
    rules = Rules(delta=None, monthly=True, take_profit=None, manage_dte=None, cost_frac=0.0)
    res = run_short_puts(d[m], s[m], v[m], r[m], rules)
    c = compare_to_index(put_write(d[m], s[m], v[m], r[m]), put.dates, put.values)
    c2 = compare_to_index(type("R", (), {"dates": res.dates, "equity": res.equity})(), put.dates,
                          put.values)  # fmt: skip
    assert c2["monthly_corr"] == pytest.approx(c["monthly_corr"]) and c2["monthly_corr"] >= 0.9
