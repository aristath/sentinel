"""Emergency rebalancing - executes immediately when negative balances detected.

This module provides immediate execution of emergency rebalancing when negative
cash balances are detected. It should be called after any operation that might
affect cash balances (portfolio sync, trade execution, etc.).
"""

import logging

from app.core.database.manager import get_db_manager
from app.infrastructure.dependencies import (
    get_currency_exchange_service_dep,
    get_exchange_rate_service,
    get_tradernet_client,
)
from app.infrastructure.locking import file_lock
from app.modules.portfolio.database.position_repository import PositionRepository
from app.modules.rebalancing.services.negative_balance_rebalancer import (
    NegativeBalanceRebalancer,
)
from app.modules.trading.services.trade_execution_service import TradeExecutionService
from app.repositories import (
    RecommendationRepository,
    SecurityRepository,
    TradeRepository,
)

logger = logging.getLogger(__name__)


async def check_and_rebalance_immediately() -> bool:
    """
    Check for negative balances and rebalance immediately if detected.

    This function executes immediately when called - no waiting, no scheduling.
    Should be called after operations that might affect cash balances.

    Uses a lock to prevent concurrent execution, which could lead to duplicate trades.

    Returns:
        True if rebalancing was needed and executed, False otherwise
    """
    # Use a lock to prevent concurrent emergency rebalancing
    # This prevents duplicate trades when multiple triggers happen simultaneously
    async with file_lock("emergency_rebalance", timeout=60.0):
        return await _check_and_rebalance_immediately_internal()


async def _check_and_rebalance_immediately_internal() -> bool:
    """Internal implementation of emergency rebalancing check."""
    try:
        client = get_tradernet_client()
        if not client.is_connected:
            if not client.connect():
                logger.warning(
                    "Cannot connect to Tradernet for emergency rebalancing check"
                )
                return False

        # Check if there are any negative balances or currencies below minimum
        cash_balances_raw = client.get_cash_balances()
        cash_balances = {cb.currency: cb.amount for cb in cash_balances_raw}
        has_negative = any(balance < 0 for balance in cash_balances.values())

        if not has_negative:
            # Check for currencies below minimum
            trading_currencies = set()
            security_repo = SecurityRepository()
            securities = await security_repo.get_all_active()
            for security in securities:
                if security.currency:
                    currency_str = (
                        security.currency.value
                        if hasattr(security.currency, "value")
                        else str(security.currency)
                    )
                    trading_currencies.add(currency_str.upper())

            below_minimum = any(
                cash_balances.get(currency, 0) < 5.0 for currency in trading_currencies
            )

            if not below_minimum:
                # No rebalancing needed, but clean up any stale emergency recommendations
                recommendation_repo = RecommendationRepository()
                emergency_portfolio_hash = "EMERGENCY:negative_balance_rebalancing"
                dismissed_count = (
                    await recommendation_repo.dismiss_all_by_portfolio_hash(
                        emergency_portfolio_hash
                    )
                )
                if dismissed_count > 0:
                    logger.info(
                        f"Dismissed {dismissed_count} stale emergency recommendations "
                        "since all currencies meet minimum requirements"
                    )
                return False

        # Negative balances or below minimum detected - rebalance immediately
        logger.warning(
            f"Emergency rebalancing triggered: has_negative={has_negative}, "
            f"balances={cash_balances}"
        )

        # Initialize services
        db_manager = get_db_manager()
        exchange_rate_service = get_exchange_rate_service(db_manager)
        currency_exchange_service = get_currency_exchange_service_dep(client)
        position_repo = PositionRepository()
        security_repo = SecurityRepository()
        trade_repo = TradeRepository()
        recommendation_repo = RecommendationRepository()

        trade_execution_service = TradeExecutionService(
            trade_repo,
            position_repo,
            security_repo,
            client,
            currency_exchange_service,
            exchange_rate_service,
        )

        rebalancer = NegativeBalanceRebalancer(
            client,
            currency_exchange_service,
            trade_execution_service,
            security_repo,
            position_repo,
            exchange_rate_service,
            recommendation_repo,
        )

        # Execute immediately - no waiting
        await rebalancer.rebalance_negative_balances()
        return True

    except Exception as e:
        logger.error(f"Emergency rebalancing failed: {e}", exc_info=True)
        # Don't raise - emergency rebalancing failure shouldn't block other operations
        return False
