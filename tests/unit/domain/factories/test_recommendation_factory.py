"""Tests for RecommendationFactory."""

from app.domain.factories.recommendation_factory import RecommendationFactory
from app.domain.value_objects.trade_side import TradeSide
from app.shared.domain.value_objects.currency import Currency


class TestRecommendationFactory:
    """Test RecommendationFactory creation methods."""

    def test_create_buy_recommendation(self):
        """Test creating buy recommendation."""
        data = RecommendationFactory.create_buy_recommendation(
            symbol="AAPL.US",
            name="Apple Inc.",
            quantity=10,
            estimated_price=150.0,
            estimated_value=1500.0,
            reason="High priority score",
            country="United States",
            industry="Consumer Electronics",
            currency=Currency.USD,
            priority=0.85,
            current_portfolio_score=75.0,
            new_portfolio_score=77.5,
        )

        assert data["symbol"] == "AAPL.US"
        assert data["name"] == "Apple Inc."
        assert data["side"] == TradeSide.BUY
        assert data["quantity"] == 10
        assert data["estimated_price"] == 150.0
        assert data["estimated_value"] == 1500.0
        assert data["reason"] == "High priority score"
        assert data["country"] == "United States"
        assert data["industry"] == "Consumer Electronics"
        assert data["currency"] == Currency.USD
        assert data["priority"] == 0.85
        assert data["current_portfolio_score"] == 75.0
        assert data["new_portfolio_score"] == 77.5
        assert data["score_change"] == 2.5

    def test_create_sell_recommendation(self):
        """Test creating sell recommendation."""
        data = RecommendationFactory.create_sell_recommendation(
            symbol="MSFT.US",
            name="Microsoft Corporation",
            quantity=5,
            estimated_price=300.0,
            estimated_value=1500.0,
            reason="Underperforming position",
            country="United States",
            industry="Consumer Electronics",
            currency=Currency.USD,
        )

        assert data["symbol"] == "MSFT.US"
        assert data["side"] == TradeSide.SELL
        assert data["quantity"] == 5
        assert data["estimated_price"] == 300.0
        assert data["estimated_value"] == 1500.0
        assert data["reason"] == "Underperforming position"

    def test_create_buy_recommendation_calculates_score_change(self):
        """Test that score_change is calculated automatically."""
        data = RecommendationFactory.create_buy_recommendation(
            symbol="AAPL.US",
            name="Apple Inc.",
            quantity=10,
            estimated_price=150.0,
            estimated_value=1500.0,
            reason="Test",
            country="United States",
            current_portfolio_score=70.0,
            new_portfolio_score=72.5,
        )

        assert data["score_change"] == 2.5

    def test_create_buy_recommendation_without_scores(self):
        """Test creating buy recommendation without portfolio scores."""
        data = RecommendationFactory.create_buy_recommendation(
            symbol="AAPL.US",
            name="Apple Inc.",
            quantity=10,
            estimated_price=150.0,
            estimated_value=1500.0,
            reason="Test",
            country="United States",
        )

        assert data["current_portfolio_score"] is None
        assert data["new_portfolio_score"] is None
        assert data["score_change"] is None

    def test_create_buy_recommendation_defaults(self):
        """Test that optional fields have sensible defaults."""
        data = RecommendationFactory.create_buy_recommendation(
            symbol="AAPL.US",
            name="Apple Inc.",
            quantity=10,
            estimated_price=150.0,
            estimated_value=1500.0,
            reason="Test",
            country="United States",
        )

        assert data["industry"] is None
        assert data["currency"] == Currency.EUR  # Default
        assert data["priority"] is None
        assert data["amount"] == 1500.0  # Should match estimated_value
