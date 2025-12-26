"""Tests for domain model validation."""

from datetime import datetime

import pytest

from app.domain.exceptions import ValidationError
from app.domain.models import Position, Recommendation, Stock, Trade
from app.domain.value_objects.currency import Currency
from app.domain.value_objects.recommendation_status import RecommendationStatus
from app.domain.value_objects.trade_side import TradeSide


class TestStockValidation:
    """Test Stock domain model validation."""

    def test_stock_validates_symbol_not_empty(self):
        """Test that Stock validates symbol is not empty."""
        with pytest.raises(ValidationError, match="Symbol cannot be empty"):
            Stock(symbol="", name="Test", geography="US")

    def test_stock_validates_name_not_empty(self):
        """Test that Stock validates name is not empty."""
        with pytest.raises(ValidationError, match="Name cannot be empty"):
            Stock(symbol="AAPL.US", name="", geography="US")

    def test_stock_accepts_any_geography(self):
        """Test that Stock accepts any non-empty geography (relaxed validation)."""
        stock = Stock(symbol="AAPL.US", name="Test", geography="GREECE")
        assert stock.geography == "GREECE"

    def test_stock_validates_min_lot_positive(self):
        """Test that Stock validates min_lot is positive."""
        stock = Stock(symbol="AAPL.US", name="Test", geography="US", min_lot=0)
        assert stock.min_lot == 1  # Should default to 1

        stock = Stock(symbol="AAPL.US", name="Test", geography="US", min_lot=-5)
        assert stock.min_lot == 1  # Should default to 1

    def test_stock_valid_creation(self):
        """Test that valid Stock creation works."""
        stock = Stock(
            symbol="AAPL.US",
            name="Apple Inc.",
            geography="US",
            currency=Currency.USD,
        )
        assert stock.symbol == "AAPL.US"
        assert stock.name == "Apple Inc."
        assert stock.geography == "US"


class TestPositionValidation:
    """Test Position domain model validation."""

    def test_position_validates_quantity_non_negative(self):
        """Test that Position validates quantity is non-negative."""
        with pytest.raises(ValidationError, match="Quantity must be non-negative"):
            Position(symbol="AAPL.US", quantity=-1.0, avg_price=150.0)

    def test_position_validates_avg_price_positive(self):
        """Test that Position validates avg_price is positive."""
        with pytest.raises(ValidationError, match="Average price must be positive"):
            Position(symbol="AAPL.US", quantity=10.0, avg_price=0.0)

        with pytest.raises(ValidationError, match="Average price must be positive"):
            Position(symbol="AAPL.US", quantity=10.0, avg_price=-10.0)

    def test_position_valid_creation(self):
        """Test that valid Position creation works."""
        position = Position(
            symbol="AAPL.US",
            quantity=10.0,
            avg_price=150.0,
            currency=Currency.USD,
        )
        assert position.quantity == 10.0
        assert position.avg_price == 150.0


class TestTradeValidation:
    """Test Trade domain model validation."""

    def test_trade_validates_quantity_positive(self):
        """Test that Trade validates quantity is positive."""
        with pytest.raises(ValidationError, match="Quantity must be positive"):
            Trade(
                symbol="AAPL.US",
                side=TradeSide.BUY,
                quantity=0.0,
                price=150.0,
                executed_at=datetime.now(),
            )

        with pytest.raises(ValidationError, match="Quantity must be positive"):
            Trade(
                symbol="AAPL.US",
                side=TradeSide.BUY,
                quantity=-10.0,
                price=150.0,
                executed_at=datetime.now(),
            )

    def test_trade_validates_price_positive(self):
        """Test that Trade validates price is positive."""
        with pytest.raises(ValidationError, match="Price must be positive"):
            Trade(
                symbol="AAPL.US",
                side=TradeSide.BUY,
                quantity=10.0,
                price=0.0,
                executed_at=datetime.now(),
            )

    def test_trade_valid_creation(self):
        """Test that valid Trade creation works."""
        trade = Trade(
            symbol="AAPL.US",
            side=TradeSide.BUY,
            quantity=10.0,
            price=150.0,
            executed_at=datetime.now(),
        )
        assert trade.quantity == 10.0
        assert trade.price == 150.0


class TestRecommendationValidation:
    """Test Recommendation domain model validation."""

    def test_recommendation_validates_quantity_positive(self):
        """Test that Recommendation validates quantity is positive."""
        with pytest.raises(ValidationError, match="Quantity must be positive"):
            Recommendation(
                symbol="AAPL.US",
                name="Apple Inc.",
                side=TradeSide.BUY,
                quantity=0,
                estimated_price=150.0,
                estimated_value=1500.0,
                reason="Test",
                geography="US",
            )

    def test_recommendation_validates_estimated_price_positive(self):
        """Test that Recommendation validates estimated_price is positive."""
        with pytest.raises(ValidationError, match="Estimated price must be positive"):
            Recommendation(
                symbol="AAPL.US",
                name="Apple Inc.",
                side=TradeSide.BUY,
                quantity=10,
                estimated_price=0.0,
                estimated_value=1500.0,
                reason="Test",
                geography="US",
            )

    def test_recommendation_validates_estimated_value_positive(self):
        """Test that Recommendation validates estimated_value is positive."""
        with pytest.raises(ValidationError, match="Estimated value must be positive"):
            Recommendation(
                symbol="AAPL.US",
                name="Apple Inc.",
                side=TradeSide.BUY,
                quantity=10,
                estimated_price=150.0,
                estimated_value=0.0,
                reason="Test",
                geography="US",
            )

    def test_recommendation_valid_creation(self):
        """Test that valid Recommendation creation works."""
        rec = Recommendation(
            symbol="AAPL.US",
            name="Apple Inc.",
            side=TradeSide.BUY,
            quantity=10,
            estimated_price=150.0,
            estimated_value=1500.0,
            reason="Test",
            geography="US",
        )
        assert rec.quantity == 10
        assert rec.estimated_price == 150.0
