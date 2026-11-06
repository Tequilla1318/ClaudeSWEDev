"""Extraction tests on wording taken from real 2026 merger filings (shortened)."""

from datetime import date

import pytest

from mergerarb.extract import (
    extract_terms,
    find_cash,
    find_expected_close,
    find_ratio,
    html_to_text,
)

TENDER = (
    "Offer to purchase all outstanding shares of common stock, par value $0.001 per share "
    '("Shares"), of Pacira BioSciences, Inc. at $36.50 per Share, to the seller thereof in cash, '
    "net of applicable withholding taxes and without interest. The Offer and withdrawal rights "
    "will expire at one minute after 11:59 p.m., New York City time, on November 16, 2026, "
    "unless the Offer is extended."
)
CASH_AND_STOCK = (
    "each share of UniFirst stock will be converted into the right to receive $155.00 in cash, "
    "without interest, and 0.7720 shares of Cintas common stock for each share held. "
    "We expect the merger to be completed in the second half of 2027."
)
SMALL_RATIO = (
    "Blue Ridge shareholders will receive 0.086 of a share of HomeTrust common stock "
    '(the "exchange ratio") for each share of Blue Ridge common stock they own. '
    "HomeTrust and Blue Ridge expect the mergers will be completed early in the first "
    "quarter of 2027."
)
TODAY = date(2026, 11, 5)


def test_tender_offer_cash_skips_par_value():
    cash, ev = find_cash(TENDER)
    assert cash == 36.50
    assert ev and "36.50" in ev[0]


def test_tender_offer_expiry_despite_periods_in_pm():
    d, basis, _ = find_expected_close(TENDER, after=TODAY)
    assert (d, basis) == (date(2026, 11, 16), "tender offer expiry")


def test_cash_and_stock():
    t = extract_terms(CASH_AND_STOCK, after=TODAY)
    assert (t.cash, t.ratio, t.acquirer_name) == (155.0, 0.772, "Cintas")
    assert (t.expected_close, t.close_basis) == (date(2027, 12, 31), "expected half")


def test_ratio_below_point_one():
    ratio, name, _ = find_ratio(SMALL_RATIO)
    assert (ratio, name) == (0.086, "HomeTrust")
    assert find_cash(SMALL_RATIO)[0] is None


def test_quarter_close():
    d, basis, _ = find_expected_close(SMALL_RATIO, after=TODAY)
    assert (d, basis) == (date(2027, 3, 31), "expected quarter")


def test_past_dates_are_skipped():
    text = (
        "The options expire at 5:00 p.m. on June 1, 2026. "
        "We expect the merger to close in the first half of 2027."
    )
    d, basis, _ = find_expected_close(text, after=TODAY)
    assert (d, basis) == (date(2027, 6, 30), "expected half")


@pytest.mark.parametrize(
    "phrase,expected",
    [
        ("we anticipate the transaction will close in mid-2027", date(2027, 6, 30)),
        ("the merger is expected to be completed by the end of 2026", date(2026, 12, 31)),
        ("expected to close in late 2027", date(2027, 12, 31)),
    ],
)
def test_other_close_wordings(phrase, expected):
    assert find_expected_close(phrase + ".", after=TODAY)[0] == expected


def test_flags():
    t = extract_terms(
        "receive $31.00 per share in cash (plus the Per Share Ticking Fee, if applicable) and "
        "one contingent value right. Holders may make a cash election."
    )
    assert t.cash == 31.0
    assert t.has_ticking_fee and t.has_cvr and t.has_election


def test_html_to_text():
    raw = "<p>Price&nbsp;of <b>$10.00</b> per&#160;share</p><script>x=1</script>"
    assert html_to_text(raw) == "Price of $10.00 per share"
