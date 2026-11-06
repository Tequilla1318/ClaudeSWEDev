"""Turn results.json into the CSV files the results dashboard reads.

python -m mergerarb.backtest.export results.json outdir/
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from mergerarb.backtest.costs import BORROW_FEE, CASH_SPREAD, IbkrFixed


def _kind(key: str) -> tuple[str, str, str, str]:
    """(strategy, account, bracket, tax_basis) for a scenario key."""
    parts = key.split("_")
    strategy = {"arb": "Merger arb", "spy": "S&P 500", "xic": "TSX", "fund": "Arb fund",
                "mom": "Momentum"}[parts[0]]
    if key == "fund_umd":
        strategy = "Momentum factor"
    account = "TFSA" if "tfsa" in parts or parts[0] == "fund" else "Non-registered"
    if parts[0] == "fund":
        account = "Before tax"
    bracket = next((p for p in parts if p in ("60k", "100k", "250k")), "")
    basis = "business income" if "biz" in parts else ("capital gains" if "nonreg" in parts else "")
    if "pretax" in parts:
        account = "Before tax"
    return strategy, account, bracket, basis


def write(results: dict, out: Path) -> list[Path]:
    """Write summary, growth, years, universe and assumptions CSVs; return their paths."""
    out.mkdir(parents=True, exist_ok=True)
    sc = results["scenarios"]
    paths = []

    def dump(name: str, header: list[str], rows: list[list]) -> None:
        p = out / name
        with p.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(header)
            w.writerows(rows)
        paths.append(p)

    rows = []
    for k, v in sc.items():
        strategy, account, bracket, basis = _kind(k)
        after = v.get("final_after_sale", v["final"])
        rows.append(
            [
                k,
                v["label"],
                strategy,
                account,
                bracket,
                basis,
                round(v["final"], 2),
                round(after, 2),
                round(v["cagr"], 6),
                round(v["vol"], 6),
                round(v["max_drawdown"], 6),
                v.get("trades", ""),
                v.get("breaks", ""),
                round(v["win_rate"], 4) if "win_rate" in v else "",
                v.get("median_hold_days", ""),
                round(v["avg_invested"], 4) if "avg_invested" in v else "",
                round(v["avg_positions"], 2) if "avg_positions" in v else "",
                round(
                    v.get("taxes_cad", v.get("sale_tax_cad", 0) + v.get("dividend_tax_cad", 0)), 2
                ),
                "variant" if any(s in k for s in ("hedged", "size", "pretax_all")) else "main",
            ]
        )
    dump(
        "summary.csv",
        [
            "key",
            "label",
            "strategy",
            "account",
            "bracket",
            "tax_basis",
            "final_cad",
            "final_after_sale_cad",
            "cagr",
            "volatility",
            "max_drawdown",
            "deals",
            "breaks",
            "win_rate",
            "median_hold_days",
            "avg_invested",
            "avg_positions",
            "taxes_cad",
            "role",
        ],
        rows,
    )

    dump(
        "growth.csv",
        ["key", "month", "value_cad"],
        [[k, d, val] for k, v in sc.items() for d, val in v["monthly"]],
    )
    dump(
        "years.csv",
        ["key", "year", "return"],
        [[k, y, round(r, 6)] for k, v in sc.items() for y, r in v["years"].items()],
    )

    u = results["universe"]
    urows = [
        ["Deal filings grouped into deals", u["groups"]],
        ["Deals the book could trade", u["usable"]],
    ]
    urows += [
        ["Closed as agreed (of tradable)", u["outcomes"].get("closed", 0)],
        ["Broke (of tradable)", u["outcomes"].get("broke", 0)],
        ["Still open at the end (of tradable)", u["outcomes"].get("open", 0)],
        ["Stock-for-stock deals (of tradable)", u["stock_deals"]],
    ]
    urows += [[f"Dropped: {reason}", n] for reason, n in u["dropped"].items()]
    dump("universe.csv", ["item", "count"], urows)

    ib = IbkrFixed()
    b = results["brackets"]
    arows = [
        ["Starting capital (CAD)", results["capital_cad"], "Assumption"],
        ["Window start", results["window"][0], "Assumption"],
        ["Window end", results["window"][1], "Assumption"],
        ["Position size (share of book per deal)", 0.05, "Assumption"],
        ["Smallest spread to enter", 0.0, "Assumption"],
        ["Largest spread to enter", 0.40, "Assumption"],
        ["Lowest share price to enter (USD)", 1.0, "Assumption"],
        ["IBKR commission per share (USD)", ib.per_share, "IBKR Fixed pricing"],
        ["IBKR minimum per order (USD)", ib.minimum, "IBKR Fixed pricing"],
        ["IBKR maximum per order (share of trade value)", ib.max_fraction, "IBKR Fixed pricing"],
        ["SEC fee on sales (share of value)", ib.sec_fee_rate, "IBKR fee schedule"],
        ["Slippage per trade (share of value)", ib.slippage, "Assumption"],
        ["Borrow fee on shorted acquirer shares (per year)", BORROW_FEE, "Assumption"],
        ["Cash interest: T-bill minus", CASH_SPREAD, "IBKR interest policy"],
    ]
    for br in b.values():
        arows += [
            [f"Ordinary income rate, {br['name']}", br["ordinary"], "Richter 2026 Ontario tables"],
            [
                f"Capital gains rate, {br['name']}",
                br["capital_gains"],
                "Richter 2026 Ontario tables",
            ],
            [
                f"Eligible dividend rate, {br['name']}",
                br["eligible_dividends"],
                "Richter 2026 Ontario tables",
            ],
        ]
    dump("assumptions.csv", ["item", "value", "source"], arows)

    mo = results.get("momentum")
    if mo:
        pre = sc.get("mom_pretax", {})
        mrows = [
            ["Index members with usable prices, on average", round(pre.get("coverage_avg", 0), 4)],
            ["Index members with usable prices, lowest month", round(pre.get("coverage_min", 0), 4)],
            ["Traded each month, as a share of equity", round(pre.get("turnover", 0), 4)],
            ["Correlation with the Fama-French momentum factor", round(mo.get("correlation_with_ff", 0), 4)],
            ["Months compared with the Fama-French factor", mo.get("months_compared", 0)],
        ]
        dump("momentum_stats.csv", ["item", "value"], mrows)
        arows += [
            ["Momentum: share of index bought and shorted (each side)", 0.10, "Assumption"],
            ["Momentum: each side as a multiple of equity", 1.0, "Assumption"],
        ]
        # assumptions were already written; rewrite with the momentum rows added
        dump("assumptions.csv", ["item", "value", "source"], arows)

    wrows = []
    for k in ("arb_nonreg_cg_100k",):
        for t in sc.get(k, {}).get("worst_trades", []):
            wrows.append([t["name"], t["entry"], round(t["ret"], 6)])
    dump("worst_deals.csv", ["deal", "entry", "return"], wrows)
    return paths


if __name__ == "__main__":
    import json

    for p in write(json.loads(Path(sys.argv[1]).read_text()), Path(sys.argv[2])):
        print(p)
