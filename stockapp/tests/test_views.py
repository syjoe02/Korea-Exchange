from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_client():
    user = User.objects.create_user(
        username="testuser", email="test@example.com", password="pass1234!"
    )
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


@pytest.mark.django_db
class TestCustomTokenCreateView:
    def test_login_with_email(self, api_client):
        User.objects.create_user(
            username="user1", email="user1@example.com", password="pass1234!"
        )
        response = api_client.post(
            "/auth/token/login/",
            {"username_or_email": "user1@example.com", "password": "pass1234!"},
        )
        assert response.status_code == 200
        assert "token" in response.data

    def test_login_with_username(self, api_client):
        User.objects.create_user(
            username="user2", email="user2@example.com", password="pass1234!"
        )
        response = api_client.post(
            "/auth/token/login/",
            {"username_or_email": "user2", "password": "pass1234!"},
        )
        assert response.status_code == 200
        assert "token" in response.data

    def test_login_invalid_credentials(self, api_client):
        response = api_client.post(
            "/auth/token/login/",
            {"username_or_email": "nobody", "password": "wrong"},
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestStockQueryAPIView:
    def test_missing_polygon_key_returns_503(self, auth_client, monkeypatch):
        monkeypatch.delenv("POLYGON_API_KEY", raising=False)
        with patch(
            "stockapp.services.nlp_service.extract_stock_info",
            return_value=("Apple", "150", "greater_than_equal"),
        ):
            response = auth_client.post("/api/stock-query/", {"query": "Apple stock above 150"})
        assert response.status_code == 503

    def test_empty_query_returns_400(self, auth_client):
        response = auth_client.post("/api/stock-query/", {"query": ""})
        assert response.status_code == 400


@pytest.mark.django_db
class TestStockDataSearchAPIView:
    def test_returns_stock_data(self, auth_client):
        mock_data = [{"Date": "2023-01-01", "Close": 150.0}]
        with patch("stockapp.views.get_stock_data", return_value=mock_data):
            response = auth_client.post(
                "/api/stock-data-search/",
                {"ticker": "AAPL", "price": 150.0, "comparison_type": "greater_than_equal"},
            )
        assert response.status_code == 200
        assert response.data["ticker"] == "AAPL"
        assert response.data["comparison_type"] == "greater_than_equal"

    def test_no_data_returns_404(self, auth_client):
        with patch("stockapp.views.get_stock_data", return_value=[]):
            response = auth_client.post(
                "/api/stock-data-search/",
                {"ticker": "FAKE", "price": 999.0, "comparison_type": "greater_than_equal"},
            )
        assert response.status_code == 404
