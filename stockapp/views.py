from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.http import HttpResponse

from datetime import datetime, timedelta
from io import BytesIO
import yfinance as yf
import pandas as pd
import spacy
import requests
import os

from .models import KospiData
from .serializers import (
    KospiDataSerializer,
    CustomTokenCreateSerializer,
    StockQuerySerializer,
    StockDataSearchSerializer,
)


# Extract stock name and price using NLP
nlp = spacy.load("en_core_web_sm")


##### CustomTokenCreateSerializer #####
class CustomTokenCreateView(APIView):
    permission_classes = [
        AllowAny
    ]  # This is because the token must be sent without authentication

    def post(self, request, *args, **kwargs):
        serializer = CustomTokenCreateSerializer(data=request.data)
        # serializer.is_valid(raise_exception=True)

        if not serializer.is_valid():
            return Response(serializer.errors, status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data["user"]
        token, created = Token.objects.get_or_create(user=user)

        return Response({"token": token.key}, status=status.HTTP_200_OK)


##### Stored Kospi data in SQL (from 1996.12.11) #####
@api_view(["GET"])
def latest_kospi_data(request):
    fifty_days = datetime.now().date() - timedelta(days=10)
    latest_data = KospiData.objects.filter(date__gte=fifty_days).order_by("-date")
    serializer = KospiDataSerializer(latest_data, many=True)

    return Response(serializer.data)


@api_view(["GET"])
def top3_close_price(request):
    top3_close_record = KospiData.objects.order_by("-close_price")[:3]

    if top3_close_record:
        response_data = [
            {
                "date": record.date,
                "close_price": record.close_price,
            }
            for record in top3_close_record
        ]
    else:
        response_data = {"error": "No data available"}

    return Response(response_data)


@api_view(["GET"])
def filter_kospi_data(request):
    close_price = request.query_params.get("close_price", None)

    if close_price is not None:
        kospi_data = KospiData.objects.filter(close_price__gt=close_price)
        serializer = KospiDataSerializer(kospi_data, many=True)

        return Response(serializer.data)

    return Response({"error": "No Close price provided."})


##### Reqeust information from API #####
def extract_stock_info(query):
    doc = nlp(query)
    stock_name = None
    price_threshold = None
    comparison_type = "greater_than_equal"  # default value

    # Extract price and stock name
    for ent in doc.ents:
        if ent.label_ in ["MONEY", "CARDINAL"]:  # price
            price_threshold = ent.text
        elif ent.label_ in ["ORG", "GPE"]:  # company name
            stock_name = ent.text

    # Determine comparison type based on keywords in the question
    for token in doc:
        if "exceed" in token.lemma_ or "greater" in token.text or "above" in token.text:
            comparison_type = "greater_than_equal"
        elif "less" in token.text or "below" in token.text:
            comparison_type = "less_than_equal"

    return stock_name, price_threshold, comparison_type


# View to process stock queries
def search_polygon_ticker(company_name):
    api_key = os.getenv("POLYGON_API_KEY")
    url = f"https://api.polygon.io/v3/reference/tickers?search={company_name}&active=true&apiKey={api_key}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        # Extract relevant company
        company_options = [
            {
                "name": item.get("name", "N/A"),
                "ticker": item.get("ticker", "N/A"),
                "exchange": item.get("primary_exchange", "N/A"),
            }
            for item in data.get("results", [])
        ]

        return company_options
    except requests.exceptions.HTTPError as e:
        print(f"Error fetching ticker for {company_name}: {e}")
        return []


class StockQueryAPIView(APIView):
    def post(self, request):
        serializer = StockQuerySerializer(data=request.data)

        if serializer.is_valid():
            query = serializer.validated_data.get("query")

            # 1. Extract company name and price
            company, price, comparison_type = extract_stock_info(query)

            if not company or not price:
                return Response(
                    {"error": "Unable to extract stock information"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # 2. Search for tickers
            company_options = search_polygon_ticker(company)

            print(company_options)

            if len(company_options) == 0:
                return Response(
                    {"error": "No stock data available for the given query"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # 3. Return company and ticker
            return Response(
                {
                    "company_options": company_options,
                    "price": price,
                    "comparison_type": comparison_type,
                },
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


##### Search #####


# Fetch stock data using yfinance
def get_stock_data(ticker, price, comparison_type):
    stock = yf.Ticker(ticker)
    hist = stock.history(period="max")

    if hist.empty:
        return []
    
    hist.reset_index(inplace=True)

    if comparison_type == "greater_than_equal":
        result = hist[hist["Close"] >= float(price)]
    elif comparison_type == "less_than_equal":
        result = hist[hist["Close"] <= float(price)]

    result.loc[:, "price_diff"] = abs(result["Close"] - float(price))
    sorted_data = result.sort_values(by="price_diff")
    sorted_data['Date'] = sorted_data['Date'].dt.strftime('%Y-%m-%d')
    
    return sorted_data.head(10).reset_index()[["Date", "Close"]].to_dict(orient="records")


class StockDataSearchAPIView(APIView):
    def post(self, request):
        serializer = StockDataSearchSerializer(data=request.data)

        if serializer.is_valid():
            ticker = serializer.validated_data.get("ticker")
            price = serializer.validated_data.get("price")
            comparison_type = serializer.validated_data.get("comparison_type")

            # 4. Fetch stock data and return
            stock_data = get_stock_data(ticker, price, comparison_type)

            if len(stock_data) == 0:
                return Response(
                    {"Error": "No stock data found for the given query"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Response data, latest 5 days
            return Response(
                {
                    "ticker": ticker,
                    "price": price,
                    "comparsion_type": comparison_type,
                    "stock_data": stock_data,
                },
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


##### Export Excel #####


class StockExportExcelAPIView(APIView):
    def post(self, request):
        serializer = StockQuerySerializer(data=request.data)

        if serializer.is_valid():
            query = serializer.validated_data.get("query")

            # Extract stock info
            stock_symbol, price = extract_stock_info(query)

            if not stock_symbol or not price:
                return Response(
                    {"error": "Unable to extract stock information"}, status=400
                )

            # Fetch stock data using yfinance
            try:
                data = get_stock_data(stock_symbol, price, "greater_than_equal")
            except Exception:
                return Response({"error": "Failed to retrieve stock data"}, status=404)

            # Filter data by price
            df = pd.DataFrame(data).reset_index()[["Date", "Close"]]

            # Create Excel file
            output = BytesIO()
            writer = pd.ExcelWriter(output, engine="openpyxl")
            df.to_excel(writer, index=False)
            writer.save()
            output.seek(0)

            response = HttpResponse(
                output,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = (
                f"attachment; filename={stock_symbol}_stock_data.xlsx"
            )
            return response

        return Response(serializer.errors, status=400)
