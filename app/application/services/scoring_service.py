"""Scoring application service.

Orchestrates stock scoring operations using the long-term value scoring system.
"""

from typing import List, Optional
from datetime import datetime

from app.domain.repositories import (
    StockRepository,
    ScoreRepository,
)
from app.domain.repositories import StockScore
from app.services.scorer import (
    calculate_stock_score,
    StockScore as ScorerStockScore,
)


class ScoringService:
    """Application service for stock scoring operations."""

    def __init__(
        self,
        stock_repo: StockRepository,
        score_repo: ScoreRepository,
    ):
        self.stock_repo = stock_repo
        self.score_repo = score_repo

    async def calculate_and_save_score(
        self,
        symbol: str,
        yahoo_symbol: Optional[str] = None,
        geography: Optional[str] = None,
        industry: Optional[str] = None,
    ) -> Optional[ScorerStockScore]:
        """
        Calculate stock score and save to database.

        Args:
            symbol: Stock symbol
            yahoo_symbol: Optional Yahoo Finance symbol override
            geography: Stock geography for allocation fit (optional)
            industry: Stock industry for allocation fit (optional)

        Returns:
            Calculated score or None if calculation failed
        """
        score = calculate_stock_score(
            symbol,
            yahoo_symbol=yahoo_symbol,
            geography=geography,
            industry=industry,
        )
        if score:
            # Convert to domain model with new scoring columns
            domain_score = StockScore(
                symbol=score.symbol,
                # New primary scores
                quality_score=score.quality.total,
                opportunity_score=score.opportunity.total,
                analyst_score=score.analyst.total,
                allocation_fit_score=score.allocation_fit.total if score.allocation_fit else None,
                # Quality breakdown
                cagr_score=score.quality.total_return_score,
                consistency_score=score.quality.consistency_score,
                history_years=score.quality.history_years,
                # Legacy fields for backwards compatibility
                technical_score=score.quality.total,
                fundamental_score=score.opportunity.total,
                total_score=score.total_score,
                volatility=score.volatility,
                calculated_at=score.calculated_at,
            )
            await self.score_repo.upsert(domain_score)

        return score

    async def score_all_stocks(self) -> List[ScorerStockScore]:
        """
        Score all active stocks in the universe and update database.

        Returns:
            List of calculated scores
        """
        stocks = await self.stock_repo.get_all_active()
        scores = []

        for stock in stocks:
            score = calculate_stock_score(
                stock.symbol,
                yahoo_symbol=stock.yahoo_symbol,
                geography=stock.geography,
                industry=stock.industry,
            )
            if score:
                scores.append(score)

                # Convert to domain model and save
                domain_score = StockScore(
                    symbol=score.symbol,
                    # New primary scores
                    quality_score=score.quality.total,
                    opportunity_score=score.opportunity.total,
                    analyst_score=score.analyst.total,
                    allocation_fit_score=score.allocation_fit.total if score.allocation_fit else None,
                    # Quality breakdown
                    cagr_score=score.quality.total_return_score,
                    consistency_score=score.quality.consistency_score,
                    history_years=score.quality.history_years,
                    # Legacy fields for backwards compatibility
                    technical_score=score.quality.total,
                    fundamental_score=score.opportunity.total,
                    total_score=score.total_score,
                    volatility=score.volatility,
                    calculated_at=score.calculated_at,
                )
                await self.score_repo.upsert(domain_score)

        return scores
