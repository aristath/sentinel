"""
Sustainability Strategy - Focuses on long-term portfolio sustainability and quality.
"""

import logging
from typing import List, Dict

from app.domain.planning.strategies.base import RecommendationStrategy, StrategicGoal
from app.domain.scoring.models import PortfolioContext
from app.domain.scoring.diversification import calculate_portfolio_score
from app.domain.scoring import calculate_post_transaction_score
from app.domain.models import Stock, Position
from app.services import yahoo
from app.services.tradernet import get_exchange_rate
from app.config import settings
from app.domain.constants import BUY_COOLDOWN_DAYS

logger = logging.getLogger(__name__)


class SustainabilityStrategy(RecommendationStrategy):
    """Strategy focused on long-term portfolio sustainability and quality."""
    
    @property
    def strategy_name(self) -> str:
        return "sustainability"
    
    @property
    def strategy_description(self) -> str:
        return "Optimizes portfolio for long-term sustainability by improving quality scores, fundamentals, and long-term performance metrics"
    
    async def analyze_goals(
        self,
        portfolio_context: PortfolioContext,
        positions: List[Position],
        stocks: List[Stock],
        min_gap_threshold: float = 0.05
    ) -> List[StrategicGoal]:
        """
        Analyze long-term portfolio health metrics.
        
        Goals:
        - Improve average quality score (if below threshold)
        - Increase long-term performance (CAGR, Sortino, Sharpe)
        - Strengthen fundamentals (financial strength, consistency)
        - Reduce low-quality positions
        """
        goals = []
        total_value = portfolio_context.total_value
        
        if total_value <= 0 or not portfolio_context.stock_scores:
            return goals
        
        # Calculate weighted average quality score
        weighted_quality = 0.0
        for symbol, value in portfolio_context.positions.items():
            quality = portfolio_context.stock_scores.get(symbol, 0.5) or 0.5
            weighted_quality += quality * (value / total_value)
        
        # Target quality score
        target_quality = 0.70
        quality_gap = target_quality - weighted_quality
        
        if quality_gap >= min_gap_threshold:
            # Calculate priority based on gap size
            priority_score = quality_gap * 10.0  # 0.1 gap = 1.0 priority
            target_value_change = quality_gap * total_value * 0.5  # Estimate: need to replace 50% of gap
            
            goals.append(StrategicGoal(
                strategy_type="sustainability",
                category="quality",
                name="quality_score",
                action="increase",
                current_value=weighted_quality,
                target_value=target_quality,
                gap_size=quality_gap,
                priority_score=priority_score,
                target_value_change=target_value_change,
                description=f"Increase average quality score from {weighted_quality:.2f} to {target_quality:.2f}"
            ))
        
        # Identify low-quality positions to replace
        low_quality_threshold = 0.50
        low_quality_value = 0.0
        low_quality_count = 0
        
        for symbol, value in portfolio_context.positions.items():
            quality = portfolio_context.stock_scores.get(symbol, 0.5) or 0.5
            if quality < low_quality_threshold:
                low_quality_value += value
                low_quality_count += 1
        
        if low_quality_count > 0 and low_quality_value / total_value >= min_gap_threshold:
            priority_score = (low_quality_value / total_value) * 8.0
            target_value_change = low_quality_value * 0.5  # Replace 50% of low-quality positions
            
            goals.append(StrategicGoal(
                strategy_type="sustainability",
                category="quality",
                name="low_quality_positions",
                action="decrease",
                current_value=low_quality_value / total_value,
                target_value=0.0,
                gap_size=low_quality_value / total_value,
                priority_score=priority_score,
                target_value_change=target_value_change,
                description=f"Replace {low_quality_count} low-quality positions ({low_quality_value/total_value*100:.1f}% of portfolio)"
            ))
        
        # Sort by priority score
        goals.sort(key=lambda g: g.priority_score, reverse=True)
        
        return goals
    
    async def find_best_buys(
        self,
        goals: List[StrategicGoal],
        portfolio_context: PortfolioContext,
        available_stocks: List[Stock],
        available_cash: float
    ) -> List[Dict]:
        """Find stocks with high long_term + fundamentals scores."""
        increase_goals = [g for g in goals if g.action == "increase"]
        
        if not increase_goals:
            return []
        
        # Get base trade amount
        from app.repositories import SettingsRepository
        settings_repo = SettingsRepository()
        base_trade_amount = await settings_repo.get_float("min_trade_size", 150.0)
        
        # Get recently bought symbols
        from app.repositories import TradeRepository
        trade_repo = TradeRepository()
        recently_bought = await trade_repo.get_recently_bought_symbols(BUY_COOLDOWN_DAYS)
        
        # Filter stocks
        candidate_stocks = [
            s for s in available_stocks
            if s.allow_buy and s.symbol not in recently_bought
        ]
        
        if not candidate_stocks:
            return []
        
        # Get prices
        symbol_yahoo_map = {s.symbol: s.yahoo_symbol for s in candidate_stocks if s.yahoo_symbol}
        batch_prices = yahoo.get_batch_quotes(symbol_yahoo_map)
        
        # Get scores from database
        from app.infrastructure.database.manager import get_db_manager
        db_manager = get_db_manager()
        
        candidates = []
        for stock in candidate_stocks:
            symbol = stock.symbol
            price = batch_prices.get(symbol)
            if not price or price <= 0:
                continue
            
            # Get scores - focus on quality, long_term, fundamentals
            score_row = await db_manager.state.fetchone(
                "SELECT * FROM scores WHERE symbol = ?",
                (symbol,)
            )
            if not score_row:
                continue
            
            quality_score = score_row["quality_score"] or 0.5
            total_score = score_row["total_score"] or 0.5

            # Only consider above-average quality stocks
            # Lowered from 0.65 to 0.55 to ensure buy candidates are available
            if quality_score < 0.55 or total_score < settings.min_stock_score:
                continue
            
            # Determine currency and exchange rate
            currency = stock.currency or "EUR"
            exchange_rate = 1.0
            if currency != "EUR":
                exchange_rate = get_exchange_rate(currency, "EUR")
                if exchange_rate <= 0:
                    exchange_rate = 1.0
            
            # Calculate trade amount
            min_lot = stock.min_lot or 1
            lot_cost_native = min_lot * price
            lot_cost_eur = lot_cost_native / exchange_rate
            
            if lot_cost_eur > base_trade_amount:
                quantity = min_lot
                trade_value_eur = lot_cost_eur
            else:
                base_trade_amount_native = base_trade_amount * exchange_rate
                num_lots = int(base_trade_amount_native / lot_cost_native)
                quantity = num_lots * min_lot
                trade_value_eur = quantity * price / exchange_rate
            
            # Calculate portfolio score improvement
            new_score, score_change = await calculate_post_transaction_score(
                symbol=symbol,
                geography=stock.geography,
                industry=stock.industry,
                proposed_value=trade_value_eur,
                stock_quality=quality_score,
                stock_dividend=0.0,
                portfolio_context=portfolio_context,
            )
            
            # Build reason
            reason_parts = []
            if quality_score >= 0.75:
                reason_parts.append("high quality")
            if quality_score >= 0.80:
                reason_parts.append("excellent quality")
            if score_change > 0:
                reason_parts.append(f"+{score_change:.1f} portfolio")
            
            candidates.append({
                "symbol": symbol,
                "name": stock.name,
                "amount": trade_value_eur,
                "quantity": quantity,
                "price": price,
                "reason": ", ".join(reason_parts) if reason_parts else "sustainability",
                "score_change": score_change,
                "quality_score": quality_score,  # For sorting
            })
        
        # Sort by quality score first, then score change
        candidates.sort(key=lambda x: (x["quality_score"], x["score_change"]), reverse=True)
        
        return candidates
    
    async def find_best_sells(
        self,
        goals: List[StrategicGoal],
        portfolio_context: PortfolioContext,
        positions: List[Position],
        available_cash: float
    ) -> List[Dict]:
        """Find positions with low quality, underperforming long-term."""
        decrease_goals = [g for g in goals if g.action == "decrease"]
        
        if not decrease_goals:
            return []
        
        # Get stock info
        from app.repositories import StockRepository
        stock_repo = StockRepository()
        stocks = await stock_repo.get_all_active()
        stocks_by_symbol = {s.symbol: s for s in stocks}
        
        # Filter to low-quality positions
        low_quality_threshold = 0.50
        candidate_positions = []
        
        for pos in positions:
            stock = stocks_by_symbol.get(pos.symbol)
            if not stock or not stock.allow_sell:
                continue
            
            quality = portfolio_context.stock_scores.get(pos.symbol, 0.5) or 0.5
            if quality < low_quality_threshold and pos.market_value_eur and pos.market_value_eur > 0:
                candidate_positions.append((pos, stock, quality))
        
        if not candidate_positions:
            return []
        
        # Use existing sell scoring
        from app.domain.scoring import calculate_all_sell_scores
        from app.repositories import TradeRepository
        trade_repo = TradeRepository()
        
        position_dicts = []
        for pos, stock, quality in candidate_positions:
            first_buy = await trade_repo.get_first_buy_date(pos.symbol)
            last_sell = await trade_repo.get_last_sell_date(pos.symbol)
            
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
        
        # Get technical data
        from app.application.services.rebalancing_service import RebalancingService
        rebalancing_service = RebalancingService()
        symbols = [p["symbol"] for p in position_dicts]
        technical_data = await rebalancing_service._get_technical_data_for_positions(symbols)
        
        # Build allocation maps
        total_value = portfolio_context.total_value
        geo_allocations = {}
        ind_allocations = {}
        for pos_dict in position_dicts:
            geo = pos_dict.get("geography")
            ind = pos_dict.get("industry")
            value = pos_dict.get("market_value_eur") or 0
            if geo:
                geo_allocations[geo] = geo_allocations.get(geo, 0) + value / total_value
            if ind:
                ind_allocations[ind] = ind_allocations.get(ind, 0) + value / total_value
        
        # Get sell settings
        from app.repositories import SettingsRepository
        settings_repo = SettingsRepository()
        sell_settings = {
            "min_hold_days": await settings_repo.get_int("min_hold_days", 90),
            "sell_cooldown_days": await settings_repo.get_int("sell_cooldown_days", 180),
            "max_loss_threshold": await settings_repo.get_float("max_loss_threshold", -0.20),
            "target_annual_return": await settings_repo.get_float("target_annual_return", 0.10),
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
        
        # Filter to eligible sells and build results
        eligible_sells = [s for s in sell_scores if s.eligible]
        candidates = []
        
        # Create quality map for sorting
        quality_map = {pos.symbol: quality for pos, _, quality in candidate_positions}
        
        for score in eligible_sells:
            pos_dict = next((p for p in position_dicts if p["symbol"] == score.symbol), None)
            if not pos_dict:
                continue
            
            quality = quality_map.get(score.symbol, 0.5)
            
            # Build reason
            reason_parts = []
            reason_parts.append(f"low quality ({quality:.2f})")
            reason_parts.append(f"sell score: {score.total_score:.2f}")
            
            candidates.append({
                "symbol": score.symbol,
                "name": pos_dict.get("name", score.symbol),
                "quantity": score.suggested_sell_quantity,
                "estimated_value": score.suggested_sell_value,
                "reason": ", ".join(reason_parts),
                "quality_score": quality,  # For sorting
            })
        
        # Sort by quality (lowest first) then sell score
        candidates.sort(key=lambda x: (x["quality_score"], -next(
            s.total_score for s in eligible_sells if s.symbol == x["symbol"]
        )))
        
        return candidates

