"""Tests for ScoreResult response type.

These tests validate the ScoreResult type for scoring function results.
"""

from app.domain.responses.score import ScoreResult


class TestScoreResult:
    """Test ScoreResult type."""

    def test_score_result_creation_with_score_only(self):
        """Test creating ScoreResult with score only."""
        result = ScoreResult(score=0.85)

        assert result.score == 0.85
        assert result.sub_scores == {}
        assert result.confidence is None
        assert result.metadata is None

    def test_score_result_creation_with_all_fields(self):
        """Test creating ScoreResult with all fields."""
        result = ScoreResult(
            score=0.90,
            sub_scores={"cagr": 0.8, "sharpe": 0.7, "quality": 0.9},
            confidence=0.95,
            metadata={"symbol": "AAPL", "calculation_date": "2024-01-15"},
        )

        assert result.score == 0.90
        assert result.sub_scores == {"cagr": 0.8, "sharpe": 0.7, "quality": 0.9}
        assert result.confidence == 0.95
        assert result.metadata == {"symbol": "AAPL", "calculation_date": "2024-01-15"}

    def test_score_result_with_sub_scores(self):
        """Test ScoreResult with sub-scores breakdown."""
        result = ScoreResult(
            score=0.75,
            sub_scores={
                "cagr_score": 0.8,
                "consistency_score": 0.7,
                "financial_strength_score": 0.75,
                "sharpe_score": 0.8,
                "drawdown_score": 0.7,
            },
        )

        assert result.score == 0.75
        assert len(result.sub_scores) == 5
        assert result.sub_scores["cagr_score"] == 0.8
        assert result.sub_scores["sharpe_score"] == 0.8

    def test_score_result_with_confidence(self):
        """Test ScoreResult with confidence level."""
        result = ScoreResult(score=0.80, confidence=0.85)

        assert result.score == 0.80
        assert result.confidence == 0.85

    def test_score_result_with_metadata(self):
        """Test ScoreResult with metadata."""
        result = ScoreResult(
            score=0.70,
            metadata={"history_years": 5, "data_quality": "high"},
        )

        assert result.score == 0.70
        assert result.metadata == {"history_years": 5, "data_quality": "high"}

    def test_score_result_zero_score(self):
        """Test ScoreResult with zero score."""
        result = ScoreResult(score=0.0)

        assert result.score == 0.0

    def test_score_result_max_score(self):
        """Test ScoreResult with maximum score."""
        result = ScoreResult(score=1.0)

        assert result.score == 1.0

    def test_score_result_low_score(self):
        """Test ScoreResult with low score."""
        result = ScoreResult(score=0.25)

        assert result.score == 0.25
