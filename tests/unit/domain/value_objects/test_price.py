"""Tests for Price value object.

These tests validate the Price value object for representing per-share/unit prices with currency.
"""

import pytest

from app.shared.domain.value_objects.currency import Currency
from app.shared.domain.value_objects.money import Money
from app.shared.domain.value_objects.price import Price


class TestPrice:
    """Test Price value object."""

    def test_create_price_with_amount_and_currency(self):
        """Test creating Price with amount and currency."""
        price = Price(amount=100.0, currency=Currency.EUR)
        assert price.amount == 100.0
        assert price.currency == Currency.EUR

    def test_create_price_with_default_currency(self):
        """Test creating Price with default currency (EUR)."""
        price = Price(amount=50.0)
        assert price.amount == 50.0
        assert price.currency == Currency.EUR

    def test_create_price_with_int_amount(self):
        """Test creating Price with integer amount."""
        price = Price(amount=100, currency=Currency.USD)
        assert price.amount == 100
        assert price.currency == Currency.USD

    def test_price_raises_error_for_non_numeric_amount(self):
        """Test that Price raises ValueError for non-numeric amount."""
        with pytest.raises(ValueError, match="Amount must be numeric"):
            Price(amount="100", currency=Currency.EUR)

    def test_price_raises_error_for_zero_amount(self):
        """Test that Price raises ValueError for zero amount."""
        with pytest.raises(ValueError, match="Price must be positive"):
            Price(amount=0.0, currency=Currency.EUR)

    def test_price_raises_error_for_negative_amount(self):
        """Test that Price raises ValueError for negative amount."""
        with pytest.raises(ValueError, match="Price must be positive"):
            Price(amount=-10.0, currency=Currency.EUR)

    def test_multiply_price_by_quantity(self):
        """Test multiplying Price by quantity to get Money."""
        price = Price(amount=100.0, currency=Currency.EUR)
        result = price * 5.0

        assert isinstance(result, Money)
        assert result.amount == 500.0
        assert result.currency == Currency.EUR

    def test_multiply_price_by_int_quantity(self):
        """Test multiplying Price by integer quantity."""
        price = Price(amount=50.0, currency=Currency.USD)
        result = price * 10

        assert isinstance(result, Money)
        assert result.amount == 500.0
        assert result.currency == Currency.USD

    def test_right_multiply_quantity_by_price(self):
        """Test right multiplication (quantity * price)."""
        price = Price(amount=25.0, currency=Currency.EUR)
        result = 4 * price

        assert isinstance(result, Money)
        assert result.amount == 100.0
        assert result.currency == Currency.EUR

    def test_multiply_price_by_zero_quantity(self):
        """Test multiplying Price by zero quantity."""
        price = Price(amount=100.0, currency=Currency.EUR)
        result = price * 0

        assert isinstance(result, Money)
        assert result.amount == 0.0
        assert result.currency == Currency.EUR

    def test_multiply_price_by_negative_quantity_raises_error(self):
        """Test that multiplying Price by negative quantity raises ValueError."""
        price = Price(amount=100.0, currency=Currency.EUR)

        with pytest.raises(ValueError, match="Quantity must be non-negative"):
            price * -5

    def test_round_price(self):
        """Test rounding Price to specified decimal places."""
        price = Price(amount=123.456789, currency=Currency.EUR)
        rounded = price.round(decimals=2)

        assert rounded.amount == 123.46
        assert rounded.currency == Currency.EUR
        assert rounded != price  # Different instance

    def test_round_price_to_zero_decimals(self):
        """Test rounding Price to zero decimal places."""
        price = Price(amount=123.7, currency=Currency.USD)
        rounded = price.round(decimals=0)

        assert rounded.amount == 124.0
        assert rounded.currency == Currency.USD

    def test_from_money_with_positive_amount(self):
        """Test creating Price from Money with positive amount."""
        money = Money(amount=100.0, currency=Currency.EUR)
        price = Price.from_money(money)

        assert price.amount == 100.0
        assert price.currency == Currency.EUR

    def test_from_money_with_zero_amount_raises_error(self):
        """Test that from_money raises ValueError for zero amount."""
        money = Money(amount=0.0, currency=Currency.EUR)

        with pytest.raises(
            ValueError, match="Cannot create price from non-positive money"
        ):
            Price.from_money(money)

    def test_from_money_with_negative_amount_raises_error(self):
        """Test that from_money raises ValueError for negative amount."""
        money = Money(amount=-50.0, currency=Currency.EUR)

        with pytest.raises(
            ValueError, match="Cannot create price from non-positive money"
        ):
            Price.from_money(money)

    def test_price_immutability(self):
        """Test that Price is immutable (frozen dataclass)."""
        price = Price(amount=100.0, currency=Currency.EUR)

        with pytest.raises(Exception):  # dataclass.FrozenInstanceError
            price.amount = 200.0

    def test_price_equality(self):
        """Test Price equality."""
        price1 = Price(amount=100.0, currency=Currency.EUR)
        price2 = Price(amount=100.0, currency=Currency.EUR)
        price3 = Price(amount=100.0, currency=Currency.USD)
        price4 = Price(amount=50.0, currency=Currency.EUR)

        assert price1 == price2
        assert price1 != price3  # Different currency
        assert price1 != price4  # Different amount

    def test_price_str_representation(self):
        """Test Price string representation."""
        price = Price(amount=123.45, currency=Currency.EUR)
        assert "123.45" in str(price)
        assert "EUR" in str(price)

    def test_price_repr_representation(self):
        """Test Price developer representation."""
        price = Price(amount=100.0, currency=Currency.USD)
        repr_str = repr(price)

        assert "Price" in repr_str
        assert "100.0" in repr_str
        assert "Currency.USD" in repr_str or "USD" in repr_str
