"""Money value object for representing monetary amounts with currency."""

from dataclasses import dataclass
from typing import Union

from app.domain.value_objects.currency import Currency


@dataclass(frozen=True)
class Money:
    """Value object representing a monetary amount with currency.

    Immutable and provides type-safe operations on money.
    """

    amount: float
    currency: Currency = Currency.EUR

    def __post_init__(self):
        """Validate money amount."""
        if not isinstance(self.amount, (int, float)):
            raise ValueError(f"Amount must be numeric, got {type(self.amount)}")

    def __add__(self, other: "Money") -> "Money":
        """Add two money amounts (must have same currency)."""
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot add money with different currencies: {self.currency} and {other.currency}"
            )
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def __sub__(self, other: "Money") -> "Money":
        """Subtract money amounts (must have same currency)."""
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot subtract money with different currencies: {self.currency} and {other.currency}"
            )
        return Money(amount=self.amount - other.amount, currency=self.currency)

    def __mul__(self, scalar: Union[int, float]) -> "Money":
        """Multiply money by a scalar."""
        if not isinstance(scalar, (int, float)):
            return NotImplemented
        return Money(amount=self.amount * scalar, currency=self.currency)

    def __rmul__(self, scalar: Union[int, float]) -> "Money":
        """Right multiplication (scalar * money)."""
        return self.__mul__(scalar)

    def __truediv__(self, scalar: Union[int, float]) -> "Money":
        """Divide money by a scalar."""
        if not isinstance(scalar, (int, float)):
            return NotImplemented
        if scalar == 0:
            raise ValueError("Cannot divide money by zero")
        return Money(amount=self.amount / scalar, currency=self.currency)

    def __lt__(self, other: "Money") -> bool:
        """Less than comparison (must have same currency)."""
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot compare money with different currencies: {self.currency} and {other.currency}"
            )
        return self.amount < other.amount

    def __le__(self, other: "Money") -> bool:
        """Less than or equal comparison."""
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot compare money with different currencies: {self.currency} and {other.currency}"
            )
        return self.amount <= other.amount

    def __gt__(self, other: "Money") -> bool:
        """Greater than comparison."""
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot compare money with different currencies: {self.currency} and {other.currency}"
            )
        return self.amount > other.amount

    def __ge__(self, other: "Money") -> bool:
        """Greater than or equal comparison."""
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot compare money with different currencies: {self.currency} and {other.currency}"
            )
        return self.amount >= other.amount

    def __abs__(self) -> "Money":
        """Absolute value of money."""
        return Money(amount=abs(self.amount), currency=self.currency)

    def round(self, decimals: int = 2) -> "Money":
        """Round money to specified decimal places.

        Args:
            decimals: Number of decimal places (default: 2)

        Returns:
            New Money instance with rounded amount
        """
        return Money(amount=round(self.amount, decimals), currency=self.currency)

    def __str__(self) -> str:
        """String representation of money."""
        return f"{self.amount:.2f} {self.currency.value}"

    def __repr__(self) -> str:
        """Developer representation of money."""
        return f"Money(amount={self.amount}, currency={self.currency})"

