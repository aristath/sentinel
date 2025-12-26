"""Trade safety service - consolidates safety checks for trade execution."""

import logging
from typing import Optional

from fastapi import HTTPException

from app.domain.constants import BUY_COOLDOWN_DAYS
from app.domain.repositories.protocols import IPositionRepository, ITradeRepository
from app.domain.value_objects.trade_side import TradeSide
from app.infrastructure.external.tradernet import TradernetClient

logger = logging.getLogger(__name__)


class TradeSafetyService:
    """Service for trade safety checks before execution."""

    def __init__(
        self,
        trade_repo: ITradeRepository,
        position_repo: IPositionRepository,
    ):
        self._trade_repo = trade_repo
        self._position_repo = position_repo

    async def check_pending_orders(
        self, symbol: str, side: str, client: TradernetClient, hours: int = 2
    ) -> bool:
        """
        Check if there are pending orders for a symbol.

        Checks both broker API and local database for recent orders.

        Args:
            symbol: Stock symbol to check
            side: Trade side (BUY or SELL)
            client: Tradernet client instance
            hours: Hours to look back for recent SELL orders (default: 2)

        Returns:
            True if there are pending orders, False otherwise
        """
        # Check broker API for pending orders
        has_pending = client.has_pending_order_for_symbol(symbol)

        # Also check database for recent SELL orders (catches orders just placed)
        if not has_pending and TradeSide.from_string(side).is_sell():
            try:
                has_recent = await self._trade_repo.has_recent_sell_order(
                    symbol, hours=hours
                )
                if has_recent:
                    has_pending = True
                    logger.info(f"Found recent SELL order in database for {symbol}")
            except Exception as e:
                logger.warning(f"Failed to check database for recent sell orders: {e}")

        return has_pending

    async def check_cooldown(
        self, symbol: str, side: str, days: int = BUY_COOLDOWN_DAYS
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a symbol is in cooldown period.

        Args:
            symbol: Stock symbol to check
            side: Trade side (BUY or SELL)
            days: Cooldown period in days (default: BUY_COOLDOWN_DAYS)

        Returns:
            Tuple of (is_in_cooldown: bool, error_message: Optional[str])
        """
        if not TradeSide.from_string(side).is_buy():
            return False, None

        try:
            recently_bought = await self._trade_repo.get_recently_bought_symbols(days)
            if symbol in recently_bought:
                return (
                    True,
                    f"Cannot buy {symbol}: cooldown period active (bought within {days} days)",
                )
        except Exception as e:
            logger.error(f"Failed to check cooldown for {symbol}: {e}")
            # If we can't check cooldown, be conservative and block
            return True, f"Cooldown check failed for {symbol}"

        return False, None

    async def validate_sell_position(
        self, symbol: str, quantity: float
    ) -> tuple[bool, Optional[str]]:
        """
        Validate that a SELL order has sufficient position.

        Args:
            symbol: Stock symbol
            quantity: Quantity to sell

        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str])
        """
        if not self._position_repo:
            logger.warning("PositionRepository not available for SELL validation")
            return True, None

        try:
            position = await self._position_repo.get_by_symbol(symbol)
            if not position:
                return False, f"No position found for {symbol}"

            if quantity > position.quantity:
                return (
                    False,
                    f"SELL quantity ({quantity}) exceeds position ({position.quantity})",
                )

            return True, None
        except Exception as e:
            logger.error(f"Failed to validate SELL position for {symbol}: {e}")
            return False, f"Position validation failed: {str(e)}"

    async def validate_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        client: TradernetClient,
        raise_on_error: bool = True,
    ) -> tuple[bool, Optional[str]]:
        """
        Perform all safety checks for a trade.

        Args:
            symbol: Stock symbol
            side: Trade side (BUY or SELL)
            quantity: Trade quantity
            client: Tradernet client instance
            raise_on_error: If True, raise HTTPException on validation failure

        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str])

        Raises:
            HTTPException: If raise_on_error=True and validation fails
        """
        # Check cooldown for BUY orders
        is_cooldown, cooldown_error = await self.check_cooldown(symbol, side)
        if is_cooldown:
            if raise_on_error:
                raise HTTPException(status_code=400, detail=cooldown_error)
            return False, cooldown_error

        # Check for pending orders
        has_pending = await self.check_pending_orders(symbol, side, client)
        if has_pending:
            error_msg = f"A pending order already exists for {symbol}"
            if raise_on_error:
                raise HTTPException(status_code=409, detail=error_msg)
            return False, error_msg

        # Validate SELL position
        if TradeSide.from_string(side).is_sell():
            is_valid, validation_error = await self.validate_sell_position(
                symbol, quantity
            )
            if not is_valid:
                if raise_on_error:
                    raise HTTPException(status_code=400, detail=validation_error)
                return False, validation_error

        return True, None
