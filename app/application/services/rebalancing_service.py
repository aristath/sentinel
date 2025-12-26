"""Rebalancing application service.

Orchestrates rebalancing operations using domain services and repositories.
Uses long-term value scoring with portfolio-aware allocation fit.
"""

import logging
from typing import Dict, List, Optional, Tuple

from app.config import settings as app_settings
from app.domain.constants import (
    BUY_COOLDOWN_DAYS,
    DEFAULT_VOLATILITY,
    MAX_POSITION_PCT,
    MAX_VOL_WEIGHT,
    MIN_VOL_WEIGHT,
    MIN_VOLATILITY_FOR_SIZING,
    REBALANCE_BAND_PCT,
    TARGET_PORTFOLIO_VOLATILITY,
)
from app.domain.events import RecommendationCreatedEvent, get_event_bus
from app.domain.models import MultiStepRecommendation, Recommendation
from app.domain.repositories.protocols import (
    IAllocationRepository,
    IPositionRepository,
    ISettingsRepository,
    IStockRepository,
    ITradeRepository,
)
from app.domain.scoring import (
    PortfolioContext,
    TechnicalData,
    calculate_all_sell_scores,
    calculate_portfolio_score,
    calculate_post_transaction_score,
)
from app.domain.scoring.groups.opportunity import is_price_too_high
from app.domain.services.allocation_calculator import get_max_trades
from app.domain.services.exchange_rate_service import ExchangeRateService
from app.domain.services.settings_service import SettingsService
from app.domain.services.trade_sizing_service import TradeSizingService
from app.domain.value_objects.recommendation_status import RecommendationStatus
from app.domain.value_objects.trade_side import TradeSide
from app.infrastructure.database.manager import DatabaseManager
from app.infrastructure.external import yahoo_finance as yahoo
from app.infrastructure.external.tradernet import TradernetClient
from app.repositories import (
    PortfolioRepository,
    RecommendationRepository,
)

# Constants for heuristic path (optimizer path uses settings directly)
# These replace the removed min_trade_size and max_balance_worsening settings
MAX_BALANCE_WORSENING = (
    -5.0
)  # Maximum allowed portfolio score decrease for recommendations


def calculate_min_trade_amount(
    transaction_cost_fixed: float,
    transaction_cost_percent: float,
    max_cost_ratio: float = 0.01,  # 1% max cost-to-trade ratio
) -> float:
    """
    Calculate minimum trade amount where transaction costs are acceptable.

    With Freedom24's €2 + 0.2% fee structure:
    - €50 trade: €2.10 cost = 4.2% drag → not worthwhile
    - €200 trade: €2.40 cost = 1.2% drag → marginal
    - €400 trade: €2.80 cost = 0.7% drag → acceptable

    Args:
        transaction_cost_fixed: Fixed cost per trade (e.g., €2.00)
        transaction_cost_percent: Variable cost as fraction (e.g., 0.002 = 0.2%)
        max_cost_ratio: Maximum acceptable cost-to-trade ratio (default 1%)

    Returns:
        Minimum trade amount in EUR
    """
    # Solve for trade amount where: (fixed + trade * percent) / trade = max_ratio
    # fixed / trade + percent = max_ratio
    # trade = fixed / (max_ratio - percent)
    denominator = max_cost_ratio - transaction_cost_percent
    if denominator <= 0:
        # If variable cost exceeds max ratio, return a high minimum
        return 1000.0
    return transaction_cost_fixed / denominator


from app.application.services.recommendation.performance_adjustment_calculator import (
    get_performance_adjusted_weights,
)
from app.application.services.recommendation.portfolio_context_builder import (
    build_portfolio_context,
)
from app.application.services.recommendation.technical_data_calculator import (
    get_technical_data_for_positions,
)
from app.infrastructure.recommendation_cache import get_recommendation_cache

logger = logging.getLogger(__name__)


class RebalancingService:
    """Application service for rebalancing operations."""

    def __init__(
        self,
        stock_repo: IStockRepository,
        position_repo: IPositionRepository,
        allocation_repo: IAllocationRepository,
        portfolio_repo: PortfolioRepository,
        trade_repo: ITradeRepository,
        settings_repo: ISettingsRepository,
        recommendation_repo: RecommendationRepository,
        db_manager: DatabaseManager,
        tradernet_client: TradernetClient,
        exchange_rate_service: ExchangeRateService,
    ):
        self._stock_repo = stock_repo
        self._position_repo = position_repo
        self._allocation_repo = allocation_repo
        self._portfolio_repo = portfolio_repo
        self._trade_repo = trade_repo
        self._settings_repo = settings_repo
        self._settings_service = SettingsService(self._settings_repo)
        self._recommendation_repo = recommendation_repo
        self._db_manager = db_manager
        self._tradernet_client = tradernet_client
        self._exchange_rate_service = exchange_rate_service

    async def get_recommendations(self, limit: int = 3) -> List[Recommendation]:
        """
        Get top N trade recommendations based on POST-TRANSACTION portfolio impact.

        Each recommendation respects min_lot and shows the actual trade amount.
        Recommendations are scored by how much they IMPROVE portfolio balance.
        """
        # Get settings first (needed for cache key)
        settings = await self._settings_service.get_settings()
        # Calculate minimum worthwhile trade from transaction costs
        base_trade_amount = calculate_min_trade_amount(
            settings.transaction_cost_fixed,
            settings.transaction_cost_percent,
        )

        # Generate cache key from both positions and settings
        from app.domain.portfolio_hash import generate_recommendation_cache_key

        positions = await self._position_repo.get_all()
        position_dicts = [
            {"symbol": p.symbol, "quantity": p.quantity} for p in positions
        ]
        cache_key = generate_recommendation_cache_key(
            position_dicts, settings.to_dict()
        )

        # Check cache first (48h TTL)
        rec_cache = get_recommendation_cache()
        cached = await rec_cache.get_recommendations(cache_key, "buy")
        if cached:
            logger.info(f"Using cached buy recommendations ({len(cached)} items)")
            # Convert cached dicts back to Recommendation objects
            recommendations = []
            for c in cached[:limit]:
                # Map old fields to unified model
                from app.domain.value_objects.currency import Currency

                currency_str = c.get("currency", "EUR")
                currency = (
                    Currency.from_string(currency_str)
                    if isinstance(currency_str, str)
                    else currency_str
                )

                recommendations.append(
                    Recommendation(
                        symbol=c["symbol"],
                        name=c["name"],
                        side=TradeSide.BUY,
                        quantity=c.get("quantity", 0),
                        estimated_price=c.get("current_price")
                        or c.get("estimated_price", 0),
                        estimated_value=c.get("amount") or c.get("estimated_value", 0),
                        reason=c["reason"],
                        geography=c["geography"],
                        industry=c.get("industry"),
                        currency=currency,
                        priority=c.get("priority"),
                        current_portfolio_score=c.get("current_portfolio_score"),
                        new_portfolio_score=c.get("new_portfolio_score"),
                        status=RecommendationStatus.PENDING,
                    )
                )
            return recommendations

        # Build portfolio context
        portfolio_context = await build_portfolio_context(
            position_repo=self._position_repo,
            stock_repo=self._stock_repo,
            allocation_repo=self._allocation_repo,
            db_manager=self._db_manager,
        )

        # Get performance-adjusted allocation weights (PyFolio enhancement)
        # Pass cache_key for caching (saves ~27s on repeat calls)
        adjusted_geo_weights, adjusted_ind_weights = (
            await get_performance_adjusted_weights(
                allocation_repo=self._allocation_repo,
                portfolio_hash=cache_key,
            )
        )

        # Update portfolio context with adjusted weights if available
        if adjusted_geo_weights:
            portfolio_context.geo_weights.update(adjusted_geo_weights)
        if adjusted_ind_weights:
            portfolio_context.industry_weights.update(adjusted_ind_weights)

        # Get recently bought symbols for cooldown filtering
        recently_bought = await self._trade_repo.get_recently_bought_symbols(
            BUY_COOLDOWN_DAYS
        )

        # Get all active stocks with scores
        stocks = await self._stock_repo.get_all_active()

        # Calculate current portfolio score (with caching)
        current_portfolio_score = await calculate_portfolio_score(
            portfolio_context, portfolio_hash=cache_key
        )

        # BATCH FETCH ALL PRICES UPFRONT (performance optimization)
        # This replaces sequential get_current_price() calls which caused timeouts
        symbol_yahoo_map = {
            s.symbol: s.yahoo_symbol
            for s in stocks
            if s.allow_buy and s.symbol not in recently_bought
        }
        batch_prices = yahoo.get_batch_quotes(symbol_yahoo_map)
        logger.info(
            f"Batch fetched {len(batch_prices)} prices for {len(symbol_yahoo_map)} eligible stocks"
        )

        # Debug: log stocks that didn't get prices
        missing_prices = [s for s in symbol_yahoo_map if s not in batch_prices]
        if missing_prices:
            logger.warning(
                f"Missing prices for {len(missing_prices)} stocks: {missing_prices[:10]}"
            )

        candidates = []
        filter_stats = {
            "no_allow_buy": 0,
            "recently_bought": 0,
            "no_score": 0,
            "low_score": 0,
            "no_price": 0,
            "price_too_high": 0,
            "exceeds_position_cap": 0,
            "worsens_balance": 0,
        }

        for stock in stocks:
            symbol = stock.symbol
            name = stock.name
            geography = stock.geography
            industry = stock.industry
            multiplier = stock.priority_multiplier or 1.0
            min_lot = stock.min_lot or 1

            # Skip stocks where allow_buy is disabled
            if not stock.allow_buy:
                filter_stats["no_allow_buy"] += 1
                continue

            # Skip stocks bought recently (cooldown period)
            if symbol in recently_bought:
                filter_stats["recently_bought"] += 1
                continue

            # Get scores from database
            score_row = await self._db_manager.state.fetchone(
                "SELECT * FROM scores WHERE symbol = ?", (symbol,)
            )

            if not score_row:
                filter_stats["no_score"] += 1
                continue

            quality_score = score_row["quality_score"] or 0.5
            opportunity_score = score_row["opportunity_score"] or 0.5
            analyst_score = score_row["analyst_score"] or 0.5
            total_score = score_row["total_score"] or 0.5

            if total_score < settings.min_stock_score:
                filter_stats["low_score"] += 1
                continue

            # Get current price from batch-fetched prices
            price = batch_prices.get(symbol)
            if not price or price <= 0:
                filter_stats["no_price"] += 1
                continue

            # GUARDRAIL: Price ceiling - don't buy near 52-week highs
            # Get 52-week high from cached calculations
            from app.repositories.calculations import CalculationsRepository

            calc_repo = CalculationsRepository()
            high_52w = await calc_repo.get_metric(symbol, "52W_HIGH")
            if high_52w and is_price_too_high(price, high_52w):
                filter_stats["price_too_high"] += 1
                logger.debug(
                    f"Skipping {symbol}: price ${price:.2f} too close to 52W high ${high_52w:.2f}"
                )
                continue

            # Determine stock currency and exchange rate
            currency = stock.currency or "EUR"
            exchange_rate = 1.0
            if currency != "EUR":
                exchange_rate = await self._exchange_rate_service.get_rate(
                    currency, "EUR"
                )
                if exchange_rate <= 0:
                    exchange_rate = 1.0

            # Get volatility for risk parity position sizing
            stock_vol = DEFAULT_VOLATILITY
            try:
                from datetime import datetime, timedelta

                from app.domain.analytics import get_position_risk_metrics

                end_date = datetime.now().strftime("%Y-%m-%d")
                start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
                risk_metrics = await get_position_risk_metrics(
                    symbol, start_date, end_date
                )
                stock_vol = risk_metrics.get("volatility", DEFAULT_VOLATILITY)
            except Exception as e:
                logger.debug(f"Could not get risk metrics for {symbol}: {e}")

            # Risk Parity Position Sizing (MOSEK Portfolio Cookbook principles)
            # Size inversely to volatility so each position contributes equal risk
            vol_weight = TARGET_PORTFOLIO_VOLATILITY / max(
                stock_vol, MIN_VOLATILITY_FOR_SIZING
            )
            vol_weight = max(MIN_VOL_WEIGHT, min(MAX_VOL_WEIGHT, vol_weight))

            # Small stock score adjustment (±10%)
            score_adj = 1.0 + (total_score - 0.5) * 0.2
            score_adj = max(0.9, min(1.1, score_adj))

            risk_parity_amount = base_trade_amount * vol_weight * score_adj

            # Calculate actual transaction value (respecting min_lot)
            sized = TradeSizingService.calculate_buy_quantity(
                target_value_eur=risk_parity_amount,
                price=price,
                min_lot=min_lot,
                exchange_rate=exchange_rate,
            )
            quantity = sized.quantity
            trade_value_eur = sized.value_eur

            # GUARDRAIL: Position size cap - no single position > 15% of portfolio
            current_position_value = portfolio_context.positions.get(symbol, 0)
            new_position_value = current_position_value + trade_value_eur
            total_after = portfolio_context.total_value + trade_value_eur
            new_position_pct = (
                new_position_value / total_after if total_after > 0 else 0
            )
            if new_position_pct > MAX_POSITION_PCT:
                filter_stats["exceeds_position_cap"] += 1
                logger.debug(
                    f"Skipping {symbol}: would be {new_position_pct*100:.1f}% of portfolio (max {MAX_POSITION_PCT*100:.0f}%)"
                )
                continue

            # Calculate POST-TRANSACTION portfolio score (with caching)
            dividend_yield = 0  # Could be enhanced later
            new_score, score_change = await calculate_post_transaction_score(
                symbol=symbol,
                geography=geography,
                industry=industry,
                proposed_value=trade_value_eur,
                stock_quality=quality_score,
                stock_dividend=dividend_yield,
                portfolio_context=portfolio_context,
                portfolio_hash=cache_key,
            )

            # Skip stocks that worsen portfolio balance significantly
            if score_change < MAX_BALANCE_WORSENING:
                filter_stats["worsens_balance"] += 1
                logger.debug(
                    f"Skipping {symbol}: transaction worsens balance ({score_change:.2f})"
                )
                continue

            # Calculate final priority score
            base_score = (
                quality_score * 0.35
                + opportunity_score * 0.35
                + analyst_score * 0.05  # Reduced from 0.15 - tiebreaker only
            )
            normalized_score_change = max(0, min(1, (score_change + 5) / 10))
            final_score = (
                base_score * 0.75 + normalized_score_change * 0.25
            )  # Increased portfolio impact weight

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

            candidates.append(
                {
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
                }
            )

        # Log filter statistics
        logger.info(
            f"Recommendation filtering: {len(stocks)} total -> {len(candidates)} candidates. Filtered: {filter_stats}"
        )

        # Sort by final score
        candidates.sort(key=lambda x: x["final_score"], reverse=True)

        # Build recommendations and store them
        recommendations = []
        for candidate in candidates[:limit]:
            # Get currency from stock
            stock = next((s for s in stocks if s.symbol == candidate["symbol"]), None)
            currency = stock.currency if stock else Currency.EUR

            rec = Recommendation(
                symbol=candidate["symbol"],
                name=candidate["name"],
                side=TradeSide.BUY,
                quantity=candidate["quantity"],
                estimated_price=round(candidate["price"], 2),
                estimated_value=round(candidate["trade_value"], 2),
                reason=candidate["reason"],
                geography=candidate["geography"],
                industry=candidate.get("industry"),
                currency=currency,
                priority=round(candidate["final_score"], 2),
                current_portfolio_score=round(candidate["current_portfolio_score"], 1),
                new_portfolio_score=round(candidate["new_portfolio_score"], 1),
                status=RecommendationStatus.PENDING,
            )

            # Store recommendation in database (create or update)
            recommendation_data = {
                "symbol": rec.symbol,
                "name": rec.name,
                "side": "BUY",
                "amount": rec.estimated_value,
                "quantity": rec.quantity,
                "estimated_price": rec.estimated_price,
                "estimated_value": rec.estimated_value,
                "reason": rec.reason,
                "geography": rec.geography,
                "industry": rec.industry,
                "currency": currency,
                "priority": rec.priority,
                "current_portfolio_score": rec.current_portfolio_score,
                "new_portfolio_score": rec.new_portfolio_score,
                "score_change": rec.score_change,
            }

            # create_or_update returns UUID if not dismissed, None if dismissed
            uuid = await self._recommendation_repo.create_or_update(
                recommendation_data, portfolio_hash=cache_key
            )
            if uuid:
                # Only include if not dismissed
                recommendations.append(rec)
                # Publish domain event for recommendations (new or updated)
                event_bus = get_event_bus()
                event_bus.publish(RecommendationCreatedEvent(recommendation=rec))

        # Cache the full recommendation list (not just the limited ones)
        # This allows returning different limit values from the same cache
        all_recs_for_cache = []
        for candidate in candidates:
            all_recs_for_cache.append(
                {
                    "symbol": candidate["symbol"],
                    "name": candidate["name"],
                    "amount": round(candidate["trade_value"], 2),
                    "priority": round(candidate["final_score"], 2),
                    "reason": candidate["reason"],
                    "geography": candidate["geography"],
                    "industry": candidate["industry"],
                    "current_price": round(candidate["price"], 2),
                    "quantity": candidate["quantity"],
                    "current_portfolio_score": round(
                        candidate["current_portfolio_score"], 1
                    ),
                    "new_portfolio_score": round(candidate["new_portfolio_score"], 1),
                    "score_change": round(candidate["score_change"], 2),
                }
            )

        if all_recs_for_cache:
            await rec_cache.set_recommendations(cache_key, "buy", all_recs_for_cache)

        return recommendations

    async def get_recommendations_debug(self) -> dict:
        """
        Debug method to show why recommendations are being filtered.
        Returns detailed filter statistics.
        """
        from app.domain.portfolio_hash import generate_recommendation_cache_key
        from app.domain.scoring.diversification import calculate_post_transaction_score
        from app.infrastructure.external import yahoo_finance as yahoo

        settings = await self._settings_service.get_settings()
        recently_bought = await self._trade_repo.get_recently_bought_symbols(
            BUY_COOLDOWN_DAYS
        )
        stocks = await self._stock_repo.get_all_active()

        # Get portfolio context for score calculation
        positions = await self._position_repo.get_all()
        position_dicts = [
            {"symbol": p.symbol, "quantity": p.quantity} for p in positions
        ]
        cache_key = generate_recommendation_cache_key(
            position_dicts, settings.to_dict()
        )
        portfolio_context = await self._build_portfolio_context()

        symbol_yahoo_map = {
            s.symbol: s.yahoo_symbol
            for s in stocks
            if s.allow_buy and s.symbol not in recently_bought
        }
        batch_prices = yahoo.get_batch_quotes(symbol_yahoo_map)

        # Calculate minimum worthwhile trade from transaction costs
        min_trade_amount = calculate_min_trade_amount(
            settings.transaction_cost_fixed,
            settings.transaction_cost_percent,
        )

        filter_stats = {
            "total_stocks": len(stocks),
            "eligible_for_pricing": len(symbol_yahoo_map),
            "got_prices": len(batch_prices),
            "recently_bought": list(recently_bought),
            "settings": {
                "min_trade_amount": min_trade_amount,
                "min_stock_score": settings.min_stock_score,
            },
            "no_allow_buy": [],
            "no_score": [],
            "low_score": [],
            "no_price": [],
            "worsens_balance": [],
            "passed_all_filters": [],
        }

        for stock in stocks:
            symbol = stock.symbol
            if not stock.allow_buy:
                filter_stats["no_allow_buy"].append(symbol)
                continue
            if symbol in recently_bought:
                continue

            score_row = await self._db_manager.state.fetchone(
                "SELECT * FROM scores WHERE symbol = ?", (symbol,)
            )
            if not score_row:
                filter_stats["no_score"].append(symbol)
                continue

            total_score = score_row["total_score"] or 0.5
            quality_score = score_row["quality_score"] or 0.5
            if total_score < settings.min_stock_score:
                filter_stats["low_score"].append(
                    {"symbol": symbol, "score": total_score}
                )
                continue

            price = batch_prices.get(symbol)
            if not price or price <= 0:
                filter_stats["no_price"].append(symbol)
                continue

            # Calculate trade value
            min_lot = stock.min_lot or 1
            trade_value = max(min_trade_amount, min_lot * price)

            # Calculate portfolio score impact
            try:
                new_score, score_change = await calculate_post_transaction_score(
                    symbol=symbol,
                    geography=stock.geography,
                    industry=stock.industry,
                    proposed_value=trade_value,
                    stock_quality=quality_score,
                    stock_dividend=0,
                    portfolio_context=portfolio_context,
                    portfolio_hash=cache_key,
                )
                if score_change < MAX_BALANCE_WORSENING:
                    filter_stats["worsens_balance"].append(
                        {
                            "symbol": symbol,
                            "geography": stock.geography,
                            "industry": stock.industry,
                            "score_change": round(score_change, 2),
                            "trade_value": round(trade_value, 2),
                        }
                    )
                    continue

                filter_stats["passed_all_filters"].append(
                    {
                        "symbol": symbol,
                        "score": total_score,
                        "price": round(price, 2),
                        "trade_value": round(trade_value, 2),
                        "score_change": round(score_change, 2),
                    }
                )
            except Exception as e:
                filter_stats["worsens_balance"].append(
                    {
                        "symbol": symbol,
                        "error": str(e),
                    }
                )

        return filter_stats

    async def calculate_rebalance_trades(
        self, available_cash: float
    ) -> List[Recommendation]:
        """
        Calculate optimal trades using get_recommendations() as the source of truth.
        """
        settings = await self._settings_service.get_settings()
        min_trade_amount = calculate_min_trade_amount(
            settings.transaction_cost_fixed,
            settings.transaction_cost_percent,
        )

        if available_cash < min_trade_amount:
            logger.info(
                f"Cash €{available_cash:.2f} below minimum trade €{min_trade_amount:.2f}"
            )
            return []

        max_trades = get_max_trades(available_cash, min_trade_amount)
        if max_trades == 0:
            return []

        recommendations = await self.get_recommendations(limit=max_trades)

        if not recommendations:
            logger.info("No buy recommendations available")
            return []

        # Recommendations are already in unified format, just filter valid ones
        trades = []
        for rec in recommendations:
            if (
                rec.quantity is None
                or rec.quantity <= 0
                or rec.estimated_price is None
                or rec.estimated_price <= 0
            ):
                logger.warning(
                    f"Skipping {rec.symbol}: missing or invalid quantity or price"
                )
                continue

            # Recommendation is already in the correct format
            trades.append(rec)

        logger.info(
            f"Generated {len(trades)} trade recommendations from {len(recommendations)} buy recommendations"
        )

        return trades

    async def calculate_sell_recommendations(
        self, limit: int = 3
    ) -> List[Recommendation]:
        """
        Calculate optimal SELL recommendations based on sell scoring system.
        """
        # Build portfolio context
        portfolio_context = await build_portfolio_context(
            position_repo=self._position_repo,
            stock_repo=self._stock_repo,
            allocation_repo=self._allocation_repo,
            db_manager=self._db_manager,
        )
        total_value = portfolio_context.total_value

        # Get all positions
        positions = await self._position_repo.get_all()
        if not positions:
            logger.info("No positions to evaluate for selling")
            return []

        # Get settings for cache key
        settings = await self._settings_service.get_settings()

        # Generate cache key from positions and settings
        from app.domain.portfolio_hash import generate_recommendation_cache_key

        position_hash_dicts = [
            {"symbol": p.symbol, "quantity": p.quantity} for p in positions
        ]
        cache_key = generate_recommendation_cache_key(
            position_hash_dicts, settings.to_dict()
        )

        # Check cache first (48h TTL)
        rec_cache = get_recommendation_cache()
        cached = await rec_cache.get_recommendations(cache_key, "sell")
        if cached:
            logger.info(f"Using cached sell recommendations ({len(cached)} items)")
            # Convert cached dicts back to Recommendation objects
            from app.domain.value_objects.currency import Currency

            recommendations = []
            for c in cached[:limit]:
                currency_str = c.get("currency", "EUR")
                currency = (
                    Currency.from_string(currency_str)
                    if isinstance(currency_str, str)
                    else currency_str
                )

                recommendations.append(
                    Recommendation(
                        symbol=c["symbol"],
                        name=c["name"],
                        side=TradeSide.SELL,
                        quantity=c["quantity"],
                        estimated_price=c["estimated_price"],
                        estimated_value=c["estimated_value"],
                        reason=c["reason"],
                        geography=c.get("geography", ""),
                        currency=currency,
                        status=RecommendationStatus.PENDING,
                    )
                )
            return recommendations

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

            position_dicts.append(
                {
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
                }
            )

        if not position_dicts:
            return []

        # Get technical data
        symbols = [p["symbol"] for p in position_dicts]
        technical_data = await get_technical_data_for_positions(
            symbols=symbols,
            db_manager=self._db_manager,
        )

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
        settings = await self._settings_service.get_settings()
        from app.domain.value_objects.settings import TradingSettings

        trading_settings = TradingSettings.from_settings(settings)
        sell_settings = {
            "min_hold_days": trading_settings.min_hold_days,
            "sell_cooldown_days": trading_settings.sell_cooldown_days,
            "max_loss_threshold": trading_settings.max_loss_threshold,
            "target_annual_return": trading_settings.target_annual_return,
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

        # Get target allocations for band check
        allocations = await self._allocation_repo.get_all()
        target_geo_weights = {
            key.split(":", 1)[1]: val
            for key, val in allocations.items()
            if key.startswith("geography:")
        }
        target_ind_weights = {
            key.split(":", 1)[1]: val
            for key, val in allocations.items()
            if key.startswith("industry:")
        }

        # Apply rebalancing band filter: skip positions where BOTH geography AND industry
        # are within 7% of target. Sell if EITHER is significantly overweight.
        band_filtered_sells = []
        for score in eligible_sells:
            pos = next((p for p in position_dicts if p["symbol"] == score.symbol), None)
            if not pos:
                continue

            geo = pos.get("geography")
            ind = pos.get("industry")

            # Check if geography is overweight beyond the band
            geo_overweight = False
            if geo:
                current_geo_weight = geo_allocations.get(geo, 0)
                target_geo_weight = target_geo_weights.get(geo, 0.33)
                geo_overweight = (
                    current_geo_weight > target_geo_weight + REBALANCE_BAND_PCT
                )

            # Check if industry is overweight beyond the band
            ind_overweight = False
            if ind:
                current_ind_weight = ind_allocations.get(ind, 0)
                target_ind_weight = target_ind_weights.get(
                    ind, 0.10
                )  # Default 10% per industry
                ind_overweight = (
                    current_ind_weight > target_ind_weight + REBALANCE_BAND_PCT
                )

            # Include if EITHER geography OR industry is overweight
            if not geo_overweight and not ind_overweight:
                # Both are within band, skip this sell
                logger.debug(
                    f"Skipping sell {score.symbol}: both geo ({geo}) and ind ({ind}) within band"
                )
                continue

            band_filtered_sells.append(score)

        if not band_filtered_sells:
            logger.info("No sells remain after rebalancing band filter")
            return []

        eligible_sells = band_filtered_sells
        logger.info(
            f"Found {len(eligible_sells)} positions eligible for selling (after band filter)"
        )

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

            rec = Recommendation(
                symbol=score.symbol,
                name=pos.get("name", score.symbol),
                side=TradeSide.SELL,
                quantity=score.suggested_sell_quantity,
                estimated_price=round(current_price, 2),
                estimated_value=round(score.suggested_sell_value, 2),
                reason=reason,
                geography=stock.geography if stock else "",
                currency=currency,
                status=RecommendationStatus.PENDING,
            )

            # Store recommendation in database (create or update)
            recommendation_data = {
                "symbol": rec.symbol,
                "name": rec.name,
                "side": "SELL",
                "amount": rec.estimated_value,
                "quantity": rec.quantity,
                "estimated_price": rec.estimated_price,
                "estimated_value": rec.estimated_value,
                "reason": rec.reason,
                "geography": pos.get("geography"),
                "industry": pos.get("industry"),
                "currency": currency,
                "priority": score.total_score,
            }

            # create_or_update returns UUID if not dismissed, None if dismissed
            uuid = await self._recommendation_repo.create_or_update(
                recommendation_data, portfolio_hash=cache_key
            )
            if uuid:
                # Only include if not dismissed
                recommendations.append(rec)
                # Publish domain event for recommendations (new or updated)
                event_bus = get_event_bus()
                event_bus.publish(RecommendationCreatedEvent(recommendation=rec))

        # Cache all eligible sell recommendations
        all_sells_for_cache = []
        for score in eligible_sells:
            pos = next((p for p in position_dicts if p["symbol"] == score.symbol), None)
            if pos:
                current_price = pos.get("current_price") or pos.get("avg_price", 0)
                all_sells_for_cache.append(
                    {
                        "symbol": score.symbol,
                        "name": pos.get("name", score.symbol),
                        "quantity": score.suggested_sell_quantity,
                        "estimated_price": round(current_price, 2),
                        "estimated_value": round(score.suggested_sell_value, 2),
                        "reason": f"sell score: {score.total_score:.2f}",
                        "currency": pos.get("currency", "EUR"),
                        "priority": score.total_score,
                    }
                )

        if all_sells_for_cache:
            await rec_cache.set_recommendations(cache_key, "sell", all_sells_for_cache)

        logger.info(f"Generated {len(recommendations)} sell recommendations")

        return recommendations

    async def get_multi_step_recommendations(self) -> List[MultiStepRecommendation]:
        """
        Generate optimal recommendation sequence using the portfolio optimizer + holistic planner.

        Flow:
        1. Portfolio optimizer calculates target weights (MV + HRP blend)
        2. Holistic planner identifies opportunities from weight gaps
        3. Planner generates action sequences and evaluates end-states
        4. Returns the optimal sequence

        Returns:
            List of MultiStepRecommendation objects representing the optimal sequence
        """
        from app.application.services.optimization import PortfolioOptimizer
        from app.domain.planning.holistic_planner import create_holistic_plan
        from app.repositories import DividendRepository

        # Get optimizer settings
        optimizer_blend = await self._settings_repo.get_float("optimizer_blend", 0.5)
        optimizer_target = await self._settings_repo.get_float(
            "optimizer_target_return", 0.11
        )
        transaction_fixed = await self._settings_repo.get_float(
            "transaction_cost_fixed", 2.0
        )
        transaction_pct = await self._settings_repo.get_float(
            "transaction_cost_percent", 0.002
        )
        min_cash = await self._settings_repo.get_float("min_cash_reserve", 500.0)

        # Build portfolio context
        portfolio_context = await build_portfolio_context(
            position_repo=self._position_repo,
            stock_repo=self._stock_repo,
            allocation_repo=self._allocation_repo,
            db_manager=self._db_manager,
        )

        # Get positions and stocks
        positions = await self._position_repo.get_all()
        stocks = await self._stock_repo.get_all_active()

        # Get current cash balance
        available_cash = (
            self._tradernet_client.get_total_cash_eur()
            if self._tradernet_client.is_connected
            else 0.0
        )

        # Get current prices for all stocks
        yahoo_symbols = {s.symbol: s.yahoo_symbol for s in stocks if s.yahoo_symbol}
        current_prices = yahoo.get_batch_quotes(yahoo_symbols)

        # Build positions dict for optimizer
        positions_dict = {p.symbol: p for p in positions}

        # Calculate portfolio value
        portfolio_value = portfolio_context.total_value

        # Get geography/industry targets from allocations
        geo_allocations = await self._allocation_repo.get_by_type("geography")
        ind_allocations = await self._allocation_repo.get_by_type("industry")
        geo_targets = {a.name: a.target_pct / 100 for a in geo_allocations}
        ind_targets = {a.name: a.target_pct / 100 for a in ind_allocations}

        # Get pending dividend bonuses (DRIP fallback)
        dividend_repo = DividendRepository()
        dividend_bonuses = await dividend_repo.get_pending_bonuses()

        # Run portfolio optimizer
        optimizer = PortfolioOptimizer()
        optimization_result = await optimizer.optimize(
            stocks=stocks,
            positions=positions_dict,
            portfolio_value=portfolio_value,
            current_prices=current_prices,
            cash_balance=available_cash,
            blend=optimizer_blend,
            target_return=optimizer_target,
            geo_targets=geo_targets,
            ind_targets=ind_targets,
            min_cash_reserve=min_cash,
            dividend_bonuses=dividend_bonuses,
        )

        # Log optimizer result
        if optimization_result.success:
            logger.info(
                f"Optimizer: blend={optimizer_blend}, "
                f"target={optimizer_target:.1%}, "
                f"achieved={optimization_result.achieved_expected_return:.1%}, "
                f"fallback={optimization_result.fallback_used}"
            )
            target_weights = optimization_result.target_weights
        else:
            logger.warning(
                f"Optimizer failed: {optimization_result.error}, using heuristics"
            )
            target_weights = None

        # Create holistic plan with optimizer weights
        plan = await create_holistic_plan(
            portfolio_context=portfolio_context,
            available_cash=available_cash,
            stocks=stocks,
            positions=positions,
            exchange_rate_service=self._exchange_rate_service,
            target_weights=target_weights,
            current_prices=current_prices,
            transaction_cost_fixed=transaction_fixed,
            transaction_cost_percent=transaction_pct,
        )

        # Convert HolisticPlan to MultiStepRecommendation list
        if not plan.steps:
            return []

        recommendations = []
        running_cash = available_cash
        for step in plan.steps:
            cash_before = running_cash
            if step.side == TradeSide.SELL:
                running_cash += step.estimated_value
            else:
                running_cash -= step.estimated_value
            running_cash = max(0, running_cash)

            recommendations.append(
                MultiStepRecommendation(
                    step=step.step_number,
                    side=step.side,
                    symbol=step.symbol,
                    name=step.name,
                    quantity=step.quantity,
                    estimated_price=step.estimated_price,
                    estimated_value=step.estimated_value,
                    currency=step.currency,
                    reason=step.narrative,
                    portfolio_score_before=plan.current_score,
                    portfolio_score_after=plan.end_state_score,
                    score_change=plan.improvement,
                    available_cash_before=cash_before,
                    available_cash_after=running_cash,
                )
            )

        logger.info(
            f"Holistic planner generated {len(recommendations)} recommendations"
        )
        return recommendations
