"""Pre-trade option checker: what a trade costs before you know if it's right.

Everything is computed from numbers the user types in (quote, strike, expiry, and
optionally an event date and recent realized volatility). No market data is fetched.
Wording describes costs and market-implied odds; it never recommends a trade.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any, Literal

from occheck.audit import Thresholds
from occheck.pricing import bs_greeks, bs_price, implied_vol, norm_cdf

RESEARCH = {
    "spreads": (
        "de Silva, Smith & So, Losing is Optional (retail option spreads and IV around earnings)",
        "https://quantpedia.com/how-retail-losses-money-in-option-trading/",
    ),
    "retail": (
        "Bryzgalova, Pavlova & Sikorskaya (2023), Retail Trading in Options",
        "https://academicnewsletter.sufe.edu.cn/info/359005",
    ),
    "lottery": (
        "Bali, Cakici & Whitelaw (2011), Maxing Out",
        "https://academicnewsletter.sufe.edu.cn/info/356984",
    ),
    "vrp": (
        "Bondarenko, Cboe PutWrite study (implied vs realized volatility)",
        "https://www.cboe.com/insights/posts/white-paper-shows-volatility-risk-premium-facilitated-higher-risk-adjusted-returns-for-put-index/",
    ),
}


def _item(mid: str, title: str, status: str, display: str, why: str, research: str) -> dict:
    label, url = RESEARCH[research]
    return {
        "id": mid,
        "title": title,
        "status": status,
        "display": display,
        "explanation": why,
        "research": {"label": label, "url": url},
    }


def check_trade(
    spot: float,
    strike: float,
    expiry: date,
    today: date,
    right: Literal["C", "P"],
    side: Literal["buy", "sell"],
    bid: float,
    ask: float,
    contracts: int = 1,
    multiplier: float = 100.0,
    rate_pct: float = 4.0,
    event_date: date | None = None,
    realized_vol_pct: float | None = None,
    thresholds: Thresholds | None = None,
) -> dict[str, Any]:
    """Cost, break-even and market-implied odds of one option trade, plus flags."""
    th = thresholds or Thresholds()
    if not (spot > 0 and strike > 0):
        raise ValueError("price and strike must be positive")
    if not 0 <= bid <= ask or ask <= 0:
        raise ValueError("need 0 <= bid <= ask, with ask > 0")
    days = (expiry - today).days
    if days < 0:
        raise ValueError("expiry is in the past")
    t = max(days, 0.5) / 365.0  # same-day options: treat as half a day left
    r = rate_pct / 100.0
    mid = 0.5 * (bid + ask)
    fill = ask if side == "buy" else bid
    spread = ask - bid
    spread_pct = spread / mid if mid > 0 else math.inf
    try:
        iv = implied_vol(mid, spot, strike, t, r, right)
    except ValueError:
        iv = None
    sign = 1.0 if right == "C" else -1.0
    breakeven = strike + sign * fill
    move_needed = breakeven / spot - 1.0
    items: list[dict] = []

    half_cost = 0.5 * spread * multiplier * contracts
    items.append(
        _item(
            "spread",
            "Cost of the bid-ask spread",
            "flag" if spread_pct > 0.10 else "watch" if spread_pct > 0.03 else "ok",
            f"Spread ${spread:.2f} = {spread_pct:.1%} of the mid price. Filling at the "
            f"{'ask' if side == 'buy' else 'bid'} costs about ${half_cost:,.2f} now, and about "
            f"${2 * half_cost:,.2f} for a round trip.",
            "This cost is paid whether the trade works or not. A limit order near the mid price "
            "often fills for less, but not always.",
            "spreads",
        )
    )

    if iv is not None:
        exp_move = iv * math.sqrt(t)
        d2 = (math.log(spot / strike) + (r - 0.5 * iv * iv) * t) / (iv * math.sqrt(t))
        p_itm = float(norm_cdf(sign * d2))
        delta = float(bs_greeks(spot, strike, t, r, iv, right)["delta"])
        items.append(
            _item(
                "breakeven",
                "Break-even and the expected move",
                "info",
                f"Break-even at expiry {breakeven:,.2f} ({move_needed:+.1%} from {spot:,.2f}). The "
                f"option price implies a typical move of about ±{exp_move:.1%} by expiry "
                f"(implied vol {iv:.1%}).",
                "The implied move is what the market is pricing, not a forecast. A break-even "
                "beyond it needs a larger-than-priced move for a buyer to profit.",
                "retail",
            )
        )
        # Profit at expiry needs the price beyond the break-even, not just past the strike.
        if breakeven > 0:
            d2_be = (math.log(spot / breakeven) + (r - 0.5 * iv * iv) * t) / (iv * math.sqrt(t))
            p_beyond = float(norm_cdf(sign * d2_be))
        else:
            p_beyond = 1.0 if right == "P" else 0.0  # put seller with premium above strike
        p_profit_side = p_beyond if side == "buy" else 1.0 - p_beyond
        items.append(
            _item(
                "odds",
                "Market-implied odds",
                "info",
                f"About {p_itm:.0%} chance of finishing in the money (delta {delta:+.2f}). "
                f"Held to expiry, {'buying' if side == 'buy' else 'selling'} at this price ends "
                f"with a profit about {p_profit_side:.0%} of the time, before commissions.",
                "These odds come from the option price itself. They describe how the market prices "
                "the trade, not whether it is a good trade.",
                "vrp",
            )
        )
    else:
        items.append(
            _item(
                "breakeven",
                "Break-even",
                "na",
                f"Break-even at expiry {breakeven:,.2f} ({move_needed:+.1%}). Implied vol "
                "could not be computed: the mid price is at or below intrinsic value.",
                "Check the quote. Deep in-the-money options often have stale or wide quotes.",
                "retail",
            )
        )

    if event_date is not None:
        inside = today <= event_date <= expiry
        items.append(
            _item(
                "event",
                "Event before expiry",
                ("flag" if side == "buy" else "watch") if inside else "ok",
                (
                    "The event falls before expiry, so the price includes the expected jump. "
                    "Implied vol usually drops right after the event (IV crush)."
                )
                if inside
                else "The event is after expiry, so it isn't in this option's price.",
                "Around earnings, retail option buyers lost 5–14% on average, mostly by paying up "
                "for volatility ahead of the announcement and holding afterwards.",
                "spreads",
            )
        )

    if realized_vol_pct is not None and iv is not None and realized_vol_pct > 0:
        ratio = iv / (realized_vol_pct / 100.0)
        rich = ratio > 1.25
        items.append(
            _item(
                "iv_rv",
                "Implied vs recent realized volatility",
                ("watch" if side == "buy" else "info") if rich else "info",
                f"Implied {iv:.1%} vs realized {realized_vol_pct:.1f}%: options are priced at "
                f"{ratio:.2f}x recent movement.",
                "Implied vol has usually been above the volatility that followed. That gap is what "
                "option sellers are paid for carrying crash risk.",
                "vrp",
            )
        )

    is_lottery = side == "buy" and fill < th.lottery_max_premium and days <= th.lottery_max_dte
    if side == "buy":
        items.append(
            _item(
                "lottery",
                "Lottery-ticket profile",
                "flag" if is_lottery else "ok",
                f"${fill:.2f} premium with {days} day(s) to expiry"
                + (": cheap and short-dated." if is_lottery else "."),
                "Cheap, short-dated options are priced like lottery tickets; assets with "
                "lottery-like payoffs have earned less on average.",
                "lottery",
            )
        )

    premium_total = fill * multiplier * contracts
    if side == "buy":
        max_loss = f"${premium_total:,.2f} (the premium paid)"
    elif right == "P":
        max_loss = f"${(strike - fill) * multiplier * contracts:,.2f} if the stock goes to zero"
    else:
        max_loss = "unlimited unless you own the shares (a covered call)"
    return {
        "disclaimer": "Educational tool, not financial advice. Odds come from the option's price.",
        "summary": {
            "side": side,
            "right": right,
            "mid": mid,
            "fill": fill,
            "premium_total": premium_total,
            "notional": strike * multiplier * contracts,
            "days": days,
            "implied_vol": iv,
            "max_loss": max_loss,
            "theoretical_at_iv": float(bs_price(spot, strike, t, r, iv, right)) if iv else None,
        },
        "items": items,
    }


def check_from_form(fields: dict[str, Any]) -> dict[str, Any]:
    """Entry point for the web page: parse form strings, then :func:`check_trade`."""

    def num(key: str) -> float | None:
        v = fields.get(key)
        return None if v in (None, "") else float(v)

    def day(key: str) -> date | None:
        v = fields.get(key)
        return None if not v else date.fromisoformat(v)

    return check_trade(
        spot=num("spot"),
        strike=num("strike"),
        expiry=day("expiry"),
        today=day("today") or date.today(),
        right=fields["right"],
        side=fields["side"],
        bid=num("bid"),
        ask=num("ask"),
        contracts=int(num("contracts") or 1),
        rate_pct=num("rate") if num("rate") is not None else 4.0,
        event_date=day("event"),
        realized_vol_pct=num("rv"),
    )
