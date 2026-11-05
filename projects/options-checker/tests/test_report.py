"""Bias metrics and report card."""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from occheck import audit
from occheck.brokers.ibkr_flex import ParseResult
from occheck.cli import main
from occheck.report import build_report, render_text, report_from_csv
from occheck.roundtrips import RoundTrip

FIXTURES = Path(__file__).parent / "fixtures"
T0 = datetime(2025, 1, 1)


def _rt(pnl, days, *, opt=False, direction="long", price=1.0, dte=None, sym="X"):
    """Round trip with a given net P&L (zero commission) and holding period."""
    qty = 1.0
    close = price + (pnl if direction == "long" else -pnl) / (qty * (100 if opt else 1))
    return RoundTrip(
        symbol=sym,
        underlying=sym,
        asset_class="OPT" if opt else "STK",
        direction=direction,
        quantity=qty,
        multiplier=100.0 if opt else 1.0,
        open_time=T0,
        close_time=T0 + timedelta(days=days),
        open_price=price,
        close_price=close,
        commission=0.0,
        close_reason="closed",
        expiry=(T0 + timedelta(days=dte)).date() if dte is not None else None,
    )


def test_expectancy_high_win_rate_negative():
    rts = [_rt(10, 1) for _ in range(9)] + [_rt(-200, 1)]
    e = audit.expectancy(rts)
    assert e["win_rate"] == pytest.approx(0.9)
    assert e["expectancy"] == pytest.approx((90 - 200) / 10)
    assert e["wins_to_cover_largest_loss"] == pytest.approx(20.0)


def test_disposition_ratio():
    rts = [_rt(5, d) for d in (1, 2, 3)] + [_rt(-5, d) for d in (4, 6, 8, 10)]
    d = audit.disposition(rts)
    assert d["median_days_winners"] == pytest.approx(2.0)
    assert d["median_days_losers"] == pytest.approx(7.0)
    assert d["ratio"] == pytest.approx(3.5)


def test_lottery_and_zero_dte():
    th = audit.Thresholds()
    rts = [
        _rt(-30, 1, opt=True, price=0.30, dte=3),  # lottery: premium 30
        _rt(-40, 0.2, opt=True, price=0.40, dte=0),  # lottery and 0DTE: premium 40
        _rt(50, 10, opt=True, price=3.00, dte=30),  # not lottery: premium 300
        _rt(20, 5, opt=True, price=0.30, dte=30, direction="short"),  # short: excluded
    ]
    lot = audit.lottery(rts, th)
    assert lot["long_premium_paid"] == pytest.approx(370.0)
    assert lot["lottery_share"] == pytest.approx(70 / 370)
    assert lot["lottery_n"] == 2 and lot["lottery_net_pnl"] == pytest.approx(-70)
    assert lot["zero_dte_share"] == pytest.approx(1 / 4)


def test_buyer_seller_and_concentration():
    rts = [_rt(-50, 1, opt=True), _rt(30, 1, opt=True, direction="short"), _rt(-200, 1, sym="Y")]
    bs = audit.buyer_seller(rts)
    assert bs["buyer"]["net_pnl"] == pytest.approx(-50) and bs["seller"]["n"] == 1
    c = audit.concentration(rts, account_value=10000)
    assert c["symbol"] == "Y" and c["share_of_account"] == pytest.approx(0.02)
    assert c["share_of_losses"] == pytest.approx(200 / 250)


@pytest.fixture
def fixture_report():
    return report_from_csv((FIXTURES / "flex_basic.csv").read_text(), account_value=50000)


def test_report_shape_and_json(fixture_report):
    r = fixture_report
    ids = [m["id"] for m in r["metrics"]]
    assert ids == [
        "costs", "turnover", "expectancy", "disposition",
        "lottery", "zero_dte", "buyer_seller", "concentration",
    ]  # fmt: skip
    for m in r["metrics"]:
        assert m["status"] in {"flag", "watch", "ok", "info", "na"}
        assert m["research"]["url"].startswith("https://")
        assert m["display"] and m["explanation"]
    json.dumps(r, default=str)  # serializable for the web page
    assert r["summary"]["round_trips"] == 5  # wheel view: SPY put folded into the shares
    assert r["summary"]["convention"] == "wheel"
    assert r["summary"]["net_pnl"] == pytest.approx(1442.45)


def test_broker_and_wheel_views_agree_on_totals():
    text = (FIXTURES / "flex_basic.csv").read_text()
    wheel = report_from_csv(text, convention="wheel")
    broker = report_from_csv(text, convention="broker")
    assert broker["summary"]["round_trips"] == 6
    assert wheel["summary"]["net_pnl"] == pytest.approx(broker["summary"]["net_pnl"])
    with pytest.raises(ValueError):
        report_from_csv(text, convention="other")


def test_threshold_overrides_by_name():
    text = (FIXTURES / "flex_basic.csv").read_text()
    r = report_from_csv(text, thresholds={"lottery_max_premium": 0.25})
    lot = next(m for m in r["metrics"] if m["id"] == "lottery")
    assert lot["data"]["lottery_n"] == 0  # the TSLA calls opened at 0.40, above the 0.25 cut
    assert "not financial advice" in r["disclaimer"]


def test_report_fixture_statuses(fixture_report):
    by = {m["id"]: m for m in fixture_report["metrics"]}
    # TSLA lottery calls: premium 120 of 120 long premium -> 100% share.
    assert by["lottery"]["status"] == "flag"
    assert by["lottery"]["data"]["lottery_share"] == pytest.approx(1.0)
    # Only 6 round trips (3 winners, 3 losers) -> not enough for disposition.
    assert by["disposition"]["status"] == "na"
    # SPY stock loss -1001 = 2.0% of 50k account -> under the 5% flag.
    assert by["concentration"]["status"] == "ok"


def test_report_wording_has_no_advice(fixture_report):
    text = render_text(fixture_report).lower()
    for phrase in ("you should", "we recommend", "buy now", "sell now"):
        assert phrase not in text


def test_empty_report():
    r = build_report(ParseResult(trades=[]))
    assert r["summary"]["round_trips"] == 0
    assert {m["status"] for m in r["metrics"]} <= {"na", "info", "ok"}


def test_cli_audit(capsys):
    assert main(["audit", str(FIXTURES / "flex_basic.csv"), "--account-value", "50000"]) == 0
    out = capsys.readouterr().out
    assert "Lottery-ticket options" in out and "not financial advice" in out
    assert main(["audit", str(FIXTURES / "flex_basic.csv"), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["summary"]["trades"] == 11


def test_cli_audit_bad_file(tmp_path, capsys):
    bad = tmp_path / "x.csv"
    bad.write_text("a,b\n1,2\n")
    assert main(["audit", str(bad)]) == 2
    assert "Trades header" in capsys.readouterr().err


def test_thresholds_are_configurable():
    th = audit.Thresholds(lottery_max_premium=0.25)
    rts = [_rt(-30, 1, opt=True, price=0.30, dte=3)]
    assert audit.lottery(rts, th)["lottery_n"] == 0
    assert date(2025, 1, 4) == rts[0].expiry
