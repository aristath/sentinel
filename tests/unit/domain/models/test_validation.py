"""Tests for domain model validation logic.

These tests validate the __post_init__ validation methods in domain models.
"""

from datetime import datetime

import pytest

from app.domain.exceptions import ValidationError
from app.domain.models import Position, Recommendation, Security, Trade
from app.domain.value_objects.product_type import ProductType
from app.domain.value_objects.trade_side import TradeSide


class TestSecurityValidation:
    """Test Stock model validation."""

    def test_stock_validates_empty_symbol(self):
        """Test that Stock raises ValidationError for empty symbol."""
        with pytest.raises(ValidationError, match="Symbol cannot be empty"):
            Security(symbol="", name="Apple Inc.")

    def test_stock_validates_whitespace_symbol(self):
        """Test that Stock raises ValidationError for whitespace-only symbol."""
        with pytest.raises(ValidationError, match="Symbol cannot be empty"):
            Security(symbol="   ", name="Apple Inc.")

    def test_stock_validates_empty_name(self):
        """Test that Stock raises ValidationError for empty name."""
        with pytest.raises(ValidationError, match="Name cannot be empty"):
            Security(symbol="AAPL", name="")

    def test_stock_normalizes_symbol_to_uppercase(self):
        """Test that Stock normalizes symbol to uppercase."""
        stock = Security(
            symbol="aapl", name="Apple Inc.", product_type=ProductType.EQUITY
        )
        assert stock.symbol == "AAPL"

    def test_stock_strips_symbol_whitespace(self):
        """Test that Stock strips whitespace from symbol."""
        stock = Security(
            symbol="  AAPL  ", name="Apple Inc.", product_type=ProductType.EQUITY
        )
        assert stock.symbol == "AAPL"

    def test_stock_validates_min_lot(self):
        """Test that Stock corrects min_lot to minimum 1."""
        stock = Security(
            symbol="AAPL", name="Apple Inc.", min_lot=0, product_type=ProductType.EQUITY
        )
        assert stock.min_lot == 1

    def test_stock_validates_min_portfolio_target_range(self):
        """Test that Stock validates min_portfolio_target is 0-20."""
        with pytest.raises(
            ValidationError, match="min_portfolio_target must be between 0 and 20"
        ):
            Security(
                symbol="AAPL",
                name="Apple Inc.",
                min_portfolio_target=21.0,
                active=False,
            )

        with pytest.raises(ValidationError):
            Security(
                symbol="AAPL",
                name="Apple Inc.",
                min_portfolio_target=-0.1,
                active=False,
            )

    def test_stock_validates_max_portfolio_target_range(self):
        """Test that Stock validates max_portfolio_target is 0-30."""
        with pytest.raises(
            ValidationError, match="max_portfolio_target must be between 0 and 30"
        ):
            Security(
                symbol="AAPL",
                name="Apple Inc.",
                max_portfolio_target=31.0,
                active=False,
            )

        with pytest.raises(ValidationError):
            Security(
                symbol="AAPL",
                name="Apple Inc.",
                max_portfolio_target=-0.1,
                active=False,
            )

    def test_stock_validates_max_greater_than_min(self):
        """Test that Stock validates max_portfolio_target >= min_portfolio_target."""
        with pytest.raises(
            ValidationError,
            match="max_portfolio_target must be >= min_portfolio_target",
        ):
            Security(
                symbol="AAPL",
                name="Apple Inc.",
                min_portfolio_target=0.15,
                max_portfolio_target=0.10,
                active=False,
            )


class TestPositionValidation:
    """Test Position model validation."""

    def test_position_validates_empty_symbol(self):
        """Test that Position raises ValidationError for empty symbol."""
        with pytest.raises(ValidationError, match="Symbol cannot be empty"):
            Position(symbol="", quantity=10.0, avg_price=100.0)

    def test_position_validates_negative_quantity(self):
        """Test that Position raises ValidationError for negative quantity."""
        with pytest.raises(ValidationError, match="Quantity must be non-negative"):
            Position(symbol="AAPL", quantity=-10.0, avg_price=100.0)

    def test_position_validates_zero_avg_price(self):
        """Test that Position raises ValidationError for zero avg_price."""
        with pytest.raises(ValidationError, match="Average price must be positive"):
            Position(symbol="AAPL", quantity=10.0, avg_price=0.0)

    def test_position_validates_negative_avg_price(self):
        """Test that Position raises ValidationError for negative avg_price."""
        with pytest.raises(ValidationError, match="Average price must be positive"):
            Position(symbol="AAPL", quantity=10.0, avg_price=-100.0)

    def test_position_normalizes_symbol_to_uppercase(self):
        """Test that Position normalizes symbol to uppercase."""
        position = Position(symbol="aapl", quantity=10.0, avg_price=100.0)
        assert position.symbol == "AAPL"

    def test_position_validates_currency_rate(self):
        """Test that Position corrects invalid currency_rate to 1.0."""
        position = Position(
            symbol="AAPL", quantity=10.0, avg_price=100.0, currency_rate=0.0
        )
        assert position.currency_rate == 1.0

        position2 = Position(
            symbol="AAPL", quantity=10.0, avg_price=100.0, currency_rate=-0.5
        )
        assert position2.currency_rate == 1.0

    def test_position_allows_zero_quantity(self):
        """Test that Position allows zero quantity."""
        position = Position(symbol="AAPL", quantity=0.0, avg_price=100.0)
        assert position.quantity == 0.0


class TestTradeValidation:
    """Test Trade model validation."""

    def test_trade_validates_empty_symbol(self):
        """Test that Trade raises ValidationError for empty symbol."""
        with pytest.raises(ValidationError, match="Symbol cannot be empty"):
            Trade(
                symbol="",
                side=TradeSide.BUY,
                quantity=10.0,
                price=100.0,
                executed_at=datetime.now(),
            )

    def test_trade_validates_zero_quantity(self):
        """Test that Trade raises ValidationError for zero quantity."""
        with pytest.raises(ValidationError, match="Quantity must be positive"):
            Trade(
                symbol="AAPL",
                side=TradeSide.BUY,
                quantity=0.0,
                price=100.0,
                executed_at=datetime.now(),
            )

    def test_trade_validates_negative_quantity(self):
        """Test that Trade raises ValidationError for negative quantity."""
        with pytest.raises(ValidationError, match="Quantity must be positive"):
            Trade(
                symbol="AAPL",
                side=TradeSide.BUY,
                quantity=-10.0,
                price=100.0,
                executed_at=datetime.now(),
            )

    def test_trade_validates_zero_price(self):
        """Test that Trade raises ValidationError for zero price."""
        with pytest.raises(ValidationError, match="Price must be positive"):
            Trade(
                symbol="AAPL",
                side=TradeSide.BUY,
                quantity=10.0,
                price=0.0,
                executed_at=datetime.now(),
            )

    def test_trade_validates_negative_price(self):
        """Test that Trade raises ValidationError for negative price."""
        with pytest.raises(ValidationError, match="Price must be positive"):
            Trade(
                symbol="AAPL",
                side=TradeSide.BUY,
                quantity=10.0,
                price=-100.0,
                executed_at=datetime.now(),
            )

    def test_trade_normalizes_symbol_to_uppercase(self):
        """Test that Trade normalizes symbol to uppercase."""
        trade = Trade(
            symbol="aapl",
            side=TradeSide.BUY,
            quantity=10.0,
            price=100.0,
            executed_at=datetime.now(),
        )
        assert trade.symbol == "AAPL"


class TestRecommendationValidation:
    """Test Recommendation model validation."""

    def test_recommendation_validates_empty_symbol(self):
        """Test that Recommendation raises ValidationError for empty symbol."""
        with pytest.raises(ValidationError, match="Symbol cannot be empty"):
            Recommendation(
                symbol="",
                name="Apple Inc.",
                side=TradeSide.BUY,
                quantity=10,
                estimated_price=100.0,
                estimated_value=1000.0,
                reason="High score",
            )

    def test_recommendation_validates_empty_name(self):
        """Test that Recommendation raises ValidationError for empty name."""
        with pytest.raises(ValidationError, match="Name cannot be empty"):
            Recommendation(
                symbol="AAPL",
                name="",
                side=TradeSide.BUY,
                quantity=10,
                estimated_price=100.0,
                estimated_value=1000.0,
                reason="High score",
            )

    def test_recommendation_validates_zero_quantity(self):
        """Test that Recommendation raises ValidationError for zero quantity."""
        with pytest.raises(ValidationError, match="Quantity must be positive"):
            Recommendation(
                symbol="AAPL",
                name="Apple Inc.",
                side=TradeSide.BUY,
                quantity=0,
                estimated_price=100.0,
                estimated_value=1000.0,
                reason="High score",
            )

    def test_recommendation_validates_zero_estimated_price(self):
        """Test that Recommendation raises ValidationError for zero estimated_price."""
        with pytest.raises(ValidationError, match="Estimated price must be positive"):
            Recommendation(
                symbol="AAPL",
                name="Apple Inc.",
                side=TradeSide.BUY,
                quantity=10,
                estimated_price=0.0,
                estimated_value=1000.0,
                reason="High score",
            )

    def test_recommendation_validates_zero_estimated_value(self):
        """Test that Recommendation raises ValidationError for zero estimated_value."""
        with pytest.raises(ValidationError, match="Estimated value must be positive"):
            Recommendation(
                symbol="AAPL",
                name="Apple Inc.",
                side=TradeSide.BUY,
                quantity=10,
                estimated_price=100.0,
                estimated_value=0.0,
                reason="High score",
            )

    def test_recommendation_validates_empty_reason(self):
        """Test that Recommendation raises ValidationError for empty reason."""
        with pytest.raises(ValidationError, match="Reason cannot be empty"):
            Recommendation(
                symbol="AAPL",
                name="Apple Inc.",
                side=TradeSide.BUY,
                quantity=10,
                estimated_price=100.0,
                estimated_value=1000.0,
                reason="",
            )

    def test_recommendation_normalizes_symbol_to_uppercase(self):
        """Test that Recommendation normalizes symbol to uppercase."""
        recommendation = Recommendation(
            symbol="aapl",
            name="Apple Inc.",
            side=TradeSide.BUY,
            quantity=10,
            estimated_price=100.0,
            estimated_value=1000.0,
            reason="High score",
        )
        assert recommendation.symbol == "AAPL"

    def test_recommendation_calculates_score_change(self):
        """Test that Recommendation calculates score_change from portfolio scores."""
        recommendation = Recommendation(
            symbol="AAPL",
            name="Apple Inc.",
            side=TradeSide.BUY,
            quantity=10,
            estimated_price=100.0,
            estimated_value=1000.0,
            reason="High score",
            current_portfolio_score=75.0,
            new_portfolio_score=77.5,
        )
        assert recommendation.score_change == 2.5

    def test_recommendation_score_change_none_when_scores_missing(self):
        """Test that Recommendation score_change is None when scores are missing."""
        recommendation = Recommendation(
            symbol="AAPL",
            name="Apple Inc.",
            side=TradeSide.BUY,
            quantity=10,
            estimated_price=100.0,
            estimated_value=1000.0,
            reason="High score",
        )
        assert recommendation.score_change is None
