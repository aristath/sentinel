"""Local (in-process) scoring service implementation."""

from typing import List, Optional

from app.core.database.manager import get_db_manager
from app.modules.scoring.services.scoring_service import ScoringService
from app.modules.scoring.services.scoring_service_interface import SecurityScore
from app.modules.universe.database.security_repository import SecurityRepository
from app.repositories.score import ScoreRepository


class LocalScoringService:
    """
    Local scoring service implementation.

    Wraps existing domain logic for in-process execution.
    """

    def __init__(self):
        """Initialize local scoring service."""
        # Create dependencies for ScoringService
        self.security_repo = SecurityRepository()
        self.score_repo = ScoreRepository()
        self.db_manager = get_db_manager()
        self.scoring_service = ScoringService(
            security_repo=self.security_repo,
            score_repo=self.score_repo,
            db_manager=self.db_manager,
        )

    async def score_security(self, isin: str, symbol: str) -> Optional[SecurityScore]:
        """
        Score a single security.

        Args:
            isin: Security ISIN
            symbol: Security symbol

        Returns:
            Security score if found, None otherwise
        """
        try:
            # Get security from repository
            security = self.security_repo.get_by_symbol(symbol)
            if not security:
                return None

            # Calculate and save score using existing service
            calculated_score = await self.scoring_service.calculate_and_save_score(
                symbol=symbol,
            )

            if not calculated_score:
                return None

            # Convert to interface SecurityScore
            return SecurityScore(
                isin=isin,
                symbol=symbol,
                total_score=calculated_score.total_score,
                component_scores=calculated_score.group_scores or {},
                percentile=0.0,  # Would need to calculate from all scores
                grade=self._score_to_grade(calculated_score.total_score),
            )
        except Exception:
            return None

    async def batch_score_securities(self, isins: List[str]) -> List[SecurityScore]:
        """
        Score multiple securities.

        Args:
            isins: List of ISINs to score

        Returns:
            List of security scores
        """
        # Score all securities using existing service
        calculated_scores = await self.scoring_service.score_all_securities()

        # Convert to list of SecurityScore
        result = []
        for calc_score in calculated_scores:
            # Get ISIN from security
            security = self.security_repo.get_by_symbol(calc_score.symbol)
            if not security:
                continue

            result.append(
                SecurityScore(
                    isin=security.isin,
                    symbol=calc_score.symbol,
                    total_score=calc_score.total_score,
                    component_scores=calc_score.group_scores or {},
                    percentile=0.0,  # Would need to calculate from all scores
                    grade=self._score_to_grade(calc_score.total_score),
                )
            )

        return result

    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade."""
        if score >= 0.9:
            return "A+"
        elif score >= 0.8:
            return "A"
        elif score >= 0.7:
            return "B"
        elif score >= 0.6:
            return "C"
        elif score >= 0.5:
            return "D"
        else:
            return "F"
