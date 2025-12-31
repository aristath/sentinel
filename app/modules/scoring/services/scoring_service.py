"""Scoring application service.

Orchestrates security scoring operations using the long-term value scoring system.
"""

import logging
from typing import List, Optional

from app.core.database.manager import DatabaseManager
from app.domain.models import SecurityScore
from app.domain.repositories.protocols import ISecurityRepository
from app.infrastructure.external import yahoo_finance as yahoo
from app.modules.scoring.domain import CalculatedSecurityScore, calculate_security_score
from app.repositories import ScoreRepository

logger = logging.getLogger(__name__)


def _to_domain_score(score: CalculatedSecurityScore) -> SecurityScore:
    """Convert CalculatedSecurityScore to domain SecurityScore model."""
    group_scores = score.group_scores or {}
    sub_scores = score.sub_scores or {}

    # Map new group scores to domain model
    # quality_score = average of long_term and fundamentals
    quality_score = None
    if "long_term" in group_scores and "fundamentals" in group_scores:
        quality_score = (group_scores["long_term"] + group_scores["fundamentals"]) / 2
    elif "long_term" in group_scores:
        quality_score = group_scores["long_term"]
    elif "fundamentals" in group_scores:
        quality_score = group_scores["fundamentals"]

    # Extract sub-component scores
    long_term_subs = sub_scores.get("long_term", {})
    fundamentals_subs = sub_scores.get("fundamentals", {})

    cagr_score = long_term_subs.get("cagr")
    consistency_score = fundamentals_subs.get("consistency")

    # Calculate history_years from available data (approximate)
    history_years = None
    if long_term_subs or fundamentals_subs:
        # If we have CAGR data, assume at least 5 years
        history_years = 5.0 if cagr_score else None

    return SecurityScore(
        symbol=score.symbol,
        quality_score=quality_score,
        opportunity_score=group_scores.get("opportunity"),
        analyst_score=group_scores.get("opinion"),
        allocation_fit_score=group_scores.get("diversification"),
        cagr_score=cagr_score,
        consistency_score=consistency_score,
        history_years=history_years,
        technical_score=group_scores.get("technicals"),
        fundamental_score=group_scores.get("fundamentals"),
        total_score=score.total_score,
        volatility=score.volatility,
        calculated_at=score.calculated_at,
    )


class ScoringService:
    """Application service for security scoring operations."""

    def __init__(
        self,
        security_repo: ISecurityRepository,
        score_repo: ScoreRepository,
        db_manager: DatabaseManager,
    ):
        self.security_repo = security_repo
        self.score_repo = score_repo
        self._db_manager = db_manager

    async def _get_price_data(self, symbol: str, yahoo_symbol: str):
        """Fetch daily and monthly price data for a symbol."""
        # Get history database for this symbol
        history_db = await self._db_manager.history(symbol)

        # Fetch daily prices
        rows = await history_db.fetchall(
            "SELECT date, close_price as close, high_price as high, low_price as low, open_price as open FROM daily_prices ORDER BY date DESC LIMIT 400"
        )
        daily_prices = [{key: row[key] for key in row.keys()} for row in rows]

        # Fetch monthly prices
        rows = await history_db.fetchall(
            "SELECT year_month, avg_adj_close FROM monthly_prices ORDER BY year_month DESC LIMIT 150"
        )
        monthly_prices = [
            {"year_month": row[0], "avg_adj_close": row[1]} for row in rows
        ]

        return daily_prices, monthly_prices

    async def calculate_and_save_score(
        self,
        symbol: str,
        yahoo_symbol: Optional[str] = None,
        country: Optional[str] = None,
        industry: Optional[str] = None,
    ) -> Optional[CalculatedSecurityScore]:
        """
        Calculate security score and save to database.

        Args:
            symbol: Security symbol
            yahoo_symbol: Optional Yahoo Finance symbol override
            country: Security country for allocation fit (optional)
            industry: Security industry for allocation fit (optional)

        Returns:
            Calculated score or None if calculation failed
        """
        try:
            # Fetch price data - use symbol as fallback if yahoo_symbol is None
            yahoo_symbol_str = yahoo_symbol or symbol
            daily_prices, monthly_prices = await self._get_price_data(
                symbol, yahoo_symbol_str
            )

            if not daily_prices or len(daily_prices) < 50:
                logger.warning(
                    f"Insufficient daily data for {symbol}: {len(daily_prices)} days"
                )
                return None

            if not monthly_prices or len(monthly_prices) < 12:
                logger.warning(
                    f"Insufficient monthly data for {symbol}: {len(monthly_prices)} months"
                )
                return None

            # Fetch fundamentals from Yahoo
            yahoo_symbol_str = yahoo_symbol or symbol
            fundamentals = yahoo.get_fundamental_data(
                symbol, yahoo_symbol=yahoo_symbol_str
            )

            score = await calculate_security_score(
                symbol,
                daily_prices=daily_prices,
                monthly_prices=monthly_prices,
                fundamentals=fundamentals,
                yahoo_symbol=yahoo_symbol_str,
                country=country,
                industry=industry or "UNKNOWN",
            )
            if score:
                await self.score_repo.upsert(_to_domain_score(score))
            return score
        except Exception as e:
            logger.error(f"Failed to calculate score for {symbol}: {e}")
            return None

    async def score_all_securities(self) -> List[CalculatedSecurityScore]:
        """
        Score all active securities in the universe and update database.

        Returns:
            List of calculated scores
        """
        securities = await self.security_repo.get_all_active()
        scores = []

        for security in securities:
            logger.info(f"Scoring {security.symbol}...")
            score = await self.calculate_and_save_score(
                security.symbol,
                yahoo_symbol=security.yahoo_symbol,
                country=security.country,
                industry=security.industry,
            )
            if score:
                scores.append(score)
                logger.info(f"Scored {security.symbol}: {score.total_score:.3f}")

        logger.info(f"Scored {len(scores)} securities")
        return scores

    # Backward compatibility alias
    score_all_stocks = score_all_securities
