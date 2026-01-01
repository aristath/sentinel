"""Trading service interface."""

from dataclasses import dataclass
from typing import List, Optional, Protocol


@dataclass
class TradeRequest:
    """Trade request data class."""

    account_id: str
    isin: str
    symbol: str
    side: str  # "BUY" or "SELL"
    quantity: float
    limit_price: Optional[float] = None


@dataclass
class TradeResult:
    """Trade execution result."""

    trade_id: str
    success: bool
    message: str
    executed_quantity: float
    executed_price: Optional[float] = None


class TradingServiceInterface(Protocol):
    """Trading service interface."""

    async def execute_trade(self, request: TradeRequest) -> TradeResult:
        """
        Execute a single trade.

        Args:
            request: Trade request

        Returns:
            Trade execution result
        """
        ...

    async def batch_execute_trades(
        self, requests: List[TradeRequest]
    ) -> List[TradeResult]:
        """
        Execute multiple trades.

        Args:
            requests: List of trade requests

        Returns:
            List of trade results
        """
        ...
