"""Scanner tests with fixed inputs; no network."""

from datetime import date

from mergerarb.scan import (
    Status,
    build_record,
    clean_name,
    match_ticker,
    pick_candidates,
    status_from_submissions,
)
from mergerarb.sources import Hit, PriceHistory, parse_hits, parse_yahoo

TODAY = date(2026, 11, 5)


def hit(form, filed, ciks=(1, 2), names=("Target Co  (TGT)  (CIK 0000000001)",), sics=()):
    return Hit("0000000000-26-000001", "doc.htm", form, filed, ciks, names, sics)


def test_clean_name():
    assert clean_name("Pacira BioSciences, Inc.  (PCRX)  (CIK 0001396814)") == (
        "Pacira BioSciences, Inc."
    )
    assert clean_name("WAFD INC  (WAFD, WAFDP)  (CIK 0000936528)") == "WAFD INC"
    assert clean_name("HOLCIM LTD.  (CIK 0002016373)") == "HOLCIM LTD."


def test_pick_candidates_prefers_tender_then_definitive_and_skips_noise():
    hits = [
        hit("PREM14A", date(2026, 9, 1)),
        hit("DEFM14A", date(2026, 10, 1)),
        hit("SC TO-T/A", date(2026, 10, 20)),
        hit("DEFM14A", date(2026, 10, 2), ciks=(9,), sics=("6770",)),  # SPAC
        hit("DEFM14A", date(2026, 8, 1), ciks=(5,)),
        hit("DEFM14A", date(2026, 9, 1), ciks=(5,)),
    ]
    got = pick_candidates(hits)
    assert [(h.ciks[0], h.form, h.file_date) for h in got] == [
        (1, "DEFM14A", date(2026, 10, 1)),
        (5, "DEFM14A", date(2026, 9, 1)),
    ]


def test_status_from_submissions():
    sub = {
        "tickers": ["TGT"],
        "filings": {
            "recent": {
                "form": ["8-K", "8-K", "8-K", "25-NSE"],
                "filingDate": ["2026-10-20", "2026-06-01", "2026-03-11", "2026-01-10"],
                "items": ["1.02", "1.01,9.01", "1.01,7.01", ""],
            }
        },
    }
    st = status_from_submissions(sub, filed=date(2026, 9, 1))
    # The Form 25 predates the filing, so it isn't this deal's delisting.
    assert st == Status(delisted=False, terminated=True, announced=date(2026, 6, 1), ticker="TGT")
    sub["filings"]["recent"]["filingDate"][3] = "2026-10-25"
    assert status_from_submissions(sub, filed=date(2026, 9, 1)).delisted


def test_match_ticker():
    tickers = [
        {"ticker": "CTAS", "title": "CINTAS CORP"},
        {"ticker": "HTB", "title": "HomeTrust Bancshares, Inc."},
        {"ticker": "OLN", "title": "OLIN Corp"},
        {"ticker": "FHB", "title": "First Hawaiian, Inc."},
        {"ticker": "FHN", "title": "First Horizon Corp"},
    ]
    assert match_ticker("Cintas", tickers) == "CTAS"
    assert match_ticker("HomeTrust", tickers) == "HTB"
    assert match_ticker("First Hawaiian", tickers) == "FHB"
    assert match_ticker("First", tickers) is None  # ambiguous


def test_build_record_cash_tender():
    h = hit(
        "SC TO-T",
        date(2026, 10, 30),
        names=(
            "Pacira BioSciences, Inc.  (PCRX)  (CIK 0001396814)",
            "Viatris Inc  (CIK 0001792044)",
        ),
    )
    text = (
        "at $36.50 per Share, to the seller thereof in cash. The Offer will expire at one minute "
        "after 11:59 p.m., New York City time, on November 16, 2026."
    )
    st = Status(False, False, date(2026, 10, 15), "PCRX")
    r = build_record(h, st, text, TODAY, "VTRS", [])
    assert (r.target, r.acquirer, r.kind, r.cash, r.days_to_close) == (
        "Pacira BioSciences, Inc.",
        "Viatris Inc",
        "cash",
        36.5,
        11,
    )
    assert r.review is None and not r.flags


def test_build_record_needs_review_without_terms():
    r = build_record(
        hit("DEFM14A", date(2026, 10, 1)),
        Status(False, False, None, "TGT"),
        "a redomiciliation proxy with no price",
        TODAY,
        None,
        [],
    )
    assert r.review and "No cash price" in r.review
    assert any("Close date not found" in f for f in r.flags)


def test_parse_hits_and_yahoo():
    payload = {
        "hits": {
            "hits": [
                {
                    "_id": "0001140361-26-041224:ny20084254x1_sctot.htm",
                    "_source": {
                        "form": "SC TO-T",
                        "file_date": "2026-10-30",
                        "ciks": ["0001396814", "0001792044"],
                        "display_names": ["Pacira", "Viatris"],
                        "sics": ["2834"],
                    },
                }
            ]
        }
    }
    (h,) = parse_hits(payload)
    assert h.ciks == (1396814, 1792044)
    assert h.url.endswith("/1396814/000114036126041224/ny20084254x1_sctot.htm")
    y = {
        "chart": {
            "result": [
                {
                    "timestamp": [1780000000, 1780086400, 1780172800],
                    "indicators": {"quote": [{"close": [10.0, None, 11.0]}]},
                }
            ]
        }
    }
    ph = parse_yahoo("TGT", y)
    assert ph.closes == (10.0, 11.0)
    assert ph.close_before(ph.dates[1]) == (ph.dates[0], 10.0)
    assert isinstance(ph, PriceHistory)
