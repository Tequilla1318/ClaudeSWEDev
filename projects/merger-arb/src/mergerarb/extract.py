"""Pull deal terms out of merger-filing text.

These are heuristics over free text, not a parser of a structured format. Every
result carries the sentence it came from so a person can check it, and the
scanner marks anything ambiguous for review instead of guessing.
"""

from __future__ import annotations

import html
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

MONTHS = {
    m: i
    for i, m in enumerate(
        [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ],
        start=1,
    )
}
ORDINAL = {"first": 1, "second": 2, "third": 3, "fourth": 4}
_NUM = r"\d{1,4}(?:,\d{3})*(?:\.\d{1,4})?"


@dataclass
class Terms:
    """Deal terms found in one filing."""

    cash: float | None = None
    ratio: float | None = None
    acquirer_name: str | None = None
    expected_close: date | None = None
    close_basis: str | None = None
    has_cvr: bool = False
    has_election: bool = False
    has_ticking_fee: bool = False
    evidence: list[str] = field(default_factory=list)


def html_to_text(raw: str) -> str:
    """Strip tags, scripts and entities; collapse whitespace."""
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(raw).replace("\u200b", " ").replace("\xa0", " ")
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    return re.sub(r"\s+", " ", text).strip()


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def _snippet(text: str, start: int, end: int, pad: int = 60) -> str:
    return "…" + text[max(0, start - pad) : min(len(text), end + pad)].strip() + "…"


def _mode(values: list[float]) -> float | None:
    """Most common value; ties go to the value seen first."""
    if not values:
        return None
    counts = Counter(values)
    best = max(counts.values())
    return next(v for v in values if counts[v] == best)


_CASH_PATTERNS = [
    # "$36.50 per Share, to the seller thereof in cash"
    re.compile(
        rf"\$\s?({_NUM})\s+per\s+(?:share|Share)\b(?:(?!\$).){{0,90}}?\bin\s+cash", re.DOTALL
    ),
    # "right to receive $40.00 in cash" / "for $16.00 in cash"
    re.compile(
        rf"(?:receive|for|of|equal to)\s+\$\s?({_NUM})\s+(?:per\s+share\s+)?in\s+cash",
        re.IGNORECASE,
    ),
]
_RATIO_PATTERN = re.compile(
    r"(\d{0,2}\.\d{2,5}|\d{1,2})\s+(?:of\s+a\s+|validly issued[^.]{0,40}?)?"
    r"(?:fully\s+paid\s+(?:and\s+)?nonassessable\s+)?shares?\s+of\s+"
    r"(?:the\s+)?(?:common\s+stock\s+of\s+)?"
    r"([A-Z][A-Za-z0-9&.'\- ]{1,50}?)\s+(?:common|ordinary|Class\s+[A-Z]|American)",
)
_PAR = re.compile(r"par\s+value|nominal\s+value", re.IGNORECASE)


def find_cash(text: str) -> tuple[float | None, list[str]]:
    """Cash consideration per target share, ignoring par values."""
    vals, ev = [], []
    for pat in _CASH_PATTERNS:
        for m in pat.finditer(text):
            if _PAR.search(text[max(0, m.start() - 40) : m.start()]):
                continue
            v = _num(m.group(1))
            if v < 0.5:  # par values and fractions of a cent, not deal prices
                continue
            vals.append(v)
            if len(ev) < 2:
                ev.append(_snippet(text, m.start(), m.end()))
    return _mode(vals), ev


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 2} - {
        "inc",
        "corp",
        "the",
        "company",
        "holdings",
        "group",
        "ltd",
        "plc",
    }


def find_ratio(
    text: str, target_name: str | None = None
) -> tuple[float | None, str | None, list[str]]:
    """Exchange ratio (acquirer shares per target share) and the acquirer's name.

    Matches naming the target itself ("15 shares of Heinz common stock") are
    share counts, not exchange ratios, and are dropped.
    """
    target_words = _words(target_name) if target_name else set()
    found: list[tuple[float, str]] = []
    ev = []
    for m in _RATIO_PATTERN.finditer(text):
        tail = text[m.end() : m.end() + 160].lower()
        head = text[max(0, m.start() - 160) : m.start()].lower()
        if "for each" not in tail and "exchange ratio" not in tail + head and "each" not in head:
            continue
        r = float(m.group(1))
        name = m.group(2).strip()
        if not 0 < r <= 20 or (target_words and _words(name) & target_words):
            continue
        found.append((r, name))
        if len(ev) < 2:
            ev.append(_snippet(text, m.start(), m.end()))
    if not found:
        return None, None, []
    ratio = _mode([r for r, _ in found])
    name = Counter(n for r, n in found if r == ratio).most_common(1)[0][0]
    return ratio, name, ev


def _end_of_quarter(year: int, q: int) -> date:
    month = 3 * q
    day = 31 if month in (3, 12) else 30
    return date(year, month, day)


_CLOSE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (
        re.compile(
            r"expire[sd]?\s+at\s+.{0,100}?\bon\s+(?:[A-Z][a-z]+day,\s+)?(January|February|March|April|May|June|July|"
            r"August|September|October|November|December)\s+(\d{1,2}),\s+(20\d\d)",
            re.IGNORECASE,
        ),
        "tender offer expiry",
    ),
    (
        re.compile(
            r"(?:expect(?:ed)?|anticipate[sd]?)[^.]{0,120}?(?:close|closing|complet\w*|"
            r"consummat\w*)[^.]{0,80}?(first|second|third|fourth)\s+(?:calendar\s+|fiscal\s+)?"
            r"quarter\s+of\s+(20\d\d)",
            re.IGNORECASE,
        ),
        "expected quarter",
    ),
    (
        re.compile(
            r"(?:expect(?:ed)?|anticipate[sd]?)[^.]{0,120}?(?:close|closing|complet\w*|"
            r"consummat\w*)[^.]{0,80}?(first|second)\s+half\s+of\s+(20\d\d)",
            re.IGNORECASE,
        ),
        "expected half",
    ),
    (
        re.compile(
            r"(?:expect(?:ed)?|anticipate[sd]?)[^.]{0,120}?(?:close|closing|complet\w*|"
            r"consummat\w*)[^.]{0,60}?(?:by\s+)?(?:the\s+)?end\s+of\s+(20\d\d)",
            re.IGNORECASE,
        ),
        "expected year-end",
    ),
    (
        re.compile(
            r"(?:expect(?:ed)?|anticipate[sd]?)[^.]{0,120}?(?:close|closing|complet\w*|"
            r"consummat\w*)[^.]{0,60}?\b(early|mid|late)[- ](20\d\d)",
            re.IGNORECASE,
        ),
        "expected early/mid/late",
    ),
]
_PART_OF_YEAR = {"early": (3, 31), "mid": (6, 30), "late": (12, 31)}


def find_expected_close(
    text: str, after: date | None = None
) -> tuple[date | None, str | None, list[str]]:
    """Expected close date from a tender-offer expiry or a stated quarter/half/year.

    Patterns are tried in priority order; within each, the first match dated
    after ``after`` wins, so stale dates (an old option expiry, a prior
    deadline) are skipped.
    """
    for pat, basis in _CLOSE_PATTERNS:
        for m in pat.finditer(text):
            g = m.groups()
            try:
                if basis == "tender offer expiry":
                    d = date(int(g[2]), MONTHS[g[0].lower()], int(g[1]))
                elif basis == "expected quarter":
                    d = _end_of_quarter(int(g[1]), ORDINAL[g[0].lower()])
                elif basis == "expected half":
                    d = _end_of_quarter(int(g[1]), 2 if g[0].lower() == "first" else 4)
                elif basis == "expected year-end":
                    d = date(int(g[0]), 12, 31)
                else:
                    m_, d_ = _PART_OF_YEAR[g[0].lower()]
                    d = date(int(g[1]), m_, d_)
            except ValueError:
                continue
            if after is None or d > after:
                return d, basis, [_snippet(text, m.start(), m.end(), pad=20)]
    return None, None, []


def extract_terms(text: str, after: date | None = None, target_name: str | None = None) -> Terms:
    """Run every extractor over one filing's plain text."""
    t = Terms()
    t.cash, ev_c = find_cash(text)
    t.ratio, t.acquirer_name, ev_r = find_ratio(text, target_name)
    t.expected_close, t.close_basis, ev_d = find_expected_close(text, after)
    t.has_cvr = bool(re.search(r"contingent\s+value\s+right", text, re.IGNORECASE))
    t.has_ticking_fee = bool(re.search(r"ticking\s+fee", text, re.IGNORECASE))
    t.has_election = bool(
        re.search(r"(?:cash|stock|mixed)\s+election|election\s+to\s+receive", text, re.IGNORECASE)
    )
    t.evidence = ev_c + ev_r + ev_d
    return t
