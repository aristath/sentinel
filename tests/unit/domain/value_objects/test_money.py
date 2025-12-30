"""Tests for Money value object.

These tests validate the Money value object for representing monetary amounts with currency.
"""

import pytest

from app.domain.value_objects.currency import Currency
from app.domain.value_objects.money import Money


class TestMoney:
    """Test Money value object."""

    def test_create_money_with_amount_and_currency(self):
        """Test creating Money with amount and currency."""
        money = Money(amount=100.0, currency=Currency.EUR)
        assert money.amount == 100.0
        assert money.currency == Currency.EUR

    def test_create_money_with_default_currency(self):
        """Test creating Money with default currency (EUR)."""
        money = Money(amount=50.0)
        assert money.amount == 50.0
        assert money.currency == Currency.EUR

    def test_create_money_with_int_amount(self):
        """Test creating Money with integer amount."""
        money = Money(amount=100, currency=Currency.USD)
        assert money.amount == 100
        assert money.currency == Currency.USD

    def test_money_raises_error_for_non_numeric_amount(self):
        """Test that Money raises ValueError for non-numeric amount."""
        with pytest.raises(ValueError, match="Amount must be numeric"):
            Money(amount="100", currency=Currency.EUR)

        with pytest.raises(ValueError):
            Money(amount=None, currency=Currency.EUR)

    def test_add_money_same_currency(self):
        """Test adding Money with same currency."""
        money1 = Money(amount=100.0, currency=Currency.EUR)
        money2 = Money(amount=50.0, currency=Currency.EUR)
        result = money1 + money2

        assert result.amount == 150.0
        assert result.currency == Currency.EUR

    def test_add_money_different_currencies_raises_error(self):
        """Test that adding Money with different currencies raises ValueError."""
        money1 = Money(amount=100.0, currency=Currency.EUR)
        money2 = Money(amount=50.0, currency=Currency.USD)

        with pytest.raises(ValueError, match="Cannot add money with different currencies"):
            money1 + money2

    def test_subtract_money_same_currency(self):
        """Test subtracting Money with same currency."""
        money1 = Money(amount=100.0, currency=Currency.EUR)
        money2 = Money(amount=30.0, currency=Currency.EUR)
        result = money1 - money2

        assert result.amount == 70.0
        assert result.currency == Currency.EUR

    def test_subtract_money_different_currencies_raises_error(self):
        """Test that subtracting Money with different currencies raises ValueError."""
        money1 = Money(amount=100.0, currency=Currency.EUR)
        money2 = Money(amount=50.0, currency=Currency.USD)

        with pytest.raises(ValueError, match="Cannot subtract money with different currencies"):
            money1 - money2

    def test_multiply_money_by_scalar(self):
        """Test multiplying Money by a scalar."""
        money = Money(amount=100.0, currency=Currency.EUR)
        result = money * 2.5

        assert result.amount == 250.0
        assert result.currency == Currency.EUR

    def test_multiply_money_by_int_scalar(self):
        """Test multiplying Money by an integer scalar."""
        money = Money(amount=100.0, currency=Currency.USD)
        result = money * 3

        assert result.amount == 300.0
        assert result.currency == Currency.USD

    def test_right_multiply_scalar_by_money(self):
        """Test right multiplication (scalar * money)."""
        money = Money(amount=50.0, currency=Currency.EUR)
        result = 4 * money

        assert result.amount == 200.0
        assert result.currency == Currency.EUR

    def test_divide_money_by_scalar(self):
        """Test dividing Money by a scalar."""
        money = Money(amount=100.0, currency=Currency.EUR)
        result = money / 4.0

        assert result.amount == 25.0
        assert result.currency == Currency.EUR

    def test_divide_money_by_int_scalar(self):
        """Test dividing Money by an integer scalar."""
        money = Money(amount=100.0, currency=Currency.USD)
        result = money / 5

        assert result.amount == 20.0
        assert result.currency == Currency.USD

    def test_money_immutability(self):
        """Test that Money is immutable (frozen dataclass)."""
        money = Money(amount=100.0, currency=Currency.EUR)

        with pytest.raises(Exception):  # dataclass.FrozenInstanceError
            money.amount = 200.0

    def test_money_equality(self):
        """Test Money equality."""
        money1 = Money(amount=100.0, currency=Currency.EUR)
        money2 = Money(amount=100.0, currency=Currency.EUR)
        money3 = Money(amount=100.0, currency=Currency.USD)
        money4 = Money(amount=50.0, currency=Currency.EUR)

        assert money1 == money2
        assert money1 != money3  # Different currency
        assert money1 != money4  # Different amount

    def test_money_negative_amount_allowed(self):
        """Test that Money allows negative amounts (for losses)."""
        money = Money(amount=-50.0, currency=Currency.EUR)
        assert money.amount == -50.0
        assert money.currency == Currency.EUR

    def test_money_zero_amount_allowed(self):
        """Test that Money allows zero amount."""
        money = Money(amount=0.0, currency=Currency.EUR)
        assert money.amount == 0.0
