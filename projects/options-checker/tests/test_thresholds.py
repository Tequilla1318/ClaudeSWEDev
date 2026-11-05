"""Threshold defaults match docs/research/thresholds.md, and the page exposes every one."""

from dataclasses import fields
from pathlib import Path

import pytest

from occheck.audit import Thresholds
from occheck.brokers.ibkr_flex import ParseResult
from occheck.report import build_report
from occheck.roundtrips import RoundTrip

ROOT = Path(__file__).resolve().parent.parent
DOC = (ROOT / "docs" / "research" / "thresholds.md").read_text()
PAGE = (ROOT / "src" / "occheck" / "web" / "audit.html").read_text()


@pytest.mark.parametrize("name", [f.name for f in fields(Thresholds)])
def test_every_threshold_is_documented_and_adjustable(name):
    assert f"`{name}`" in DOC, f"{name} missing from thresholds.md"
    assert f'data-th="{name}"' in PAGE, f"{name} has no input on audit.html"


def test_disposition_watch_and_flag(monkeypatch):
    from datetime import datetime, timedelta

    from occheck import report as rep

    t0 = datetime(2025, 1, 1)

    def rt(pnl, days):
        return RoundTrip("X", "X", "STK", "long", 1, 1, t0, t0 + timedelta(days=days), 10,
                         10 + pnl, 0, "closed")  # fmt: skip

    for loser_days, status in ((1.3, "watch"), (1.6, "flag"), (1.0, "ok")):
        rts = [rt(1, 1.0) for _ in range(5)] + [rt(-1, loser_days) for _ in range(5)]
        monkeypatch.setattr(
            rep, "match_round_trips", lambda _t, r=rts: type("M", (), {"round_trips": r})
        )
        out = build_report(ParseResult(trades=[]), convention="broker")
        assert next(m for m in out["metrics"] if m["id"] == "disposition")["status"] == status
