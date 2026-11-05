"""Trade-log report card: metrics plus plain-language explanations and research links.

Output is a JSON-serializable dict so the same report feeds the CLI and the web page.
Wording describes what the data shows and what research found; it never tells the
reader what to trade.

Statuses: ``flag`` (matches a costly pattern from the research), ``watch``
(borderline), ``ok``, ``info`` (no judgment) and ``na`` (not enough data).
"""

from __future__ import annotations

from typing import Any

from occheck import audit
from occheck.brokers.ibkr_flex import ParseResult, parse_flex_csv
from occheck.roundtrips import match_round_trips, wheel_view

DISCLAIMER = "Educational tool, not financial advice. It describes your past trades only."

RESEARCH = {
    "french": (
        "French (2008), The Cost of Active Investing",
        "https://ideas.repec.org/a/bla/jfinan/v63y2008i4p1537-1573.html",
    ),
    "barber_odean": (
        "Barber & Odean (2000), Trading Is Hazardous to Your Wealth",
        "https://faculty.haas.berkeley.edu/odean/papers/returns/returns.html",
    ),
    "odean": (
        "Odean (1998), Are Investors Reluctant to Realize Their Losses?",
        "https://academicnewsletter.sufe.edu.cn/info/361849",
    ),
    "lottery": (
        "Bali, Cakici & Whitelaw (2011), Maxing Out",
        "https://academicnewsletter.sufe.edu.cn/info/356984",
    ),
    "zero_dte": (
        "Beckmeyer, Branger & Gayda (2023), Retail traders love 0DTE options",
        "https://neudata.co/literature-reviews/zero-day-to-expiry-options-a-losing-bet-for-retail-traders",
    ),
    "retail_options": (
        "Bryzgalova, Pavlova & Sikorskaya (2023), Retail Trading in Options",
        "https://academicnewsletter.sufe.edu.cn/info/359005",
    ),
    "vrp": (
        "Bondarenko, Cboe PutWrite study (volatility risk premium)",
        "https://www.cboe.com/insights/posts/white-paper-shows-volatility-risk-premium-facilitated-higher-risk-adjusted-returns-for-put-index/",
    ),
}


def _money(x: float | None) -> str:
    return "n/a" if x is None else f"{'-' if x < 0 else ''}${abs(x):,.2f}"


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def _metric(mid, title, status, display, explanation, research, data) -> dict[str, Any]:
    label, url = RESEARCH[research]
    return {
        "id": mid,
        "title": title,
        "status": status,
        "display": display,
        "explanation": explanation,
        "research": {"label": label, "url": url},
        "data": data,
    }


def build_report(
    parsed: ParseResult,
    account_value: float | None = None,
    thresholds: audit.Thresholds | None = None,
    convention: str = "wheel",
) -> dict[str, Any]:
    """Build the report card from parsed trades.

    ``convention="wheel"`` (default) folds assigned short-option premiums into the
    stock's cost basis or sale price; ``"broker"`` keeps them as separate round trips,
    as the statement shows them. Totals are the same either way.
    """
    if convention not in {"wheel", "broker"}:
        raise ValueError("convention must be 'wheel' or 'broker'")
    th = thresholds or audit.Thresholds()
    trades = parsed.trades
    rts = match_round_trips(trades).round_trips
    if convention == "wheel":
        rts = wheel_view(rts, trades)
    costs = audit.cost_summary(trades, rts)
    turn = audit.turnover(trades, account_value)
    exp = audit.expectancy(rts)
    disp = audit.disposition(rts)
    lot = audit.lottery(rts, th)
    bs = audit.buyer_seller(rts)
    conc = audit.concentration(rts, account_value)
    m: list[dict[str, Any]] = []

    share = costs.commission_share_of_gross_profit
    m.append(
        _metric(
            "costs",
            "What commissions took",
            "info"
            if share is None
            else "flag"
            if share > 0.25
            else "watch"
            if share > 0.10
            else "ok",
            f"{_money(costs.commission)} in commissions "
            f"({costs.commission_bps_of_notional:.1f} bps of {_money(costs.traded_notional)} "
            f"traded); {_pct(share)} of gross profits",
            "Commissions are the one cost you always pay. Bid-ask spreads are a second, "
            "hidden cost not shown in the statement and often larger for options.",
            "french",
            {**costs.__dict__},
        )
    )

    annual = turn["annual_turnover"]
    m.append(
        _metric(
            "turnover",
            "How much you traded",
            "info"
            if annual is None
            else "flag"
            if annual > 1.15
            else "watch"
            if annual > 0.8
            else "ok",
            f"{_money(turn['notional_per_year'])} traded per year"
            + ("" if annual is None else f" = {annual:.2f}x annual turnover"),
            "In Barber & Odean's data the average household turned over 0.8x its account a "
            "year; the most active fifth (1.15x or more) earned 10.0% a year net vs 17.1% for "
            "the market." + ("" if account_value else " Enter your account value to compare."),
            "barber_odean",
            turn,
        )
    )

    if exp["n"] and exp["n"] >= th.min_samples:
        bad = exp["win_rate"] >= th.high_win_rate and exp["expectancy"] < 0
        status = "flag" if bad else "ok" if exp["expectancy"] > 0 else "watch"
        cover = exp["wins_to_cover_largest_loss"]
        display = (
            f"Win rate {_pct(exp['win_rate'])}, average trade {_money(exp['expectancy'])}; "
            f"largest loss {_money(exp['largest_loss'])}"
            + ("" if cover is None else f" = {cover:.1f} average wins")
        )
    else:
        status, display = "na", f"Needs at least {th.min_samples} closed trades"
    m.append(
        _metric(
            "expectancy",
            "Win rate vs what a trade earns",
            status,
            display,
            "A high win rate can hide a losing strategy when the occasional loss is large. "
            "Option selling often looks like this: many small wins, rare big losses.",
            "vrp",
            exp,
        )
    )

    enough = disp["n_winners"] >= th.min_samples and disp["n_losers"] >= th.min_samples
    ratio = disp["ratio"]
    m.append(
        _metric(
            "disposition",
            "Holding losers longer than winners",
            "na"
            if not enough or ratio is None
            else "flag"
            if ratio > th.disposition_ratio_flag
            else "ok",
            f"Needs at least {th.min_samples} winning and {th.min_samples} losing trades "
            f"(this file has {disp['n_winners']} and {disp['n_losers']})"
            if not enough or ratio is None
            else f"Median hold: winners {disp['median_days_winners']:.1f} days, losers "
            f"{disp['median_days_losers']:.1f} days ({ratio:.2f}x)",
            "Investors tend to sell winners too early and hold losers too long (the disposition "
            "effect). Odean found this pattern was not justified by what happened next.",
            "odean",
            disp,
        )
    )

    ls = lot["lottery_share"]
    m.append(
        _metric(
            "lottery",
            "Lottery-ticket options",
            "na" if ls is None else "flag" if ls > 0.25 else "watch" if ls > 0.05 else "ok",
            "No long options"
            if ls is None
            else f"{_pct(ls)} of option premium paid went to options under "
            f"${th.lottery_max_premium:.2f} with {th.lottery_max_dte} days or less to expiry "
            f"({lot['lottery_n']} trades, net "
            f"{_money(lot['lottery_net_pnl'])})",
            "Cheap, short-dated options are priced like lottery tickets. Research finds assets "
            "with lottery-like payoffs earn less on average.",
            "lottery",
            lot,
        )
    )

    z = lot["zero_dte_share"]
    m.append(
        _metric(
            "zero_dte",
            "Same-day (0DTE) options",
            "na" if z is None else "flag" if z > 0.25 else "watch" if z > 0 else "ok",
            "No options"
            if z is None
            else f"{_pct(z)} of option trades opened on expiry day, "
            f"net {_money(lot['zero_dte_net_pnl'])}",
            "Retail traders lost an estimated $350k a day on same-day SPX options after daily "
            "expiries launched in 2022.",
            "zero_dte",
            lot,
        )
    )

    m.append(
        _metric(
            "buyer_seller",
            "Option buyer vs seller",
            "info",
            f"Bought: {bs['buyer']['n']} trades, net {_money(bs['buyer']['net_pnl'])}. "
            f"Sold: {bs['seller']['n']} trades, net {_money(bs['seller']['net_pnl'])}.",
            "On average option buyers pay a volatility premium and sellers collect it, in exchange "
            "for crash risk. Retail option buyers lose money on average.",
            "retail_options",
            bs,
        )
    )

    sa = conc["share_of_account"]
    m.append(
        _metric(
            "concentration",
            "Largest single loss",
            "na"
            if conc["largest_loss"] is None
            else "info"
            if sa is None
            else "flag"
            if sa > th.concentration_flag
            else "ok",
            "No losing trades"
            if conc["largest_loss"] is None
            else f"{_money(conc['largest_loss'])} on {conc['symbol']}"
            + (f" = {_pct(sa)} of account" if sa is not None else "")
            + f"; {_pct(conc['share_of_losses'])} of all losses",
            "Blow-ups usually come from position size, not from the strategy."
            + ("" if account_value else " Enter your account value to see this loss as a share."),
            "barber_odean",
            conc,
        )
    )

    return {
        "disclaimer": DISCLAIMER,
        "summary": {
            "trades": len(trades),
            "round_trips": len(rts),
            "convention": convention,
            "net_pnl": costs.net_pnl,
            "from": min(t.when for t in trades).isoformat() if trades else None,
            "to": max(t.when for t in trades).isoformat() if trades else None,
        },
        "metrics": m,
        "warnings": list(parsed.warnings),
    }


def report_from_csv(
    text: str,
    account_value: float | None = None,
    convention: str = "wheel",
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Parse a Flex CSV and build the report card (entry point for the web page).

    ``thresholds`` overrides fields of :class:`occheck.audit.Thresholds` by name.
    """
    th = audit.Thresholds(**(thresholds or {}))
    return build_report(parse_flex_csv(text), account_value, th, convention)


def render_text(report: dict[str, Any]) -> str:
    """Render a report card as plain text for the terminal."""
    s = report["summary"]
    lines = [
        f"Trade-log report card: {s['trades']} trades, {s['round_trips']} round trips, "
        f"net {_money(s['net_pnl'])}",
        "",
    ]
    for m in report["metrics"]:
        lines.append(f"[{m['status'].upper():5}] {m['title']}: {m['display']}")
        lines.append(f"        {m['explanation']}")
        lines.append(f"        Research: {m['research']['label']} <{m['research']['url']}>")
    for w in report["warnings"]:
        lines.append(f"Note: {w}")
    lines += ["", report["disclaimer"]]
    return "\n".join(lines)
