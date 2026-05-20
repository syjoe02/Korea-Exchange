import pytest
from django.contrib.auth import get_user_model

from stockapp.serializers import CustomTokenCreateSerializer

User = get_user_model()


@pytest.mark.django_db
class TestCustomTokenCreateSerializer:
    def test_valid_email_login(self):
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="pass1234!"
        )
        serializer = CustomTokenCreateSerializer(
            data={"username_or_email": "test@example.com", "password": "pass1234!"}
        )
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["user"] == user

    def test_valid_username_login(self):
        user = User.objects.create_user(
            username="testuser2", email="test2@example.com", password="pass1234!"
        )
        serializer = CustomTokenCreateSerializer(
            data={"username_or_email": "testuser2", "password": "pass1234!"}
        )
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["user"] == user

    def test_invalid_credentials_raises_error(self):
        serializer = CustomTokenCreateSerializer(
            data={"username_or_email": "nobody@example.com", "password": "wrong"}
        )
        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors

    def test_missing_fields_raises_error(self):
        serializer = CustomTokenCreateSerializer(data={"username_or_email": "only-one-field"})
        assert not serializer.is_valid()
        assert "password" in serializer.errors
