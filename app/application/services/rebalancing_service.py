"""Rebalancing application service.

Orchestrates rebalancing operations using domain services and repositories.
Uses long-term value scoring with portfolio-aware allocation fit.
"""

import logging
from dataclasses import dataclass
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
    calculate_portfolio_score,
    calculate_post_transaction_score,
    PortfolioContext,
    PortfolioScore,
)
from app.services import yahoo
from app.services.tradernet import get_exchange_rate
from app.domain.constants import TRADE_SIDE_BUY

logger = logging.getLogger(__name__)


def _determine_stock_currency(stock: dict) -> str:
    """
    Determine the currency for a stock.
    
    First checks if stock has a position with currency, otherwise infers from geography/symbol.
    
    Args:
        stock: Stock dict from get_with_scores()
        
    Returns:
        Currency code (EUR, USD, HKD, CNY, etc.)
    """
    # First, check if stock has a position with currency
    currency = stock.get("currency")
    if currency:
        return currency
    
    # Infer from geography and yahoo_symbol
    geography = stock.get("geography", "").upper()
    yahoo_symbol = stock.get("yahoo_symbol", "")
    
    if geography == "EU":
        return "EUR"
    elif geography == "US":
        return "USD"
    elif geography == "ASIA":
        # Check yahoo_symbol for exchange indicators
        if yahoo_symbol and ".HK" in yahoo_symbol:
            return "HKD"
        elif yahoo_symbol and ".SZ" in yahoo_symbol:
            return "CNY"
        # Default for ASIA if no specific indicator
        return "HKD"
    
    # Default fallback
    return "EUR"


@dataclass
class Recommendation:
    """A single trade recommendation."""
    symbol: str
    name: str
    amount: float  # Trade amount in EUR (converted from native currency)
    priority: float  # Combined priority score
    reason: str
    geography: str
    industry: str | None
    current_price: float | None = None
    quantity: int | None = None  # Actual shares to buy (respects min_lot)
    current_portfolio_score: float | None = None  # Portfolio score before transaction
    new_portfolio_score: float | None = None  # Portfolio score after transaction
    score_change: float | None = None  # Positive = improvement


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

    async def get_recommendations(self, limit: int = 3) -> List[Recommendation]:
        """
        Get top N trade recommendations based on POST-TRANSACTION portfolio impact.

        Each recommendation respects min_lot and shows the actual trade amount.
        Recommendations are scored by how much they IMPROVE portfolio balance.
        """
        from app.api.settings import get_min_trade_size
        base_trade_amount = await get_min_trade_size()

        # Get portfolio summary for allocation context
        from app.application.services.portfolio_service import PortfolioService
        portfolio_service = PortfolioService(
            self._portfolio_repo,
            self._position_repo,
            self._allocation_repo,
        )
        summary = await portfolio_service.get_portfolio_summary()
        total_value = summary.total_value if summary.total_value and summary.total_value > 0 else 1.0

        # Build weight maps
        geo_weights = {a.name: a.target_pct for a in summary.geographic_allocations}
        industry_weights = {a.name: a.target_pct for a in summary.industry_allocations}

        # Get scored stocks
        stocks_data = await self._stock_repo.get_with_scores()

        # Build complete portfolio context with all metadata
        positions = {}
        stock_geographies = {}
        stock_industries = {}
        stock_scores = {}
        stock_dividends = {}

        for stock in stocks_data:
            symbol = stock["symbol"]
            position_value = stock.get("position_value") or 0
            if position_value > 0:
                positions[symbol] = position_value
            stock_geographies[symbol] = stock["geography"]
            stock_industries[symbol] = stock.get("industry")
            stock_scores[symbol] = stock.get("quality_score") or stock.get("total_score") or 0.5
            # Get dividend yield from fundamentals if available
            stock_dividends[symbol] = stock.get("dividend_yield") or 0

        # Create rich portfolio context
        portfolio_context = PortfolioContext(
            geo_weights=geo_weights,
            industry_weights=industry_weights,
            positions=positions,
            total_value=total_value,
            stock_geographies=stock_geographies,
            stock_industries=stock_industries,
            stock_scores=stock_scores,
            stock_dividends=stock_dividends,
        )

        # Calculate current portfolio score
        current_portfolio_score = calculate_portfolio_score(portfolio_context)

        # Calculate priority for each stock with POST-TRANSACTION scoring
        candidates = []

        for stock in stocks_data:
            symbol = stock["symbol"]
            name = stock["name"]
            geography = stock["geography"]
            industry = stock.get("industry")
            multiplier = stock.get("priority_multiplier") or 1.0
            min_lot = stock.get("min_lot") or 1
            yahoo_symbol = stock.get("yahoo_symbol")

            quality_score = stock.get("quality_score") or stock.get("total_score") or 0
            opportunity_score = stock.get("opportunity_score") or stock.get("fundamental_score") or 0.5
            analyst_score = stock.get("analyst_score") or 0.5
            dividend_yield = stock.get("dividend_yield") or 0

            # Get current price early to calculate actual trade value
            price = yahoo.get_current_price(symbol, yahoo_symbol)
            if not price or price <= 0:
                continue

            # Determine stock currency
            currency = _determine_stock_currency(stock)

            # Get exchange rate for currency conversion
            exchange_rate = 1.0
            if currency != "EUR":
                exchange_rate = get_exchange_rate(currency, "EUR")
                if exchange_rate <= 0:
                    logger.warning(f"Invalid exchange rate for {currency} to EUR, assuming 1.0")
                    exchange_rate = 1.0

            # Calculate actual transaction value (respecting min_lot)
            # lot_cost is in native currency, convert to EUR for comparison with base_trade_amount
            lot_cost_native = min_lot * price
            lot_cost_eur = lot_cost_native / exchange_rate

            # If min_lot cost exceeds base trade amount, use 1 lot
            # Otherwise, use as many lots as fit in base_trade_amount
            if lot_cost_eur > base_trade_amount:
                quantity = min_lot
                trade_value_native = lot_cost_native
            else:
                # Convert base_trade_amount to native currency for lot calculation
                base_trade_amount_native = base_trade_amount * exchange_rate
                num_lots = int(base_trade_amount_native / lot_cost_native)
                quantity = num_lots * min_lot
                trade_value_native = quantity * price

            # Convert trade_value to EUR for display
            trade_value_eur = trade_value_native / exchange_rate

            # Calculate POST-TRANSACTION portfolio score
            # Use EUR value since portfolio is tracked in EUR
            new_score, score_change = calculate_post_transaction_score(
                symbol=symbol,
                geography=geography,
                industry=industry,
                proposed_value=trade_value_eur,
                stock_quality=quality_score,
                stock_dividend=dividend_yield,
                portfolio_context=portfolio_context,
            )

            # Skip stocks that worsen portfolio balance significantly
            if score_change < -1.0:
                logger.debug(f"Skipping {symbol}: transaction worsens balance ({score_change:.2f})")
                continue

            # Base score from quality and opportunity
            base_score = (
                quality_score * 0.35 +
                opportunity_score * 0.35 +
                analyst_score * 0.15
            )

            # Use score_change as allocation fit component
            # Normalize: -5 to +5 -> 0 to 1
            normalized_score_change = max(0, min(1, (score_change + 5) / 10))

            final_score = base_score * 0.85 + normalized_score_change * 0.15

            if final_score < settings.min_stock_score:
                continue

            # Build reason
            reason_parts = []
            if quality_score >= 0.7:
                reason_parts.append("high quality")
            if opportunity_score >= 0.7:
                reason_parts.append("buy opportunity")
            if score_change > 0.5:
                reason_parts.append(f"↑{score_change:.1f} portfolio")
            if multiplier != 1.0:
                reason_parts.append(f"{multiplier:.1f}x mult")
            reason = ", ".join(reason_parts) if reason_parts else "good score"

            candidates.append({
                "symbol": symbol,
                "name": name,
                "geography": geography,
                "industry": industry,
                "price": price,
                "quantity": quantity,
                "trade_value": trade_value_eur,  # Already converted to EUR
                "final_score": final_score * multiplier,
                "reason": reason,
                "current_portfolio_score": current_portfolio_score.total,
                "new_portfolio_score": new_score.total,
                "score_change": score_change,
            })

        # Sort by final score (with multiplier applied)
        candidates.sort(key=lambda x: x["final_score"], reverse=True)

        # Build recommendations for top N
        recommendations = []
        for candidate in candidates[:limit]:
            recommendations.append(Recommendation(
                symbol=candidate["symbol"],
                name=candidate["name"],
                amount=round(candidate["trade_value"], 2),
                priority=round(candidate["final_score"], 2),
                reason=candidate["reason"],
                geography=candidate["geography"],
                industry=candidate["industry"],
                current_price=round(candidate["price"], 2),
                quantity=candidate["quantity"],
                current_portfolio_score=round(candidate["current_portfolio_score"], 1),
                new_portfolio_score=round(candidate["new_portfolio_score"], 1),
                score_change=round(candidate["score_change"], 2),
            ))

        return recommendations

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

            # Determine the stock's native currency
            stock_currency = _determine_stock_currency(stock_data) if stock_data else "EUR"

            recommendations.append(TradeRecommendation(
                symbol=result.symbol,
                name=result.name,
                side=TRADE_SIDE_BUY,
                quantity=qty,
                estimated_price=round(price, 2),
                estimated_value=round(actual_value, 2),
                reason=reason,
                currency=stock_currency,
            ))

            remaining_cash -= actual_value

        total_invested = available_cash - remaining_cash
        logger.info(
            f"Generated {len(recommendations)} trade recommendations, "
            f"total value: €{total_invested:.2f} from €{available_cash:.2f}"
        )

        return recommendations
