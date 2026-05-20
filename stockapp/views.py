import logging
from datetime import datetime, timedelta

from django.http import HttpResponse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import KospiData, StockQueryLog
from .serializers import (
    CustomTokenCreateSerializer,
    KospiDataSerializer,
    StockDataSearchSerializer,
    StockQuerySerializer,
)
from .services.export_service import build_stock_excel
from .services.nlp_service import extract_stock_info
from .services.stock_service import get_stock_data, search_polygon_ticker

logger = logging.getLogger(__name__)


class CustomTokenCreateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = CustomTokenCreateSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data["user"]
        token, created = Token.objects.get_or_create(user=user)

        return Response({"token": token.key}, status=status.HTTP_200_OK)


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


class StockQueryAPIView(APIView):
    def post(self, request):
        serializer = StockQuerySerializer(data=request.data)

        if serializer.is_valid():
            query = serializer.validated_data.get("query")
            StockQueryLog.objects.create(query=query)

            company, price, comparison_type = extract_stock_info(query)

            if not company or not price:
                return Response(
                    {"error": "Unable to extract stock information"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                company_options = search_polygon_ticker(company)
            except ValueError as e:
                return Response({"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

            if len(company_options) == 0:
                return Response(
                    {"error": "No stock data available for the given query"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            return Response(
                {
                    "company_options": company_options,
                    "price": price,
                    "comparison_type": comparison_type,
                },
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StockDataSearchAPIView(APIView):
    def post(self, request):
        serializer = StockDataSearchSerializer(data=request.data)

        if serializer.is_valid():
            ticker = serializer.validated_data.get("ticker")
            price = serializer.validated_data.get("price")
            comparison_type = serializer.validated_data.get("comparison_type")

            stock_data = get_stock_data(ticker, price, comparison_type)

            if len(stock_data) == 0:
                return Response(
                    {"Error": "No stock data found for the given query"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            return Response(
                {
                    "ticker": ticker,
                    "price": price,
                    "comparison_type": comparison_type,
                    "stock_data": stock_data,
                },
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StockExportExcelAPIView(APIView):
    def post(self, request):
        serializer = StockQuerySerializer(data=request.data)

        if serializer.is_valid():
            query = serializer.validated_data.get("query")

            stock_symbol, price, comparison_type = extract_stock_info(query)

            if not stock_symbol or not price:
                return Response(
                    {"error": "Unable to extract stock information"}, status=400
                )

            try:
                data = get_stock_data(stock_symbol, price, comparison_type)
            except Exception:
                return Response({"error": "Failed to retrieve stock data"}, status=404)

            output = build_stock_excel(data)

            response = HttpResponse(
                output,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = (
                f"attachment; filename={stock_symbol}_stock_data.xlsx"
            )
            return response

        return Response(serializer.errors, status=400)
