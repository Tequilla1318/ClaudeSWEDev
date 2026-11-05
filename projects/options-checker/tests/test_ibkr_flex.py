from datetime import date, datetime
from pathlib import Path

import pytest

from occheck.brokers.ibkr_flex import FlexFormatError, parse_flex_csv

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def basic():
    return parse_flex_csv((FIXTURES / "flex_basic.csv").read_text())


def test_parses_supported_rows_and_skips_the_rest(basic):
    assert len(basic.trades) == 11
    assert basic.skipped["asset class FUT"] == 1
    assert basic.skipped["asset class CASH"] == 1
    assert basic.skipped["summary rows (LevelOfDetail not EXECUTION)"] == 1
    assert any("FUT" in w for w in basic.warnings)


def test_stock_fields(basic):
    t = next(t for t in basic.trades if t.trade_id == "1001")
    assert t.asset_class == "STK" and t.symbol == "AAPL"
    assert t.when == datetime(2025, 1, 6, 9, 35, 12)
    assert t.quantity == 100 and t.price == 180 and t.multiplier == 1
    assert t.commission == 1.0  # IBKR reports -1; stored as a positive cost
    assert t.open_close == "O" and t.cash_flow == -18000


def test_option_fields_and_codes(basic):
    t = next(t for t in basic.trades if t.trade_id == "1002")
    assert t.is_option and t.underlying == "AAPL"
    assert (t.right, t.strike, t.expiry, t.multiplier) == ("C", 190.0, date(2025, 1, 17), 100.0)
    assert t.quantity == -1 and t.cash_flow == 150.0 and t.dte == 11
    assert next(t for t in basic.trades if t.trade_id == "1003").codes == {"EXPIRED"}
    assert next(t for t in basic.trades if t.trade_id == "1005").codes == {"ASSIGNED"}


def test_sorted_by_time(basic):
    times = [t.when for t in basic.trades]
    assert times == sorted(times)


def test_contract_key_groups_same_option(basic):
    keys = {t.contract_key for t in basic.trades if t.underlying == "TSLA"}
    assert len(keys) == 1


HEADER = "AssetClass,Symbol,TradeDate,Quantity,TradePrice,IBCommission"


def test_minimal_columns_and_date_formats():
    text = HEADER + "\nSTK,MSFT,2025-03-04,10,400,-1\nSTK,MSFT,03/05/2025,-10,410,-1\n"
    res = parse_flex_csv(text)
    assert [t.when.date() for t in res.trades] == [date(2025, 3, 4), date(2025, 3, 5)]
    assert res.trades[0].trade_id == "row1" and res.trades[0].open_close is None


def test_missing_columns_listed():
    with pytest.raises(FlexFormatError, match="IBCommission"):
        parse_flex_csv("AssetClass,Symbol,TradeDate,Quantity,TradePrice\nSTK,X,20250101,1,1\n")
    with pytest.raises(FlexFormatError, match="DateTime or TradeDate"):
        parse_flex_csv("AssetClass,Symbol,Quantity,TradePrice,IBCommission\nSTK,X,1,1,0\n")


def test_options_without_option_columns_rejected():
    with pytest.raises(FlexFormatError, match="Put/Call"):
        parse_flex_csv(HEADER + "\nOPT,X 250101C1,20250101,1,1,0\n")


def test_not_a_flex_file():
    with pytest.raises(FlexFormatError, match="Trades header"):
        parse_flex_csv("hello,world\n1,2\n")


def test_multiple_currencies_warned():
    text = HEADER + ",CurrencyPrimary\nSTK,A,20250101,1,1,0,USD\nSTK,B,20250101,1,1,0,CAD\n"
    assert any("currencies" in w for w in parse_flex_csv(text).warnings)


def test_falls_back_to_order_level():
    text = HEADER + ",LevelOfDetail\nSTK,A,20250101,1,1,0,ORDER\nSTK,A,20250101,1,1,0,SUMMARY\n"
    res = parse_flex_csv(text)
    assert len(res.trades) == 1 and res.skipped["summary rows (LevelOfDetail not ORDER)"] == 1
