import pytest

from stockapp.services.nlp_service import extract_stock_info


@pytest.mark.unit
class TestExtractStockInfo:
    def test_extracts_company_and_price_above(self):
        stock_name, price, comparison_type = extract_stock_info(
            "When did Apple stock exceed 150 dollars?"
        )
        assert stock_name == "Apple"
        assert price is not None
        assert comparison_type == "greater_than_equal"

    def test_extracts_below_comparison(self):
        _, _, comparison_type = extract_stock_info(
            "Show me dates when Google stock was below 100 dollars"
        )
        assert comparison_type == "less_than_equal"

    def test_returns_none_for_empty_query(self):
        stock_name, price, comparison_type = extract_stock_info("")
        assert stock_name is None
        assert price is None
        assert comparison_type == "greater_than_equal"

    def test_default_comparison_is_greater_than_equal(self):
        _, _, comparison_type = extract_stock_info("Apple stock at 200 dollars")
        assert comparison_type == "greater_than_equal"
