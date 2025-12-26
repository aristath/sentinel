"""Priority calculation service.

Simplified priority calculator for long-term value investing.

The scoring system (scorer.py) now handles:
- Quality (35%): total return, consistency, financial strength, dividend bonus
- Opportunity (35%): buy-the-dip signals
- Analyst (15%): recommendations, price targets
- Allocation Fit (15%): geo gaps, industry gaps, averaging down

This calculator now simply:
1. Takes the stock score (which includes allocation fit)
2. Applies manual multiplier
3. Sorts by final priority
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class PriorityInput:
    """Input data for priority calculation."""

    symbol: str
    name: str
    geography: str
    industry: Optional[str]
    stock_score: float  # From scorer.py (includes allocation fit if available)
    volatility: Optional[float]
    multiplier: float  # Manual priority multiplier
    # Additional context for display
    quality_score: Optional[float] = None
    opportunity_score: Optional[float] = None
    allocation_fit_score: Optional[float] = None


@dataclass
class PriorityResult:
    """Result of priority calculation."""

    symbol: str
    name: str
    geography: str
    industry: str
    stock_score: float
    volatility: Optional[float]
    multiplier: float
    combined_priority: float  # Final priority score (score * multiplier)
    # Breakdown for display
    quality_score: Optional[float] = None
    opportunity_score: Optional[float] = None
    allocation_fit_score: Optional[float] = None


class PriorityCalculator:
    """Service for calculating stock priority scores."""

    @staticmethod
    def parse_industries(industry_str: Optional[str]) -> List[str]:
        """
        Parse comma-separated industry string into list.

        Args:
            industry_str: Comma-separated industries (e.g., "Industrial, Defense")

        Returns:
            List of industry names, or empty list if None/empty
        """
        if not industry_str:
            return []
        return [ind.strip() for ind in industry_str.split(",") if ind.strip()]

    @staticmethod
    def calculate_priority(
        input_data: PriorityInput,
        geo_weights: Dict[str, float] = None,
        industry_weights: Dict[str, float] = None,
    ) -> PriorityResult:
        """
        Calculate priority score for a stock.

        The stock_score from scorer.py already includes:
        - Quality (35%)
        - Opportunity (35%)
        - Analyst (15%)
        - Allocation Fit (15%) - if portfolio context was provided

        This function simply applies the manual multiplier.

        Args:
            input_data: Stock data for priority calculation
            geo_weights: Unused (kept for API compatibility)
            industry_weights: Unused (kept for API compatibility)

        Returns:
            PriorityResult with calculated priority
        """
        # The stock score already includes all factors from scorer.py
        # Just apply the manual multiplier
        combined_priority = input_data.stock_score * input_data.multiplier

        return PriorityResult(
            symbol=input_data.symbol,
            name=input_data.name,
            geography=input_data.geography,
            industry=input_data.industry or "Unknown",
            stock_score=input_data.stock_score,
            volatility=input_data.volatility,
            multiplier=input_data.multiplier,
            combined_priority=round(combined_priority, 4),
            quality_score=input_data.quality_score,
            opportunity_score=input_data.opportunity_score,
            allocation_fit_score=input_data.allocation_fit_score,
        )

    @staticmethod
    def calculate_priorities(
        inputs: List[PriorityInput],
        geo_weights: Dict[str, float] = None,
        industry_weights: Dict[str, float] = None,
    ) -> List[PriorityResult]:
        """
        Calculate priorities for multiple stocks.

        Args:
            inputs: List of stock data for priority calculation
            geo_weights: Unused (kept for API compatibility)
            industry_weights: Unused (kept for API compatibility)

        Returns:
            List of PriorityResult sorted by combined_priority (highest first)
        """
        results = [
            PriorityCalculator.calculate_priority(
                input_data, geo_weights, industry_weights
            )
            for input_data in inputs
        ]

        # Sort by combined priority (highest first)
        results.sort(key=lambda x: x.combined_priority, reverse=True)

        return results
