"""PGR/PLR against Odean's worked example; realized vol against a closed form."""

import math
from datetime import date, datetime

import pytest

from occheck.prices import pgr_plr, realized_vol
from occheck.trades import Trade


def _t(tid, sym, day, qty, price):
    return Trade(tid, datetime(2025, 1, day, 10), sym, sym, "STK", qty, price, 1.0, 0.0)


def test_odeans_worked_example():
    # Odean (1998): an investor holds five stocks, A-E. A and B are up, C, D and E are down.
    # Selling B and C gives 1 realized gain, 1 paper gain (A), 1 realized loss, 2 paper losses
    # (D, E): PGR = 1/2, PLR = 1/3.
    buys = [_t(str(i), s, 2, 100, 10.0) for i, s in enumerate("ABCDE")]
    sells = [_t("sB", "B", 10, -100, 12.0), _t("sC", "C", 10, -100, 8.0)]
    closes = {"A": 11.0, "D": 9.0, "E": 7.0}
    prices = {s: {date(2025, 1, 10): c} for s, c in closes.items()}
    out = pgr_plr(buys + sells, prices)
    assert (out["realized_gains"], out["paper_gains"]) == (1, 1)
    assert (out["realized_losses"], out["paper_losses"]) == (1, 2)
    assert out["pgr"] == pytest.approx(0.5) and out["plr"] == pytest.approx(1 / 3)
    assert out["ratio"] == pytest.approx(1.5)


def test_uses_latest_close_and_skips_missing():
    buys = [_t("1", "A", 2, 10, 10.0), _t("2", "B", 2, 10, 10.0), _t("3", "C", 2, 10, 10.0)]
    sells = [_t("s", "A", 10, -10, 11.0)]
    prices = {"B": {date(2025, 1, 8): 12.0}}  # no close on the 10th: use the 8th; C has none
    out = pgr_plr(buys + sells, prices)
    assert out["paper_gains"] == 1 and out["skipped_no_price"] == 1


def test_average_cost_and_no_sales():
    trades = [_t("1", "A", 2, 10, 10.0), _t("2", "A", 3, 10, 14.0), _t("3", "A", 9, -5, 11.0)]
    out = pgr_plr(trades, {})
    assert out["realized_losses"] == 1  # 11 is below the 12.00 average cost
    assert pgr_plr(trades[:2], {})["ratio"] is None


def test_realized_vol_closed_form():
    # Alternating +1% / -1% log returns: sample std = 0.01 * sqrt(n / (n - 1)).
    closes = [100.0]
    for i in range(21):
        closes.append(closes[-1] * math.exp(0.01 if i % 2 == 0 else -0.01))
    n = 21
    mean = (0.01 * 11 - 0.01 * 10) / n
    var = (11 * (0.01 - mean) ** 2 + 10 * (-0.01 - mean) ** 2) / (n - 1)
    assert realized_vol(closes) == pytest.approx(math.sqrt(var * 252))
    assert realized_vol(closes[:5]) is None
