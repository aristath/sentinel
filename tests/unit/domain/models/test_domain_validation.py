"""Tests for domain model validation."""

from datetime import datetime

import pytest

from app.domain.exceptions import ValidationError
from app.domain.models import Position, Recommendation, Security, Trade
from app.domain.value_objects.product_type import ProductType
from app.domain.value_objects.trade_side import TradeSide
from app.shared.domain.value_objects.currency import Currency


class TestStockValidation:
    """Test Stock domain model validation."""

    def test_stock_validates_symbol_not_empty(self):
        """Test that Stock validates symbol is not empty."""
        with pytest.raises(ValidationError, match="Symbol cannot be empty"):
            Security(symbol="", name="Test", country="United States")

    def test_stock_validates_name_not_empty(self):
        """Test that Stock validates name is not empty."""
        with pytest.raises(ValidationError, match="Name cannot be empty"):
            Security(symbol="AAPL.US", name="", country="United States")

    def test_stock_accepts_any_country(self):
        """Test that Stock accepts any non-empty country."""
        stock = Security(
            symbol="AAPL.US",
            name="Test",
            country="Greece",
            product_type=ProductType.EQUITY,
        )
        assert stock.country == "Greece"

    def test_stock_validates_min_lot_positive(self):
        """Test that Stock validates min_lot is positive."""
        stock = Security(
            symbol="AAPL.US",
            name="Test",
            country="United States",
            min_lot=0,
            product_type=ProductType.EQUITY,
        )
        assert stock.min_lot == 1  # Should default to 1

        stock = Security(
            symbol="AAPL.US",
            name="Test",
            country="United States",
            min_lot=-5,
            product_type=ProductType.EQUITY,
        )
        assert stock.min_lot == 1  # Should default to 1

    def test_stock_valid_creation(self):
        """Test that valid Stock creation works."""
        stock = Security(
            symbol="AAPL.US",
            name="Apple Inc.",
            country="United States",
            currency=Currency.USD,
            product_type=ProductType.EQUITY,
        )
        assert stock.symbol == "AAPL.US"
        assert stock.name == "Apple Inc."
        assert stock.country == "United States"

    def test_stock_min_portfolio_target_accepts_valid_range(self):
        """Test that min_portfolio_target accepts values 0-20."""
        stock = Security(
            symbol="AAPL.US",
            name="Test",
            min_portfolio_target=0.0,
            product_type=ProductType.EQUITY,
        )
        assert stock.min_portfolio_target == 0.0

        stock = Security(
            symbol="AAPL.US",
            name="Test",
            min_portfolio_target=10.0,
            product_type=ProductType.EQUITY,
        )
        assert stock.min_portfolio_target == 10.0

        stock = Security(
            symbol="AAPL.US",
            name="Test",
            min_portfolio_target=20.0,
            product_type=ProductType.EQUITY,
        )
        assert stock.min_portfolio_target == 20.0

    def test_stock_min_portfolio_target_rejects_negative(self):
        """Test that min_portfolio_target rejects values < 0."""
        with pytest.raises(
            ValidationError, match="min_portfolio_target must be between 0 and 20"
        ):
            Security(
                symbol="AAPL.US",
                name="Test",
                min_portfolio_target=-1.0,
                active=False,
            )

    def test_stock_min_portfolio_target_rejects_over_20(self):
        """Test that min_portfolio_target rejects values > 20."""
        with pytest.raises(
            ValidationError, match="min_portfolio_target must be between 0 and 20"
        ):
            Security(
                symbol="AAPL.US",
                name="Test",
                min_portfolio_target=21.0,
                active=False,
            )

    def test_stock_max_portfolio_target_accepts_valid_range(self):
        """Test that max_portfolio_target accepts values 0-30."""
        stock = Security(
            symbol="AAPL.US",
            name="Test",
            max_portfolio_target=0.0,
            product_type=ProductType.EQUITY,
        )
        assert stock.max_portfolio_target == 0.0

        stock = Security(
            symbol="AAPL.US",
            name="Test",
            max_portfolio_target=15.0,
            product_type=ProductType.EQUITY,
        )
        assert stock.max_portfolio_target == 15.0

        stock = Security(
            symbol="AAPL.US",
            name="Test",
            max_portfolio_target=30.0,
            product_type=ProductType.EQUITY,
        )
        assert stock.max_portfolio_target == 30.0

    def test_stock_max_portfolio_target_rejects_negative(self):
        """Test that max_portfolio_target rejects values < 0."""
        with pytest.raises(
            ValidationError, match="max_portfolio_target must be between 0 and 30"
        ):
            Security(
                symbol="AAPL.US",
                name="Test",
                max_portfolio_target=-1.0,
                active=False,
            )

    def test_stock_max_portfolio_target_rejects_over_30(self):
        """Test that max_portfolio_target rejects values > 30."""
        with pytest.raises(
            ValidationError, match="max_portfolio_target must be between 0 and 30"
        ):
            Security(
                symbol="AAPL.US",
                name="Test",
                max_portfolio_target=31.0,
                active=False,
            )

    def test_stock_max_portfolio_target_greater_than_min(self):
        """Test that max_portfolio_target >= min_portfolio_target when both provided."""
        stock = Security(
            symbol="AAPL.US",
            name="Test",
            min_portfolio_target=5.0,
            max_portfolio_target=15.0,
            product_type=ProductType.EQUITY,
        )
        assert stock.min_portfolio_target == 5.0
        assert stock.max_portfolio_target == 15.0

    def test_stock_max_portfolio_target_less_than_min_raises_error(self):
        """Test that max_portfolio_target < min_portfolio_target raises ValidationError."""
        with pytest.raises(
            ValidationError,
            match="max_portfolio_target must be >= min_portfolio_target",
        ):
            Security(
                symbol="AAPL.US",
                name="Test",
                min_portfolio_target=15.0,
                max_portfolio_target=5.0,
                active=False,
            )

    def test_stock_portfolio_targets_none_allowed(self):
        """Test that None values are allowed for portfolio targets."""
        stock = Security(symbol="AAPL.US", name="Test", product_type=ProductType.EQUITY)
        assert stock.min_portfolio_target is None
        assert stock.max_portfolio_target is None

    def test_stock_min_portfolio_target_without_max(self):
        """Test that only min_portfolio_target can be set without max."""
        stock = Security(
            symbol="AAPL.US",
            name="Test",
            min_portfolio_target=5.0,
            product_type=ProductType.EQUITY,
        )
        assert stock.min_portfolio_target == 5.0
        assert stock.max_portfolio_target is None

    def test_stock_max_portfolio_target_without_min(self):
        """Test that only max_portfolio_target can be set without min."""
        stock = Security(
            symbol="AAPL.US",
            name="Test",
            max_portfolio_target=15.0,
            product_type=ProductType.EQUITY,
        )
        assert stock.min_portfolio_target is None
        assert stock.max_portfolio_target == 15.0


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
                country="United States",
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
                country="United States",
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
                country="United States",
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
            country="United States",
        )
        assert rec.quantity == 10
        assert rec.estimated_price == 150.0
