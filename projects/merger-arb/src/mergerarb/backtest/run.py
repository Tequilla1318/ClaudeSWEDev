"""Run every backtest scenario and write results.json for the report page.

    SEC_USER_AGENT="Name email" python -m mergerarb.backtest.run \\
        --deals deals_hist.jsonl --out results.json
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import time
import urllib.parse
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

from mergerarb.backtest.bench import buy_and_hold, total_return_series
from mergerarb.backtest.collect import Fetcher
from mergerarb.backtest.costs import BRACKETS
from mergerarb.backtest.sim import Config, Series, simulate, to_sim_deals

FUNDS = {
    "MERFX": "The Merger Fund (MERFX)",
    "ARBFX": "The Arbitrage Fund (ARBFX)",
    "MNA": "IQ Merger Arbitrage ETF (MNA)",
}


def yahoo(f: Fetcher, symbol: str, start: date, end: date) -> dict:
    """Daily closes, adjusted closes and dividends for ``symbol``."""
    p1 = int(datetime(start.year, start.month, start.day, tzinfo=UTC).timestamp()) - 10 * 86400
    p2 = int(datetime(end.year, end.month, end.day, tzinfo=UTC).timestamp()) + 5 * 86400
    sym = urllib.parse.quote(symbol)
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}"
        "&interval=1d&events=div"
    )
    r = json.loads(f.get(url))["chart"]["result"][0]
    days = [datetime.fromtimestamp(t, UTC).date() for t in r["timestamp"]]
    q = r["indicators"]["quote"][0]["close"]
    adj = r["indicators"].get("adjclose", [{}])[0].get("adjclose", q)
    divs = [
        (datetime.fromtimestamp(int(v["date"]), UTC).date(), float(v["amount"]))
        for v in r.get("events", {}).get("dividends", {}).values()
    ]
    return {
        "close": Series([(d, c) for d, c in zip(days, q, strict=False) if c is not None]),
        "adj": Series([(d, c) for d, c in zip(days, adj, strict=False) if c is not None]),
        "divs": sorted(divs),
    }


def stats(nav: list[tuple[date, float]], start_value: float) -> dict:
    """CAGR, volatility, max drawdown and calendar-year returns from a value series."""
    first, last = nav[0][0], nav[-1][0]
    years = (last - first).days / 365.25
    final = nav[-1][1]
    cagr = (final / start_value) ** (1 / years) - 1
    month_end: dict[tuple[int, int], float] = {}
    year_end: dict[int, float] = {}
    for d, v in nav:
        month_end[(d.year, d.month)] = v
        year_end[d.year] = v
    m = [start_value, *month_end.values()]
    rets = [m[i] / m[i - 1] - 1 for i in range(1, len(m))]
    vol = statistics.pstdev(rets) * math.sqrt(12) if len(rets) > 2 else 0.0
    peak, mdd = start_value, 0.0
    for _, v in nav:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    yr, prev = {}, start_value
    for y in sorted(year_end):
        yr[y] = year_end[y] / prev - 1
        prev = year_end[y]
    return {"final": final, "cagr": cagr, "vol": vol, "max_drawdown": mdd, "years": yr}


def monthly(nav: list[tuple[date, float]]) -> list[list]:
    """Month-end values, for charting."""
    out: dict[tuple[int, int], tuple[date, float]] = {}
    for d, v in nav:
        out[(d.year, d.month)] = (d, v)
    return [[d.isoformat(), round(v, 2)] for d, v in out.values()]


def run_momentum(a, f, fxd, flat_fx, capital, record, out) -> None:
    """Add the long-short momentum scenarios and the Fama-French cross-check."""
    from mergerarb.backtest.momentum import (
        MomConfig,
        load_prices,
        month_ends,
        parse_members,
        parse_umd,
        simulate_momentum,
    )

    members = parse_members(a.members.read_text())
    prices = load_prices(f, members, a.start, a.end, log=lambda m: None)

    def mom(key: str, label: str, fx_series=None, **kw) -> None:
        res = simulate_momentum(members, prices, fx_series or fxd,
                                MomConfig(start=a.start, end=a.end, **kw))
        cov = [c for _, c in res.coverage]
        record(key, label, res.nav_cad, {
            "taxes_cad": res.taxes_cad,
            "fees_usd": res.fees_usd,
            "turnover": res.turnover,
            "coverage_avg": statistics.mean(cov) if cov else 0,
            "coverage_min": min(cov) if cov else 0,
            "by_year_tax": {str(y): v for y, v in res.years.items()},
        })
        return res

    pre = mom("mom_pretax", "Momentum long-short, before tax", account="pretax")
    mom("mom_pretax_hedged", "Momentum long-short, before tax, currency held constant",
        fx_series=flat_fx, account="pretax")
    for k, b in BRACKETS.items():
        mom(f"mom_nonreg_cg_{k}", f"Momentum long-short, non-registered, {b.name}",
            account="nonreg", bracket=b)
        mom(f"mom_nonreg_biz_{k}", f"Momentum taxed as business income, {b.name}",
            account="nonreg", bracket=b, regime="business")
    out["momentum"] = {
        "coverage": [[d.isoformat(), round(c, 4)] for d, c in pre.coverage],
        "leg_returns": [[d.isoformat(), round(r, 6)] for d, r in pre.leg_returns],
    }
    if a.umd:
        umd = parse_umd(a.umd.read_bytes())
        nav, v = [], capital / fxd.at(a.start)
        for d in month_ends(a.start, a.end):
            if d > a.start and (d.year, d.month) in umd:
                v *= 1 + umd[(d.year, d.month)]
            nav.append((d, v * fxd.at(d)))
        record("fund_umd", "Fama-French momentum factor, before costs and tax", nav)
        ours = {d[:7]: r for d, r in out["momentum"]["leg_returns"]}
        pairs = [(ours[f"{y}-{m:02d}"], r) for (y, m), r in umd.items() if f"{y}-{m:02d}" in ours]
        if len(pairs) > 12:
            xs, ys = zip(*pairs, strict=True)
            out["momentum"]["correlation_with_ff"] = statistics.correlation(xs, ys)
            out["momentum"]["months_compared"] = len(pairs)


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--deals", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("results.json"))
    ap.add_argument("--cache", type=Path, default=Path.home() / ".cache" / "mergerarb-hist")
    ap.add_argument("--start", type=date.fromisoformat, default=date(2011, 11, 1))
    ap.add_argument("--end", type=date.fromisoformat, default=date(2026, 10, 30))
    ap.add_argument("--members", type=Path, help="S&P 500 point-in-time membership CSV")
    ap.add_argument("--umd", type=Path, help="Fama-French momentum factor zip")
    a = ap.parse_args(argv)
    f = Fetcher(a.cache)
    t0 = time.time()
    capital = 100_000.0

    fxd = yahoo(f, "CAD=X", a.start, a.end)["close"]
    tb_raw = yahoo(f, "^IRX", a.start, a.end)["close"]
    tbill = Series([(d, v / 100) for d, v in zip(tb_raw.days, tb_raw.vals, strict=True)])

    rows = [json.loads(line) for line in a.deals.read_text().splitlines()]
    deals, dropped = to_sim_deals(rows, a.end)
    out: dict = {
        "window": [a.start.isoformat(), a.end.isoformat()],
        "capital_cad": capital,
        "universe": {
            "groups": len(rows),
            "usable": len(deals),
            "dropped": dict(Counter(dropped).most_common()),
            "outcomes": dict(Counter(d.outcome for d in deals)),
            "stock_deals": sum(1 for d in deals if d.ratio),
        },
        "scenarios": {},
        "brackets": {k: vars(b) for k, b in BRACKETS.items()},
    }

    def record(key: str, label: str, nav, extra: dict | None = None) -> None:
        s = stats(nav, capital)
        out["scenarios"][key] = {"label": label, **s, "monthly": monthly(nav), **(extra or {})}

    flat_fx = Series([(a.start, fxd.at(a.start))])

    def arb(key: str, label: str, fx_series=None, **kw) -> None:
        res = simulate(deals, fx_series or fxd, tbill, Config(start=a.start, end=a.end, **kw))
        tr = res.trades
        wins = [t for t in tr if t.usd_pnl > 0]
        holds = [(t.exit - t.entry).days for t in tr]
        record(
            key,
            label,
            res.nav_cad,
            {
                "trades": len(tr),
                "win_rate": len(wins) / len(tr) if tr else 0,
                "breaks": sum(1 for t in tr if t.outcome == "broke"),
                "median_hold_days": statistics.median(holds) if holds else 0,
                "avg_trade_return": statistics.mean(t.usd_return for t in tr) if tr else 0,
                "worst_trades": [
                    {"name": t.name, "entry": t.entry.isoformat(), "ret": t.usd_return}
                    for t in sorted(tr, key=lambda t: t.usd_return)[:5]
                ],
                "taxes_cad": res.taxes_cad,
                "interest_cad": res.interest_cad,
                "fees_usd": res.fees_usd,
                "skipped_no_cash": res.skipped_no_cash,
                "avg_invested": res.avg_invested,
                "avg_positions": res.avg_positions,
                "by_year_tax": {str(y): v for y, v in res.years.items()},
            },
        )

    arb("arb_tfsa", "Merger arb, TFSA (cash deals only)", account="tfsa")
    arb(
        "arb_pretax_all",
        "Merger arb, all deals, before tax",
        account="tfsa",
        allow_stock_deals=True,
    )
    arb(
        "arb_tfsa_hedged",
        "Merger arb, TFSA, currency held constant",
        fx_series=flat_fx,
        account="tfsa",
    )
    for pf in (0.03, 0.10):
        arb(
            f"arb_tfsa_size{int(pf * 100)}",
            f"Merger arb, TFSA, {pf:.0%} per deal",
            account="tfsa",
            position_fraction=pf,
        )
    for k, b in BRACKETS.items():
        arb(
            f"arb_nonreg_cg_{k}",
            f"Merger arb, non-registered, {b.name}",
            account="nonreg",
            bracket=b,
        )
        arb(
            f"arb_nonreg_biz_{k}",
            f"Merger arb taxed as business income, {b.name}",
            account="nonreg",
            bracket=b,
            regime="business",
        )

    spy, xic = yahoo(f, "SPY", a.start, a.end), yahoo(f, "XIC.TO", a.start, a.end)
    for sym, data, us in (("spy", spy, True), ("xic", xic, False)):
        name = "S&P 500 (SPY)" if us else "TSX (XIC)"
        r = buy_and_hold(
            data["close"], data["divs"], fxd, a.start, a.end, capital, "tfsa", us_listed=us
        )
        record(f"{sym}_tfsa", f"{name}, TFSA", r.nav_cad, {"final_after_sale": r.final_cad})
        if us:
            r = buy_and_hold(
                data["close"],
                data["divs"],
                flat_fx,
                a.start,
                a.end,
                capital,
                "tfsa",
                us_listed=True,
            )
            record(
                "spy_tfsa_hedged",
                f"{name}, TFSA, currency held constant",
                r.nav_cad,
                {"final_after_sale": r.final_cad},
            )
        for k, b in BRACKETS.items():
            r = buy_and_hold(
                data["close"], data["divs"], fxd, a.start, a.end, capital, "nonreg", b, us_listed=us
            )
            record(
                f"{sym}_nonreg_{k}",
                f"{name}, non-registered, {b.name}",
                r.nav_cad,
                {
                    "final_after_sale": r.final_cad,
                    "sale_tax_cad": r.sale_tax_cad,
                    "dividend_tax_cad": r.dividend_tax_cad,
                },
            )

    for sym, label in FUNDS.items():
        try:
            data = yahoo(f, sym, a.start, a.end)
        except Exception as e:  # noqa: BLE001 - a missing fund shouldn't stop the run
            print(f"skipping {sym}: {e}")
            continue
        nav = total_return_series(data["adj"], fxd, a.start, a.end, capital)
        record(f"fund_{sym.lower()}", f"{label}, before tax", nav)

    if a.members:
        run_momentum(a, f, fxd, flat_fx, capital, record, out)

    a.out.write_text(json.dumps(out, indent=1, default=str))
    print(f"wrote {a.out} in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
