"""Priority calculation service.

Simplified priority calculator for long-term value investing.

The scoring system (scorer.py) now handles:
- Quality (35%): total return, consistency, financial strength, dividend bonus
- Opportunity (35%): buy-the-dip signals
- Analyst (15%): recommendations, price targets
- Allocation Fit (15%): geo gaps, industry gaps, averaging down

This calculator now simply:
1. Takes the security score (which includes allocation fit)
2. Applies manual multiplier
3. Sorts by final priority
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class PriorityInput:
    """Input data for priority calculation."""

    symbol: str
    name: str
    stock_score: float  # From scorer.py (includes allocation fit if available)
    multiplier: float  # Manual priority multiplier
    country: Optional[str] = None  # Replaces geography
    industry: Optional[str] = None
    volatility: Optional[float] = None
    # Additional context for display
    quality_score: Optional[float] = None
    opportunity_score: Optional[float] = None
    allocation_fit_score: Optional[float] = None


@dataclass
class PriorityResult:
    """Result of priority calculation."""

    symbol: str
    name: str
    stock_score: float
    multiplier: float
    combined_priority: float  # Final priority score (score * multiplier)
    country: Optional[str] = None  # Replaces geography
    industry: Optional[str] = None
    volatility: Optional[float] = None
    # Breakdown for display
    quality_score: Optional[float] = None
    opportunity_score: Optional[float] = None
    allocation_fit_score: Optional[float] = None


class PriorityCalculator:
    """Service for calculating security priority scores."""

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
    ) -> PriorityResult:
        """
        Calculate priority score for a security.

        The stock_score from scorer.py already includes:
        - Quality (35%)
        - Opportunity (35%)
        - Analyst (15%)
        - Allocation Fit (15%) - if portfolio context was provided

        This function simply applies the manual multiplier.

        Args:
            input_data: Security data for priority calculation

        Returns:
            PriorityResult with calculated priority
        """
        # The security score already includes all factors from scorer.py
        # Just apply the manual multiplier
        combined_priority = input_data.stock_score * input_data.multiplier

        return PriorityResult(
            symbol=input_data.symbol,
            name=input_data.name,
            country=input_data.country,
            industry=input_data.industry,
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
    ) -> List[PriorityResult]:
        """
        Calculate priorities for multiple securities.

        Args:
            inputs: List of security data for priority calculation

        Returns:
            List of PriorityResult sorted by combined_priority (highest first)
        """
        results = [
            PriorityCalculator.calculate_priority(input_data) for input_data in inputs
        ]

        # Sort by combined priority (highest first)
        results.sort(key=lambda x: x.combined_priority, reverse=True)

        return results
