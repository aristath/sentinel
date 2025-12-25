"""
Opportunity Strategy - Focuses on value opportunities and dip-buying.
"""

import logging
from typing import List, Dict

from app.domain.planning.strategies.base import RecommendationStrategy, StrategicGoal
from app.domain.scoring.models import PortfolioContext
from app.domain.scoring.diversification import calculate_portfolio_score
from app.domain.scoring import calculate_post_transaction_score
# get_52_week_high is now async - imported in function
from app.domain.models import Stock, Position
from app.services import yahoo
from app.services.tradernet import get_exchange_rate
from app.config import settings
from app.domain.constants import BUY_COOLDOWN_DAYS
import numpy as np

logger = logging.getLogger(__name__)


class OpportunityStrategy(RecommendationStrategy):
    """Strategy focused on value opportunities and dip-buying."""
    
    @property
    def strategy_name(self) -> str:
        return "opportunity"
    
    @property
    def strategy_description(self) -> str:
        return "Seeks value opportunities by identifying undervalued stocks (far below 52W high, low P/E) and taking profits on recovered positions"
    
    async def analyze_goals(
        self,
        portfolio_context: PortfolioContext,
        positions: List[Position],
        stocks: List[Stock],
        min_gap_threshold: float = 0.05
    ) -> List[StrategicGoal]:
        """
        Analyze value opportunities in the market.
        
        Goals:
        - Capture undervalued stocks (high opportunity_score)
        - Buy dips (far below 52W high)
        - Take profits on recovered positions
        """
        goals = []
        total_value = portfolio_context.total_value
        
        if total_value <= 0:
            return goals
        
        # Calculate average opportunity score of portfolio
        from app.infrastructure.database.manager import get_db_manager
        db_manager = get_db_manager()
        
        # Batch query all opportunity scores at once (fixes N+1 query problem)
        symbols = list(portfolio_context.positions.keys())
        if not symbols:
            return goals
        
        placeholders = ",".join("?" * len(symbols))
        score_rows = await db_manager.state.fetchall(
            f"SELECT symbol, opportunity_score FROM scores WHERE symbol IN ({placeholders})",
            tuple(symbols)
        )
        
        # Build score map
        opportunity_scores = {row["symbol"]: row["opportunity_score"] or 0.5 for row in score_rows}
        
        # Calculate average opportunity score
        portfolio_opportunity_scores = [
            opportunity_scores.get(symbol, 0.5)
            for symbol in symbols
            if opportunity_scores.get(symbol) is not None
        ]
        
        avg_portfolio_opportunity = (
            sum(portfolio_opportunity_scores) / len(portfolio_opportunity_scores)
            if portfolio_opportunity_scores else 0.5
        )
        
        # Goal: Increase average opportunity score if below threshold
        target_opportunity = 0.60
        opportunity_gap = target_opportunity - avg_portfolio_opportunity
        
        if opportunity_gap >= min_gap_threshold:
            priority_score = opportunity_gap * 8.0
            target_value_change = opportunity_gap * total_value * 0.3  # Replace 30% to improve opportunity
            
            goals.append(StrategicGoal(
                strategy_type="opportunity",
                category="opportunity",
                name="opportunity_score",
                action="increase",
                current_value=avg_portfolio_opportunity,
                target_value=target_opportunity,
                gap_size=opportunity_gap,
                priority_score=priority_score,
                target_value_change=target_value_change,
                description=f"Increase average opportunity score from {avg_portfolio_opportunity:.2f} to {target_opportunity:.2f}"
            ))
        
        # Identify recovered positions (near 52W high, low opportunity)
        recovered_value = 0.0
        recovered_count = 0
        
        for symbol, value in portfolio_context.positions.items():
            opp_score = opportunity_scores.get(symbol, 0.5)
            # Low opportunity score means near 52W high (recovered)
            if opp_score < 0.30:
                recovered_value += value
                recovered_count += 1
        
        if recovered_count > 0 and recovered_value / total_value >= min_gap_threshold:
            priority_score = (recovered_value / total_value) * 6.0
            target_value_change = recovered_value * 0.4  # Take profits on 40% of recovered positions
            
            goals.append(StrategicGoal(
                strategy_type="opportunity",
                category="opportunity",
                name="recovered_positions",
                action="decrease",
                current_value=recovered_value / total_value,
                target_value=0.0,
                gap_size=recovered_value / total_value,
                priority_score=priority_score,
                target_value_change=target_value_change,
                description=f"Take profits on {recovered_count} recovered positions ({recovered_value/total_value*100:.1f}% of portfolio)"
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
        """Find stocks with high opportunity_score (52W high distance, low P/E)."""
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
        
        # Get scores and price history for opportunity calculation
        from app.infrastructure.database.manager import get_db_manager
        db_manager = get_db_manager()
        
        candidates = []
        for stock in candidate_stocks:
            symbol = stock.symbol
            price = batch_prices.get(symbol)
            if not price or price <= 0:
                continue
            
            # Get scores - focus on opportunity_score
            score_row = await db_manager.state.fetchone(
                "SELECT * FROM scores WHERE symbol = ?",
                (symbol,)
            )
            if not score_row:
                continue
            
            opportunity_score = score_row["opportunity_score"] or 0.5
            total_score = score_row["total_score"] or 0.5
            
            # Only consider high-opportunity stocks
            if opportunity_score < 0.60 or total_score < settings.min_stock_score:
                continue
            
            # Get price history to calculate 52W high distance
            try:
                from app.domain.scoring.technical import get_52_week_high
                
                history_db = await db_manager.history(symbol)
                rows = await history_db.fetchall(
                    "SELECT high_price FROM daily_prices ORDER BY date DESC LIMIT 252"
                )
                
                if rows:
                    highs = np.array([row['high_price'] for row in rows if row['high_price']])
                    if len(highs) > 0:
                        high_52w = await get_52_week_high(symbol, highs)
                        pct_below = (high_52w - price) / high_52w if high_52w > 0 else 0
                    else:
                        pct_below = 0
                else:
                    pct_below = 0
            except Exception as e:
                logger.debug(f"Could not get 52W high for {symbol}: {e}")
                pct_below = 0
            
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
            quality_score = score_row["quality_score"] or 0.5
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
            if opportunity_score >= 0.75:
                reason_parts.append("high opportunity")
            if pct_below >= 0.20:
                reason_parts.append(f"{pct_below*100:.0f}% below 52W high")
            if score_change > 0:
                reason_parts.append(f"+{score_change:.1f} portfolio")
            
            candidates.append({
                "symbol": symbol,
                "name": stock.name,
                "amount": trade_value_eur,
                "quantity": quantity,
                "price": price,
                "reason": ", ".join(reason_parts) if reason_parts else "opportunity",
                "score_change": score_change,
                "opportunity_score": opportunity_score,  # For sorting
            })
        
        # Sort by opportunity score (highest first)
        candidates.sort(key=lambda x: x["opportunity_score"], reverse=True)
        
        return candidates
    
    async def find_best_sells(
        self,
        goals: List[StrategicGoal],
        portfolio_context: PortfolioContext,
        positions: List[Position],
        available_cash: float
    ) -> List[Dict]:
        """Find positions that have recovered (near 52W high, low opportunity)."""
        decrease_goals = [g for g in goals if g.action == "decrease"]
        
        if not decrease_goals:
            return []
        
        # Get stock info
        from app.repositories import StockRepository
        stock_repo = StockRepository()
        stocks = await stock_repo.get_all_active()
        stocks_by_symbol = {s.symbol: s for s in stocks}
        
        # Get opportunity scores for positions
        from app.infrastructure.database.manager import get_db_manager
        db_manager = get_db_manager()
        
        # Filter to recovered positions (low opportunity score = near 52W high)
        recovered_threshold = 0.30
        candidate_positions = []
        
        for pos in positions:
            stock = stocks_by_symbol.get(pos.symbol)
            if not stock or not stock.allow_sell:
                continue
            
            score_row = await db_manager.state.fetchone(
                "SELECT opportunity_score FROM scores WHERE symbol = ?",
                (pos.symbol,)
            )
            if score_row:
                opp_score = score_row["opportunity_score"] or 0.5
                if opp_score < recovered_threshold and pos.market_value_eur and pos.market_value_eur > 0:
                    candidate_positions.append((pos, stock, opp_score))
        
        if not candidate_positions:
            return []
        
        # Use existing sell scoring
        from app.domain.scoring import calculate_all_sell_scores
        from app.repositories import TradeRepository
        trade_repo = TradeRepository()
        
        position_dicts = []
        for pos, stock, opp_score in candidate_positions:
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
        
        # Create opportunity score map for sorting
        opp_map = {pos.symbol: opp_score for pos, _, opp_score in candidate_positions}
        
        for score in eligible_sells:
            pos_dict = next((p for p in position_dicts if p["symbol"] == score.symbol), None)
            if not pos_dict:
                continue
            
            opp_score = opp_map.get(score.symbol, 0.5)
            
            # Build reason
            reason_parts = []
            reason_parts.append(f"recovered (opp: {opp_score:.2f})")
            reason_parts.append(f"sell score: {score.total_score:.2f}")
            
            candidates.append({
                "symbol": score.symbol,
                "name": pos_dict.get("name", score.symbol),
                "quantity": score.suggested_sell_quantity,
                "estimated_value": score.suggested_sell_value,
                "reason": ", ".join(reason_parts),
                "opportunity_score": opp_score,  # For sorting
            })
        
        # Sort by opportunity score (lowest first - most recovered) then sell score
        candidates.sort(key=lambda x: (x["opportunity_score"], -next(
            s.total_score for s in eligible_sells if s.symbol == x["symbol"]
        )))
        
        return candidates

