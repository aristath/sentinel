"""
State model for LED trade display.

Defines the data structures for trade recommendations
that get sent to the MCU as scrolling text.
"""

from dataclasses import dataclass


@dataclass
class Trade:
    """Represents a single trade to display.

    Attributes:
        action: 'BUY' or 'SELL'
        amount: Trade value in EUR
        symbol: Security symbol (e.g., "AMD.EU")
        sell_pct: For sells, percentage of position being sold (0-100)
    """
    action: str
    amount: float
    symbol: str
    sell_pct: float = 0.0

    def to_display_string(self) -> str:
        """Format trade for LED display.

        Returns:
            Formatted string like:
            - "SELL $1,874.62 (51%) BYD.285.AS"
            - "BUY $645.75 AMD.EU"
        """
        amount_str = f"${self.amount:,.2f}"

        if self.action == 'SELL':
            return f"SELL {amount_str} ({int(self.sell_pct)}%) {self.symbol}"
        else:
            return f"BUY {amount_str} {self.symbol}"
