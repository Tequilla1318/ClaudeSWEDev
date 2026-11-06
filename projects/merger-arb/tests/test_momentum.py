"""Momentum book tests on synthetic markets with hand-checkable answers."""

import io
import zipfile
from datetime import date, timedelta

import pytest

from mergerarb.backtest.costs import Bracket, IbkrFixed
from mergerarb.backtest.momentum import (
    MomConfig,
    PriceBook,
    members_on,
    momentum_scores,
    month_ends,
    parse_members,
    parse_umd,
    pick_legs,
    simulate_momentum,
)
from mergerarb.backtest.sim import Series

FREE = IbkrFixed(per_share=0, minimum=0, sec_fee_rate=0, finra_taf_per_share=0, slippage=0)
FLAT = Series([(date(2000, 1, 1), 1.25)])
B = Bracket("test", 0.40, 0.20, 0.10)


def market(monthly: dict[str, float], start: date, end: date) -> PriceBook:
    """Daily prices compounding at a fixed monthly rate per ticker."""
    out = {}
    for t, g in monthly.items():
        s, d, p = [], start, 100.0
        while d <= end:
            s.append((d, p))
            d += timedelta(days=1)
            p *= (1 + g) ** (1 / 30.4375)
        out[t] = s
    return PriceBook(out)


def test_month_ends_and_members():
    assert month_ends(date(2020, 11, 5), date(2021, 2, 10)) == [
        date(2020, 11, 30),
        date(2020, 12, 31),
        date(2021, 1, 31),
        date(2021, 2, 10),
    ]
    rows = parse_members('date,tickers\n2020-01-02,"A,B"\n2020-06-01,"A,C"\n')
    assert members_on(rows, date(2020, 3, 1)) == {"A", "B"}
    assert members_on(rows, date(2020, 7, 1)) == {"A", "C"}


def test_pick_legs_and_scores():
    pb = market(
        {"UP": 0.03, "FLAT": 0.0, "DOWN": -0.03, "MID": 0.01}, date(2018, 1, 1), date(2020, 1, 31)
    )
    sc = momentum_scores(pb, frozenset(pb.days), date(2020, 1, 31))
    assert sc["UP"] > sc["MID"] > sc["FLAT"] > sc["DOWN"]
    assert pick_legs(sc, 0.25) == (["UP"], ["DOWN"])


def test_pretax_book_earns_long_minus_short():
    start, end = date(2019, 1, 1), date(2021, 1, 31)
    pb = market({"UP": 0.02, "A": 0.0, "B": 0.0, "DOWN": -0.02}, date(2017, 1, 1), end)
    members = [(date(2010, 1, 1), frozenset(pb.days))]
    cfg = MomConfig(start=start, end=end, fraction=0.25, account="pretax", ibkr=FREE, borrow_fee=0)
    res = simulate_momentum(members, pb, FLAT, cfg)
    # Each month: the long rises ~2% and the short falls ~2% on equal notionals, scaled to
    # the month's length (prices compound by calendar day).
    prev = None
    for day, r in res.leg_returns:
        if prev:
            k = (day - prev).days / 30.4375
            assert r == pytest.approx((1.02**k - 1) - (0.98**k - 1), abs=1e-3)
        prev = day
    months = len(res.leg_returns)
    assert res.final_cad / 100_000 == pytest.approx(1.04**months, rel=0.03)


def test_nonreg_tax_on_realized_gains():
    start, end = date(2019, 1, 1), date(2019, 12, 31)
    pb = market({"UP": 0.02, "A": 0.0, "B": 0.0, "DOWN": -0.02}, date(2017, 1, 1), end)
    members = [(date(2010, 1, 1), frozenset(pb.days))]
    pre = simulate_momentum(
        members,
        pb,
        FLAT,
        MomConfig(start=start, end=end, fraction=0.25, account="pretax", ibkr=FREE, borrow_fee=0),
    )
    tax = simulate_momentum(
        members,
        pb,
        FLAT,
        MomConfig(
            start=start,
            end=end,
            fraction=0.25,
            account="nonreg",
            bracket=B,
            ibkr=FREE,
            borrow_fee=0,
        ),
    )
    gain = pre.final_cad - 100_000
    # All gains are realized by the final liquidation; with flat FX, tax is 20% of them
    # (less the CAD 2.50 opening-conversion loss).
    assert tax.taxes_cad == pytest.approx(0.20 * (gain - 2.5), rel=0.02)


def test_borrow_fee_and_commissions_cost_money():
    start, end = date(2019, 1, 1), date(2019, 12, 31)
    pb = market({"UP": 0.02, "A": 0.0, "B": 0.0, "DOWN": -0.02}, date(2017, 1, 1), end)
    members = [(date(2010, 1, 1), frozenset(pb.days))]
    free = simulate_momentum(
        members,
        pb,
        FLAT,
        MomConfig(start=start, end=end, fraction=0.25, account="pretax", ibkr=FREE, borrow_fee=0),
    )
    costly = simulate_momentum(
        members, pb, FLAT, MomConfig(start=start, end=end, fraction=0.25, account="pretax")
    )
    assert costly.final_cad < free.final_cad
    assert costly.fees_usd > 0


def test_parse_umd():
    body = (
        "header line\n,Mom\n202601,   1.50\n202602,  -2.00\n\n Annual Factors\n,Mom\n"
        "  2026,  5.00\n"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("F-F_Momentum_Factor.csv", body)
    assert parse_umd(buf.getvalue()) == {(2026, 1): 0.015, (2026, 2): -0.02}
