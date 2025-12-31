"""Tests for unified Recommendation domain model."""

from app.domain.models import Recommendation
from app.domain.value_objects.recommendation_status import RecommendationStatus
from app.domain.value_objects.trade_side import TradeSide
from app.shared.domain.value_objects.currency import Currency


class TestRecommendation:
    """Test unified Recommendation domain model."""

    def test_create_buy_recommendation(self):
        """Test creating buy recommendation."""
        rec = Recommendation(
            symbol="AAPL.US",
            name="Apple Inc.",
            side=TradeSide.BUY,
            quantity=10,
            estimated_price=150.0,
            estimated_value=1500.0,
            reason="High priority score",
            country="United States",
            industry="Consumer Electronics",
            currency=Currency.USD,
            status=RecommendationStatus.PENDING,
        )

        assert rec.symbol == "AAPL.US"
        assert rec.side == TradeSide.BUY
        assert rec.quantity == 10
        assert rec.estimated_price == 150.0
        assert rec.estimated_value == 1500.0
        assert rec.reason == "High priority score"
        assert rec.status == RecommendationStatus.PENDING

    def test_create_sell_recommendation(self):
        """Test creating sell recommendation."""
        rec = Recommendation(
            symbol="MSFT.US",
            name="Microsoft Corporation",
            side=TradeSide.SELL,
            quantity=5,
            estimated_price=300.0,
            estimated_value=1500.0,
            reason="Underperforming",
            country="United States",
            currency=Currency.USD,
            status=RecommendationStatus.PENDING,
        )

        assert rec.side == TradeSide.SELL
        assert rec.status == RecommendationStatus.PENDING

    def test_recommendation_default_status(self):
        """Test that status defaults to PENDING."""
        rec = Recommendation(
            symbol="AAPL.US",
            name="Apple Inc.",
            side=TradeSide.BUY,
            quantity=10,
            estimated_price=150.0,
            estimated_value=1500.0,
            reason="Test",
            country="United States",
        )

        assert rec.status == RecommendationStatus.PENDING

    def test_recommendation_status_transitions(self):
        """Test that status can transition from PENDING to EXECUTED or DISMISSED."""
        rec = Recommendation(
            symbol="AAPL.US",
            name="Apple Inc.",
            side=TradeSide.BUY,
            quantity=10,
            estimated_price=150.0,
            estimated_value=1500.0,
            reason="Test",
            country="United States",
            status=RecommendationStatus.PENDING,
        )

        # Can transition to EXECUTED
        assert rec.status.can_transition_to(RecommendationStatus.EXECUTED) is True

        # Can transition to DISMISSED
        assert rec.status.can_transition_to(RecommendationStatus.DISMISSED) is True

        # Cannot stay PENDING
        assert rec.status.can_transition_to(RecommendationStatus.PENDING) is False

    def test_recommendation_with_portfolio_scores(self):
        """Test recommendation with portfolio score information."""
        rec = Recommendation(
            symbol="AAPL.US",
            name="Apple Inc.",
            side=TradeSide.BUY,
            quantity=10,
            estimated_price=150.0,
            estimated_value=1500.0,
            reason="Test",
            country="United States",
            current_portfolio_score=75.0,
            new_portfolio_score=77.5,
        )

        assert rec.current_portfolio_score == 75.0
        assert rec.new_portfolio_score == 77.5
        assert rec.score_change == 2.5

    def test_recommendation_calculates_score_change(self):
        """Test that score_change is calculated automatically."""
        rec = Recommendation(
            symbol="AAPL.US",
            name="Apple Inc.",
            side=TradeSide.BUY,
            quantity=10,
            estimated_price=150.0,
            estimated_value=1500.0,
            reason="Test",
            country="United States",
            current_portfolio_score=70.0,
            new_portfolio_score=72.5,
        )

        assert rec.score_change == 2.5
