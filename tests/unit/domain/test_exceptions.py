"""Tests for domain exceptions."""

from app.domain.exceptions import (
    CurrencyConversionError,
    DomainError,
    InsufficientFundsError,
    InvalidTradeError,
    StockNotFoundError,
    ValidationError,
)


class TestDomainExceptions:
    """Test domain exception hierarchy."""

    def test_domain_error_is_base_exception(self):
        """Test that DomainError is the base exception."""
        assert issubclass(StockNotFoundError, DomainError)
        assert issubclass(InsufficientFundsError, DomainError)
        assert issubclass(InvalidTradeError, DomainError)
        assert issubclass(CurrencyConversionError, DomainError)
        assert issubclass(ValidationError, DomainError)

    def test_stock_not_found_error(self):
        """Test StockNotFoundError."""
        error = StockNotFoundError("AAPL")
        assert str(error) == "Stock not found: AAPL"
        assert error.symbol == "AAPL"

    def test_insufficient_funds_error(self):
        """Test InsufficientFundsError."""
        error = InsufficientFundsError(required=1000.0, available=500.0)
        assert "1000.0" in str(error)
        assert "500.0" in str(error)
        assert error.required == 1000.0
        assert error.available == 500.0

    def test_invalid_trade_error(self):
        """Test InvalidTradeError."""
        error = InvalidTradeError("Cannot sell more than owned")
        assert "Cannot sell more than owned" in str(error)

    def test_currency_conversion_error(self):
        """Test CurrencyConversionError."""
        error = CurrencyConversionError("USD", "JPY", "No conversion path available")
        assert "USD" in str(error)
        assert "JPY" in str(error)
        assert error.from_currency == "USD"
        assert error.to_currency == "JPY"

    def test_validation_error(self):
        """Test ValidationError."""
        error = ValidationError("Symbol cannot be empty")
        assert "Symbol cannot be empty" in str(error)

