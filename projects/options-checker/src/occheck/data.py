"""Free market-data loaders: Cboe index histories and FRED T-bill rates.

The project never republishes these files. In the browser the user downloads them
from the links in :data:`SOURCES` and drops them on the page; ``occheck serve``
downloads them on the user's own machine (:func:`download`, cached locally).

Supported files (as published on 2026-11-05):

=====  ==========================================================  =====================
kind   header                                                      values
=====  ==========================================================  =====================
SPX    ``DATE,SPX``                                                index close
PUT    ``DATE,PUT``                                                Cboe PutWrite index
BXM    ``DATE,BXM``                                                Cboe BuyWrite index
VIX    ``DATE,OPEN,HIGH,LOW,CLOSE``                                close, in vol points
DTB3   ``observation_date,DTB3`` (or ``DATE,DTB3``)                3-month T-bill, % a year
=====  ==========================================================  =====================
"""

from __future__ import annotations

import csv
import io
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

_CBOE = "https://cdn-api.cboe.com/api/global/us_indices/daily_prices/{}_History.csv"
SOURCES: dict[str, dict[str, str]] = {
    "SPX": {"url": _CBOE.format("SPX"), "label": "S&P 500 index (Cboe)"},
    "VIX": {"url": _CBOE.format("VIX"), "label": "VIX volatility index (Cboe)"},
    "PUT": {"url": _CBOE.format("PUT"), "label": "Cboe S&P 500 PutWrite index"},
    "BXM": {"url": _CBOE.format("BXM"), "label": "Cboe S&P 500 BuyWrite index"},
    "DTB3": {
        "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTB3",
        "label": "3-month Treasury bill rate (FRED)",
    },
}


USER_AGENT = "occheck/0.1 (+https://github.com/Tequilla1318/ClaudeSWEDev)"


class DataFormatError(ValueError):
    """A file isn't one of the supported histories. The message says what was expected."""


@dataclass(frozen=True)
class Series:
    """A daily time series. ``dates`` are numpy ``datetime64[D]``, sorted ascending."""

    kind: str
    dates: NDArray[np.datetime64]
    values: NDArray[np.float64]

    def __len__(self) -> int:
        return len(self.dates)

    @property
    def start(self) -> str:
        """First date, ISO format."""
        return str(self.dates[0])

    @property
    def end(self) -> str:
        """Last date, ISO format."""
        return str(self.dates[-1])


def _parse_day(text: str) -> np.datetime64:
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return np.datetime64(datetime.strptime(text.strip(), fmt).date(), "D")
        except ValueError:
            continue
    raise DataFormatError(f"unrecognized date {text!r}")


def detect_kind(text: str) -> str:
    """Identify which supported file ``text`` is, from its header row."""
    header = [h.strip().upper() for h in text.lstrip("﻿").splitlines()[0].split(",")]
    if header[:2] == ["DATE", "OPEN"] and "CLOSE" in header:
        return "VIX"
    if len(header) == 2 and header[0] in {"DATE", "OBSERVATION_DATE"} and header[1] in SOURCES:
        return header[1]
    expected = ", ".join(SOURCES)
    raise DataFormatError(
        f"unrecognized file header {','.join(header)!r}; expected one of {expected}"
    )


def load_csv(text: str) -> Series:
    """Parse any supported history file into a :class:`Series` (missing values dropped)."""
    kind = detect_kind(text)
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    header = [h.strip().upper() for h in next(reader)]
    col = header.index("CLOSE") if kind == "VIX" else 1
    days, vals = [], []
    for row in reader:
        if not row or not row[0].strip():
            continue
        raw = row[col].strip() if len(row) > col else ""
        if raw in {"", "."}:  # FRED marks holidays with "."
            continue
        days.append(_parse_day(row[0]))
        vals.append(float(raw))
    if not days:
        raise DataFormatError(f"{kind} file has no data rows")
    dates = np.array(days, dtype="datetime64[D]")
    values = np.array(vals, dtype=float)
    order = np.argsort(dates, kind="stable")
    dates, values = dates[order], values[order]
    keep = np.concatenate([dates[1:] != dates[:-1], [True]])  # last value wins on duplicates
    return Series(kind, dates[keep], values[keep])


def align(
    base: Series, *others: Series
) -> tuple[NDArray[np.datetime64], list[NDArray[np.float64]]]:
    """Put series on ``base``'s dates, carrying each other series' last value forward.

    Dates before an other series' first observation are dropped, so every output
    array is fully populated. Returns ``(dates, [base_values, *other_values])``.
    """
    start = max([base.dates[0], *[o.dates[0] for o in others]])
    mask = base.dates >= start
    dates = base.dates[mask]
    out = [base.values[mask]]
    for o in others:
        idx = np.searchsorted(o.dates, dates, side="right") - 1
        out.append(o.values[idx])
    return dates, out


def cache_dir() -> Path:
    """Where ``occheck serve`` keeps downloaded files (``~/.cache/occheck``)."""
    return Path.home() / ".cache" / "occheck"


def download(kind: str, directory: Path | None = None, timeout: float = 60.0) -> Path:
    """Download one history file to ``directory`` (default :func:`cache_dir`). Localhost only.

    The download happens on the user's own machine, from the publisher's site.
    """
    if kind not in SOURCES:
        raise ValueError(f"unknown data kind {kind!r}; expected one of {', '.join(SOURCES)}")
    directory = Path(directory or cache_dir())
    directory.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(SOURCES[kind]["url"], headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed https URLs
        text = resp.read().decode("utf-8")
    load_csv(text)  # refuse to cache something we can't parse
    path = directory / f"{kind}.csv"
    path.write_text(text)
    return path
