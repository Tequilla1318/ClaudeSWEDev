"""Round-trip matching and cost metrics against hand-computed answers."""

from datetime import datetime
from pathlib import Path

import pytest

from occheck.audit import cost_summary, turnover
from occheck.brokers.ibkr_flex import parse_flex_csv
from occheck.roundtrips import match_round_trips
from occheck.trades import Trade

FIXTURES = Path(__file__).parent / "fixtures"


def _t(tid, day, qty, price, comm=0.0, sym="X", codes=()):
    return Trade(
        trade_id=tid,
        when=datetime(2025, 1, day),
        symbol=sym,
        underlying=sym,
        asset_class="STK",
        quantity=qty,
        price=price,
        multiplier=1.0,
        commission=comm,
        codes=frozenset(codes),
    )


@pytest.fixture
def basic():
    res = parse_flex_csv((FIXTURES / "flex_basic.csv").read_text())
    return res.trades, match_round_trips(res.trades)


# Hand-computed from tests/fixtures/flex_basic.csv (see PR description):
EXPECTED = {
    # (open id, close id): (direction, qty, gross, commission, reason)
    ("1001", "1012"): ("long", 100, 2000.0, 2.00, "closed"),
    ("1002", "1003"): ("short", 1, 150.0, 0.65, "expired"),
    ("1004", "1005"): ("short", 1, 400.0, 0.65, "assigned"),
    ("1006", "1008"): ("long", 100, -1000.0, 1.00, "closed"),
    ("1009", "1010"): ("long", 2, -60.0, 2.60, "closed"),
    ("1009", "1011"): ("long", 1, -40.0, 0.65, "expired"),
}


def test_fixture_round_trips_exact(basic):
    _, m = basic
    got = {(r.open_trade_id, r.close_trade_id): r for r in m.round_trips}
    assert set(got) == set(EXPECTED)
    for key, (direction, qty, gross, comm, reason) in EXPECTED.items():
        r = got[key]
        assert (r.direction, r.quantity, r.close_reason) == (direction, qty, reason)
        assert r.gross_pnl == pytest.approx(gross)
        assert r.commission == pytest.approx(comm)
    assert m.open_lots == []


def test_fixture_cost_summary(basic):
    trades, m = basic
    s = cost_summary(trades, m.round_trips)
    assert s.round_trips == 6
    assert s.gross_pnl == pytest.approx(1450.0)
    assert s.commission == pytest.approx(7.55)
    assert s.net_pnl == pytest.approx(1442.45)
    assert s.traded_notional == pytest.approx(153690.0)
    assert s.commission_bps_of_notional == pytest.approx(7.55 / 153690 * 1e4)
    assert s.commission_share_of_gross == pytest.approx(7.55 / 1450)
    assert s.commission_share_of_gross_profit == pytest.approx(7.55 / 2550)


def test_holding_days_and_dte(basic):
    _, m = basic
    aapl = next(r for r in m.round_trips if r.open_trade_id == "1001")
    assert aapl.holding_days == pytest.approx(85.0, abs=0.1)
    lotto = next(r for r in m.round_trips if r.close_trade_id == "1010")
    assert lotto.dte_at_open == 2 and lotto.open_premium == pytest.approx(80.0)


def test_partial_fifo_and_open_remainder():
    trades = [_t("a", 1, 100, 10), _t("b", 2, 50, 12), _t("c", 3, -120, 15)]
    m = match_round_trips(trades)
    assert [(r.open_trade_id, r.quantity) for r in m.round_trips] == [("a", 100), ("b", 20)]
    assert sum(r.gross_pnl for r in m.round_trips) == pytest.approx(100 * 5 + 20 * 3)
    (lot, remaining) = m.open_lots[0]
    assert lot.trade_id == "b" and remaining == pytest.approx(30)


def test_position_flip():
    trades = [_t("a", 1, 10, 10), _t("b", 2, -15, 11), _t("c", 3, 5, 9)]
    m = match_round_trips(trades)
    assert [(r.direction, r.quantity) for r in m.round_trips] == [("long", 10), ("short", 5)]
    assert m.round_trips[1].gross_pnl == pytest.approx(5 * (11 - 9))
    assert m.open_lots == []


def test_commission_allocated_per_unit():
    trades = [
        _t("a", 1, 4, 10, comm=4.0),
        _t("b", 2, -1, 11, comm=1.0),
        _t("c", 3, -3, 12, comm=6.0),
    ]
    m = match_round_trips(trades)
    assert [r.commission for r in m.round_trips] == pytest.approx([1 + 1, 3 + 6])


def test_cost_summary_losing_account():
    trades = [_t("a", 1, 1, 10, comm=1), _t("b", 2, -1, 5, comm=1)]
    s = cost_summary(trades, match_round_trips(trades).round_trips)
    assert s.gross_pnl == -5 and s.commission_share_of_gross is None
    assert s.commission_share_of_gross_profit is None


def test_turnover():
    trades = [_t("a", 1, 100, 10), _t("b", 31, -100, 10)]
    out = turnover(trades, account_value=1000.0)
    assert out["span_days"] == pytest.approx(30.0)
    assert out["notional_per_year"] == pytest.approx(2000 * 365 / 30)
    assert out["annual_turnover"] == pytest.approx(2000 * 365 / 30 / 1000)
    assert turnover(trades, None)["annual_turnover"] is None
    assert turnover([], 1000)["notional_per_year"] == 0.0
