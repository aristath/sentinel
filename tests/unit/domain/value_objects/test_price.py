"""Tests for Price value object."""

import pytest

from app.domain.exceptions import ValidationError
from app.domain.value_objects.currency import Currency
from app.domain.value_objects.price import Price


class TestPrice:
    """Test Price value object."""

    def test_create_price_with_currency(self):
        """Test creating price with amount and currency."""
        price = Price(amount=150.50, currency=Currency.USD)

        assert price.amount == 150.50
        assert price.currency == Currency.USD

    def test_create_price_defaults_to_eur(self):
        """Test that currency defaults to EUR."""
        price = Price(amount=100.0)

        assert price.amount == 100.0
        assert price.currency == Currency.EUR

    def test_price_validation_positive(self):
        """Test that price must be positive."""
        price = Price(amount=100.0, currency=Currency.EUR)
        assert price.amount == 100.0

    def test_price_validation_zero_raises_error(self):
        """Test that zero price raises error."""
        with pytest.raises(ValueError, match="Price must be positive"):
            Price(amount=0.0, currency=Currency.EUR)

    def test_price_validation_negative_raises_error(self):
        """Test that negative price raises error."""
        with pytest.raises(ValueError, match="Price must be positive"):
            Price(amount=-10.0, currency=Currency.EUR)

    def test_price_equality(self):
        """Test price equality comparison."""
        price1 = Price(amount=100.0, currency=Currency.EUR)
        price2 = Price(amount=100.0, currency=Currency.EUR)
        price3 = Price(amount=100.0, currency=Currency.USD)
        price4 = Price(amount=200.0, currency=Currency.EUR)

        assert price1 == price2
        assert price1 != price3  # Different currency
        assert price1 != price4  # Different amount

    def test_price_multiplication_by_quantity(self):
        """Test multiplying price by quantity to get total value."""
        price = Price(amount=100.0, currency=Currency.EUR)

        # Price * quantity = Money (total value)
        from app.domain.value_objects.money import Money

        result = price * 10.0
        assert isinstance(result, Money)
        assert result.amount == 1000.0
        assert result.currency == Currency.EUR

    def test_price_round(self):
        """Test rounding price to specified decimal places."""
        price = Price(amount=100.567, currency=Currency.EUR)

        rounded = price.round(2)
        assert rounded.amount == 100.57
        assert rounded.currency == Currency.EUR

    def test_price_to_string(self):
        """Test string representation of price."""
        price = Price(amount=100.50, currency=Currency.EUR)

        assert str(price) == "100.50 EUR"
        # repr uses Python's default float representation (100.5 not 100.50)
        assert repr(price) == "Price(amount=100.5, currency=Currency.EUR)"

    def test_price_from_money(self):
        """Test creating price from money."""
        from app.domain.value_objects.money import Money

        money = Money(amount=150.0, currency=Currency.USD)
        price = Price.from_money(money)

        assert price.amount == 150.0
        assert price.currency == Currency.USD
