"""Cboe delayed-quote parsing and the local /quotes endpoint, on synthetic JSON."""

import json
import os
from datetime import date

import pytest

from occheck import quotes, site

DOC = {
    "timestamp": "2026-11-05 14:30:04",
    "data": {
        "symbol": "XYZ",
        "current_price": 101.5,
        "iv30": 24.1,
        "options": [
            {"option": "XYZ261218C00100000", "bid": 4.1, "ask": 4.3, "iv": 0.25, "delta": 0.55,
             "open_interest": 10, "volume": 2},
            {"option": "XYZ261218P00100000", "bid": 2.4, "ask": 2.6, "iv": 0.26, "delta": -0.45},
            {"option": "XYZ261218P00090000", "bid": 0.0, "ask": 0.0, "iv": 0, "delta": 0},
            {"option": "XYZ270115C00110000", "bid": 1.0, "ask": 1.2, "iv": 0.23, "delta": 0.3},
            {"option": "garbage", "bid": 1, "ask": 2},
        ],
    },
}  # fmt: skip


def test_parse_occ():
    assert quotes.parse_occ("AAPL270115P00365000") == ("AAPL", date(2027, 1, 15), "P", 365.0)
    assert quotes.parse_occ("SPXW261118P07230000") == ("SPXW", date(2026, 11, 18), "P", 7230.0)
    assert quotes.parse_occ("BRK.B261218C00500500")[3] == 500.5
    with pytest.raises(quotes.QuoteError):
        quotes.parse_occ("nonsense")


def test_feed_symbol():
    assert quotes.feed_symbol("spx") == "_SPX" and quotes.feed_symbol("^VIX") == "_VIX"
    assert quotes.feed_symbol("aapl") == "AAPL"
    with pytest.raises(quotes.QuoteError):
        quotes.feed_symbol("../etc")


def test_load_chain_summary_and_expiry_rows():
    chain = quotes.load_chain(json.dumps(DOC))
    assert chain.spot == 101.5 and len(chain.options) == 4  # garbage row skipped
    s = quotes.summary(chain)
    assert s["expiries"] == ["2026-12-18", "2027-01-15"] and s["iv30"] == 24.1
    rows = quotes.expiry_rows(chain, date(2026, 12, 18))
    assert [(r["right"], r["strike"]) for r in rows] == [
        ("C", 100.0),
        ("P", 100.0),
    ]  # no-ask row dropped


def test_bad_feed():
    with pytest.raises(quotes.QuoteError, match="not a Cboe"):
        quotes.load_chain("<html>blocked</html>")
    with pytest.raises(quotes.QuoteError, match="no options"):
        quotes.load_chain(json.dumps({"data": {"current_price": 1, "options": []}}))


def test_quote_endpoint(monkeypatch):
    chain = quotes.load_chain(json.dumps(DOC))
    calls = []
    monkeypatch.setattr(quotes, "fetch_chain", lambda sym: calls.append(sym) or chain)
    assert site.quote_response("/quotes/ping") == (200, {"ok": True})
    status, body = site.quote_response("/quotes/XYZ.json")
    assert status == 200 and body["spot"] == 101.5 and len(body["expiries"]) == 2
    status, body = site.quote_response("/quotes/XYZ/2026-12-18.json")
    assert status == 200 and len(body["options"]) == 2
    assert site.quote_response("/quotes/XYZ/not-a-date.json")[0] == 502
    assert site.quote_response("/quotes/a/b/c")[0] == 404


def test_fetch_chain_caches(monkeypatch):
    quotes._CACHE.clear()
    n = []

    class R:
        def __init__(self):
            n.append(1)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(DOC).encode()

    monkeypatch.setattr(quotes.urllib.request, "urlopen", lambda req, timeout: R())
    quotes.fetch_chain("XYZ")
    quotes.fetch_chain("xyz")
    assert len(n) == 1


@pytest.mark.skipif(not os.environ.get("OCCHECK_LIVE"), reason="network test")
def test_live_cboe_chain():
    quotes._CACHE.clear()
    chain = quotes.fetch_chain("SPX")
    assert chain.spot > 1000 and len(quotes.summary(chain)["expiries"]) > 5
