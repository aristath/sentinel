"""gRPC servicer implementation for Scoring service."""

from contracts import scoring_pb2, scoring_pb2_grpc  # type: ignore[attr-defined]
from app.modules.scoring.services.local_scoring_service import LocalScoringService


class ScoringServicer(scoring_pb2_grpc.ScoringServiceServicer):
    """
    gRPC servicer for Scoring service.

    Implements the ScoringService gRPC interface by delegating to LocalScoringService.
    """

    def __init__(self):
        """Initialize Scoring servicer."""
        self.local_service = LocalScoringService()

    async def ScoreSecurity(
        self,
        request: scoring_pb2.ScoreSecurityRequest,
        context,
    ) -> scoring_pb2.ScoreSecurityResponse:
        """Score a single security."""
        score = await self.local_service.score_security(
            isin=request.isin,
            symbol=request.symbol,
        )

        if score:
            grpc_score = scoring_pb2.SecurityScore(
                isin=score.isin,
                symbol=score.symbol,
                total_score=score.total_score,
                component_scores=score.component_scores,
                percentile=score.percentile,
                grade=score.grade,
            )
            return scoring_pb2.ScoreSecurityResponse(
                found=True,
                score=grpc_score,
            )
        else:
            return scoring_pb2.ScoreSecurityResponse(found=False)

    async def BatchScoreSecurities(
        self,
        request: scoring_pb2.BatchScoreSecuritiesRequest,
        context,
    ) -> scoring_pb2.BatchScoreSecuritiesResponse:
        """Score multiple securities."""
        scores = await self.local_service.batch_score_securities(
            isins=list(request.isins)
        )

        grpc_scores = [
            scoring_pb2.SecurityScore(
                isin=score.isin,
                symbol=score.symbol,
                total_score=score.total_score,
                component_scores=score.component_scores,
                percentile=score.percentile,
                grade=score.grade,
            )
            for score in scores
        ]

        return scoring_pb2.BatchScoreSecuritiesResponse(
            scores=grpc_scores,
            total_scored=len(scores),
            failed=0,
        )

    async def ScorePortfolio(
        self,
        request: scoring_pb2.ScorePortfolioRequest,
        context,
    ) -> scoring_pb2.ScorePortfolioResponse:
        """Score entire portfolio."""
        # TODO: Implement portfolio scoring
        return scoring_pb2.ScorePortfolioResponse(
            total_score=0.0,
            weighted_score=0.0,
            security_scores=[],
            portfolio_metrics={},
        )

    async def GetScoreHistory(
        self,
        request: scoring_pb2.GetScoreHistoryRequest,
        context,
    ) -> scoring_pb2.GetScoreHistoryResponse:
        """Get historical scores for a security."""
        # TODO: Implement score history
        return scoring_pb2.GetScoreHistoryResponse(
            isin=request.isin,
            scores=[],
        )

    async def HealthCheck(
        self,
        request: scoring_pb2.Empty,
        context,
    ) -> scoring_pb2.HealthCheckResponse:
        """Health check."""
        return scoring_pb2.HealthCheckResponse(
            healthy=True,
            version="1.0.0",
            status="OK",
        )
