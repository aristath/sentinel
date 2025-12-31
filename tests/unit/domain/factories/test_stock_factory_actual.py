"""Tests for StockFactory class.

These tests validate the StockFactory class methods for creating Stock objects.
"""

import pytest

from app.domain.exceptions import ValidationError
from app.domain.models import Stock
from app.modules.universe.domain.stock_factory import StockFactory
from app.shared.domain.value_objects.currency import Currency


class TestStockFactoryCreateFromApiRequest:
    """Test StockFactory.create_from_api_request method."""

    def test_create_stock_with_all_fields(self):
        """Test creating Stock with all fields from API request."""
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

        stock = StockFactory.create_from_api_request(data)

        assert isinstance(stock, Stock)
        assert stock.symbol == "AAPL"
        assert stock.name == "Apple Inc."
        assert stock.country == "United States"
        assert stock.fullExchangeName == "NASDAQ"
        assert stock.industry == "Technology"
        assert stock.min_lot == 1
        assert stock.allow_buy is True
        assert stock.allow_sell is False
        assert stock.yahoo_symbol == "AAPL"
        assert stock.currency == Currency.USD

    def test_create_stock_with_minimal_required_fields(self):
        """Test creating Stock with minimal required fields."""
        data = {"symbol": "AAPL", "name": "Apple Inc."}

        stock = StockFactory.create_from_api_request(data)

        assert stock.symbol == "AAPL"
        assert stock.name == "Apple Inc."
        assert stock.min_lot == 1  # Default
        assert stock.allow_buy is True  # Default
        assert stock.allow_sell is False  # Default
        assert stock.active is True  # Default

    def test_create_stock_normalizes_symbol(self):
        """Test that symbol is normalized to uppercase."""
        data = {"symbol": "aapl", "name": "Apple Inc."}

        stock = StockFactory.create_from_api_request(data)

        assert stock.symbol == "AAPL"

    def test_create_stock_raises_error_for_empty_symbol(self):
        """Test that empty symbol raises ValidationError."""
        data = {"symbol": "", "name": "Apple Inc."}

        with pytest.raises(ValidationError, match="Symbol cannot be empty"):
            StockFactory.create_from_api_request(data)

    def test_create_stock_raises_error_for_empty_name(self):
        """Test that empty name raises ValidationError."""
        data = {"symbol": "AAPL", "name": ""}

        with pytest.raises(ValidationError, match="Name cannot be empty"):
            StockFactory.create_from_api_request(data)

    def test_create_stock_raises_error_for_missing_symbol(self):
        """Test that missing symbol raises ValidationError."""
        data = {"name": "Apple Inc."}

        with pytest.raises(ValidationError, match="Symbol cannot be empty"):
            StockFactory.create_from_api_request(data)

    def test_create_stock_raises_error_for_missing_name(self):
        """Test that missing name raises ValidationError."""
        data = {"symbol": "AAPL"}

        with pytest.raises(ValidationError, match="Name cannot be empty"):
            StockFactory.create_from_api_request(data)

    def test_create_stock_with_currency_string(self):
        """Test creating Stock with currency as string."""
        data = {"symbol": "AAPL", "name": "Apple Inc.", "currency": "USD"}

        stock = StockFactory.create_from_api_request(data)

        assert stock.currency == Currency.USD

    def test_create_stock_with_min_lot_validation(self):
        """Test that min_lot is validated (minimum 1)."""
        data = {"symbol": "AAPL", "name": "Apple Inc.", "min_lot": 0}

        stock = StockFactory.create_from_api_request(data)

        assert stock.min_lot == 1  # Should be corrected to 1

    def test_create_stock_strips_whitespace(self):
        """Test that symbol and name are stripped of whitespace."""
        data = {"symbol": "  AAPL  ", "name": "  Apple Inc.  "}

        stock = StockFactory.create_from_api_request(data)

        assert stock.symbol == "AAPL"
        assert stock.name == "Apple Inc."


class TestStockFactoryCreateFromImport:
    """Test StockFactory.create_from_import method."""

    def test_create_stock_from_import_with_all_fields(self):
        """Test creating Stock from import data with all fields."""
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

        stock = StockFactory.create_from_import(data)

        assert isinstance(stock, Stock)
        assert stock.symbol == "MSFT"
        assert stock.name == "Microsoft Corporation"
        assert stock.country == "United States"
        assert stock.fullExchangeName == "NASDAQ"
        assert stock.yahoo_symbol == "MSFT"
        assert stock.industry == "Technology"
        assert stock.currency == Currency.USD
        assert stock.min_lot == 1
        assert stock.priority_multiplier == 1.5
        assert stock.active is True
        assert stock.allow_buy is True
        assert stock.allow_sell is False

    def test_create_stock_from_import_with_defaults(self):
        """Test creating Stock from import with default values."""
        data = {"symbol": "GOOGL", "name": "Alphabet Inc."}

        stock = StockFactory.create_from_import(data)

        assert stock.symbol == "GOOGL"
        assert stock.name == "Alphabet Inc."
        assert stock.priority_multiplier == 1.0  # Default
        assert stock.min_lot == 1  # Default
        assert stock.active is True  # Default
        assert stock.allow_buy is True  # Default
        assert stock.allow_sell is False  # Default

    def test_create_stock_from_import_normalizes_symbol(self):
        """Test that symbol is normalized to uppercase."""
        data = {"symbol": "googl", "name": "Alphabet Inc."}

        stock = StockFactory.create_from_import(data)

        assert stock.symbol == "GOOGL"

    def test_create_stock_from_import_with_currency_string(self):
        """Test creating Stock from import with currency as string."""
        data = {"symbol": "TSLA", "name": "Tesla Inc.", "currency": "USD"}

        stock = StockFactory.create_from_import(data)

        assert stock.currency == Currency.USD

    def test_create_stock_from_import_with_currency_enum(self):
        """Test creating Stock from import with currency as Currency enum."""
        data = {"symbol": "TSLA", "name": "Tesla Inc.", "currency": Currency.USD}

        stock = StockFactory.create_from_import(data)

        assert stock.currency == Currency.USD

    def test_create_stock_from_import_with_min_lot_validation(self):
        """Test that min_lot is validated (minimum 1)."""
        data = {"symbol": "AAPL", "name": "Apple Inc.", "min_lot": 0}

        stock = StockFactory.create_from_import(data)

        assert stock.min_lot == 1  # Should be corrected to 1


class TestStockFactoryCreateWithIndustryDetection:
    """Test StockFactory.create_with_industry_detection method."""

    def test_create_stock_with_detected_industry(self):
        """Test creating Stock with detected industry."""
        data = {"symbol": "AAPL", "name": "Apple Inc."}
        detected_industry = "Consumer Electronics"

        stock = StockFactory.create_with_industry_detection(data, detected_industry)

        assert stock.industry == "Consumer Electronics"

    def test_create_stock_with_industry_from_data(self):
        """Test creating Stock with industry from data (when detected_industry is None)."""
        data = {"symbol": "AAPL", "name": "Apple Inc.", "industry": "Technology"}

        stock = StockFactory.create_with_industry_detection(data, None)

        assert stock.industry == "Technology"

    def test_create_stock_prioritizes_detected_industry(self):
        """Test that detected_industry takes precedence over data industry."""
        data = {"symbol": "AAPL", "name": "Apple Inc.", "industry": "Technology"}
        detected_industry = "Consumer Electronics"

        stock = StockFactory.create_with_industry_detection(data, detected_industry)

        assert stock.industry == "Consumer Electronics"
