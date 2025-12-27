"""Trade side value object."""

from enum import Enum


class TradeSide(str, Enum):
    """Trade side enumeration (BUY or SELL)."""

    BUY = "BUY"
    SELL = "SELL"

    @classmethod
    def from_string(cls, value: str) -> "TradeSide":
        """Create TradeSide from string (case-insensitive).

        Args:
            value: Trade side string (e.g., "BUY", "buy", "SELL")

        Returns:
            TradeSide enum value

        Raises:
            ValueError: If trade side is not supported
        """
        if not value:
            raise ValueError("Invalid trade side: empty string")

        value_upper = value.upper()
        try:
            return cls(value_upper)
        except ValueError:
            raise ValueError(f"Invalid trade side: {value}")

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if string is a valid trade side (case-insensitive).

        Args:
            value: Trade side string to check

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

    def is_buy(self) -> bool:
        """Check if this trade side is BUY.

        Returns:
            True if BUY, False otherwise
        """
        return self == TradeSide.BUY

    def is_sell(self) -> bool:
        """Check if this trade side is SELL.

        Returns:
            True if SELL, False otherwise
        """
        return self == TradeSide.SELL

