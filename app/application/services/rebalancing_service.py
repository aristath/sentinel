"""Rebalancing application service.

Orchestrates rebalancing operations using domain services and repositories.
Uses long-term value scoring with portfolio-aware allocation fit.
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

import numpy as np
import pandas as pd
import empyrical
import pandas_ta as ta

from app.config import settings
from app.infrastructure.database.manager import get_db_manager
from app.repositories import (
    StockRepository,
    PositionRepository,
    AllocationRepository,
    PortfolioRepository,
    TradeRepository,
    SettingsRepository,
)
from app.domain.scoring import (
    calculate_portfolio_score,
    calculate_post_transaction_score,
    calculate_all_sell_scores,
    PortfolioContext,
    TechnicalData,
)
from app.domain.models import TradeRecommendation, StockPriority
from app.services.allocator import calculate_position_size, get_max_trades
from app.services import yahoo
from app.services.tradernet import get_exchange_rate
from app.domain.constants import TRADE_SIDE_BUY, TRADE_SIDE_SELL, BUY_COOLDOWN_DAYS
from app.infrastructure.hardware.led_display import set_activity
from app.domain.analytics import (
    reconstruct_portfolio_values,
    calculate_portfolio_returns,
    get_performance_attribution,
)

logger = logging.getLogger(__name__)


def _determine_stock_currency(stock: dict) -> str:
    """
    Determine the trading currency for a stock.

    Priority:
    1. Stored currency from stocks.currency (synced from Tradernet x_curr)
    2. Position currency (from broker sync)
    3. Default to EUR

    Args:
        stock: Stock dict with currency info

    Returns:
        Currency code (EUR, USD, HKD, GBP, etc.)
    """
    currency = stock.get("currency")
    if currency:
        return currency

    pos_currency = stock.get("pos_currency")
    if pos_currency:
        return pos_currency

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
        stock_repo: Optional[StockRepository] = None,
        position_repo: Optional[PositionRepository] = None,
        allocation_repo: Optional[AllocationRepository] = None,
        portfolio_repo: Optional[PortfolioRepository] = None,
        trade_repo: Optional[TradeRepository] = None,
    ):
        # Use provided repos or create new ones
        self._stock_repo = stock_repo or StockRepository()
        self._position_repo = position_repo or PositionRepository()
        self._allocation_repo = allocation_repo or AllocationRepository()
        self._portfolio_repo = portfolio_repo or PortfolioRepository()
        self._trade_repo = trade_repo or TradeRepository()
        self._settings_repo = SettingsRepository()
        self._db_manager = get_db_manager()

    async def _get_technical_data_for_positions(
        self,
        symbols: List[str]
    ) -> Dict[str, TechnicalData]:
        """
        Calculate technical indicators for instability detection.

        Uses per-symbol history databases to calculate:
        - Current volatility (last 60 days)
        - Historical volatility (last 365 days)
        - Distance from 200-day MA
        """
        result = {}

        for symbol in symbols:
            try:
                history_db = await self._db_manager.history(symbol)
                rows = await history_db.fetchall(
                    """
                    SELECT date, close_price FROM daily_prices
                    ORDER BY date DESC LIMIT 400
                    """,
                )

                if len(rows) < 60:
                    result[symbol] = TechnicalData(
                        current_volatility=0.20,
                        historical_volatility=0.20,
                        distance_from_ma_200=0.0
                    )
                    continue

                closes = np.array([row['close_price'] for row in reversed(rows)])
                closes_series = pd.Series(closes)

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
                    if not np.isfinite(current_vol) or current_vol < 0:
                        current_vol = 0.20
                else:
                    current_vol = 0.20

                # Historical volatility using empyrical
                returns = np.diff(closes) / closes[:-1]
                historical_vol = float(empyrical.annual_volatility(returns))
                if not np.isfinite(historical_vol) or historical_vol < 0:
                    historical_vol = 0.20

                # Distance from 200-day EMA using pandas-ta
                if len(closes) >= 200:
                    ema_200 = ta.ema(closes_series, length=200)
                    if ema_200 is not None and len(ema_200) > 0 and not pd.isna(ema_200.iloc[-1]):
                        ema_value = float(ema_200.iloc[-1])
                    else:
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

    async def _build_portfolio_context(self) -> PortfolioContext:
        """Build portfolio context for scoring."""
        positions = await self._position_repo.get_all()
        stocks = await self._stock_repo.get_all_active()
        allocations = await self._allocation_repo.get_all()
        total_value = await self._position_repo.get_total_value()

        # Build allocation weight maps
        geo_weights = {}
        industry_weights = {}
        for alloc in allocations:
            if alloc.category == "geography":
                geo_weights[alloc.name] = alloc.target_pct
            elif alloc.category == "industry":
                industry_weights[alloc.name] = alloc.target_pct

        # Build stock metadata maps
        position_map = {p.symbol: p.market_value_eur or 0 for p in positions}
        stock_geographies = {s.symbol: s.geography for s in stocks}
        stock_industries = {s.symbol: s.industry for s in stocks if s.industry}
        stock_scores = {}

        # Get existing scores
        score_rows = await self._db_manager.state.fetchall(
            "SELECT symbol, quality_score FROM scores"
        )
        for row in score_rows:
            if row["quality_score"]:
                stock_scores[row["symbol"]] = row["quality_score"]

        return PortfolioContext(
            geo_weights=geo_weights,
            industry_weights=industry_weights,
            positions=position_map,
            total_value=total_value if total_value > 0 else 1.0,
            stock_geographies=stock_geographies,
            stock_industries=stock_industries,
            stock_scores=stock_scores,
        )

    async def get_recommendations(self, limit: int = 3) -> List[Recommendation]:
        """
        Get top N trade recommendations based on POST-TRANSACTION portfolio impact.

        Each recommendation respects min_lot and shows the actual trade amount.
        Recommendations are scored by how much they IMPROVE portfolio balance.
        """
        set_activity("PROCESSING RECOMMENDATIONS (BUY)...", duration=10.0)

        base_trade_amount = await self._settings_repo.get_value("min_trade_size", 150.0)

        # Build portfolio context
        portfolio_context = await self._build_portfolio_context()
        
        # Get performance-adjusted allocation weights (PyFolio enhancement)
        adjusted_geo_weights, adjusted_ind_weights = await self._get_performance_adjusted_weights()
        
        # Update portfolio context with adjusted weights if available
        if adjusted_geo_weights:
            portfolio_context.geo_weights.update(adjusted_geo_weights)
        if adjusted_ind_weights:
            portfolio_context.industry_weights.update(adjusted_ind_weights)

        # Get recently bought symbols for cooldown filtering
        recently_bought = await self._trade_repo.get_recently_bought_symbols(BUY_COOLDOWN_DAYS)

        # Get all active stocks with scores
        stocks = await self._stock_repo.get_all_active()

        # Calculate current portfolio score
        current_portfolio_score = calculate_portfolio_score(portfolio_context)

        candidates = []

        for stock in stocks:
            symbol = stock.symbol
            name = stock.name
            geography = stock.geography
            industry = stock.industry
            multiplier = stock.priority_multiplier or 1.0
            min_lot = stock.min_lot or 1

            # Skip stocks where allow_buy is disabled
            if not stock.allow_buy:
                continue

            # Skip stocks bought recently (cooldown period)
            if symbol in recently_bought:
                continue

            # Get scores from database
            score_row = await self._db_manager.state.fetchone(
                "SELECT * FROM scores WHERE symbol = ?",
                (symbol,)
            )

            if not score_row:
                continue

            quality_score = score_row["quality_score"] or 0.5
            opportunity_score = score_row["opportunity_score"] or 0.5
            analyst_score = score_row["analyst_score"] or 0.5
            total_score = score_row["total_score"] or 0.5

            if total_score < settings.min_stock_score:
                continue

            # Get current price
            price = yahoo.get_current_price(symbol, stock.yahoo_symbol)
            if not price or price <= 0:
                continue

            # Determine stock currency and exchange rate
            currency = stock.currency or "EUR"
            exchange_rate = 1.0
            if currency != "EUR":
                exchange_rate = get_exchange_rate(currency, "EUR")
                if exchange_rate <= 0:
                    exchange_rate = 1.0

            # Get Sortino ratio for risk-adjusted position sizing (PyFolio enhancement)
            sortino_ratio = None
            try:
                from datetime import datetime, timedelta
                from app.domain.analytics import get_position_risk_metrics
                
                end_date = datetime.now().strftime("%Y-%m-%d")
                start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
                risk_metrics = await get_position_risk_metrics(symbol, start_date, end_date)
                sortino_ratio = risk_metrics.get("sortino_ratio")
            except Exception as e:
                logger.debug(f"Could not get Sortino ratio for {symbol}: {e}")
            
            # Calculate base trade amount with risk adjustment
            risk_adjusted_amount = base_trade_amount
            if sortino_ratio is not None:
                if sortino_ratio > 2.0:
                    # Excellent risk-adjusted returns - increase size by 15%
                    risk_adjusted_amount = base_trade_amount * 1.15
                elif sortino_ratio > 1.5:
                    # Good risk-adjusted returns - increase by 5%
                    risk_adjusted_amount = base_trade_amount * 1.05
                elif sortino_ratio < 0.5:
                    # Poor risk-adjusted returns - reduce by 20%
                    risk_adjusted_amount = base_trade_amount * 0.8
                elif sortino_ratio < 1.0:
                    # Below average - reduce by 10%
                    risk_adjusted_amount = base_trade_amount * 0.9
            
            # Calculate actual transaction value (respecting min_lot)
            lot_cost_native = min_lot * price
            lot_cost_eur = lot_cost_native / exchange_rate

            if lot_cost_eur > risk_adjusted_amount:
                quantity = min_lot
                trade_value_native = lot_cost_native
            else:
                risk_adjusted_amount_native = risk_adjusted_amount * exchange_rate
                num_lots = int(risk_adjusted_amount_native / lot_cost_native)
                quantity = num_lots * min_lot
                trade_value_native = quantity * price

            trade_value_eur = trade_value_native / exchange_rate

            # Calculate POST-TRANSACTION portfolio score
            dividend_yield = 0  # Could be enhanced later
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

            # Calculate final priority score
            base_score = (
                quality_score * 0.35 +
                opportunity_score * 0.35 +
                analyst_score * 0.15
            )
            normalized_score_change = max(0, min(1, (score_change + 5) / 10))
            final_score = base_score * 0.85 + normalized_score_change * 0.15

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
                "trade_value": trade_value_eur,
                "final_score": final_score * multiplier,
                "reason": reason,
                "current_portfolio_score": current_portfolio_score.total,
                "new_portfolio_score": new_score.total,
                "score_change": score_change,
            })

        # Sort by final score
        candidates.sort(key=lambda x: x["final_score"], reverse=True)

        # Build recommendations
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
        """
        if available_cash < settings.min_cash_threshold:
            logger.info(f"Cash €{available_cash:.2f} below minimum €{settings.min_cash_threshold:.2f}")
            return []

        max_trades = get_max_trades(available_cash)
        if max_trades == 0:
            return []

        recommendations = await self.get_recommendations(limit=max_trades)

        if not recommendations:
            logger.info("No buy recommendations available")
            return []

        # Convert Recommendation → TradeRecommendation
        trades = []
        stocks = await self._stock_repo.get_all_active()
        stocks_by_symbol = {s.symbol: s for s in stocks}

        for rec in recommendations:
            if rec.quantity is None or rec.current_price is None:
                logger.warning(f"Skipping {rec.symbol}: missing quantity or price")
                continue

            stock = stocks_by_symbol.get(rec.symbol)
            currency = stock.currency if stock else "EUR"

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
        """
        set_activity("PROCESSING RECOMMENDATIONS (SELL)...", duration=10.0)

        # Build portfolio context
        portfolio_context = await self._build_portfolio_context()
        total_value = portfolio_context.total_value

        # Get all positions
        positions = await self._position_repo.get_all()
        if not positions:
            logger.info("No positions to evaluate for selling")
            return []

        # Get stock info
        stocks = await self._stock_repo.get_all_active()
        stocks_by_symbol = {s.symbol: s for s in stocks}

        # Build position dicts for sell scoring
        position_dicts = []
        for pos in positions:
            stock = stocks_by_symbol.get(pos.symbol)
            if not stock:
                continue

            first_buy = await self._trade_repo.get_first_buy_date(pos.symbol)
            last_sell = await self._trade_repo.get_last_sell_date(pos.symbol)

            position_dicts.append({
                "symbol": pos.symbol,
                "name": stock.name,
                "quantity": pos.quantity,
                "avg_price": pos.avg_price,
                "current_price": pos.current_price,
                "market_value_eur": pos.market_value_eur,
                "currency": pos.currency,
                "geography": stock.geography,
                "industry": stock.industry,
                "allow_sell": stock.allow_sell,
                "first_bought_at": first_buy,
                "last_sold_at": last_sell,
            })

        if not position_dicts:
            return []

        # Get technical data
        symbols = [p["symbol"] for p in position_dicts]
        technical_data = await self._get_technical_data_for_positions(symbols)

        # Build allocation maps
        geo_allocations = {}
        ind_allocations = {}
        for pos in position_dicts:
            geo = pos.get("geography")
            ind = pos.get("industry")
            value = pos.get("market_value_eur") or 0
            if geo:
                geo_allocations[geo] = geo_allocations.get(geo, 0) + value / total_value
            if ind:
                ind_allocations[ind] = ind_allocations.get(ind, 0) + value / total_value

        # Get sell settings
        sell_settings = {
            "min_hold_days": await self._settings_repo.get_int("min_hold_days", 90),
            "sell_cooldown_days": await self._settings_repo.get_int("sell_cooldown_days", 180),
            "max_loss_threshold": await self._settings_repo.get_float("max_loss_threshold", -0.20),
            "target_annual_return": await self._settings_repo.get_float("target_annual_return", 0.10),
        }

        # Calculate sell scores
        sell_scores = await calculate_all_sell_scores(
            positions=position_dicts,
            total_portfolio_value=total_value,
            geo_allocations=geo_allocations,
            ind_allocations=ind_allocations,
            technical_data=technical_data,
            settings=sell_settings,
        )

        # Filter to eligible sells
        eligible_sells = [s for s in sell_scores if s.eligible]

        if not eligible_sells:
            logger.info("No positions eligible for selling")
            return []

        logger.info(f"Found {len(eligible_sells)} positions eligible for selling")

        # Build recommendations
        recommendations = []
        for score in eligible_sells[:limit]:
            pos = next((p for p in position_dicts if p["symbol"] == score.symbol), None)
            if not pos:
                continue

            currency = pos.get("currency", "EUR")
            current_price = pos.get("current_price") or pos.get("avg_price", 0)

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
            reason_parts.append(f"sell score: {score.total_score:.2f}")
            reason = ", ".join(reason_parts) if reason_parts else "eligible for sell"

            recommendations.append(TradeRecommendation(
                symbol=score.symbol,
                name=pos.get("name", score.symbol),
                side=TRADE_SIDE_SELL,
                quantity=score.suggested_sell_quantity,
                estimated_price=round(current_price, 2),
                estimated_value=round(score.suggested_sell_value, 2),
                reason=reason,
                currency=currency,
            ))

        logger.info(f"Generated {len(recommendations)} sell recommendations")

        return recommendations

    async def _get_performance_adjusted_weights(self) -> Tuple[Dict[str, float], Dict[str, float]]:
        """
        Get performance-adjusted allocation weights based on PyFolio attribution.
        
        Returns:
            Tuple of (adjusted_geo_weights, adjusted_ind_weights)
        """
        try:
            from datetime import datetime, timedelta
            
            # Calculate date range (last 365 days)
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
            
            # Reconstruct portfolio and get returns
            portfolio_values = await reconstruct_portfolio_values(start_date, end_date)
            returns = calculate_portfolio_returns(portfolio_values)
            
            if returns.empty or len(returns) < 30:
                # Not enough data, return empty dicts (use base weights)
                return {}, {}
            
            # Get performance attribution
            attribution = await get_performance_attribution(returns, start_date, end_date)
            
            geo_attribution = attribution.get("geography", {})
            ind_attribution = attribution.get("industry", {})
            
            # Adjust weights based on performance
            # If a geography/industry outperformed, increase its target slightly
            adjusted_geo = {}
            adjusted_ind = {}
            
            # Get base allocation targets
            allocations = await self._allocation_repo.get_all()
            
            base_geo_weights = {a.name: a.target_pct for a in allocations if a.category == "geography"}
            base_ind_weights = {a.name: a.target_pct for a in allocations if a.category == "industry"}
            
            # Calculate average return for comparison
            avg_geo_return = sum(geo_attribution.values()) / len(geo_attribution) if geo_attribution else 0.0
            avg_ind_return = sum(ind_attribution.values()) / len(ind_attribution) if ind_attribution else 0.0
            
            # Adjust geography weights (max 5% adjustment)
            for geo, base_weight in base_geo_weights.items():
                perf_return = geo_attribution.get(geo, 0.0)
                if perf_return > avg_geo_return * 1.2:  # 20% above average
                    # Increase weight by up to 5%
                    adjustment = min(0.05, (perf_return - avg_geo_return) * 0.1)
                    adjusted_geo[geo] = base_weight + adjustment
                elif perf_return < avg_geo_return * 0.8:  # 20% below average
                    # Decrease weight by up to 5%
                    adjustment = min(0.05, (avg_geo_return - perf_return) * 0.1)
                    adjusted_geo[geo] = max(-1.0, base_weight - adjustment)
                else:
                    adjusted_geo[geo] = base_weight
            
            # Adjust industry weights (max 3% adjustment)
            for ind, base_weight in base_ind_weights.items():
                perf_return = ind_attribution.get(ind, 0.0)
                if perf_return > avg_ind_return * 1.2:  # 20% above average
                    adjustment = min(0.03, (perf_return - avg_ind_return) * 0.1)
                    adjusted_ind[ind] = base_weight + adjustment
                elif perf_return < avg_ind_return * 0.8:  # 20% below average
                    adjustment = min(0.03, (avg_ind_return - perf_return) * 0.1)
                    adjusted_ind[ind] = max(-1.0, base_weight - adjustment)
                else:
                    adjusted_ind[ind] = base_weight
            
            return adjusted_geo, adjusted_ind
            
        except Exception as e:
            logger.debug(f"Could not calculate performance-adjusted weights: {e}")
            # Return empty dicts on error (use base weights)
            return {}, {}
