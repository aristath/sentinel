"""
Stock Scorer - Orchestrator for all scoring calculations.

Combines 8 scoring groups with configurable weights:
- Long-term Performance (20%): CAGR, Sortino, Sharpe
- Fundamentals (15%): Financial strength, Consistency
- Opportunity (15%): 52W high distance, P/E ratio
- Dividends (12%): Yield, Dividend consistency
- Short-term Performance (10%): Recent momentum, Drawdown
- Technicals (10%): RSI, Bollinger, EMA
- Opinion (10%): Analyst recommendations, Price targets
- Diversification (8%): Geography, Industry, Averaging down

Weights are configurable via settings (must sum to 1.0).
Raw metrics are cached in calculations.db with per-metric TTLs.
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict

import numpy as np

from app.domain.scoring.models import (
    PortfolioContext,
    CalculatedStockScore,
    PrefetchedStockData,
)
from app.domain.scoring.constants import (
    DEFAULT_TARGET_ANNUAL_RETURN,
    DEFAULT_MARKET_AVG_PE,
)
from app.domain.scoring.long_term import calculate_long_term_score
from app.domain.scoring.fundamentals import calculate_fundamentals_score
from app.domain.scoring.opportunity import calculate_opportunity_score
from app.domain.scoring.dividends import calculate_dividends_score
from app.domain.scoring.short_term import calculate_short_term_score
from app.domain.scoring.technicals import calculate_technicals_score
from app.domain.scoring.opinion import calculate_opinion_score
from app.domain.scoring.diversification import calculate_diversification_score
from app.domain.scoring.technical import calculate_volatility

logger = logging.getLogger(__name__)

# Default weights (can be overridden by settings)
DEFAULT_WEIGHTS = {
    "long_term": 0.20,
    "fundamentals": 0.15,
    "opportunity": 0.15,
    "dividends": 0.12,
    "short_term": 0.10,
    "technicals": 0.10,
    "opinion": 0.10,
    "diversification": 0.08,
}

async def get_score_weights() -> Dict[str, float]:
    """Get score weights from settings or use defaults."""
    try:
        from app.api.settings import get_buy_score_weights
        return await get_buy_score_weights()
    except Exception as e:
        logger.warning(f"Failed to load score weights from settings: {e}")
        return DEFAULT_WEIGHTS


async def calculate_stock_score(
    symbol: str,
    daily_prices: List[dict],
    monthly_prices: List[dict],
    fundamentals,
    geography: str = None,
    industry: str = None,
    portfolio_context: PortfolioContext = None,
    yahoo_symbol: str = None,
    target_annual_return: float = DEFAULT_TARGET_ANNUAL_RETURN,
    market_avg_pe: float = DEFAULT_MARKET_AVG_PE,
    sortino_ratio: Optional[float] = None,
    pyfolio_drawdown: Optional[float] = None,
    weights: Dict[str, float] = None,
) -> Optional[CalculatedStockScore]:
    """
    Calculate complete stock score with all 8 groups.

    Raw metrics are cached in calculations.db. Scores are calculated on-demand.

    Args:
        symbol: Tradernet symbol
        daily_prices: List of daily price dicts
        monthly_prices: List of monthly price dicts
        fundamentals: Yahoo fundamentals data
        geography: Stock geography (EU, ASIA, US)
        industry: Stock industry
        portfolio_context: Portfolio context for diversification
        yahoo_symbol: Optional explicit Yahoo symbol override
        target_annual_return: Target annual return for scoring
        market_avg_pe: Market average P/E for opportunity scoring
        sortino_ratio: Pre-calculated Sortino from PyFolio
        pyfolio_drawdown: Current drawdown from PyFolio
        weights: Score group weights (defaults loaded from settings)

    Returns:
        CalculatedStockScore with all components
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    scores = {}
    sub_scores = {}

    # 1. Long-term Performance
    total, subs = await calculate_long_term_score(
        symbol=symbol,
        monthly_prices=monthly_prices,
        daily_prices=daily_prices,
        sortino_ratio=sortino_ratio,
        target_annual_return=target_annual_return,
    )
    scores["long_term"] = total
    sub_scores["long_term"] = subs

    # 2. Fundamentals
    total, subs = await calculate_fundamentals_score(
        symbol=symbol,
        monthly_prices=monthly_prices,
        fundamentals=fundamentals,
    )
    scores["fundamentals"] = total
    sub_scores["fundamentals"] = subs

    # 3. Opportunity
    total, subs = await calculate_opportunity_score(
        symbol=symbol,
        daily_prices=daily_prices,
        fundamentals=fundamentals,
        market_avg_pe=market_avg_pe,
    )
    scores["opportunity"] = total
    sub_scores["opportunity"] = subs

    # 4. Dividends
    total, subs = await calculate_dividends_score(
        symbol=symbol,
        fundamentals=fundamentals,
    )
    scores["dividends"] = total
    sub_scores["dividends"] = subs

    # 5. Short-term Performance
    total, subs = await calculate_short_term_score(
        symbol=symbol,
        daily_prices=daily_prices,
        pyfolio_drawdown=pyfolio_drawdown,
    )
    scores["short_term"] = total
    sub_scores["short_term"] = subs

    # 6. Technicals
    total, subs = await calculate_technicals_score(
        symbol=symbol,
        daily_prices=daily_prices,
    )
    scores["technicals"] = total
    sub_scores["technicals"] = subs

    # 7. Opinion
    total, subs = await calculate_opinion_score(
        symbol=symbol,
        yahoo_symbol=yahoo_symbol,
    )
    scores["opinion"] = total
    sub_scores["opinion"] = subs

    # 8. Diversification (DYNAMIC - never cached)
    if portfolio_context and geography:
        # Need quality and opportunity for averaging down calculation
        quality_approx = (scores["long_term"] + scores["fundamentals"]) / 2
        total, subs = calculate_diversification_score(
            symbol=symbol,
            geography=geography,
            industry=industry,
            quality_score=quality_approx,
            opportunity_score=scores["opportunity"],
            portfolio_context=portfolio_context,
        )
        scores["diversification"] = total
        sub_scores["diversification"] = subs
    else:
        scores["diversification"] = 0.5
        sub_scores["diversification"] = {"geography": 0.5, "industry": 0.5, "averaging": 0.5}

    # Normalize weights so they sum to 1.0 (allows relative weight system)
    weight_sum = sum(weights.get(group, DEFAULT_WEIGHTS[group]) for group in scores)
    if weight_sum > 0:
        normalized_weights = {
            group: weights.get(group, DEFAULT_WEIGHTS[group]) / weight_sum
            for group in scores
        }
    else:
        normalized_weights = DEFAULT_WEIGHTS

    # Calculate weighted total
    total_score = sum(
        scores[group] * normalized_weights[group]
        for group in scores
    )

    # Calculate volatility from daily prices
    volatility = None
    if len(daily_prices) >= 30:
        closes = np.array([p["close"] for p in daily_prices])
        volatility = calculate_volatility(closes)

    return CalculatedStockScore(
        symbol=symbol,
        total_score=round(total_score, 3),
        volatility=round(volatility, 4) if volatility else None,
        calculated_at=datetime.now(),
        group_scores=scores,
        sub_scores=sub_scores,
    )


async def calculate_stock_score_from_prefetched(
    symbol: str,
    prefetched: PrefetchedStockData,
    geography: str = None,
    industry: str = None,
    portfolio_context: PortfolioContext = None,
    yahoo_symbol: str = None,
    target_annual_return: float = DEFAULT_TARGET_ANNUAL_RETURN,
    market_avg_pe: float = DEFAULT_MARKET_AVG_PE,
    weights: Dict[str, float] = None,
) -> Optional[CalculatedStockScore]:
    """
    Calculate stock score using pre-fetched data.

    Args:
        symbol: Tradernet symbol
        prefetched: Pre-fetched data containing daily/monthly prices and fundamentals
        geography: Stock geography (EU, ASIA, US)
        industry: Stock industry
        portfolio_context: Portfolio context for diversification
        yahoo_symbol: Optional explicit Yahoo symbol override
        target_annual_return: Target annual return for scoring
        market_avg_pe: Market average P/E for opportunity scoring
        weights: Score group weights

    Returns:
        CalculatedStockScore with all components
    """
    return await calculate_stock_score(
        symbol=symbol,
        daily_prices=prefetched.daily_prices,
        monthly_prices=prefetched.monthly_prices,
        fundamentals=prefetched.fundamentals,
        geography=geography,
        industry=industry,
        portfolio_context=portfolio_context,
        yahoo_symbol=yahoo_symbol,
        target_annual_return=target_annual_return,
        market_avg_pe=market_avg_pe,
        weights=weights,
    )
