"""
Security Scorer - Orchestrator for all scoring calculations.

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
from typing import Dict, List, Optional

import numpy as np

from app.modules.scoring.domain.calculations import calculate_volatility
from app.modules.scoring.domain.constants import (
    DEFAULT_MARKET_AVG_PE,
    DEFAULT_TARGET_ANNUAL_RETURN,
)
from app.modules.scoring.domain.diversification import calculate_diversification_score
from app.modules.scoring.domain.groups.dividends import calculate_dividends_score
from app.modules.scoring.domain.groups.fundamentals import calculate_fundamentals_score
from app.modules.scoring.domain.groups.long_term import calculate_long_term_score
from app.modules.scoring.domain.groups.opinion import calculate_opinion_score
from app.modules.scoring.domain.groups.opportunity import calculate_opportunity_score
from app.modules.scoring.domain.groups.short_term import calculate_short_term_score
from app.modules.scoring.domain.groups.technicals import calculate_technicals_score
from app.modules.scoring.domain.models import (
    CalculatedSecurityScore,
    PortfolioContext,
    PrefetchedStockData,
)

logger = logging.getLogger(__name__)

# Fixed weights for stock scoring
# These are no longer configurable via settings - the portfolio optimizer
# now handles portfolio-level allocation decisions. Per-stock scoring uses
# these fixed weights that balance quality, opportunity, and diversification.
SCORE_WEIGHTS = {
    "long_term": 0.20,  # CAGR, Sortino, Sharpe
    "fundamentals": 0.15,  # Financial strength, Consistency
    "opportunity": 0.15,  # 52W high distance, P/E ratio
    "dividends": 0.12,  # Yield, Dividend consistency
    "short_term": 0.10,  # Recent momentum, Drawdown
    "technicals": 0.10,  # RSI, Bollinger, EMA
    "opinion": 0.10,  # Analyst recommendations, Price targets
    "diversification": 0.08,  # Geography, Industry, Averaging down
}


async def calculate_security_score(
    symbol: str,
    daily_prices: List[dict],
    monthly_prices: List[dict],
    fundamentals,
    country: Optional[str] = None,
    industry: Optional[str] = None,
    portfolio_context: Optional[PortfolioContext] = None,
    yahoo_symbol: Optional[str] = None,
    target_annual_return: float = DEFAULT_TARGET_ANNUAL_RETURN,
    market_avg_pe: float = DEFAULT_MARKET_AVG_PE,
    sortino_ratio: Optional[float] = None,
    pyfolio_drawdown: Optional[float] = None,
    weights: Optional[Dict[str, float]] = None,
) -> Optional[CalculatedSecurityScore]:
    """
    Calculate complete stock score with all 8 groups.

    Raw metrics are cached in calculations.db. Scores are calculated on-demand.

    Args:
        symbol: Tradernet symbol
        daily_prices: List of daily price dicts
        monthly_prices: List of monthly price dicts
        fundamentals: Yahoo fundamentals data
        country: Stock country (e.g., "United States", "Germany")
        industry: Stock industry
        portfolio_context: Portfolio context for diversification
        yahoo_symbol: Optional explicit Yahoo symbol override
        target_annual_return: Target annual return for scoring
        market_avg_pe: Market average P/E for opportunity scoring
        sortino_ratio: Pre-calculated Sortino from PyFolio
        pyfolio_drawdown: Current drawdown from PyFolio
        weights: Score group weights (defaults loaded from settings)

    Returns:
        CalculatedSecurityScore with all components
    """
    # Always use fixed weights - the optimizer handles portfolio-level allocation
    if weights is None:
        weights = SCORE_WEIGHTS

    scores = {}
    sub_scores = {}

    # 1. Long-term Performance
    result = await calculate_long_term_score(
        symbol=symbol,
        monthly_prices=monthly_prices,
        daily_prices=daily_prices,
        sortino_ratio=sortino_ratio,
        target_annual_return=target_annual_return,
    )
    scores["long_term"] = result.score
    sub_scores["long_term"] = result.sub_scores

    # 2. Fundamentals
    result = await calculate_fundamentals_score(
        symbol=symbol,
        monthly_prices=monthly_prices,
        fundamentals=fundamentals,
    )
    scores["fundamentals"] = result.score
    sub_scores["fundamentals"] = result.sub_scores

    # 3. Opportunity
    result = await calculate_opportunity_score(
        symbol=symbol,
        daily_prices=daily_prices,
        fundamentals=fundamentals,
        market_avg_pe=market_avg_pe,
    )
    scores["opportunity"] = result.score
    sub_scores["opportunity"] = result.sub_scores

    # 4. Dividends
    result = await calculate_dividends_score(
        symbol=symbol,
        fundamentals=fundamentals,
    )
    scores["dividends"] = result.score
    sub_scores["dividends"] = result.sub_scores

    # 5. Short-term Performance
    result = await calculate_short_term_score(
        symbol=symbol,
        daily_prices=daily_prices,
        pyfolio_drawdown=pyfolio_drawdown,
    )
    scores["short_term"] = result.score
    sub_scores["short_term"] = result.sub_scores

    # 6. Technicals
    result = await calculate_technicals_score(
        symbol=symbol,
        daily_prices=daily_prices,
    )
    scores["technicals"] = result.score
    sub_scores["technicals"] = result.sub_scores

    # 7. Opinion
    result = await calculate_opinion_score(
        symbol=symbol,
        yahoo_symbol=yahoo_symbol,
    )
    scores["opinion"] = result.score
    sub_scores["opinion"] = result.sub_scores

    # 8. Diversification (DYNAMIC - never cached)
    if portfolio_context and country:
        # Need quality and opportunity for averaging down calculation
        quality_approx = (scores["long_term"] + scores["fundamentals"]) / 2
        result = calculate_diversification_score(
            symbol=symbol,
            country=country,
            industry=industry,
            quality_score=quality_approx,
            opportunity_score=scores["opportunity"],
            portfolio_context=portfolio_context,
        )
        scores["diversification"] = result.score
        sub_scores["diversification"] = result.sub_scores
    else:
        scores["diversification"] = 0.5
        sub_scores["diversification"] = {
            "country": 0.5,
            "industry": 0.5,
            "averaging": 0.5,
        }

    # Normalize weights so they sum to 1.0 (allows relative weight system)
    weight_sum = sum(weights.get(group, SCORE_WEIGHTS[group]) for group in scores)
    if weight_sum > 0:
        normalized_weights = {
            group: weights.get(group, SCORE_WEIGHTS[group]) / weight_sum
            for group in scores
        }
    else:
        normalized_weights = SCORE_WEIGHTS

    # Calculate weighted total
    total_score = sum(scores[group] * normalized_weights[group] for group in scores)

    # Calculate volatility from daily prices
    volatility = None
    if len(daily_prices) >= 30:
        closes = np.array([p["close"] for p in daily_prices])
        volatility = calculate_volatility(closes)

    return CalculatedSecurityScore(
        symbol=symbol,
        total_score=round(total_score, 3),
        volatility=round(volatility, 4) if volatility else None,
        calculated_at=datetime.now(),
        group_scores=scores,
        sub_scores=sub_scores,
    )


async def calculate_security_score_from_prefetched(
    symbol: str,
    prefetched: PrefetchedStockData,
    country: Optional[str] = None,
    industry: Optional[str] = None,
    portfolio_context: Optional[PortfolioContext] = None,
    yahoo_symbol: Optional[str] = None,
    target_annual_return: float = DEFAULT_TARGET_ANNUAL_RETURN,
    market_avg_pe: float = DEFAULT_MARKET_AVG_PE,
    weights: Optional[Dict[str, float]] = None,
) -> Optional[CalculatedSecurityScore]:
    """
    Calculate stock score using pre-fetched data.

    Args:
        symbol: Tradernet symbol
        prefetched: Pre-fetched data containing daily/monthly prices and fundamentals
        country: Stock country (e.g., "United States", "Germany")
        industry: Stock industry
        portfolio_context: Portfolio context for diversification
        yahoo_symbol: Optional explicit Yahoo symbol override
        target_annual_return: Target annual return for scoring
        market_avg_pe: Market average P/E for opportunity scoring
        weights: Score group weights

    Returns:
        CalculatedSecurityScore with all components
    """
    return await calculate_security_score(
        symbol=symbol,
        daily_prices=prefetched.daily_prices,
        monthly_prices=prefetched.monthly_prices,
        fundamentals=prefetched.fundamentals,
        country=country,
        industry=industry,
        portfolio_context=portfolio_context,
        yahoo_symbol=yahoo_symbol,
        target_annual_return=target_annual_return,
        market_avg_pe=market_avg_pe,
        weights=weights,
    )
