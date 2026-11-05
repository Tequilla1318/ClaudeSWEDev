import math
import random

import pytest

from mergerarb import (
    Deal,
    analyze,
    annualize,
    delay_table,
    expected_return,
    implied_probability,
    position_size,
)


def video_deal(**kw) -> Deal:
    """The video's example: $15 cash offer, target at $14, falls to $10 on a break."""
    base = {"target_price": 14.0, "fallback_price": 10.0, "days_to_close": 180, "cash": 15.0}
    base.update(kw)
    return Deal(**base)


def test_video_example_implied_probability_is_80_percent():
    # Analytic: p*15 + (1-p)*10 = 14  ->  p = 4/5
    a = analyze(video_deal())
    assert a.gross_spread == pytest.approx(1.0)
    assert a.implied_probability == pytest.approx(0.8)
    assert a.breakeven_probability == pytest.approx(0.8)  # no costs
    assert a.loss_if_break == pytest.approx(-4.0)


def test_implied_probability_reprices_the_target():
    # Plugging p back in must reproduce the market price exactly.
    for _ in range(200):
        f = random.uniform(1, 50)
        o = f + random.uniform(0.5, 30)
        p_true = random.uniform(0.01, 0.99)
        price = p_true * o + (1 - p_true) * f
        assert implied_probability(price, o, f) == pytest.approx(p_true)


def test_costs_raise_breakeven_probability():
    a = analyze(video_deal(trading_costs=0.10))
    assert a.net_spread == pytest.approx(0.90)
    # p*14.90 + (1-p)*10 = 14  ->  p = 4/4.9
    assert a.breakeven_probability == pytest.approx(4 / 4.9)
    assert a.breakeven_probability > a.implied_probability


def test_annualize_compounds():
    assert annualize(0.10, 365) == pytest.approx(0.10)
    assert annualize(0.05, 182.5) == pytest.approx(1.05**2 - 1)
    assert annualize(-1.0, 30) == -1.0
    with pytest.raises(ValueError):
        annualize(-1.5, 30)


def test_video_example_returns():
    a = analyze(video_deal())
    assert a.net_return == pytest.approx(1 / 14)
    assert a.annualized_net_return == pytest.approx((15 / 14) ** (365 / 180) - 1)


def test_stock_deal_payoff_is_independent_of_acquirer_price():
    """Market-neutral check: long 1 target, short `ratio` acquirer shares.

    At close the target converts to cash + ratio*A_close, and buying back the
    short costs ratio*(A_close - A0). P&L = cash + ratio*A0 - T for every A_close.
    """
    d = Deal(
        target_price=48.0,
        fallback_price=38.0,
        days_to_close=120,
        cash=10.0,
        ratio=0.5,
        acquirer_price=80.0,
    )
    a = analyze(d)
    assert a.deal_value == pytest.approx(50.0)
    for a_close in [20.0, 60.0, 80.0, 140.0, 300.0]:
        long_pnl = d.cash + d.ratio * a_close - d.target_price
        short_pnl = -d.ratio * (a_close - d.acquirer_price)
        assert long_pnl + short_pnl == pytest.approx(a.gross_spread)


def test_stock_deal_carry_components():
    d = Deal(
        target_price=48.0,
        fallback_price=38.0,
        days_to_close=365,
        ratio=0.6,
        acquirer_price=80.0,
        target_dividends=0.50,
        acquirer_dividends=1.00,
        borrow_fee_rate=0.02,
        trading_costs=0.05,
    )
    a = analyze(d)
    # borrow: 2% * 0.6 * 80 * 1 year = 0.96
    assert a.borrow_cost == pytest.approx(0.96)
    # carry: +0.50 - 0.6*1.00 - 0.96 - 0.05
    assert a.carry == pytest.approx(0.50 - 0.60 - 0.96 - 0.05)
    assert a.hedge_shares_per_target == pytest.approx(0.6)


def test_expected_return_matches_hand_calc():
    d = video_deal()
    # 0.9 * 1 + 0.1 * (-4) = 0.5 per share
    assert expected_return(d, 0.9) == pytest.approx(0.5 / 14)
    # At the implied probability the expected return is zero.
    assert expected_return(d, 0.8) == pytest.approx(0.0, abs=1e-12)


def test_delay_lowers_annualized_return():
    rows = delay_table(video_deal(), (0, 90, 180))
    ann = [r["annualized"] for r in rows]
    assert ann[0] > ann[1] > ann[2]
    assert rows[1]["days"] == 270


def test_delay_increases_borrow_cost():
    d = Deal(
        target_price=48.0,
        fallback_price=38.0,
        days_to_close=100,
        ratio=0.625,
        acquirer_price=80.0,
        borrow_fee_rate=0.05,
    )
    rows = delay_table(d, (0, 365))
    assert rows[1]["net_return"] < rows[0]["net_return"]


def test_position_size():
    p = position_size(video_deal(), account_size=100_000, max_loss_fraction=0.02)
    # $2,000 budget / $4 per share loss = 500 shares
    assert p["target_shares"] == 500
    assert p["capital"] == pytest.approx(7_000)
    assert p["loss_if_break"] == pytest.approx(2_000)


def test_notes_flag_negative_spread_and_stock_deal():
    a = analyze(video_deal(target_price=15.5, fallback_price=10.0))
    assert a.gross_spread < 0
    assert any("Negative spread" in n for n in a.notes)
    s = analyze(
        Deal(target_price=40, fallback_price=30, days_to_close=90, ratio=0.5, acquirer_price=85)
    )
    assert any("Stock deal" in n for n in s.notes)


@pytest.mark.parametrize(
    "kw",
    [
        {"target_price": 0},
        {"days_to_close": 0},
        {"cash": 0},
        {"cash": 0, "ratio": 0.5, "acquirer_price": 0},
    ],
)
def test_invalid_inputs(kw):
    with pytest.raises(ValueError):
        video_deal(**kw)


def test_nan_free_for_normal_inputs():
    a = analyze(video_deal())
    assert not any(math.isnan(x) for x in (a.implied_probability, a.breakeven_probability))
