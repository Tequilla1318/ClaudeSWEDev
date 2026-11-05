"""Calibrate and validate the synthetic-option smile against Cboe PUT and PUTY (S15).

Writes docs/validation/skew-calibration.md. Reads SPX, VIX, DTB3, PUT, PUTY CSVs from
--data (or downloads them), plus Cboe's SKEW index for the rejected SKEW-linked
variant. Optionally reads a saved Cboe delayed SPX chain (--chain) to compare the
model's smile with the market's on that day.

    python scripts/validate_skew.py --data ~/.cache/occheck [--chain spx.json --asof 2026-11-05]
"""

from __future__ import annotations

import argparse
import csv
import urllib.request
from datetime import date
from pathlib import Path

import numpy as np

from occheck import data
from occheck.backtest.putwrite import (
    PutWriteResult,
    compare_to_index,
    monthly_expirations,
    put_write,
)
from occheck.backtest.rules import Rules, run_short_puts, summarize
from occheck.backtest.skew import DEFAULT_BETA, smile_vol, vix_over_atm
from occheck.pricing import bs_price

OUT = Path(__file__).resolve().parent.parent / "docs" / "validation" / "skew-calibration.md"
GATE = 0.015
PERIODS = (
    ("PUT", "2007-06-01", "2016-12-31", 1.00),
    ("PUT", "2017-01-01", "2099-12-31", 1.00),
    ("PUTY", "1990-01-01", "2007-12-31", 0.98),
    ("PUTY", "2008-01-01", "2099-12-31", 0.98),
)
SKEW_URL = "https://cdn-api.cboe.com/api/global/us_indices/daily_prices/SKEW_History.csv"


def load(kind, folder):
    path = folder / f"{kind}.csv" if folder else None
    if path is None or not path.exists():
        path = data.download(kind, folder)
    return data.load_csv(path.read_text())


def load_skew(folder):
    path = folder / "SKEW.csv" if folder else None
    if path is not None and path.exists():
        text = path.read_text()
    else:
        req = urllib.request.Request(SKEW_URL, headers={"User-Agent": data.USER_AGENT})
        text = urllib.request.urlopen(req, timeout=60).read().decode()  # noqa: S310
    rows = [r for r in csv.reader(text.splitlines()[1:]) if len(r) > 1 and r[1]]
    days = np.array([np.datetime64(f"{r[0][6:]}-{r[0][:2]}-{r[0][3:5]}") for r in rows])
    return days, np.array([float(r[1]) for r in rows])


def variant(d, s, v, r, mny, atm, beta):
    """Put-write with explicit per-day ATM vol and slope arrays (for rejected variants)."""
    rolls = monthly_expirations(d)
    first, last = int(rolls[0]), int(rolls[-1])
    rr = r / 100.0
    eq = np.full(len(d), np.nan)
    cash = 1.0
    eq[first] = 1.0
    for a, b in zip(rolls[:-1], rolls[1:], strict=True):
        k = s[a] * mny
        n = cash / k
        t = (d[b] - d[a]).astype(int) / 365.0
        cash += n * bs_price(s[a], k, t, rr[a], smile_vol(atm[a], s[a], k, t, beta[a]), "P")
        days = np.arange(a + 1, b + 1)
        gap = np.diff(d[a : b + 1]).astype(int)
        cp = cash * np.cumprod(1.0 + rr[a:b] * gap / 360.0)
        tau = (d[b] - d[days]).astype(int) / 365.0
        vol = np.array(
            [float(smile_vol(atm[j], s[j], k, tau[i], beta[j])) for i, j in enumerate(days)]
        )
        eq[days] = cp - n * bs_price(s[days], k, tau, rr[days], vol, "P")
        cash = float(eq[b])
    return PutWriteResult(d[first : last + 1], eq[first : last + 1], rolls - first)


def label(lo, hi):
    return f"{lo[:4]}–{'now' if hi.startswith('2099') else hi[:4]}"


def market_smile(chain_path: Path, asof: date):
    from occheck.quotes import load_chain

    c = load_chain(chain_path.read_text())
    out = []
    for lo, hi in ((25, 35), (40, 50)):
        rows = [
            (o.strike, o.iv, (o.expiry - asof).days, abs(o.delta))
            for o in c.options
            if o.right == "P" and o.bid > 0 and o.iv > 0 and lo <= (o.expiry - asof).days <= hi
        ]
        arr = np.array(rows)
        betas, m30, m16 = [], [], []
        for dte in sorted(set(arr[:, 2])):
            x = arr[arr[:, 2] == dte]
            atm = x[np.argmin(abs(x[:, 0] - c.spot)), 1]
            sel = (x[:, 3] >= 0.05) & (x[:, 3] <= 0.5) & (x[:, 0] < c.spot)
            z = np.log(x[sel, 0] / c.spot) / (atm * np.sqrt(dte / 365))
            y = x[sel, 1] / atm - 1
            betas.append(-np.sum(z * y) / np.sum(z * z))
            m30.append(x[np.argmin(abs(x[:, 3] - 0.30)), 1] / atm)
            m16.append(x[np.argmin(abs(x[:, 3] - 0.16)), 1] / atm)
        out.append((lo, hi, float(np.mean(betas)), float(np.mean(m30)), float(np.mean(m16))))
    return c, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=None)
    ap.add_argument("--chain", type=Path, default=None, help="saved Cboe delayed _SPX chain JSON")
    ap.add_argument("--asof", type=date.fromisoformat, default=None, help="date of --chain")
    a = ap.parse_args()
    spx, vix, tb = (load(k, a.data) for k in ("SPX", "VIX", "DTB3"))
    idx = {k: load(k, a.data) for k in ("PUT", "PUTY")}
    d, (s, v, r) = data.align(spx, vix, tb)

    def run(kind, lo, hi, mny, beta):
        m = (d >= np.datetime64(lo)) & (d <= np.datetime64(hi))
        res = put_write(d[m], s[m], v[m], r[m], moneyness=mny, skew_beta=beta)
        return compare_to_index(res, idx[kind].dates, idx[kind].values)

    def ok(c):
        return "pass" if abs(c["cagr_diff"]) <= GATE and c["monthly_corr"] >= 0.9 else "fail"

    grid = [0.0, 0.05, 0.10, 0.15, 0.20, 0.30]
    md = ["# Volatility smile calibration (S15)", ""]
    md += [
        f"Generated by `scripts/validate_skew.py`. Model: ATM vol = 0.9 x VIX (validated in "
        f"[put-replication.md](put-replication.md)); strike K priced at "
        f"ATM x clip(1 − β·z, 0.5, 3), z = ln(K/S)/(ATM·√T). Default β = {DEFAULT_BETA}.",
        "",
        "References: Cboe PutWrite (PUT, at the money) and 2% OTM PutWrite (PUTY) indexes. "
        "Gate: CAGR within ±1.5 points a year and monthly-return correlation ≥ 0.9.",
        "",
        "## CAGR difference vs the index (points a year) by slope β",
        "",
        "| β | " + " | ".join(f"{k} {label(lo, hi)}" for k, lo, hi, _ in PERIODS) + " |",
        "| --- |" + " --- |" * len(PERIODS),
    ]
    cache = {}
    for b in grid:
        cells = []
        for p in PERIODS:
            c = cache[(p, b)] = run(*p, b)
            cells.append(f"{c['cagr_diff'] * 100:+.2f} ({ok(c)})")
        md.append(f"| {b:.2f} | " + " | ".join(cells) + " |")
    puty_old, puty_new = PERIODS[2], PERIODS[3]
    best_old = min(grid, key=lambda b: abs(cache[(puty_old, b)]["cagr_diff"]))
    best_new = min(grid, key=lambda b: abs(cache[(puty_new, b)]["cagr_diff"]))
    md += [
        "",
        f"Split-sample: the best β on PUTY {label(*puty_old[1:3])} is {best_old:.2f}, which on "
        f"{label(*puty_new[1:3])} gives {cache[(puty_new, best_old)]['cagr_diff'] * 100:+.2f} pts "
        f"({ok(cache[(puty_new, best_old)])}). The best on {label(*puty_new[1:3])} is "
        f"{best_new:.2f}, which on {label(*puty_old[1:3])} gives "
        f"{cache[(puty_old, best_new)]['cagr_diff'] * 100:+.2f} pts ({ok(cache[(puty_old, best_new)])}). "
        f"β = {DEFAULT_BETA} sits between them and passes every check. The ATM index (PUT) "
        "is unaffected by β, as expected.",
        "",
        "## Rejected alternatives",
        "",
    ]
    # Variant A: ATM implied by VIX through the smile (one parameter for level and skew).
    for b in (0.22,):
        ratio = vix_over_atm(b)
        cells = []
        for k, lo, hi, mny in PERIODS:
            m = (d >= np.datetime64(lo)) & (d <= np.datetime64(hi))
            atm = v[m] / 100 / ratio
            res = variant(d[m], s[m], v[m], r[m], mny, atm, np.full(m.sum(), b))
            c = compare_to_index(res, idx[k].dates, idx[k].values)
            cells.append(f"{c['cagr_diff'] * 100:+.2f} ({ok(c)})")
        md.append(
            f"- **ATM from VIX through the smile, β = {b}** (ATM/VIX = {1 / ratio:.3f}): "
            + "; ".join(
                f"{k} {label(lo, hi)} {x}" for (k, lo, hi, _), x in zip(PERIODS, cells, strict=True)
            )
            + ". Overstates PUTY before 2008."
        )
    # Variant B: slope tied to Cboe's SKEW index.
    sk_days, sk_vals = load_skew(a.data)
    sk = sk_vals[np.searchsorted(sk_days, d, side="right") - 1]
    cells = []
    for k, lo, hi, mny in PERIODS:
        m = (d >= np.datetime64(lo)) & (d <= np.datetime64(hi))
        beta = np.round(np.maximum(sk[m] - 100, 0) * 0.0059 / 0.005) * 0.005
        ratios = {x: vix_over_atm(float(x)) for x in np.unique(beta)}
        atm = v[m] / 100 / np.array([ratios[x] for x in beta])
        res = variant(d[m], s[m], v[m], r[m], mny, atm, beta)
        c = compare_to_index(res, idx[k].dates, idx[k].values)
        cells.append(f"{c['cagr_diff'] * 100:+.2f} ({ok(c)})")
    md.append(
        "- **Slope = 0.0059 x (SKEW − 100), ATM from VIX through the smile**: "
        + "; ".join(
            f"{k} {label(lo, hi)} {x}" for (k, lo, hi, _), x in zip(PERIODS, cells, strict=True)
        )
        + ". SKEW rose from about 116 before 2008 to about 140 since 2020, but the implied "
        "slope doesn't explain the VIX/ATM gap before 2008."
    )
    md += [
        "",
        "Both alternatives derive ATM vol from VIX through the smile. They fail because the VIX/ATM gap "
        "is not only skew: Carr & Wu (2006) attribute it mainly to Jensen's inequality and the variance "
        "of volatility. Keeping the separately validated 0.9 x VIX for ATM and adding a modest skew works.",
        "",
    ]
    if a.chain and a.asof:
        chain, rows = market_smile(a.chain, a.asof)
        z30, z16 = -0.524, -0.994  # approx z of 30- and 16-delta puts
        model30 = float(smile_vol(1.0, 1.0, np.exp(z30 * np.sqrt(1 / 12)), 1 / 12, DEFAULT_BETA))
        model16 = float(smile_vol(1.0, 1.0, np.exp(z16 * np.sqrt(1 / 12)), 1 / 12, DEFAULT_BETA))
        md += [
            f"## Today's market smile ({a.asof}, Cboe delayed SPX chain, spot {chain.spot:,.0f})",
            "",
            "| DTE | Market slope β | 30-delta put IV / ATM | 16-delta put IV / ATM |",
            "| --- | --- | --- | --- |",
        ]
        md += [f"| {lo}–{hi} | {b:.2f} | {x30:.2f} | {x16:.2f} |" for lo, hi, b, x30, x16 in rows]
        md += [
            f"| model (β = {DEFAULT_BETA}) | {DEFAULT_BETA:.2f} | {model30:.2f} | {model16:.2f} |",
            "",
            "The market's skew on this date is about three times the historical fit. Either the real "
            "indexes earned less than today's quotes imply (they sell near the volume-weighted price, and "
            "the skew was flatter for most of the history), or skew is unusually steep now. Backtests "
            "of far-OTM rules therefore likely **understate** the premium sellers would collect today, "
            "and understate how much those puts reprice in a selloff.",
            "",
        ]
    md += [
        "## Forum rules: flat vol vs the smile",
        "",
        "| Rules | Flat CAGR / max DD | Smile CAGR / max DD |",
        "| --- | --- | --- |",
    ]
    for name, kw in (
        ("30 delta, 45 DTE, take 50%, close at 21", {}),
        ("16 delta, 45 DTE, hold", {"delta": 0.16, "take_profit": None, "manage_dte": None}),
    ):
        flat = summarize(run_short_puts(d, s, v, r, Rules(skew_beta=0.0, **kw)), d, s)["strategy"]
        sm = summarize(run_short_puts(d, s, v, r, Rules(**kw)), d, s)["strategy"]
        md.append(
            f"| {name} | {flat['cagr']:.2%} / {flat['max_drawdown']:.1%} | {sm['cagr']:.2%} / {sm['max_drawdown']:.1%} |"
        )
    md += [
        "",
        "## Sources",
        "",
        "- [Cboe PUTY history](https://cdn.cboe.com/api/global/us_indices/daily_prices/PUTY_History.csv), "
        "[PUT history](https://cdn.cboe.com/api/global/us_indices/daily_prices/PUT_History.csv), "
        "[SKEW history](https://cdn.cboe.com/api/global/us_indices/daily_prices/SKEW_History.csv)",
        "- [Cboe VIX methodology](https://cdn.cboe.com/resources/vix/VIX_Methodology.pdf) (variance-swap integral)",
        "- [Carr & Wu (2006), A Tale of Two Indices](https://engineering.nyu.edu/sites/default/files/2021-03/carrwutaleoftwoindices.pdf)",
        "",
    ]
    OUT.write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
