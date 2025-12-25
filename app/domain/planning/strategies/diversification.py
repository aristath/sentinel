"""
Diversification Strategy - Focuses on portfolio diversification (geography/industry).
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


class DiversificationStrategy(RecommendationStrategy):
    """Strategy focused on portfolio diversification (geography/industry)."""
    
    @property
    def strategy_name(self) -> str:
        return "diversification"
    
    @property
    def strategy_description(self) -> str:
        return "Optimizes portfolio diversification by rebalancing geography and industry allocations to match targets"
    
    async def analyze_goals(
        self,
        portfolio_context: PortfolioContext,
        positions: List[Position],
        stocks: List[Stock],
        min_gap_threshold: float = 0.05
    ) -> List[StrategicGoal]:
        """
        Analyze geography/industry allocation gaps.
        
        Logic:
        - Calculate current allocations for each geography/industry
        - Compare to target allocations
        - Identify gaps: gap = current_pct - target_pct
        - For each gap above threshold:
          - Calculate priority: gap_size * portfolio_score_impact
          - Estimate value change needed: gap_size * total_portfolio_value
        - Sort by priority score
        """
        goals = []
        total_value = portfolio_context.total_value
        
        if total_value <= 0:
            return goals
        
        # Calculate current geography allocations
        geo_values: Dict[str, float] = {}
        for symbol, value in portfolio_context.positions.items():
            geo = portfolio_context.stock_geographies.get(symbol, "OTHER")
            geo_values[geo] = geo_values.get(geo, 0) + value
        
        # Calculate current industry allocations
        ind_values: Dict[str, float] = {}
        for symbol, value in portfolio_context.positions.items():
            industries = portfolio_context.stock_industries.get(symbol)
            if industries:
                # Handle comma-separated industries
                for ind in industries.split(","):
                    ind = ind.strip()
                    if ind:
                        ind_values[ind] = ind_values.get(ind, 0) + value
        
        # Analyze geography gaps
        for geo, weight in portfolio_context.geo_weights.items():
            target_pct = 0.33 + (weight * 0.15)  # Base 33% +/- 15%
            current_pct = geo_values.get(geo, 0) / total_value if total_value > 0 else 0
            gap = current_pct - target_pct
            
            if abs(gap) >= min_gap_threshold:
                # Calculate portfolio score impact
                # Simulate closing the gap and see score improvement
                impact = abs(gap) * 2.0  # Rough estimate: 1% gap = 2 points impact
                
                priority_score = abs(gap) * impact
                target_value_change = abs(gap) * total_value
                
                action = "decrease" if gap > 0 else "increase"
                description = f"{action.capitalize()} {geo} allocation from {current_pct*100:.1f}% to {target_pct*100:.1f}%"
                
                goals.append(StrategicGoal(
                    strategy_type="diversification",
                    category="geography",
                    name=geo,
                    action=action,
                    current_value=current_pct,
                    target_value=target_pct,
                    gap_size=abs(gap),
                    priority_score=priority_score,
                    target_value_change=target_value_change,
                    description=description
                ))
        
        # Analyze industry gaps
        for ind, weight in portfolio_context.industry_weights.items():
            # Industry targets are typically smaller (base 10% +/- 10%)
            target_pct = 0.10 + (weight * 0.10)
            current_pct = ind_values.get(ind, 0) / total_value if total_value > 0 else 0
            gap = current_pct - target_pct
            
            if abs(gap) >= min_gap_threshold:
                impact = abs(gap) * 1.5  # Industry gaps have less impact
                priority_score = abs(gap) * impact
                target_value_change = abs(gap) * total_value
                
                action = "decrease" if gap > 0 else "increase"
                description = f"{action.capitalize()} {ind} allocation from {current_pct*100:.1f}% to {target_pct*100:.1f}%"
                
                goals.append(StrategicGoal(
                    strategy_type="diversification",
                    category="industry",
                    name=ind,
                    action=action,
                    current_value=current_pct,
                    target_value=target_pct,
                    gap_size=abs(gap),
                    priority_score=priority_score,
                    target_value_change=target_value_change,
                    description=description
                ))
        
        # Sort by priority score (highest first)
        goals.sort(key=lambda g: g.priority_score, reverse=True)
        
        return goals
    
    async def find_best_buys(
        self,
        goals: List[StrategicGoal],
        portfolio_context: PortfolioContext,
        available_stocks: List[Stock],
        available_cash: float
    ) -> List[Dict]:
        """Find stocks in underweight regions/industries."""
        increase_goals = [g for g in goals if g.action == "increase"]
        
        if not increase_goals:
            return []
        
        # Get base trade amount
        from app.repositories import SettingsRepository
        settings_repo = SettingsRepository()
        base_trade_amount = await settings_repo.get_float("min_trade_size", 150.0)
        
        # Get recently bought symbols for cooldown
        from app.repositories import TradeRepository
        trade_repo = TradeRepository()
        recently_bought = await trade_repo.get_recently_bought_symbols(BUY_COOLDOWN_DAYS)
        
        # Build target geographies/industries to focus on
        target_geos = {g.name for g in increase_goals if g.category == "geography"}
        target_industries = {g.name for g in increase_goals if g.category == "industry"}
        
        # Filter stocks by target geography/industry
        candidate_stocks = []
        for stock in available_stocks:
            if not stock.allow_buy:
                continue
            if stock.symbol in recently_bought:
                continue
            
            matches = False
            if stock.geography in target_geos:
                matches = True
            if stock.industry and target_industries:
                stock_industries = [i.strip() for i in stock.industry.split(",")]
                if any(ind in target_industries for ind in stock_industries):
                    matches = True
            
            if matches:
                candidate_stocks.append(stock)
        
        if not candidate_stocks:
            return []
        
        # Get prices for candidates
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
            
            # Get scores
            score_row = await db_manager.state.fetchone(
                "SELECT * FROM scores WHERE symbol = ?",
                (symbol,)
            )
            if not score_row:
                continue
            
            total_score = score_row["total_score"] or 0.5
            if total_score < settings.min_stock_score:
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
            geography = stock.geography
            industry = stock.industry
            quality_score = score_row["quality_score"] or 0.5
            
            new_score, score_change = calculate_post_transaction_score(
                symbol=symbol,
                geography=geography,
                industry=industry,
                proposed_value=trade_value_eur,
                stock_quality=quality_score,
                stock_dividend=0.0,
                portfolio_context=portfolio_context,
            )
            
            # Build reason
            reason_parts = []
            if stock.geography in target_geos:
                reason_parts.append(f"underweight {stock.geography}")
            if stock.industry and target_industries:
                stock_industries = [i.strip() for i in stock.industry.split(",")]
                matching_inds = [ind for ind in stock_industries if ind in target_industries]
                if matching_inds:
                    reason_parts.append(f"underweight {', '.join(matching_inds)}")
            if score_change > 0:
                reason_parts.append(f"+{score_change:.1f} portfolio")
            
            candidates.append({
                "symbol": symbol,
                "name": stock.name,
                "amount": trade_value_eur,
                "quantity": quantity,
                "price": price,
                "reason": ", ".join(reason_parts) if reason_parts else "diversification",
                "score_change": score_change,
            })
        
        # Sort by score change (best improvements first)
        candidates.sort(key=lambda x: x["score_change"], reverse=True)
        
        return candidates
    
    async def find_best_sells(
        self,
        goals: List[StrategicGoal],
        portfolio_context: PortfolioContext,
        positions: List[Position],
        available_cash: float
    ) -> List[Dict]:
        """Find positions in overweight regions/industries."""
        decrease_goals = [g for g in goals if g.action == "decrease"]
        
        if not decrease_goals:
            return []
        
        # Build target geographies/industries to reduce
        target_geos = {g.name for g in decrease_goals if g.category == "geography"}
        target_industries = {g.name for g in decrease_goals if g.category == "industry"}
        
        # Filter positions by target geography/industry
        from app.repositories import StockRepository
        stock_repo = StockRepository()
        stocks = await stock_repo.get_all_active()
        stocks_by_symbol = {s.symbol: s for s in stocks}
        
        candidate_positions = []
        for pos in positions:
            stock = stocks_by_symbol.get(pos.symbol)
            if not stock:
                continue
            if not stock.allow_sell:
                continue
            
            matches = False
            if stock.geography in target_geos:
                matches = True
            if stock.industry and target_industries:
                stock_industries = [i.strip() for i in stock.industry.split(",")]
                if any(ind in target_industries for ind in stock_industries):
                    matches = True
            
            if matches and pos.market_value_eur and pos.market_value_eur > 0:
                candidate_positions.append((pos, stock))
        
        if not candidate_positions:
            return []
        
        # Use existing sell scoring to prioritize
        from app.domain.scoring import calculate_all_sell_scores
        from app.repositories import TradeRepository
        trade_repo = TradeRepository()
        
        position_dicts = []
        for pos, stock in candidate_positions:
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
        
        for score in eligible_sells:
            pos_dict = next((p for p in position_dicts if p["symbol"] == score.symbol), None)
            if not pos_dict:
                continue
            
            # Build reason
            reason_parts = []
            if pos_dict["geography"] in target_geos:
                reason_parts.append(f"overweight {pos_dict['geography']}")
            if pos_dict.get("industry") and target_industries:
                stock_industries = [i.strip() for i in pos_dict["industry"].split(",")]
                matching_inds = [ind for ind in stock_industries if ind in target_industries]
                if matching_inds:
                    reason_parts.append(f"overweight {', '.join(matching_inds)}")
            reason_parts.append(f"sell score: {score.total_score:.2f}")
            
            candidates.append({
                "symbol": score.symbol,
                "name": pos_dict.get("name", score.symbol),
                "quantity": score.suggested_sell_quantity,
                "estimated_value": score.suggested_sell_value,
                "reason": ", ".join(reason_parts),
            })
        
        # Sort by sell score (highest first)
        candidates.sort(key=lambda x: next(
            s.total_score for s in eligible_sells if s.symbol == x["symbol"]
        ), reverse=True)
        
        return candidates

