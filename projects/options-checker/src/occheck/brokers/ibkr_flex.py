"""Parser for Interactive Brokers Flex Query CSV exports (Trades section).

How users get the file: IBKR Portal → Performance & Reports → Flex Queries →
create an Activity Flex Query with the **Trades** section, format **CSV**, then run
it for the period they want. Column names below are IBKR's Flex field names.

Required columns: see :data:`REQUIRED_COLUMNS`. Everything else is optional and
improves the report (e.g. ``Open/CloseIndicator``, ``Notes/Codes``).

Tolerated quirks: repeated header rows (multi-account or multi-section queries),
``BOF``/``BOA``/``BOS``/``EOS``/``EOA``/``EOF`` marker lines, several date formats,
and ``LevelOfDetail`` (keeps ``EXECUTION`` rows; falls back to ``ORDER`` rows).
Asset classes other than stocks and equity/index options are skipped with a warning.
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime

from occheck.trades import Trade

REQUIRED_COLUMNS: tuple[str, ...] = (
    "AssetClass",
    "Symbol",
    "Quantity",
    "TradePrice",
    "IBCommission",
)
DATE_COLUMNS: tuple[str, ...] = ("DateTime", "TradeDate")
OPTION_COLUMNS: tuple[str, ...] = ("Put/Call", "Strike", "Expiry")

_MARKERS = {"BOF", "BOA", "BOS", "EOS", "EOA", "EOF", "HEADER", "DATA"}
_CODE_MAP = {"Ep": "EXPIRED", "A": "ASSIGNED", "Ex": "EXERCISED"}
_SUPPORTED = {"STK": "STK", "OPT": "OPT"}


class FlexFormatError(ValueError):
    """The file is not a usable Flex Trades CSV. The message says what's missing."""


@dataclass
class ParseResult:
    """Parsed trades plus anything the user should know about the file."""

    trades: list[Trade]
    warnings: list[str] = field(default_factory=list)
    skipped: Counter = field(default_factory=Counter)


def _parse_date(text: str) -> date:
    text = text.strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise FlexFormatError(f"unrecognized date {text!r}")


def _parse_datetime(text: str) -> datetime:
    text = text.strip().replace(",", " ").replace(";", " ")
    parts = text.split()
    day = _parse_date(parts[0])
    if len(parts) == 1:
        return datetime(day.year, day.month, day.day)
    clock = parts[1].replace(":", "")
    if not (clock.isdigit() and len(clock) == 6):
        raise FlexFormatError(f"unrecognized time {parts[1]!r}")
    return datetime(day.year, day.month, day.day, int(clock[:2]), int(clock[2:4]), int(clock[4:]))


def _num(text: str | None, default: float | None = None) -> float | None:
    if text is None or text.strip() in {"", "--", "N/A"}:
        return default
    return float(text.replace(",", ""))


def _codes(text: str | None) -> frozenset[str]:
    if not text:
        return frozenset()
    return frozenset(_CODE_MAP[c] for c in text.replace(",", ";").split(";") if c in _CODE_MAP)


def _is_header(row: list[str]) -> bool:
    return "AssetClass" in row and "Symbol" in row


def _rows(text: str) -> tuple[list[str], list[list[str]]]:
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    header: list[str] | None = None
    rows: list[list[str]] = []
    for row in reader:
        row = [c.strip() for c in row]
        if not row or not any(row) or row[0] in _MARKERS:
            continue
        if _is_header(row):
            if header is None:
                header = row
            continue  # repeated header from another section/account
        if header is not None:
            rows.append(row)
    if header is None:
        raise FlexFormatError(
            "no Trades header found. Export a Flex Query with the Trades section in CSV format."
        )
    return header, rows


def parse_flex_csv(text: str) -> ParseResult:
    """Parse a Flex Trades CSV export into :class:`Trade` objects.

    Raises :class:`FlexFormatError` if required columns are missing.
    """
    header, raw_rows = _rows(text)
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if not any(c in header for c in DATE_COLUMNS):
        missing.append(" or ".join(DATE_COLUMNS))
    if missing:
        raise FlexFormatError("missing required column(s): " + ", ".join(missing))

    records = [dict(zip(header, r, strict=False)) for r in raw_rows]
    result = ParseResult(trades=[])
    if "LevelOfDetail" in header:
        levels = {r.get("LevelOfDetail", "").upper() for r in records}
        keep = "EXECUTION" if "EXECUTION" in levels else "ORDER"
        dropped = [r for r in records if r.get("LevelOfDetail", "").upper() != keep]
        if dropped:
            result.skipped[f"LevelOfDetail != {keep}"] += len(dropped)
        records = [r for r in records if r.get("LevelOfDetail", "").upper() == keep]

    has_option_cols = all(c in header for c in OPTION_COLUMNS)
    for i, r in enumerate(records):
        asset = _SUPPORTED.get(r["AssetClass"].upper())
        if asset is None:
            result.skipped[f"asset class {r['AssetClass'] or '(blank)'}"] += 1
            continue
        if asset == "OPT" and not has_option_cols:
            raise FlexFormatError(
                "option trades need columns: "
                + ", ".join(OPTION_COLUMNS)
                + " (add them to the query)"
            )
        when_text = r.get("DateTime") or r.get("TradeDate") or ""
        right = r.get("Put/Call", "").upper()[:1] or None
        oc = r.get("Open/CloseIndicator", "").upper()
        result.trades.append(
            Trade(
                trade_id=r.get("TradeID") or f"row{i + 1}",
                when=_parse_datetime(when_text),
                symbol=r["Symbol"],
                underlying=r.get("UnderlyingSymbol") or r["Symbol"].split()[0],
                asset_class=asset,
                quantity=_num(r["Quantity"], 0.0),
                price=_num(r["TradePrice"], 0.0),
                multiplier=_num(r.get("Multiplier"), 100.0 if asset == "OPT" else 1.0),
                commission=abs(_num(r["IBCommission"], 0.0)),
                currency=r.get("CurrencyPrimary") or "USD",
                right=right if asset == "OPT" else None,
                strike=_num(r.get("Strike")) if asset == "OPT" else None,
                expiry=_parse_date(r["Expiry"]) if asset == "OPT" else None,
                open_close="O" if oc.startswith("O") else "C" if oc.startswith("C") else None,
                codes=_codes(r.get("Notes/Codes")),
            )
        )
    for reason, n in result.skipped.items():
        result.warnings.append(f"skipped {n} row(s): {reason}")
    currencies = {t.currency for t in result.trades}
    if len(currencies) > 1:
        result.warnings.append(
            "multiple currencies ("
            + ", ".join(sorted(currencies))
            + "): totals are not FX-converted"
        )
    result.trades.sort(key=lambda t: (t.when, t.trade_id))
    return result
