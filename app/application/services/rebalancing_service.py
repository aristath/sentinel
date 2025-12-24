"""Rebalancing application service.

Orchestrates rebalancing operations using domain services and repositories.
Uses long-term value scoring with portfolio-aware allocation fit.
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Optional

import numpy as np
import pandas as pd
import empyrical
import pandas_ta as ta

from app.config import settings
from app.database import get_db_connection
from app.domain.repositories import (
    StockRepository,
    PositionRepository,
    AllocationRepository,
    PortfolioRepository,
    TradeRepository,
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
    _get_daily_prices_from_db,
)
from app.services import yahoo
from app.services.tradernet import get_exchange_rate
from app.services.sell_scorer import calculate_all_sell_scores, SellScore, TechnicalData, get_sell_settings
from app.domain.constants import TRADE_SIDE_BUY, TRADE_SIDE_SELL, BUY_COOLDOWN_DAYS

logger = logging.getLogger(__name__)


def _determine_stock_currency(stock: dict) -> str:
    """
    Determine the trading currency for a stock.

    Priority:
    1. Stored currency from stocks.currency (synced from Tradernet x_curr)
    2. Position currency (from broker sync)
    3. Default to EUR

    Args:
        stock: Stock dict from get_with_scores()

    Returns:
        Currency code (EUR, USD, HKD, GBP, etc.)
    """
    # Use stored currency from Tradernet sync (most accurate)
    currency = stock.get("currency")
    if currency:
        return currency

    # Fallback: position currency from broker (for existing positions)
    pos_currency = stock.get("pos_currency")
    if pos_currency:
        return pos_currency

    # Last resort: default to EUR and log warning
    symbol = stock.get("symbol", "unknown")
    logger.warning(f"No currency found for {symbol}, defaulting to EUR")
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
        trade_repo: TradeRepository | None = None,
    ):
        self._stock_repo = stock_repo
        self._position_repo = position_repo
        self._allocation_repo = allocation_repo
        self._portfolio_repo = portfolio_repo
        self._trade_repo = trade_repo

    async def _get_technical_data_for_positions(
        self,
        symbols: List[str]
    ) -> Dict[str, TechnicalData]:
        """
        Calculate technical indicators for instability detection.

        Uses stock_price_history table to calculate:
        - Current volatility (last 60 days)
        - Historical volatility (last 365 days)
        - Distance from 200-day MA

        Args:
            symbols: List of stock symbols to fetch data for

        Returns:
            Dict mapping symbol to TechnicalData
        """
        result = {}

        async with get_db_connection() as db:
            for symbol in symbols:
                try:
                    daily_prices = await _get_daily_prices_from_db(db, symbol, days=400)

                    if len(daily_prices) < 60:
                        # Not enough data - use neutral values
                        result[symbol] = TechnicalData(
                            current_volatility=0.20,  # Assume 20% baseline
                            historical_volatility=0.20,
                            distance_from_ma_200=0.0
                        )
                        continue

                    closes = np.array([p['close'] for p in daily_prices])
                    closes_series = pd.Series(closes)

                    # Validate no zero/negative prices that would corrupt returns
                    if np.any(closes <= 0):
                        logger.warning(f"Zero/negative prices detected for {symbol}, using fallback values")
                        result[symbol] = TechnicalData(
                            current_volatility=0.20,
                            historical_volatility=0.20,
                            distance_from_ma_200=0.0
                        )
                        continue

                    # Current volatility (last 60 days) using empyrical
                    if len(closes) >= 60:
                        recent_returns = np.diff(closes[-60:]) / closes[-60:-1]
                        current_vol = float(empyrical.annual_volatility(recent_returns))
                        # Validate empyrical output
                        if not np.isfinite(current_vol) or current_vol < 0:
                            current_vol = 0.20
                    else:
                        current_vol = 0.20

                    # Historical volatility (full period, up to 365 days) using empyrical
                    returns = np.diff(closes) / closes[:-1]
                    historical_vol = float(empyrical.annual_volatility(returns))
                    # Validate empyrical output
                    if not np.isfinite(historical_vol) or historical_vol < 0:
                        historical_vol = 0.20

                    # Distance from 200-day EMA using pandas-ta (more responsive than SMA)
                    if len(closes) >= 200:
                        ema_200 = ta.ema(closes_series, length=200)
                        if ema_200 is not None and len(ema_200) > 0 and not pd.isna(ema_200.iloc[-1]):
                            ema_value = float(ema_200.iloc[-1])
                        else:
                            # Fallback to SMA when EMA unavailable
                            logger.debug(f"EMA unavailable for {symbol}, using SMA fallback")
                            ema_value = float(np.mean(closes[-200:]))
                        current_price = float(closes[-1])
                        distance = (current_price - ema_value) / ema_value if ema_value > 0 else 0.0
                    else:
                        distance = 0.0

                    result[symbol] = TechnicalData(
                        current_volatility=current_vol,
                        historical_volatility=historical_vol,
                        distance_from_ma_200=distance
                    )

                except (ValueError, ZeroDivisionError) as e:
                    logger.warning(f"Invalid data for {symbol}: {e}")
                    result[symbol] = TechnicalData(
                        current_volatility=0.20,
                        historical_volatility=0.20,
                        distance_from_ma_200=0.0
                    )
                except Exception as e:
                    logger.error(f"Unexpected error getting technical data for {symbol}: {e}", exc_info=True)
                    result[symbol] = TechnicalData(
                        current_volatility=0.20,
                        historical_volatility=0.20,
                        distance_from_ma_200=0.0
                    )

        return result

    async def get_recommendations(self, limit: int = 3) -> List[Recommendation]:
        """
        Get top N trade recommendations based on POST-TRANSACTION portfolio impact.

        Each recommendation respects min_lot and shows the actual trade amount.
        Recommendations are scored by how much they IMPROVE portfolio balance.
        """
        from app.api.settings import get_setting_value
        base_trade_amount = await get_setting_value("min_trade_size")

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

        # Get recently bought symbols for cooldown filtering
        recently_bought: set[str] = set()
        if self._trade_repo:
            recently_bought = await self._trade_repo.get_recently_bought_symbols(BUY_COOLDOWN_DAYS)

        # Build complete portfolio context with all metadata
        positions = {}
        stock_geographies = {}
        stock_industries = {}
        stock_scores = {}
        stock_dividends = {}
        position_avg_prices = {}
        current_prices = {}

        for stock in stocks_data:
            symbol = stock["symbol"]
            position_value = stock.get("position_value") or 0
            if position_value > 0:
                positions[symbol] = position_value
                # Track cost basis data for averaging down
                if stock.get("avg_price"):
                    position_avg_prices[symbol] = stock["avg_price"]
                if stock.get("current_price"):
                    current_prices[symbol] = stock["current_price"]
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
            position_avg_prices=position_avg_prices,
            current_prices=current_prices,
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

            # Skip stocks where allow_buy is disabled
            allow_buy = stock.get("allow_buy")
            if allow_buy is not None and not allow_buy:
                continue

            # Skip stocks bought recently (cooldown period)
            if symbol in recently_bought:
                continue

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
        Calculate optimal trades using get_recommendations() as the source of truth.

        This ensures all filtering (including cooldown) is applied consistently.
        """
        # Check minimum cash threshold
        if available_cash < settings.min_cash_threshold:
            logger.info(f"Cash €{available_cash:.2f} below minimum €{settings.min_cash_threshold:.2f}")
            return []

        max_trades = get_max_trades(available_cash)
        if max_trades == 0:
            return []

        # Get recommendations (includes cooldown filtering, score filtering, etc.)
        recommendations = await self.get_recommendations(limit=max_trades)

        if not recommendations:
            logger.info("No buy recommendations available")
            return []

        # Convert Recommendation → TradeRecommendation
        trades = []
        for rec in recommendations:
            # Skip if missing required fields
            if rec.quantity is None or rec.current_price is None:
                logger.warning(f"Skipping {rec.symbol}: missing quantity or price")
                continue

            # Determine stock currency from geography
            currency = _determine_stock_currency({"geography": rec.geography})

            trades.append(TradeRecommendation(
                symbol=rec.symbol,
                name=rec.name,
                side=TRADE_SIDE_BUY,
                quantity=rec.quantity,
                estimated_price=rec.current_price,
                estimated_value=rec.amount,
                reason=rec.reason,
                currency=currency,
            ))

        logger.info(f"Generated {len(trades)} trade recommendations from {len(recommendations)} buy recommendations")

        return trades

    async def calculate_sell_recommendations(
        self,
        limit: int = 3
    ) -> List[TradeRecommendation]:
        """
        Calculate optimal SELL recommendations based on sell scoring system.

        Strategy:
        1. Get all positions with stock info (including allow_sell flag)
        2. Calculate sell scores using the 4-component weighted model
        3. Filter to eligible sells (passes hard blocks)
        4. Return top N sell candidates

        Returns:
            List of TradeRecommendation with side=SELL
        """
        # Get portfolio summary for allocation context
        from app.application.services.portfolio_service import PortfolioService
        portfolio_service = PortfolioService(
            self._portfolio_repo,
            self._position_repo,
            self._allocation_repo,
        )
        summary = await portfolio_service.get_portfolio_summary()
        total_value = summary.total_value if summary.total_value and summary.total_value > 0 else 1.0

        # Build allocation maps (current allocations)
        geo_allocations = {a.name: a.current_pct for a in summary.geographic_allocations}
        ind_allocations = {a.name: a.current_pct for a in summary.industry_allocations}

        # Get all positions with stock info
        positions = await self._position_repo.get_with_stock_info()

        if not positions:
            logger.info("No positions to evaluate for selling")
            return []

        # Get technical data for instability detection
        symbols = [p['symbol'] for p in positions]
        technical_data = await self._get_technical_data_for_positions(symbols)

        # Load settings from database
        settings = await get_sell_settings()

        # Calculate sell scores for all positions
        sell_scores = calculate_all_sell_scores(
            positions=positions,
            total_portfolio_value=total_value,
            geo_allocations=geo_allocations,
            ind_allocations=ind_allocations,
            technical_data=technical_data,
            settings=settings
        )

        # Filter to eligible sells
        eligible_sells = [s for s in sell_scores if s.eligible]

        if not eligible_sells:
            logger.info("No positions eligible for selling")
            return []

        logger.info(f"Found {len(eligible_sells)} positions eligible for selling")

        # Build recommendations for top N
        recommendations = []
        for score in eligible_sells[:limit]:
            # Get position data
            pos = next((p for p in positions if p['symbol'] == score.symbol), None)
            if not pos:
                continue

            # Determine currency
            currency = pos.get('currency', 'EUR')

            # Get current price
            current_price = pos.get('current_price') or pos.get('avg_price', 0)

            # Build reason string
            reason_parts = []
            if score.profit_pct > 0.30:
                reason_parts.append(f"profit {score.profit_pct*100:.1f}%")
            elif score.profit_pct < 0:
                reason_parts.append(f"loss {score.profit_pct*100:.1f}%")
            if score.underperformance_score >= 0.7:
                reason_parts.append("underperforming")
            if score.time_held_score >= 0.8:
                reason_parts.append(f"held {score.days_held} days")
            if score.portfolio_balance_score >= 0.7:
                reason_parts.append("overweight")
            if score.instability_score >= 0.6:
                reason_parts.append("high instability")
            elif score.instability_score >= 0.4:
                reason_parts.append("elevated instability")
            reason_parts.append(f"sell score: {score.total_score:.2f}")
            reason = ", ".join(reason_parts) if reason_parts else "eligible for sell"

            recommendations.append(TradeRecommendation(
                symbol=score.symbol,
                name=pos.get('name', score.symbol),
                side=TRADE_SIDE_SELL,
                quantity=score.suggested_sell_quantity,
                estimated_price=round(current_price, 2),
                estimated_value=round(score.suggested_sell_value, 2),
                reason=reason,
                currency=currency,
            ))

        logger.info(
            f"Generated {len(recommendations)} sell recommendations"
        )

        return recommendations

