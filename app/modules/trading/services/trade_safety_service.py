"""Trade safety service - consolidates safety checks for trade execution."""

import logging
from datetime import datetime
from typing import Optional

from fastapi import HTTPException

from app.domain.constants import BUY_COOLDOWN_DAYS
from app.domain.repositories.protocols import (
    IPositionRepository,
    ISecurityRepository,
    ITradeRepository,
)
from app.domain.value_objects.trade_side import TradeSide
from app.infrastructure.external.tradernet import TradernetClient
from app.infrastructure.market_hours import is_market_open, should_check_market_hours
from app.modules.scoring.domain.constants import DEFAULT_MIN_HOLD_DAYS
from app.shared.utils import safe_parse_datetime_string

logger = logging.getLogger(__name__)


class TradeSafetyService:
    """Service for trade safety checks before execution."""

    def __init__(
        self,
        trade_repo: ITradeRepository,
        position_repo: IPositionRepository,
        stock_repo: ISecurityRepository,
    ):
        self._trade_repo = trade_repo
        self._position_repo = position_repo
        self._stock_repo = stock_repo

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

    async def check_minimum_hold_time(
        self, symbol: str, min_hold_days: int = DEFAULT_MIN_HOLD_DAYS
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a position has been held for the minimum required days.

        Uses the last transaction date (buy or sell) to calculate hold time.

        Args:
            symbol: Stock symbol to check
            min_hold_days: Minimum hold period in days (default: DEFAULT_MIN_HOLD_DAYS)

        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str])
        """
        try:
            last_transaction_at = await self._trade_repo.get_last_transaction_date(
                symbol
            )
            if not last_transaction_at:
                # No transaction date found - allow (might be legacy data or edge case)
                logger.warning(f"No transaction date found for {symbol}, allowing sell")
                return True, None

            transaction_date = safe_parse_datetime_string(last_transaction_at)
            if not transaction_date:
                # Can't parse date - allow (fail open)
                logger.warning(
                    f"Could not parse transaction date for {symbol}, allowing sell"
                )
                return True, None

            days_held = (datetime.now() - transaction_date).days
            if days_held < min_hold_days:
                return (
                    False,
                    f"Cannot sell {symbol}: last transaction {days_held} days ago (minimum {min_hold_days} days required)",
                )

            return True, None
        except Exception as e:
            logger.error(f"Failed to check minimum hold time for {symbol}: {e}")
            # On error, be conservative and block
            return False, f"Minimum hold time check failed for {symbol}"

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
        # Check market hours first (if required for this trade)
        market_hours_error = await self.check_market_hours(symbol, side)
        if market_hours_error:
            if raise_on_error:
                raise HTTPException(status_code=400, detail=market_hours_error)
            return False, market_hours_error

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
            # Check minimum hold time first
            is_valid, hold_time_error = await self.check_minimum_hold_time(symbol)
            if not is_valid:
                if raise_on_error:
                    raise HTTPException(status_code=400, detail=hold_time_error)
                return False, hold_time_error

            # Check position quantity
            is_valid, validation_error = await self.validate_sell_position(
                symbol, quantity
            )
            if not is_valid:
                if raise_on_error:
                    raise HTTPException(status_code=400, detail=validation_error)
                return False, validation_error

        return True, None

    async def check_market_hours(self, symbol: str, side: str) -> Optional[str]:
        """
        Check if the stock's market is currently open (if required for this trade).

        Args:
            symbol: Stock symbol to check
            side: Trade side (BUY or SELL)

        Returns:
            Error message if market is closed, None if open, check not required, or check failed
        """
        try:
            stock = await self._stock_repo.get_by_symbol(symbol)
            if not stock:
                logger.warning(
                    f"Stock {symbol} not found, cannot check market hours. Allowing trade."
                )
                return None

            exchange = getattr(stock, "fullExchangeName", None)
            if not exchange:
                logger.warning(f"Stock {symbol} has no exchange set. Allowing trade.")
                return None

            # Check if market hours validation is required for this trade
            if not should_check_market_hours(exchange, side):
                # Market hours check not required (e.g., BUY order on flexible hours market)
                return None

            if not is_market_open(exchange):
                logger.info(
                    f"Market closed for {symbol} (exchange: {exchange}). Blocking trade."
                )
                return f"Market closed for {exchange}"

            return None
        except Exception as e:
            logger.warning(f"Failed to check market hours for {symbol}: {e}")
            # On error, allow trade (fail open) - better than blocking all trades
            return None
