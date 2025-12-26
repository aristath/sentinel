"""Tests for Money value object."""

import pytest

from app.domain.value_objects.currency import Currency
from app.domain.value_objects.money import Money


class TestMoney:
    """Test Money value object."""

    def test_create_money_with_currency(self):
        """Test creating money with amount and currency."""
        money = Money(amount=100.50, currency=Currency.EUR)

        assert money.amount == 100.50
        assert money.currency == Currency.EUR

    def test_create_money_defaults_to_eur(self):
        """Test that currency defaults to EUR."""
        money = Money(amount=100.0)

        assert money.amount == 100.0
        assert money.currency == Currency.EUR

    def test_money_validation_negative_amount(self):
        """Test that negative amounts are allowed (for losses)."""
        money = Money(amount=-50.0, currency=Currency.EUR)
        assert money.amount == -50.0

    def test_money_validation_zero(self):
        """Test that zero amount is allowed."""
        money = Money(amount=0.0, currency=Currency.EUR)
        assert money.amount == 0.0

    def test_money_equality(self):
        """Test money equality comparison."""
        money1 = Money(amount=100.0, currency=Currency.EUR)
        money2 = Money(amount=100.0, currency=Currency.EUR)
        money3 = Money(amount=100.0, currency=Currency.USD)
        money4 = Money(amount=200.0, currency=Currency.EUR)

        assert money1 == money2
        assert money1 != money3  # Different currency
        assert money1 != money4  # Different amount

    def test_money_addition_same_currency(self):
        """Test adding money with same currency."""
        money1 = Money(amount=100.0, currency=Currency.EUR)
        money2 = Money(amount=50.0, currency=Currency.EUR)

        result = money1 + money2
        assert result.amount == 150.0
        assert result.currency == Currency.EUR

    def test_money_addition_different_currency_raises_error(self):
        """Test that adding money with different currencies raises error."""
        money1 = Money(amount=100.0, currency=Currency.EUR)
        money2 = Money(amount=50.0, currency=Currency.USD)

        with pytest.raises(
            ValueError, match="Cannot add money with different currencies"
        ):
            money1 + money2

    def test_money_subtraction(self):
        """Test subtracting money."""
        money1 = Money(amount=100.0, currency=Currency.EUR)
        money2 = Money(amount=30.0, currency=Currency.EUR)

        result = money1 - money2
        assert result.amount == 70.0
        assert result.currency == Currency.EUR

    def test_money_multiplication(self):
        """Test multiplying money by a scalar."""
        money = Money(amount=100.0, currency=Currency.EUR)

        result = money * 2.5
        assert result.amount == 250.0
        assert result.currency == Currency.EUR

    def test_money_division(self):
        """Test dividing money by a scalar."""
        money = Money(amount=100.0, currency=Currency.EUR)

        result = money / 2.0
        assert result.amount == 50.0
        assert result.currency == Currency.EUR

    def test_money_comparison(self):
        """Test money comparison operators."""
        money1 = Money(amount=100.0, currency=Currency.EUR)
        money2 = Money(amount=50.0, currency=Currency.EUR)
        money3 = Money(amount=100.0, currency=Currency.EUR)

        assert money1 > money2
        assert money2 < money1
        assert money1 >= money3
        assert money2 <= money1
        assert money1 == money3

    def test_money_comparison_different_currency_raises_error(self):
        """Test that comparing money with different currencies raises error."""
        money1 = Money(amount=100.0, currency=Currency.EUR)
        money2 = Money(amount=100.0, currency=Currency.USD)

        with pytest.raises(
            ValueError, match="Cannot compare money with different currencies"
        ):
            money1 > money2

    def test_money_round(self):
        """Test rounding money to specified decimal places."""
        money = Money(amount=100.567, currency=Currency.EUR)

        rounded = money.round(2)
        assert rounded.amount == 100.57
        assert rounded.currency == Currency.EUR

    def test_money_abs(self):
        """Test absolute value of money."""
        money = Money(amount=-50.0, currency=Currency.EUR)

        abs_money = abs(money)
        assert abs_money.amount == 50.0
        assert abs_money.currency == Currency.EUR

    def test_money_to_string(self):
        """Test string representation of money."""
        money = Money(amount=100.50, currency=Currency.EUR)

        assert str(money) == "100.50 EUR"
        # repr uses Python's default float representation (100.5 not 100.50)
        assert repr(money) == "Money(amount=100.5, currency=Currency.EUR)"
