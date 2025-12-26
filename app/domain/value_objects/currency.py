"""Currency value object."""

from enum import Enum


class Currency(str, Enum):
    """Currency enumeration for supported currencies."""

    EUR = "EUR"
    USD = "USD"
    HKD = "HKD"
    GBP = "GBP"

    @classmethod
    def from_string(cls, value: str) -> "Currency":
        """Create Currency from string (case-insensitive).

        Args:
            value: Currency string (e.g., "EUR", "eur", "USD")

        Returns:
            Currency enum value

        Raises:
            ValueError: If currency is not supported
        """
        if not value:
            raise ValueError("Invalid currency: empty string")

        value_upper = value.upper()
        try:
            return cls(value_upper)
        except ValueError:
            raise ValueError(f"Invalid currency: {value}")

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if string is a valid currency (case-insensitive).

        Args:
            value: Currency string to check

        Returns:
            True if valid, False otherwise
        """
        if not value:
            return False
        try:
            cls.from_string(value)
            return True
        except ValueError:
            return False

    @classmethod
    def default(cls) -> "Currency":
        """Get default currency (EUR).

        Returns:
            EUR currency
        """
        return cls.EUR
