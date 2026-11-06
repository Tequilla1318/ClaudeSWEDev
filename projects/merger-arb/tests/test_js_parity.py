"""Check that the web calculator's JavaScript math matches the Python core."""

import json
import random
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path

import pytest

from mergerarb import Deal, analyze, delay_table, expected_return, position_size

MATH_JS = Path(__file__).resolve().parents[1] / "web" / "math.js"
FIELDS = (
    "deal_value",
    "gross_spread",
    "carry",
    "borrow_cost",
    "net_spread",
    "gross_return",
    "net_return",
    "annualized_net_return",
    "loss_if_break",
    "implied_probability",
    "breakeven_probability",
)

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def random_deals(n: int = 60) -> list[Deal]:
    rng = random.Random(7)
    deals = []
    for _ in range(n):
        stock = rng.random() < 0.6
        ratio = round(rng.uniform(0.2, 2.0), 4) if stock else 0.0
        cash = round(rng.uniform(0, 30), 2) if (not stock or rng.random() < 0.5) else 0.0
        acq = round(rng.uniform(10, 200), 2) if stock else 0.0
        value = cash + ratio * acq
        target = round(value * rng.uniform(0.85, 1.01), 2)
        deals.append(
            Deal(
                target_price=target,
                fallback_price=round(target * rng.uniform(0.5, 0.95), 2),
                days_to_close=rng.randint(20, 500),
                cash=cash,
                ratio=ratio,
                acquirer_price=acq,
                target_dividends=round(rng.uniform(0, 1), 2),
                acquirer_dividends=round(rng.uniform(0, 1), 2) if stock else 0.0,
                borrow_fee_rate=round(rng.uniform(0, 0.08), 4) if stock else 0.0,
                trading_costs=round(rng.uniform(0, 0.05), 3),
            )
        )
    return deals


def test_js_matches_python():
    deals = random_deals()
    script = f"""
const MA = require({json.dumps(str(MATH_JS))});
const deals = {json.dumps([asdict(d) for d in deals])};
console.log(JSON.stringify(deals.map(d => ({{
  a: MA.analyze(d),
  ev: MA.expectedReturn(d, 0.85),
  delay: MA.delayTable(d),
  size: MA.positionSize(d, 50000, 0.03),
}}))));
"""
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    js = json.loads(out.stdout)
    for d, j in zip(deals, js, strict=True):
        py = analyze(d)
        for f in FIELDS:
            assert j["a"][f] == pytest.approx(getattr(py, f), rel=1e-12, abs=1e-12), f
        assert j["ev"] == pytest.approx(expected_return(d, 0.85), rel=1e-12, abs=1e-12)
        for jr, pr in zip(j["delay"], delay_table(d), strict=True):
            assert jr["annualized"] == pytest.approx(pr["annualized"], rel=1e-12, abs=1e-12)
        assert j["size"] == position_size(d, 50000, 0.03)
