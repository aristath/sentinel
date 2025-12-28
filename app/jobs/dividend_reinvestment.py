"""Dividend reinvestment job.

Automatically reinvests dividends by executing buy orders when dividends are received.
Groups dividends by symbol to minimize transaction costs.
"""

import logging
from collections import defaultdict
from typing import Dict, List

from app.application.services.rebalancing_service import calculate_min_trade_amount
from app.application.services.trade_execution_service import TradeExecutionService
from app.domain.models import DividendRecord, Recommendation
from app.domain.services.settings_service import SettingsService
from app.domain.value_objects.currency import Currency
from app.domain.value_objects.recommendation_status import RecommendationStatus
from app.domain.value_objects.trade_side import TradeSide
from app.infrastructure.database.manager import get_db_manager
from app.infrastructure.dependencies import (
    get_currency_exchange_service_dep,
    get_exchange_rate_service,
    get_tradernet_client,
)
from app.repositories import (
    DividendRepository,
    PositionRepository,
    SettingsRepository,
    StockRepository,
    TradeRepository,
)

logger = logging.getLogger(__name__)


async def auto_reinvest_dividends() -> None:
    """
    Automatically reinvest dividends by executing buy orders.

    Process:
    1. Get all unreinvested dividends
    2. Group dividends by symbol and sum amounts
    3. For each symbol with total >= min_trade_size:
       - Get current stock price
       - Calculate shares to buy
       - Create BUY recommendation
       - Execute trade
       - Mark ALL dividend records for that symbol as reinvested
    4. For small dividends (< min_trade_size) that couldn't be grouped:
       - Set pending bonus
    """
    logger.info("Starting automatic dividend reinvestment...")

    try:
        # Get dependencies
        dividend_repo = DividendRepository()
        stock_repo = StockRepository()
        settings_repo = SettingsRepository()
        settings_service = SettingsService(settings_repo)
        client = get_tradernet_client()

        # Create TradeExecutionService with all dependencies
        trade_repo = TradeRepository()
        position_repo = PositionRepository()
        db_manager = get_db_manager()
        exchange_rate_service = get_exchange_rate_service(db_manager)
        currency_exchange_service = get_currency_exchange_service_dep(client)

        trade_execution_service = TradeExecutionService(
            trade_repo=trade_repo,
            position_repo=position_repo,
            tradernet_client=client,
            currency_exchange_service=currency_exchange_service,
            exchange_rate_service=exchange_rate_service,
        )

        # Get settings
        settings = await settings_service.get_settings()
        min_trade_size = calculate_min_trade_amount(
            settings.transaction_cost_fixed,
            settings.transaction_cost_percent,
        )

        # Get all unreinvested dividends (no min_amount filter initially)
        dividends = await dividend_repo.get_unreinvested_dividends(min_amount_eur=0.0)

        if not dividends:
            logger.info("No unreinvested dividends found")
            return

        logger.info(f"Found {len(dividends)} unreinvested dividends")

        # Group dividends by symbol and sum amounts
        grouped_dividends: Dict[str, List[DividendRecord]] = defaultdict(list)
        for dividend in dividends:
            grouped_dividends[dividend.symbol].append(dividend)

        logger.info(f"Grouped into {len(grouped_dividends)} symbols")

        # Ensure client is connected
        if not client.is_connected:
            if not client.connect():
                logger.error(
                    "Failed to connect to Tradernet, skipping dividend reinvestment"
                )
                return

        recommendations: List[Recommendation] = []
        dividends_to_mark: Dict[str, List[int]] = {}  # symbol -> list of dividend IDs

        # Process each symbol
        for symbol, symbol_dividends in grouped_dividends.items():
            total_amount = sum(d.amount_eur for d in symbol_dividends)

            # Check if total meets minimum trade size
            if total_amount < min_trade_size:
                logger.info(
                    f"Symbol {symbol}: total {total_amount:.2f} EUR below min_trade_size "
                    f"{min_trade_size:.2f} EUR, setting pending bonus"
                )
                # Set pending bonus for each small dividend
                for dividend in symbol_dividends:
                    await dividend_repo.set_pending_bonus(
                        dividend.id, dividend.amount_eur
                    )
                continue

            # Get current stock price
            try:
                quote = client.get_quote(symbol)
                if not quote or "price" not in quote:
                    logger.warning(f"Could not get price for {symbol}, skipping")
                    continue

                price = quote["price"]
                if price <= 0:
                    logger.warning(f"Invalid price {price} for {symbol}, skipping")
                    continue

            except Exception as e:
                logger.error(f"Error getting price for {symbol}: {e}, skipping")
                continue

            # Get stock info for name and other details
            stock = await stock_repo.get_by_symbol(symbol)
            if not stock:
                logger.warning(f"Stock {symbol} not found in universe, skipping")
                continue

            # Calculate shares to buy
            quantity = int(total_amount / price)
            if quantity <= 0:
                logger.warning(
                    f"Symbol {symbol}: calculated quantity {quantity} is invalid, skipping"
                )
                continue

            # Adjust for min_lot
            if stock.min_lot > 1:
                quantity = (quantity // stock.min_lot) * stock.min_lot
                if quantity == 0:
                    quantity = stock.min_lot

            estimated_value = quantity * price

            # Create BUY recommendation
            currency = stock.currency or Currency.EUR
            recommendation = Recommendation(
                symbol=symbol,
                name=stock.name,
                side=TradeSide.BUY,
                quantity=float(quantity),
                estimated_price=price,
                estimated_value=estimated_value,
                reason=f"Dividend reinvestment: {total_amount:.2f} EUR from {len(symbol_dividends)} dividend(s)",
                country=stock.country,
                industry=stock.industry,
                currency=currency,
                status=RecommendationStatus.PENDING,
            )

            recommendations.append(recommendation)
            dividends_to_mark[symbol] = [d.id for d in symbol_dividends]

        # Execute trades if any
        if recommendations:
            logger.info(
                f"Executing {len(recommendations)} dividend reinvestment trades"
            )

            try:
                results = await trade_execution_service.execute_trades(recommendations)

                # Mark dividends as reinvested for successful trades
                for i, result in enumerate(results):
                    if result.get("status") == "success":
                        symbol = recommendations[i].symbol
                        if symbol in dividends_to_mark:
                            # Mark all dividend records for this symbol as reinvested
                            for dividend_id in dividends_to_mark[symbol]:
                                # Get quantity from the executed trade
                                executed_quantity = (
                                    result.get("quantity")
                                    or recommendations[i].quantity
                                )
                                await dividend_repo.mark_reinvested(
                                    dividend_id, int(executed_quantity)
                                )
                            logger.info(
                                f"Marked {len(dividends_to_mark[symbol])} dividend records "
                                f"as reinvested for {symbol}"
                            )
                    else:
                        symbol = recommendations[i].symbol
                        error = result.get("error", "Unknown error")
                        logger.error(
                            f"Trade execution failed for {symbol}: {error}, "
                            f"dividends NOT marked as reinvested"
                        )

            except Exception as e:
                logger.error(
                    f"Error executing dividend reinvestment trades: {e}", exc_info=True
                )
        else:
            logger.info("No dividend reinvestment trades to execute")

    except Exception as e:
        logger.error(f"Error in dividend reinvestment job: {e}", exc_info=True)
