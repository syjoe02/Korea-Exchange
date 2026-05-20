from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from stockapp.services.stock_service import get_stock_data, search_polygon_ticker


@pytest.mark.unit
class TestSearchPolygonTicker:
    def test_raises_when_api_key_missing(self, monkeypatch):
        monkeypatch.delenv("POLYGON_API_KEY", raising=False)
        with pytest.raises(ValueError, match="POLYGON_API_KEY"):
            search_polygon_ticker("Apple")

    def test_returns_company_options(self, monkeypatch):
        monkeypatch.setenv("POLYGON_API_KEY", "test-key")
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"name": "Apple Inc.", "ticker": "AAPL", "primary_exchange": "XNAS"}
            ]
        }
        with patch("stockapp.services.stock_service.requests.get", return_value=mock_response):
            result = search_polygon_ticker("Apple")
        assert result == [{"name": "Apple Inc.", "ticker": "AAPL", "exchange": "XNAS"}]

    def test_returns_empty_list_on_http_error(self, monkeypatch):
        import requests as req

        monkeypatch.setenv("POLYGON_API_KEY", "test-key")
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = req.exceptions.HTTPError("404")
        with patch("stockapp.services.stock_service.requests.get", return_value=mock_response):
            result = search_polygon_ticker("UnknownCorp")
        assert result == []


@pytest.mark.unit
class TestGetStockData:
    def _make_hist(self, prices: list[float]) -> pd.DataFrame:
        dates = pd.date_range("2023-01-01", periods=len(prices), tz="UTC")
        return pd.DataFrame({"Date": dates, "Close": prices})

    def test_filters_greater_than_equal(self):
        hist = self._make_hist([90.0, 100.0, 110.0, 120.0])
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = hist
        with patch("stockapp.services.stock_service.yf.Ticker", return_value=mock_ticker):
            result = get_stock_data("AAPL", 100.0, "greater_than_equal")
        closes = [r["Close"] for r in result]
        assert all(c >= 100.0 for c in closes)

    def test_filters_less_than_equal(self):
        hist = self._make_hist([90.0, 100.0, 110.0, 120.0])
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = hist
        with patch("stockapp.services.stock_service.yf.Ticker", return_value=mock_ticker):
            result = get_stock_data("AAPL", 100.0, "less_than_equal")
        closes = [r["Close"] for r in result]
        assert all(c <= 100.0 for c in closes)

    def test_returns_empty_for_empty_history(self):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        with patch("stockapp.services.stock_service.yf.Ticker", return_value=mock_ticker):
            result = get_stock_data("INVALID", 100.0, "greater_than_equal")
        assert result == []

    def test_returns_at_most_10_records(self):
        hist = self._make_hist([float(i) for i in range(100, 200)])
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = hist
        with patch("stockapp.services.stock_service.yf.Ticker", return_value=mock_ticker):
            result = get_stock_data("AAPL", 150.0, "greater_than_equal")
        assert len(result) <= 10
