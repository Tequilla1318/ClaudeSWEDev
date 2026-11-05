"""Wheel cost-basis view: assigned premiums fold into the stock, totals unchanged."""

from pathlib import Path

import pytest

from occheck.brokers.ibkr_flex import parse_flex_csv
from occheck.roundtrips import match_round_trips, wheel_view

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    trades = parse_flex_csv((FIXTURES / name).read_text()).trades
    return trades, match_round_trips(trades).round_trips


def test_full_wheel_cycle_becomes_one_stock_round_trip():
    trades, broker = _load("flex_wheel.csv")
    # Broker view: put +200, stock +400, call +160 (2 contracts / 200 shares).
    assert sorted(round(r.gross_pnl, 2) for r in broker) == [160.0, 200.0, 400.0]
    wheel = wheel_view(broker, trades)
    assert len(wheel) == 1
    w = wheel[0]
    assert w.open_price == pytest.approx(50 - 1.00)  # strike minus put premium
    assert w.close_price == pytest.approx(52 + 0.80)  # strike plus call premium
    assert w.gross_pnl == pytest.approx(760.0)
    assert w.commission == pytest.approx(2.60)  # both option commissions moved in
    assert w.wheel_premium == pytest.approx(360.0)
    assert str(w.open_time.date()) == "2025-01-02"  # the cycle starts at the put sale


def test_totals_unchanged_on_basic_fixture():
    trades, broker = _load("flex_basic.csv")
    wheel = wheel_view(broker, trades)
    assert len(wheel) == len(broker) - 1  # the SPY put folds into the SPY shares
    assert sum(r.gross_pnl for r in wheel) == pytest.approx(sum(r.gross_pnl for r in broker))
    assert sum(r.commission for r in wheel) == pytest.approx(sum(r.commission for r in broker))
    spy = next(r for r in wheel if r.symbol == "SPY")
    assert spy.open_price == pytest.approx(576.0) and spy.gross_pnl == pytest.approx(-600.0)


def test_open_shares_leave_option_separate():
    trades, broker = _load("flex_wheel.csv")
    trades = [t for t in trades if t.trade_id in {"2001", "2002", "2003"}]  # shares never sold
    rts = match_round_trips(trades).round_trips
    assert wheel_view(rts, trades) == rts
