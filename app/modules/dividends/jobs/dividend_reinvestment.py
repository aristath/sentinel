"""Dividend reinvestment job.

Automatically reinvests dividends by executing buy orders when dividends are received.
Uses yield-based strategy:
- High-yield stocks (>=3%): reinvest in same stock
- Low-yield stocks (<3%): use holistic planner to find best opportunities
"""

import logging
from collections import defaultdict
from typing import Dict, List

from app.core.database.manager import get_db_manager
from app.domain.models import DividendRecord, Recommendation
from app.domain.services.settings_service import SettingsService
from app.domain.value_objects.recommendation_status import RecommendationStatus
from app.domain.value_objects.trade_side import TradeSide
from app.infrastructure.dependencies import (
    get_currency_exchange_service_dep,
    get_exchange_rate_service,
    get_tradernet_client,
)
from app.modules.dividends.database.dividend_repository import DividendRepository
from app.modules.rebalancing.services.rebalancing_service import (
    RebalancingService,
    calculate_min_trade_amount,
)
from app.modules.scoring.domain.constants import HIGH_DIVIDEND_REINVESTMENT_THRESHOLD
from app.modules.trading.services.trade_execution_service import TradeExecutionService
from app.repositories import (
    AllocationRepository,
    CalculationsRepository,
    PortfolioRepository,
    PositionRepository,
    RecommendationRepository,
    SettingsRepository,
    StockRepository,
    TradeRepository,
)
from app.shared.domain.value_objects.currency import Currency

logger = logging.getLogger(__name__)


async def _reinvest_in_same_stock(
    symbol: str,
    symbol_dividends: List[DividendRecord],
    total_amount: float,
    client,
    stock_repo: StockRepository,
    recommendations: List[Recommendation],
    dividends_to_mark: Dict[str, List[int]],
) -> None:
    """Reinvest dividends in the same stock (high-yield strategy)."""
    # Get current stock price
    try:
        quote = client.get_quote(symbol)
        if not quote or not hasattr(quote, "price"):
            logger.warning(f"Could not get price for {symbol}, skipping")
            return

        price = quote.price
        if price <= 0:
            logger.warning(f"Invalid price {price} for {symbol}, skipping")
            return

    except Exception as e:
        logger.error(f"Error getting price for {symbol}: {e}, skipping")
        return

    # Get stock info for name and other details
    stock = await stock_repo.get_by_symbol(symbol)
    if not stock:
        logger.warning(f"Stock {symbol} not found in universe, skipping")
        return

    # Calculate shares to buy
    quantity = int(total_amount / price)
    if quantity <= 0:
        logger.warning(
            f"Symbol {symbol}: calculated quantity {quantity} is invalid, skipping"
        )
        return

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
        reason=f"Dividend reinvestment (high yield): {total_amount:.2f} EUR from {len(symbol_dividends)} dividend(s)",
        country=stock.country,
        industry=stock.industry,
        currency=currency,
        status=RecommendationStatus.PENDING,
    )

    recommendations.append(recommendation)
    dividends_to_mark[symbol] = [d.id for d in symbol_dividends if d.id is not None]


async def auto_reinvest_dividends() -> None:
    """
    Automatically reinvest dividends using yield-based strategy.

    Process:
    1. Get all unreinvested dividends
    2. Group dividends by symbol and sum amounts
    3. For each symbol with total >= min_trade_size:
       - Check dividend yield
       - If yield >= 3%: reinvest in same stock
       - If yield < 3%: aggregate for best opportunities
    4. For low-yield dividends: use holistic planner to find highest-scoring opportunities
    5. For small dividends (< min_trade_size): set pending bonus
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
            stock_repo=stock_repo,
            tradernet_client=client,
            currency_exchange_service=currency_exchange_service,
            exchange_rate_service=exchange_rate_service,
            settings_repo=settings_repo,
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

        # Get dividend yields to determine reinvestment strategy
        calc_repo = CalculationsRepository()
        recommendations: List[Recommendation] = []
        dividends_to_mark: Dict[str, List[int]] = {}  # symbol -> list of dividend IDs
        low_yield_dividends: Dict[str, float] = (
            {}
        )  # symbol -> total amount for low-yield stocks

        # Process each symbol - check yield and categorize
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
                    if dividend.id is not None:
                        await dividend_repo.set_pending_bonus(
                            dividend.id, dividend.amount_eur
                        )
                continue

            # Get dividend yield for this stock
            dividend_yield = await calc_repo.get_metric(symbol, "DIVIDEND_YIELD")
            if dividend_yield is None:
                # Yield not in cache, assume low yield and use for opportunities
                logger.debug(
                    f"Symbol {symbol}: no dividend yield data, treating as low-yield"
                )
                low_yield_dividends[symbol] = total_amount
                continue

            # Check if yield is high enough for same-stock reinvestment
            if dividend_yield >= HIGH_DIVIDEND_REINVESTMENT_THRESHOLD:
                # High-yield stock (>=3%): reinvest in same stock
                logger.info(
                    f"Symbol {symbol}: high yield {dividend_yield*100:.1f}%, "
                    f"reinvesting {total_amount:.2f} EUR in same stock"
                )
                await _reinvest_in_same_stock(
                    symbol,
                    symbol_dividends,
                    total_amount,
                    client,
                    stock_repo,
                    recommendations,
                    dividends_to_mark,
                )
            else:
                # Low-yield stock (<3%): aggregate for best opportunities
                logger.info(
                    f"Symbol {symbol}: low yield {dividend_yield*100:.1f}%, "
                    f"aggregating {total_amount:.2f} EUR for best opportunities"
                )
                low_yield_dividends[symbol] = total_amount

        # Process low-yield dividends using holistic planner
        if low_yield_dividends:
            total_low_yield = sum(low_yield_dividends.values())
            logger.info(
                f"Aggregated {len(low_yield_dividends)} low-yield dividends: "
                f"{total_low_yield:.2f} EUR total"
            )
            # For low-yield dividends, use rebalancing service to find best opportunities
            # This will use the holistic planner internally
            allocation_repo = AllocationRepository()
            portfolio_repo = PortfolioRepository()
            recommendation_repo = RecommendationRepository()

            rebalancing_service = RebalancingService(
                stock_repo=stock_repo,
                position_repo=position_repo,
                allocation_repo=allocation_repo,
                portfolio_repo=portfolio_repo,
                trade_repo=trade_repo,
                settings_repo=settings_repo,
                recommendation_repo=recommendation_repo,
                db_manager=db_manager,
                tradernet_client=client,
                exchange_rate_service=exchange_rate_service,
            )

            # Get recommendations for low-yield dividend amount
            low_yield_recommendations = (
                await rebalancing_service.calculate_rebalance_trades(
                    available_cash=total_low_yield
                )
            )

            # Filter to only BUY recommendations and limit to available cash
            buy_recommendations = [
                r for r in low_yield_recommendations if r.side == TradeSide.BUY
            ][
                :5
            ]  # Limit to top 5 opportunities

            if buy_recommendations:
                logger.info(
                    f"Found {len(buy_recommendations)} opportunities for low-yield dividends"
                )
                recommendations.extend(buy_recommendations)
                # Mark all low-yield dividends as contributing to these recommendations
                for symbol in low_yield_dividends.keys():
                    if symbol in grouped_dividends:
                        dividends_to_mark[symbol] = [
                            d.id for d in grouped_dividends[symbol] if d.id is not None
                        ]
            else:
                # No opportunities found, set pending bonuses
                logger.info(
                    "No opportunities found for low-yield dividends, setting pending bonuses"
                )
                for symbol in low_yield_dividends.keys():
                    if symbol in grouped_dividends:
                        for dividend in grouped_dividends[symbol]:
                            if dividend.id is not None:
                                await dividend_repo.set_pending_bonus(
                                    dividend.id, dividend.amount_eur
                                )

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
