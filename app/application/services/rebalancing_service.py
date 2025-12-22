"""Rebalancing application service.

Orchestrates rebalancing operations using domain services and repositories.
Uses long-term value scoring with portfolio-aware allocation fit.
"""

import logging
from typing import List

from app.config import settings
from app.domain.repositories import (
    StockRepository,
    PositionRepository,
    AllocationRepository,
    PortfolioRepository,
)
from app.domain.services.priority_calculator import (
    PriorityCalculator,
    PriorityInput,
)
from app.services.allocator import (
    TradeRecommendation,
    StockPriority,
    calculate_position_size,
    get_max_trades,
)
from app.services.scorer import (
    calculate_allocation_fit_score,
    PortfolioContext,
)
from app.services import yahoo
from app.domain.constants import TRADE_SIDE_BUY

logger = logging.getLogger(__name__)


class RebalancingService:
    """Application service for rebalancing operations."""

    def __init__(
        self,
        stock_repo: StockRepository,
        position_repo: PositionRepository,
        allocation_repo: AllocationRepository,
        portfolio_repo: PortfolioRepository,
    ):
        self._stock_repo = stock_repo
        self._position_repo = position_repo
        self._allocation_repo = allocation_repo
        self._portfolio_repo = portfolio_repo

    async def calculate_rebalance_trades(
        self,
        available_cash: float
    ) -> List[TradeRecommendation]:
        """
        Calculate optimal trades using long-term value scoring with allocation fit.

        Strategy:
        1. Build portfolio context for allocation-aware scoring
        2. Calculate scores with allocation fit (geo gaps, industry gaps, averaging down)
        3. Only consider stocks with score > min_stock_score
        4. Select top N stocks by combined priority
        5. Dynamic position sizing based on conviction/risk
        6. Minimum €400 per trade (min_trade_size)
        7. Maximum 5 trades per cycle (max_trades_per_cycle)
        """
        # Check minimum cash threshold
        if available_cash < settings.min_cash_threshold:
            logger.info(f"Cash €{available_cash:.2f} below minimum €{settings.min_cash_threshold:.2f}")
            return []

        max_trades = get_max_trades(available_cash)
        if max_trades == 0:
            return []

        # Get portfolio summary for weight lookups
        from app.application.services.portfolio_service import PortfolioService
        portfolio_service = PortfolioService(
            self._portfolio_repo,
            self._position_repo,
            self._allocation_repo,
        )
        summary = await portfolio_service.get_portfolio_summary()
        total_value = summary.total_value if summary.total_value and summary.total_value > 0 else 1.0  # Avoid division by zero

        # Build weight maps for quick lookup (target_pct stores weights -1 to +1)
        geo_weights = {a.name: a.target_pct for a in summary.geographic_allocations}
        industry_weights = {a.name: a.target_pct for a in summary.industry_allocations}

        # Get scored stocks from universe with volatility, multiplier, and min_lot
        stocks_data = await self._stock_repo.get_with_scores()

        # Build positions map for portfolio context
        positions = {}
        for stock in stocks_data:
            position_value = stock.get("position_value") or 0
            if position_value > 0:
                positions[stock["symbol"]] = position_value

        # Create portfolio context for allocation fit calculation
        portfolio_context = PortfolioContext(
            geo_weights=geo_weights,
            industry_weights=industry_weights,
            positions=positions,
            total_value=total_value,
        )

        # Calculate priority for each stock with allocation fit
        priority_inputs = []
        stock_metadata = {}  # Store min_lot for later use

        for stock in stocks_data:
            symbol = stock["symbol"]
            name = stock["name"]
            geography = stock["geography"]
            industry = stock.get("industry")
            yahoo_symbol = stock.get("yahoo_symbol")
            multiplier = stock.get("priority_multiplier") or 1.0
            min_lot = stock.get("min_lot") or 1
            volatility = stock.get("volatility")

            # Use cached base scores from database
            quality_score = stock.get("quality_score") or stock.get("total_score") or 0
            opportunity_score = stock.get("opportunity_score") or stock.get("fundamental_score") or 0.5

            # Calculate allocation fit on-the-fly with current portfolio context
            allocation_fit = calculate_allocation_fit_score(
                symbol=symbol,
                geography=geography,
                industry=industry,
                quality_score=quality_score,
                opportunity_score=opportunity_score,
                portfolio_context=portfolio_context,
            )

            # Calculate final score: Quality (35%) + Opportunity (35%) + Analyst (15%) + Allocation Fit (15%)
            analyst_score = stock.get("analyst_score") or 0.5
            final_score = (
                quality_score * 0.35 +
                opportunity_score * 0.35 +
                analyst_score * 0.15 +
                allocation_fit.total * 0.15
            )

            # Only consider stocks with score above threshold
            if final_score < settings.min_stock_score:
                logger.debug(f"Skipping {symbol}: score {final_score:.2f} < {settings.min_stock_score}")
                continue

            priority_inputs.append(PriorityInput(
                symbol=symbol,
                name=name,
                geography=geography,
                industry=industry,
                stock_score=final_score,
                volatility=volatility,
                multiplier=multiplier,
                quality_score=quality_score,
                opportunity_score=opportunity_score,
                allocation_fit_score=allocation_fit.total,
            ))

            stock_metadata[symbol] = {
                "min_lot": min_lot,
                "name": name,
                "geography": geography,
                "industry": industry,
                "yahoo_symbol": yahoo_symbol,
            }

        if not priority_inputs:
            logger.warning("No stocks qualify for purchase (all scores below threshold)")
            return []

        # Calculate priorities using domain service (now just applies multiplier)
        priority_results = PriorityCalculator.calculate_priorities(
            priority_inputs,
            geo_weights,
            industry_weights,
        )

        logger.info(f"Found {len(priority_results)} qualified stocks (score >= {settings.min_stock_score})")

        # Select top N candidates
        selected = priority_results[:max_trades]

        # Calculate base trade size per stock
        base_trade_size = available_cash / len(selected)

        # Get current prices and generate recommendations with dynamic sizing
        recommendations = []
        remaining_cash = available_cash

        for result in selected:
            if remaining_cash < settings.min_trade_size:
                break

            metadata = stock_metadata[result.symbol]

            # Get current price from Yahoo Finance with retry logic
            # Note: This could be moved to a price service in the future
            # We need yahoo_symbol for proper price lookup - get it from stock data
            stock_data = next((s for s in stocks_data if s["symbol"] == result.symbol), None)
            yahoo_symbol = stock_data.get("yahoo_symbol") if stock_data else None
            # Use config value for retries
            price = yahoo.get_current_price(result.symbol, yahoo_symbol)
            if not price or price <= 0:
                logger.warning(f"Could not get valid price for {result.symbol} after retries, skipping")
                continue

            # Create StockPriority for position sizing calculation
            candidate = StockPriority(
                symbol=result.symbol,
                name=result.name,
                geography=result.geography,
                industry=result.industry,
                stock_score=result.stock_score,
                volatility=result.volatility,
                multiplier=result.multiplier,
                min_lot=metadata["min_lot"],
                combined_priority=result.combined_priority,
                quality_score=result.quality_score,
                opportunity_score=result.opportunity_score,
                allocation_fit_score=result.allocation_fit_score,
            )

            # Dynamic position sizing based on conviction and risk
            dynamic_size = calculate_position_size(
                candidate,
                base_trade_size,
                settings.min_trade_size
            )
            invest_amount = min(dynamic_size, remaining_cash)
            if invest_amount < settings.min_trade_size:
                continue

            # Calculate quantity with minimum lot size rounding
            min_lot = metadata["min_lot"]
            lot_cost = min_lot * price

            # Check if we can afford at least one lot
            if lot_cost > invest_amount:
                logger.debug(
                    f"Skipping {result.symbol}: min lot {min_lot} @ €{price:.2f} = "
                    f"€{lot_cost:.2f} > available €{invest_amount:.2f}"
                )
                continue

            # Calculate how many lots we can buy (rounding down to whole lots)
            num_lots = int(invest_amount / lot_cost)
            qty = num_lots * min_lot

            if qty <= 0:
                continue

            actual_value = qty * price

            # Build reason string with new scoring breakdown
            reason_parts = []
            if result.quality_score and result.quality_score >= 0.7:
                reason_parts.append("high quality")
            if result.opportunity_score and result.opportunity_score >= 0.7:
                reason_parts.append("buy opportunity")
            if result.allocation_fit_score and result.allocation_fit_score >= 0.7:
                reason_parts.append("fills gap")
            reason_parts.append(f"score: {result.stock_score:.2f}")
            if result.multiplier != 1.0:
                reason_parts.append(f"mult: {result.multiplier:.1f}x")
            reason = ", ".join(reason_parts)

            recommendations.append(TradeRecommendation(
                symbol=result.symbol,
                name=result.name,
                side=TRADE_SIDE_BUY,
                quantity=qty,
                estimated_price=round(price, 2),
                estimated_value=round(actual_value, 2),
                reason=reason,
            ))

            remaining_cash -= actual_value

        total_invested = available_cash - remaining_cash
        logger.info(
            f"Generated {len(recommendations)} trade recommendations, "
            f"total value: €{total_invested:.2f} from €{available_cash:.2f}"
        )

        return recommendations
