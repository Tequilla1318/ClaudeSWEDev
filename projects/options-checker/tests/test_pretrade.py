"""Pre-trade checker: known quotes in, hand-checked numbers out."""

import math
from datetime import date

import pytest

from occheck.pretrade import check_from_form, check_trade
from occheck.pricing import bs_price

TODAY = date(2026, 1, 5)
EXP = date(2026, 2, 4)  # 30 days


def _by_id(out):
    return {i["id"]: i for i in out["items"]}


def test_implied_vol_recovers_a_model_quote():
    # Quote a 30-day ATM call at exactly its Black-Scholes value at 25% vol.
    px = bs_price(100, 100, 30 / 365, 0.04, 0.25, "C")
    out = check_trade(100, 100, EXP, TODAY, "C", "buy", px - 0.05, px + 0.05)
    assert out["summary"]["implied_vol"] == pytest.approx(0.25, abs=1e-6)
    assert out["summary"]["fill"] == pytest.approx(px + 0.05)
    exp_move = 0.25 * math.sqrt(30 / 365)
    assert f"±{exp_move:.1%}" in _by_id(out)["breakeven"]["display"]


def test_spread_cost_and_breakeven():
    out = check_trade(50, 55, EXP, TODAY, "C", "buy", 0.80, 1.00, contracts=2)
    items = _by_id(out)
    assert items["spread"]["status"] == "flag"  # 0.20 / 0.90 = 22% of mid
    assert "$20.00 now" in items["spread"]["display"]  # half of 0.20 x 100 x 2
    assert "$40.00 for a round trip" in items["spread"]["display"]
    assert "56.00" in items["breakeven"]["display"]  # 55 + 1.00 paid
    assert out["summary"]["premium_total"] == pytest.approx(200.0)


def test_seller_side_put():
    out = check_trade(100, 95, EXP, TODAY, "P", "sell", 1.48, 1.52)
    s = out["summary"]
    assert s["fill"] == 1.48 and "if the stock goes to zero" in s["max_loss"]
    assert "93.52" in _by_id(out)["breakeven"]["display"]
    assert _by_id(out)["spread"]["status"] == "ok"  # 0.04 / 1.50 = 2.7%, under 3%
    assert "lottery" not in _by_id(out)


def test_event_inside_expiry_flags_buyer():
    out = check_trade(100, 100, EXP, TODAY, "C", "buy", 2.9, 3.0, event_date=date(2026, 1, 20))
    assert _by_id(out)["event"]["status"] == "flag"
    out = check_trade(100, 100, EXP, TODAY, "C", "buy", 2.9, 3.0, event_date=date(2026, 3, 1))
    assert _by_id(out)["event"]["status"] == "ok"


def test_lottery_and_iv_vs_realized():
    out = check_trade(
        100, 110, date(2026, 1, 8), TODAY, "C", "buy", 0.05, 0.10, realized_vol_pct=20
    )
    items = _by_id(out)
    assert items["lottery"]["status"] == "flag"
    assert "x recent movement" in items["iv_rv"]["display"]


def test_market_implied_odds_sum():
    out = check_trade(100, 100, EXP, TODAY, "P", "sell", 2.8, 2.9)
    text = _by_id(out)["odds"]["display"]
    assert "chance of finishing in the money" in text and "selling at this price" in text


def test_profit_probability_uses_breakeven():
    # Buyer and seller profit probabilities at the same fill sum to 100%.
    buy = check_trade(100, 105, EXP, TODAY, "C", "buy", 1.20, 1.20)
    sell = check_trade(100, 105, EXP, TODAY, "C", "sell", 1.20, 1.20)
    pb = int(_by_id(buy)["odds"]["display"].split("profit about ")[1].split("%")[0])
    ps = int(_by_id(sell)["odds"]["display"].split("profit about ")[1].split("%")[0])
    assert pb + ps in (99, 100, 101)  # rounding
    itm = int(_by_id(buy)["odds"]["display"].split("About ")[1].split("%")[0])
    assert pb < itm  # beyond the break-even is less likely than past the strike


def test_bad_inputs():
    with pytest.raises(ValueError):
        check_trade(100, 100, EXP, TODAY, "C", "buy", 2.0, 1.0)
    with pytest.raises(ValueError):
        check_trade(100, 100, date(2025, 1, 1), TODAY, "C", "buy", 1.0, 1.1)


def test_form_entry_point_and_no_advice_wording():
    out = check_from_form({
        "spot": "100", "strike": "100", "expiry": "2026-02-04", "today": "2026-01-05",
        "right": "C", "side": "buy", "bid": "2.9", "ask": "3.0", "contracts": "",
        "rate": "", "event": "", "rv": "",
    })  # fmt: skip
    assert out["summary"]["days"] == 30
    text = " ".join(i["display"] + i["explanation"] for i in out["items"]).lower()
    for phrase in ("you should", "we recommend", "good trade to"):
        assert phrase not in text
