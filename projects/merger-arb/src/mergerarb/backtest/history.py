"""Pure parsing for the historical backtest: price statements and deal outcomes.

Merger proxies and tender-offer documents state the target's closing price on
two kinds of dates, and these become the backtest's entry and break prices:

- the "most recent practicable date" before the filing (or the last trading day
  before a tender offer starts): what an arbitrageur could have paid then;
- the last trading day before the deal was announced (the "unaffected" price):
  a fallback for where the target trades if the deal dies.

Outcomes come from the target's EDGAR filing history: a Form 25/15 or an 8-K
reporting a change in control (item 5.01) means the deal closed; an 8-K
terminating a material agreement (item 1.02) with no change in control means it
probably broke.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from mergerarb.extract import MONTHS

_DATE = (
    r"(January|February|March|April|May|June|July|August|September|October|November|"
    r"December)\s+(\d{1,2}),\s+((?:19|20)\d\d)"
)
_NUM = r"(\d{1,4}(?:,\d{3})*\.\d{2,4})"
_ANCHOR = r"(?:closing|last\s+reported|last\s+sale|reported\s+closing)"
# "On March 13, 2013, ..., the closing price ... was $9.14"
_P1 = re.compile(
    rf"(?:On|As\s+of)\s+{_DATE}([^$]{{0,220}}?){_ANCHOR}[^$]{{0,120}}?price[^$]{{0,140}}?"
    rf"(?:was|of|were)\s+(?:approximately\s+)?\$\s?{_NUM}",
    re.IGNORECASE,
)
# "The closing sale price ... on January 28, 2013, the last trading day prior to ..., was $9.05"
_P2 = re.compile(
    rf"{_ANCHOR}[^$]{{0,60}}?price[^$]{{0,170}}?\bon\s+{_DATE}([^$]{{0,220}}?)"
    rf"(?:was|of|were)\s+(?:approximately\s+)?\$\s?{_NUM}",
    re.IGNORECASE,
)
_ENTRY_WORDS = re.compile(
    r"practicable|record\s+date|commencement|prior\s+to\s+the\s+(?:date|printing|mailing|filing)"
    r"|before\s+the\s+(?:date|printing|mailing|filing)|date\s+of\s+this",
    re.IGNORECASE,
)
_UNAFFECTED_WORDS = re.compile(r"announce|unaffected|rumor|speculation|proposal", re.IGNORECASE)

COMPLETION_FORMS = {"25", "25-NSE", "15-12B", "15-12G", "15F-12B", "15F-12G", "15-15D"}


@dataclass(frozen=True)
class PriceStatement:
    """A dated closing price found in a filing."""

    day: date
    price: float
    kind: str  # "entry", "unaffected" or "other"
    snippet: str


def _wordset(s: str | None) -> set[str]:
    if not s:
        return set()
    stop = {"inc", "corp", "the", "company", "holdings", "group", "ltd", "plc", "co", "llc"}
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 2} - stop


def price_statements(
    text: str, target_name: str | None = None, acquirer_name: str | None = None
) -> list[PriceStatement]:
    """All dated closing-price statements, with statements about the acquirer dropped."""
    tw, aw = _wordset(target_name), _wordset(acquirer_name)
    out: list[PriceStatement] = []
    seen = set()
    for pat in (_P1, _P2):
        for m in pat.finditer(text):
            g = m.groups()
            mon, day, yr, between, num = g[0], g[1], g[2], g[3], g[4]
            ctx = text[max(0, m.start() - 80) : m.end()]
            words = _wordset(ctx)
            if aw and (words & aw) and not (words & tw) and "company" not in ctx.lower():
                continue
            try:
                d = date(int(yr), MONTHS[mon.lower()], int(day))
            except ValueError:
                continue
            qualifier = between + " " + text[max(0, m.start() - 80) : m.start()]
            if _UNAFFECTED_WORDS.search(between):
                kind = "unaffected"
            elif _ENTRY_WORDS.search(qualifier):
                kind = "entry"
            else:
                kind = "other"
            key = (d, num, kind)
            if key in seen:
                continue
            seen.add(key)
            out.append(PriceStatement(d, float(num.replace(",", "")), kind, ctx[-260:]))
    return out


def pick_prices(
    stmts: list[PriceStatement], filed: date, offer_value: float | None
) -> tuple[PriceStatement | None, PriceStatement | None]:
    """Choose the entry price and the unaffected (break) price.

    Entry: the latest statement dated within 45 days before the filing that is
    labelled as a recent/practicable date, or failing that any statement in
    that window. Unaffected: the lowest statement labelled as pre-announcement
    (lowest = more conservative for a break). Prices implausibly far from the
    offer are discarded as misreads.
    """

    def plausible(s: PriceStatement, lo: float, hi: float) -> bool:
        return offer_value is None or lo * offer_value <= s.price <= hi * offer_value

    window = [
        s for s in stmts if filed - timedelta(days=45) <= s.day <= filed and plausible(s, 0.5, 1.3)
    ]
    # Only statements labelled as a recent/practicable date count: an unlabelled
    # price shortly before a preliminary proxy is usually the pre-announcement price.
    labelled = [s for s in window if s.kind == "entry"]
    entry = max(labelled, key=lambda s: s.day) if labelled else None
    unaff = [
        s for s in stmts if s.kind == "unaffected" and s.day <= filed and plausible(s, 0.2, 1.1)
    ]
    unaffected = min(unaff, key=lambda s: s.price) if unaff else None
    return entry, unaffected


@dataclass(frozen=True)
class Outcome:
    """How and when a deal resolved, from the target's filing history."""

    status: str  # "closed", "broke" or "open"
    day: date | None
    evidence: str


def deal_outcome(
    forms: list[str],
    dates: list[date],
    items: list[str],
    filed: date,
    horizon_days: int = 900,
    break_days: int = 540,
) -> Outcome:
    """Classify a deal as closed, broken or still open after ``filed``.

    Closed: Form 25/15 or an 8-K with item 5.01 (change in control).
    Broke: an 8-K with item 1.02 (termination of a material agreement) and no
    change in control in the same report, with no completion in the next 45
    days. Closing 8-Ks also terminate credit agreements under item 1.02, which
    is why a completion within 45 days overrides it. A termination more than
    ``break_days`` after the filing is taken to be about something else.
    """
    events = sorted(
        (d, f, it or "")
        for f, d, it in zip(forms, dates, items, strict=False)
        if filed < d <= filed + timedelta(days=horizon_days)
    )

    def completion(f: str, it: str) -> bool:
        return f in COMPLETION_FORMS or (f.startswith("8-K") and "5.01" in it)

    for i, (d, f, it) in enumerate(events):
        if completion(f, it):
            return Outcome("closed", d, f"{f} {it}".strip())
        if f.startswith("8-K") and "1.02" in it and d <= filed + timedelta(days=break_days):
            soon = [e for e in events[i + 1 :] if e[0] <= d + timedelta(days=45)]
            if not any(completion(f2, it2) for _, f2, it2 in soon):
                return Outcome("broke", d, f"{f} {it}")
    return Outcome("open", None, "")
