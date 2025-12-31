"""Tests for SecurityFactory class.

These tests validate the SecurityFactory class methods for creating Security objects.
"""

import pytest

from app.domain.exceptions import ValidationError
from app.domain.models import Security
from app.modules.universe.domain.security_factory import SecurityFactory
from app.shared.domain.value_objects.currency import Currency


class TestSecurityFactoryCreateFromApiRequest:
    """Test SecurityFactory.create_from_api_request method."""

    def test_create_stock_with_all_fields(self):
        """Test creating Security with all fields from API request."""
        data = {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "country": "United States",
            "fullExchangeName": "NASDAQ",
            "industry": "Technology",
            "min_lot": 1,
            "allow_buy": True,
            "allow_sell": False,
            "yahoo_symbol": "AAPL",
            "currency": Currency.USD,
        }

        security = SecurityFactory.create_from_api_request(data)

        assert isinstance(security, Security)
        assert security.symbol == "AAPL"
        assert security.name == "Apple Inc."
        assert security.country == "United States"
        assert security.fullExchangeName == "NASDAQ"
        assert security.industry == "Technology"
        assert security.min_lot == 1
        assert security.allow_buy is True
        assert security.allow_sell is False
        assert security.yahoo_symbol == "AAPL"
        assert security.currency == Currency.USD

    def test_create_stock_with_minimal_required_fields(self):
        """Test creating Security with minimal required fields."""
        data = {"symbol": "AAPL", "name": "Apple Inc."}

        security = SecurityFactory.create_from_api_request(data)

        assert security.symbol == "AAPL"
        assert security.name == "Apple Inc."
        assert security.min_lot == 1  # Default
        assert security.allow_buy is True  # Default
        assert security.allow_sell is False  # Default
        assert security.active is True  # Default

    def test_create_stock_normalizes_symbol(self):
        """Test that symbol is normalized to uppercase."""
        data = {"symbol": "aapl", "name": "Apple Inc."}

        security = SecurityFactory.create_from_api_request(data)

        assert security.symbol == "AAPL"

    def test_create_stock_raises_error_for_empty_symbol(self):
        """Test that empty symbol raises ValidationError."""
        data = {"symbol": "", "name": "Apple Inc."}

        with pytest.raises(ValidationError, match="Symbol cannot be empty"):
            SecurityFactory.create_from_api_request(data)

    def test_create_stock_raises_error_for_empty_name(self):
        """Test that empty name raises ValidationError."""
        data = {"symbol": "AAPL", "name": ""}

        with pytest.raises(ValidationError, match="Name cannot be empty"):
            SecurityFactory.create_from_api_request(data)

    def test_create_stock_raises_error_for_missing_symbol(self):
        """Test that missing symbol raises ValidationError."""
        data = {"name": "Apple Inc."}

        with pytest.raises(ValidationError, match="Symbol cannot be empty"):
            SecurityFactory.create_from_api_request(data)

    def test_create_stock_raises_error_for_missing_name(self):
        """Test that missing name raises ValidationError."""
        data = {"symbol": "AAPL"}

        with pytest.raises(ValidationError, match="Name cannot be empty"):
            SecurityFactory.create_from_api_request(data)

    def test_create_stock_with_currency_string(self):
        """Test creating Security with currency as string."""
        data = {"symbol": "AAPL", "name": "Apple Inc.", "currency": "USD"}

        security = SecurityFactory.create_from_api_request(data)

        assert security.currency == Currency.USD

    def test_create_stock_with_min_lot_validation(self):
        """Test that min_lot is validated (minimum 1)."""
        data = {"symbol": "AAPL", "name": "Apple Inc.", "min_lot": 0}

        security = SecurityFactory.create_from_api_request(data)

        assert security.min_lot == 1  # Should be corrected to 1

    def test_create_stock_strips_whitespace(self):
        """Test that symbol and name are stripped of whitespace."""
        data = {"symbol": "  AAPL  ", "name": "  Apple Inc.  "}

        security = SecurityFactory.create_from_api_request(data)

        assert security.symbol == "AAPL"
        assert security.name == "Apple Inc."


class TestSecurityFactoryCreateFromImport:
    """Test SecurityFactory.create_from_import method."""

    def test_create_stock_from_import_with_all_fields(self):
        """Test creating Security from import data with all fields."""
        data = {
            "symbol": "MSFT",
            "name": "Microsoft Corporation",
            "country": "United States",
            "fullExchangeName": "NASDAQ",
            "yahoo_symbol": "MSFT",
            "industry": "Technology",
            "currency": "USD",
            "min_lot": 1,
            "priority_multiplier": 1.5,
            "active": True,
            "allow_buy": True,
            "allow_sell": False,
        }

        security = SecurityFactory.create_from_import(data)

        assert isinstance(security, Security)
        assert security.symbol == "MSFT"
        assert security.name == "Microsoft Corporation"
        assert security.country == "United States"
        assert security.fullExchangeName == "NASDAQ"
        assert security.yahoo_symbol == "MSFT"
        assert security.industry == "Technology"
        assert security.currency == Currency.USD
        assert security.min_lot == 1
        assert security.priority_multiplier == 1.5
        assert security.active is True
        assert security.allow_buy is True
        assert security.allow_sell is False

    def test_create_stock_from_import_with_defaults(self):
        """Test creating Security from import with default values."""
        data = {"symbol": "GOOGL", "name": "Alphabet Inc."}

        security = SecurityFactory.create_from_import(data)

        assert security.symbol == "GOOGL"
        assert security.name == "Alphabet Inc."
        assert security.priority_multiplier == 1.0  # Default
        assert security.min_lot == 1  # Default
        assert security.active is True  # Default
        assert security.allow_buy is True  # Default
        assert security.allow_sell is False  # Default

    def test_create_stock_from_import_normalizes_symbol(self):
        """Test that symbol is normalized to uppercase."""
        data = {"symbol": "googl", "name": "Alphabet Inc."}

        security = SecurityFactory.create_from_import(data)

        assert security.symbol == "GOOGL"

    def test_create_stock_from_import_with_currency_string(self):
        """Test creating Security from import with currency as string."""
        data = {"symbol": "TSLA", "name": "Tesla Inc.", "currency": "USD"}

        security = SecurityFactory.create_from_import(data)

        assert security.currency == Currency.USD

    def test_create_stock_from_import_with_currency_enum(self):
        """Test creating Security from import with currency as Currency enum."""
        data = {"symbol": "TSLA", "name": "Tesla Inc.", "currency": Currency.USD}

        security = SecurityFactory.create_from_import(data)

        assert security.currency == Currency.USD

    def test_create_stock_from_import_with_min_lot_validation(self):
        """Test that min_lot is validated (minimum 1)."""
        data = {"symbol": "AAPL", "name": "Apple Inc.", "min_lot": 0}

        security = SecurityFactory.create_from_import(data)

        assert security.min_lot == 1  # Should be corrected to 1


class TestSecurityFactoryCreateWithIndustryDetection:
    """Test SecurityFactory.create_with_industry_detection method."""

    def test_create_stock_with_detected_industry(self):
        """Test creating Security with detected industry."""
        data = {"symbol": "AAPL", "name": "Apple Inc."}
        detected_industry = "Consumer Electronics"

        security = SecurityFactory.create_with_industry_detection(
            data, detected_industry
        )

        assert security.industry == "Consumer Electronics"

    def test_create_stock_with_industry_from_data(self):
        """Test creating Security with industry from data (when detected_industry is None)."""
        data = {"symbol": "AAPL", "name": "Apple Inc.", "industry": "Technology"}

        security = SecurityFactory.create_with_industry_detection(data, None)

        assert security.industry == "Technology"

    def test_create_stock_prioritizes_detected_industry(self):
        """Test that detected_industry takes precedence over data industry."""
        data = {"symbol": "AAPL", "name": "Apple Inc.", "industry": "Technology"}
        detected_industry = "Consumer Electronics"

        security = SecurityFactory.create_with_industry_detection(
            data, detected_industry
        )

        assert security.industry == "Consumer Electronics"
