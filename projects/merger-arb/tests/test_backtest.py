"""Backtest tests: hand-checkable cases for costs, the deal book, tax and benchmarks."""

from datetime import date

import pytest

from mergerarb.backtest.bench import buy_and_hold
from mergerarb.backtest.costs import BRACKETS, Bracket, IbkrFixed, fx_cost
from mergerarb.backtest.history import deal_outcome, pick_prices, price_statements
from mergerarb.backtest.sim import Config, Series, SimDeal, simulate, to_sim_deals

D0, D1, END = date(2020, 1, 2), date(2020, 3, 2), date(2020, 12, 30)
FLAT_FX = Series([(date(2000, 1, 1), 1.25)])
ZERO = Series([(date(2000, 1, 1), 0.0)])
NO_FRICTION = IbkrFixed(per_share=0, minimum=0, sec_fee_rate=0, finra_taf_per_share=0, slippage=0)
TEST_BRACKET = Bracket("test", ordinary=0.40, capital_gains=0.20, eligible_dividends=0.10)


def cash_deal(outcome="closed", exit_price=None, t0=19.0, cash=20.0):
    return SimDeal("Target", D0, D1, outcome, t0, cash, 0.0, 0.0, 0.0, exit_price)


# --- costs -----------------------------------------------------------------


def test_ibkr_fixed_commission():
    ib = IbkrFixed()
    assert ib.commission(100, 50) == 1.00  # 0.50 per-share charge, $1 minimum
    assert ib.commission(1_000, 50) == 5.00  # 0.005 * 1000
    assert ib.commission(10_000, 0.20) == pytest.approx(20.0)  # capped at 1% of $2,000
    assert fx_cost(10_000) == 2.0 and fx_cost(1_000_000) == pytest.approx(20.0)


def test_sell_cost_adds_regulatory_fees():
    ib = IbkrFixed(slippage=0)
    # 1,000 shares at $50: $5 commission + SEC 0.0000206*50,000 + TAF 0.000166*1,000
    assert ib.sell_cost(1_000, 50) == pytest.approx(5 + 1.03 + 0.166)


# --- deal book ---------------------------------------------------------------


def run(deals, **kw):
    cfg = Config(start=D0, end=END, ibkr=NO_FRICTION, **kw)
    return simulate(deals, FLAT_FX, ZERO, cfg)


def test_single_cash_deal_tfsa_matches_hand_calc():
    # CAD 100,000 -> USD 80,000 less $2 FX fee. 5% of 79,998 = 3,999.90 -> 210 shares at $19.
    res = run([cash_deal()], account="tfsa")
    (t,) = res.trades
    assert t.usd_pnl == pytest.approx(210 * 1.0)
    usd_end = 79_998 + 210
    assert res.final_cad == pytest.approx((usd_end - fx_cost(usd_end)) * 1.25)


def test_broken_cash_deal_loses_to_break_price():
    res = run([cash_deal("broke", exit_price=12.0)], account="tfsa")
    assert res.trades[0].usd_pnl == pytest.approx(210 * (12.0 - 19.0))


def test_stock_deal_hedge_locks_spread_when_it_closes():
    # Target $45, offer 0.5 acquirer shares at $100 = $50. Acquirer falls to $60 by close.
    d = SimDeal("T", D0, D1, "closed", 45.0, 0.0, 0.5, 100.0, 60.0, None)
    res = run([d], account="tfsa", allow_stock_deals=True)
    shares = int(0.05 * 79_998 // 45.0)
    short = round(0.5 * shares)
    borrow = 0.005 * short * 100.0 * (D1 - D0).days / 365
    # Short proceeds come back; long converts to shares that cover the short.
    assert res.trades[0].usd_pnl == pytest.approx(short * 100.0 - shares * 45.0 - borrow)


def test_tfsa_skips_stock_deals_by_default():
    d = SimDeal("T", D0, D1, "closed", 45.0, 0.0, 0.5, 100.0, 60.0, None)
    assert run([d], account="tfsa").trades == []


def test_capital_gains_tax_on_one_deal():
    res = run([cash_deal()], account="nonreg", bracket=TEST_BRACKET)
    gain_cad = 210 * 1.0 * 1.25
    assert res.years[2020]["gains_cad"] == pytest.approx(gain_cad)
    # Flat FX: the only currency effect is the $2 opening conversion fee, which sits in the
    # USD cost basis and is realized as a CAD 2.50 loss when the USD is converted back.
    assert res.taxes_cad == pytest.approx(0.20 * (gain_cad - 2.0 * 1.25), abs=0.01)


def test_business_income_taxes_at_ordinary_rate_and_refunds_losses():
    win = run([cash_deal()], account="nonreg", bracket=TEST_BRACKET, regime="business")
    assert win.taxes_cad == pytest.approx(0.40 * (210 * 1.25 - 2.5), abs=0.01)
    loss = run(
        [cash_deal("broke", exit_price=12.0)],
        account="nonreg",
        bracket=TEST_BRACKET,
        regime="business",
    )
    assert loss.taxes_cad == pytest.approx(0.40 * (210 * (12 - 19) * 1.25 - 2.5), abs=0.01)


def test_capital_losses_carry_forward():
    first = SimDeal("A", date(2020, 1, 2), date(2020, 3, 1), "broke", 19.0, 20.0, 0, 0, 0, 12.0)
    second = SimDeal("B", date(2021, 1, 4), date(2021, 3, 1), "closed", 19.0, 20.0, 0, 0, 0, None)
    cfg = Config(
        start=D0, end=date(2021, 12, 30), ibkr=NO_FRICTION, account="nonreg", bracket=TEST_BRACKET
    )
    res = simulate([first, second], FLAT_FX, ZERO, cfg)
    assert res.years[2020]["tax_cad"] == pytest.approx(0, abs=0.5)
    assert res.years[2021]["tax_cad"] == pytest.approx(0, abs=0.5)  # loss absorbs the gain


def test_fx_gain_on_usd_cash_is_taxed():
    fx = Series([(date(2000, 1, 1), 1.0), (date(2020, 6, 1), 1.5)])
    cfg = Config(start=D0, end=END, ibkr=NO_FRICTION, account="nonreg", bracket=TEST_BRACKET)
    res = simulate([], fx, ZERO, cfg)
    usd = 100_000 - fx_cost(100_000)
    assert res.years[2020]["fx_cad"] == pytest.approx(usd * 0.5, rel=1e-3)


def test_interest_over_free_tier():
    tb = Series([(date(2000, 1, 1), 0.055)])  # 5.5% benchmark -> 5% paid
    cfg = Config(start=D0, end=date(2020, 1, 31), ibkr=NO_FRICTION, account="tfsa")
    res = simulate([], FLAT_FX, tb, cfg)
    usd = 80_000 - 2
    expected_usd = (usd - 10_000) * 0.05 / 365 * 30
    assert res.interest_cad == pytest.approx(expected_usd * 1.25, rel=0.01)


def test_to_sim_deals_filters():
    base = {
        "skip": None,
        "target": "X",
        "filed": "2020-01-02",
        "outcome": "closed",
        "outcome_date": "2020-03-01",
        "entry_price": 19.0,
        "cash": 20.0,
        "ratio": 0.0,
        "exit_price_break": None,
    }
    rows = [
        base,
        {**base, "entry_price": 21.0},
        {**base, "entry_price": 10.0},
        {**base, "entry_price": 0.5, "cash": 0.6},
        {**base, "skip": "no terms found"},
    ]
    deals, dropped = to_sim_deals(rows, END)
    assert len(deals) == 1
    assert dropped == {"spread outside 0-40%": 2, "price under $1": 1, "no terms found": 1}


# --- benchmarks --------------------------------------------------------------


def test_buy_and_hold_no_dividends_flat_fx():
    prices = Series([(D0, 100.0), (END, 150.0)])
    tfsa = buy_and_hold(prices, [], FLAT_FX, D0, END, account="tfsa", ibkr=NO_FRICTION)
    usd = 80_000 - 2.0
    shares = int(usd // 100.0)
    cash = usd - shares * 100
    total = shares * 150 + cash
    assert tfsa.final_cad == pytest.approx((total - fx_cost(total)) * 1.25)
    nr = buy_and_hold(
        prices, [], FLAT_FX, D0, END, account="nonreg", bracket=TEST_BRACKET, ibkr=NO_FRICTION
    )
    gain = shares * 50 * 1.25
    assert nr.sale_tax_cad == pytest.approx(0.20 * gain)


def test_us_dividend_withholding_and_tax():
    prices = Series([(D0, 100.0)])
    divs = [(date(2020, 6, 15), 1.0)]
    tfsa = buy_and_hold(prices, divs, FLAT_FX, D0, END, account="tfsa", ibkr=NO_FRICTION)
    nr = buy_and_hold(
        prices, divs, FLAT_FX, D0, END, account="nonreg", bracket=TEST_BRACKET, ibkr=NO_FRICTION
    )
    shares = int((80_000 - 2.0) // 100.0)
    assert tfsa.dividend_tax_cad == 0
    # Non-registered: total tax on the dividend is the 40% ordinary rate (15% credited).
    assert nr.dividend_tax_cad == pytest.approx(0.40 * shares * 1.0 * 1.25)


def test_brackets_are_half_inclusion():
    for b in BRACKETS.values():
        assert b.capital_gains == pytest.approx(b.ordinary / 2, abs=0.0002)


# --- history parsing ---------------------------------------------------------

PROXY = (
    "The closing sale price of the Company's Common Stock on the NASDAQ on January 28, 2013, "
    "the last trading day prior to the public announcement of the proposed Merger, was $9.05 "
    "per share. On March 13, 2013, the most recent practicable date before this proxy statement "
    "was printed, the closing price for the Company's Common Stock on the NASDAQ was $9.14 per "
    "share."
)


def test_price_statements_entry_and_unaffected():
    st = price_statements(PROXY, "Pervasive Software Inc")
    entry, unaff = pick_prices(st, date(2013, 3, 22), 9.20)
    assert (entry.day, entry.price) == (date(2013, 3, 13), 9.14)
    assert unaff.price == 9.05


def test_unlabelled_price_is_not_an_entry():
    text = "On February 20, 2013, the closing price of the Company's common stock was $17.26."
    entry, _ = pick_prices(price_statements(text, "WMS"), date(2013, 2, 22), 26.0)
    assert entry is None


def test_outcome_closing_8k_with_credit_termination_is_not_a_break():
    forms = ["8-K", "25-NSE"]
    dates = [date(2020, 3, 1), date(2020, 3, 2)]
    items = ["1.02,2.01,3.01,5.01", ""]
    oc = deal_outcome(forms, dates, items, date(2020, 1, 1))
    assert (oc.status, oc.day) == ("closed", date(2020, 3, 1))


def test_outcome_break_and_open():
    oc = deal_outcome(["8-K"], [date(2020, 5, 1)], ["1.02,9.01"], date(2020, 1, 1))
    assert (oc.status, oc.day) == ("broke", date(2020, 5, 1))
    oc = deal_outcome(["10-Q"], [date(2020, 5, 1)], [""], date(2020, 1, 1))
    assert oc.status == "open"


def test_late_termination_is_not_this_deals_break():
    oc = deal_outcome(["8-K"], [date(2022, 1, 1)], ["1.02"], date(2020, 1, 1))
    assert oc.status == "open"
