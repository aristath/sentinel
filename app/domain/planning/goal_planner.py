"""
Goal-Driven Planner - Creates multi-step plans to achieve strategic goals.
"""

import logging
from typing import List, Dict, Optional, Callable, Awaitable, Tuple
from dataclasses import dataclass

from app.domain.planning.strategies.base import RecommendationStrategy, StrategicGoal
from app.domain.scoring.models import PortfolioContext
from app.domain.scoring.diversification import calculate_portfolio_score
from app.domain.models import Stock, Position
from app.domain.constants import TRADE_SIDE_BUY, TRADE_SIDE_SELL

logger = logging.getLogger(__name__)


@dataclass
class PlanStep:
    """A single step in a strategic plan."""
    step_number: int
    side: str  # "BUY" or "SELL"
    symbol: str
    name: str
    quantity: int
    estimated_price: float
    estimated_value: float  # In EUR
    currency: str
    reason: str
    goal_contribution: str  # "Reduces EU allocation by 2%"
    portfolio_score_before: float
    portfolio_score_after: float
    score_change: float
    available_cash_before: float
    available_cash_after: float


@dataclass
class StrategicPlan:
    """A complete strategic plan with goals and steps."""
    strategy_name: str
    goals: List[StrategicGoal]
    steps: List[PlanStep]
    total_score_improvement: float
    cash_required: float
    cash_generated: float


async def create_strategic_plan(
    strategy: RecommendationStrategy,
    goals: List[StrategicGoal],
    portfolio_context: PortfolioContext,
    available_cash: float,
    stocks: List[Stock],
    positions: List[Position],
    max_steps: int = 5,
    simulate_portfolio_after_transaction: Optional[Callable[[PortfolioContext, Dict, float], Awaitable[Tuple[PortfolioContext, float]]]] = None
) -> StrategicPlan:
    """
    Create a multi-step plan to achieve strategic goals using a specific strategy.
    
    Works backwards:
    1. Use strategy to find best buys (from "increase" goals)
    2. Calculate cash needed
    3. Use strategy to find best sells (from "decrease" goals + cash needs)
    4. Build sequence: sells first, then buys
    
    Args:
        strategy: The recommendation strategy to use
        goals: Strategic goals to achieve
        portfolio_context: Current portfolio context
        available_cash: Available cash in EUR
        stocks: Available stocks
        positions: Current positions
        max_steps: Maximum number of steps in the plan
        simulate_portfolio_after_transaction: Function to simulate portfolio after transaction
    
    Returns:
        StrategicPlan with steps to achieve goals
    """
    if not goals:
        return StrategicPlan(
            strategy_name=strategy.strategy_name,
            goals=[],
            steps=[],
            total_score_improvement=0.0,
            cash_required=0.0,
            cash_generated=0.0,
        )
    
    # Group goals by action
    increase_goals = [g for g in goals if g.action == "increase"]
    decrease_goals = [g for g in goals if g.action == "decrease"]
    
    # Find best buys for increase goals
    buy_candidates = await strategy.find_best_buys(
        increase_goals,
        portfolio_context,
        stocks,
        available_cash
    )
    
    # Find best sells for decrease goals
    sell_candidates = await strategy.find_best_sells(
        decrease_goals,
        portfolio_context,
        positions,
        available_cash
    )
    
    # Calculate total cash needed for buys
    total_cash_needed = sum(c.get("amount", 0) for c in buy_candidates)
    cash_deficit = max(0, total_cash_needed - available_cash)
    
    # If we need more cash, prioritize sells that generate cash
    # Sort sells by estimated_value (highest first) to maximize cash generation
    sell_candidates.sort(key=lambda x: x.get("estimated_value", 0), reverse=True)
    
    # Build plan steps
    steps = []
    current_context = portfolio_context
    current_cash = available_cash
    current_score = calculate_portfolio_score(current_context)
    step_num = 1
    
    # Track used symbols to avoid duplicates
    used_symbols = set()
    
    # First, execute sells (to generate cash and achieve decrease goals)
    for sell_candidate in sell_candidates:
        if step_num > max_steps:
            break
        
        symbol = sell_candidate["symbol"]
        if symbol in used_symbols:
            continue
        
        estimated_value = sell_candidate.get("estimated_value", 0)
        quantity = sell_candidate.get("quantity", 0)
        
        # Check if position still exists in simulated context
        if symbol not in current_context.positions:
            continue
        
        current_position_value = current_context.positions.get(symbol, 0)
        if estimated_value > current_position_value:
            # Adjust to available position
            if current_position_value <= 0:
                continue
            estimated_value = min(estimated_value, current_position_value * 0.5)
        
        # Get stock info for geography/industry
        stock = next((s for s in stocks if s.symbol == symbol), None)
        geography = stock.geography if stock else ""
        industry = stock.industry if stock else None
        
        # Simulate sell transaction
        if simulate_portfolio_after_transaction:
            transaction = {
                "side": TRADE_SIDE_SELL,
                "symbol": symbol,
                "value_eur": estimated_value,
                "geography": geography,
                "industry": industry,
            }
            
            new_context, new_cash = await simulate_portfolio_after_transaction(
                current_context, transaction, current_cash
            )
        else:
            # Simple simulation without function
            new_positions = dict(current_context.positions)
            new_positions[symbol] = max(0, new_positions.get(symbol, 0) - estimated_value)
            if new_positions[symbol] <= 0:
                new_positions.pop(symbol, None)
            
            new_context = PortfolioContext(
                geo_weights=current_context.geo_weights,
                industry_weights=current_context.industry_weights,
                positions=new_positions,
                total_value=max(0.01, current_context.total_value - estimated_value),
                stock_geographies=current_context.stock_geographies,
                stock_industries=current_context.stock_industries,
                stock_scores=current_context.stock_scores,
                stock_dividends=current_context.stock_dividends,
            )
            new_cash = current_cash + estimated_value
        
        new_score = calculate_portfolio_score(new_context)
        score_change = new_score.total - current_score.total
        
        # Build goal contribution
        goal_contrib = sell_candidate.get("reason", "sell")
        
        # Get price for the step (stock already retrieved above)
        estimated_price = 0.0
        currency = "EUR"
        if stock:
            # Try to get current price
            from app.services import yahoo
            prices = yahoo.get_batch_quotes({symbol: stock.yahoo_symbol} if stock.yahoo_symbol else {})
            estimated_price = prices.get(symbol, 0.0)
            currency = stock.currency or "EUR"
        
        steps.append(PlanStep(
            step_number=step_num,
            side=TRADE_SIDE_SELL,
            symbol=symbol,
            name=sell_candidate.get("name", symbol),
            quantity=quantity,
            estimated_price=estimated_price,
            estimated_value=estimated_value,
            currency=currency,
            reason=sell_candidate.get("reason", "sell"),
            goal_contribution=goal_contrib,
            portfolio_score_before=current_score.total,
            portfolio_score_after=new_score.total,
            score_change=score_change,
            available_cash_before=current_cash,
            available_cash_after=new_cash,
        ))
        
        # Update state for next iteration
        current_context = new_context
        current_cash = new_cash
        current_score = new_score
        used_symbols.add(symbol)
        step_num += 1
    
    # Then, execute buys (to achieve increase goals)
    for buy_candidate in buy_candidates:
        if step_num > max_steps:
            break
        
        symbol = buy_candidate["symbol"]
        if symbol in used_symbols:
            continue
        
        amount = buy_candidate.get("amount", 0)
        quantity = buy_candidate.get("quantity", 0)
        
        # Check if we have enough cash
        if amount > current_cash:
            continue  # Skip if we can't afford it
        
        # Simulate buy transaction
        stock = next((s for s in stocks if s.symbol == symbol), None)
        if not stock:
            continue
        
        if simulate_portfolio_after_transaction:
            transaction = {
                "side": TRADE_SIDE_BUY,
                "symbol": symbol,
                "value_eur": amount,
                "geography": stock.geography,
                "industry": stock.industry,
                "stock_quality": buy_candidate.get("quality_score", 0.5),
                "stock_dividend": 0.0,
            }
            
            new_context, new_cash = await simulate_portfolio_after_transaction(
                current_context, transaction, current_cash
            )
        else:
            # Simple simulation
            new_positions = dict(current_context.positions)
            new_positions[symbol] = new_positions.get(symbol, 0) + amount
            
            new_geographies = dict(current_context.stock_geographies or {})
            new_geographies[symbol] = stock.geography
            
            new_industries = dict(current_context.stock_industries or {})
            if stock.industry:
                new_industries[symbol] = stock.industry
            
            new_scores = dict(current_context.stock_scores or {})
            new_scores[symbol] = buy_candidate.get("quality_score", 0.5)
            
            new_context = PortfolioContext(
                geo_weights=current_context.geo_weights,
                industry_weights=current_context.industry_weights,
                positions=new_positions,
                total_value=current_context.total_value + amount,
                stock_geographies=new_geographies,
                stock_industries=new_industries,
                stock_scores=new_scores,
                stock_dividends=current_context.stock_dividends,
            )
            new_cash = max(0, current_cash - amount)
        
        new_score = calculate_portfolio_score(new_context)
        score_change = new_score.total - current_score.total

        # Strategic planners should only recommend buys that improve the portfolio
        # Skip if this buy would lower the portfolio score
        if score_change < 0:
            logger.debug(f"Skipping {symbol}: buy would lower portfolio score by {score_change:.2f}")
            continue

        # Build goal contribution
        goal_contrib = buy_candidate.get("reason", "buy")

        estimated_price = buy_candidate.get("price", 0.0)
        currency = stock.currency or "EUR"

        steps.append(PlanStep(
            step_number=step_num,
            side=TRADE_SIDE_BUY,
            symbol=symbol,
            name=buy_candidate.get("name", symbol),
            quantity=quantity,
            estimated_price=estimated_price,
            estimated_value=amount,
            currency=currency,
            reason=buy_candidate.get("reason", "buy"),
            goal_contribution=goal_contrib,
            portfolio_score_before=current_score.total,
            portfolio_score_after=new_score.total,
            score_change=score_change,
            available_cash_before=current_cash,
            available_cash_after=new_cash,
        ))
        
        # Update state for next iteration
        current_context = new_context
        current_cash = new_cash
        current_score = new_score
        used_symbols.add(symbol)
        step_num += 1
    
    # Calculate totals
    total_score_improvement = sum(step.score_change for step in steps)
    cash_required = sum(step.estimated_value for step in steps if step.side == TRADE_SIDE_BUY)
    cash_generated = sum(step.estimated_value for step in steps if step.side == TRADE_SIDE_SELL)
    
    return StrategicPlan(
        strategy_name=strategy.strategy_name,
        goals=goals,
        steps=steps,
        total_score_improvement=total_score_improvement,
        cash_required=cash_required,
        cash_generated=cash_generated,
    )


def convert_plan_to_recommendations(plan: StrategicPlan) -> List:
    """
    Convert StrategicPlan steps to MultiStepRecommendation format.
    
    This is a helper function to convert the plan format to the existing
    MultiStepRecommendation format used by the API.
    """
    from app.application.services.rebalancing_service import MultiStepRecommendation
    
    recommendations = []
    for step in plan.steps:
        recommendations.append(MultiStepRecommendation(
            step=step.step_number,
            side=step.side,
            symbol=step.symbol,
            name=step.name,
            quantity=step.quantity,
            estimated_price=step.estimated_price,
            estimated_value=step.estimated_value,
            currency=step.currency,
            reason=step.reason,
            portfolio_score_before=step.portfolio_score_before,
            portfolio_score_after=step.portfolio_score_after,
            score_change=step.score_change,
            available_cash_before=step.available_cash_before,
            available_cash_after=step.available_cash_after,
        ))
    
    return recommendations

