"""Price value object for representing per-share/unit prices."""

from dataclasses import dataclass
from typing import Union

from app.domain.value_objects.currency import Currency
from app.domain.value_objects.money import Money


@dataclass(frozen=True)
class Price:
    """Value object representing a price per share/unit with currency.

    Immutable and provides type-safe operations on prices.
    Prices must be positive (unlike Money which can be negative for losses).
    """

    amount: float
    currency: Currency = Currency.EUR

    def __post_init__(self):
        """Validate price amount."""
        if not isinstance(self.amount, (int, float)):
            raise ValueError(f"Amount must be numeric, got {type(self.amount)}")
        if self.amount <= 0:
            raise ValueError(f"Price must be positive, got {self.amount}")

    def __mul__(self, quantity: Union[int, float]) -> Money:
        """Multiply price by quantity to get total value (Money).

        Args:
            quantity: Number of shares/units

        Returns:
            Money instance representing total value
        """
        if not isinstance(quantity, (int, float)):
            return NotImplemented
        if quantity < 0:
            raise ValueError(f"Quantity must be non-negative, got {quantity}")
        return Money(amount=self.amount * quantity, currency=self.currency)

    def __rmul__(self, quantity: Union[int, float]) -> Money:
        """Right multiplication (quantity * price)."""
        return self.__mul__(quantity)

    def round(self, decimals: int = 2) -> "Price":
        """Round price to specified decimal places.

        Args:
            decimals: Number of decimal places (default: 2)

        Returns:
            New Price instance with rounded amount
        """
        return Price(amount=round(self.amount, decimals), currency=self.currency)

    @classmethod
    def from_money(cls, money: Money) -> "Price":
        """Create Price from Money value object.

        Args:
            money: Money instance (must have positive amount)

        Returns:
            Price instance

        Raises:
            ValueError: If money amount is not positive
        """
        if money.amount <= 0:
            raise ValueError(
                f"Cannot create price from non-positive money: {money.amount}"
            )
        return cls(amount=money.amount, currency=money.currency)

    def __str__(self) -> str:
        """String representation of price."""
        return f"{self.amount:.2f} {self.currency.value}"

    def __repr__(self) -> str:
        """Developer representation of price."""
        return f"Price(amount={self.amount}, currency={self.currency})"
