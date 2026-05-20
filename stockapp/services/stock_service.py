import logging
import os

import requests
import yfinance as yf

logger = logging.getLogger(__name__)


def search_polygon_ticker(company_name: str) -> list[dict]:
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        raise ValueError("POLYGON_API_KEY environment variable is not set")
    url = f"https://api.polygon.io/v3/reference/tickers?search={company_name}&active=true&apiKey={api_key}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        return [
            {
                "name": item.get("name", "N/A"),
                "ticker": item.get("ticker", "N/A"),
                "exchange": item.get("primary_exchange", "N/A"),
            }
            for item in data.get("results", [])
        ]
    except requests.exceptions.HTTPError as e:
        logger.error("Error fetching ticker for %s: %s", company_name, e)
        return []


def get_stock_data(ticker: str, price: float | str, comparison_type: str) -> list[dict]:
    stock = yf.Ticker(ticker)
    hist = stock.history(period="max")

    if hist.empty:
        return []

    hist.reset_index(inplace=True)

    if comparison_type == "greater_than_equal":
        result = hist[hist["Close"] >= float(price)]
    elif comparison_type == "less_than_equal":
        result = hist[hist["Close"] <= float(price)]
    else:
        return []

    result = result.copy()
    result["price_diff"] = abs(result["Close"] - float(price))
    sorted_data = result.sort_values(by="price_diff")
    sorted_data["Date"] = sorted_data["Date"].dt.strftime("%Y-%m-%d")

    return sorted_data.head(10).reset_index()[["Date", "Close"]].to_dict(orient="records")
