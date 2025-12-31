"""Tests for domain event classes.

These tests validate the domain event dataclasses and their properties.
"""

from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from app.domain.events.position_events import PositionUpdatedEvent
from app.domain.events.recommendation_events import RecommendationCreatedEvent
from app.domain.events.stock_events import StockAddedEvent
from app.domain.events.trade_events import TradeExecutedEvent
from app.domain.models import Position, Recommendation, Stock, Trade
from app.domain.value_objects.trade_side import TradeSide
from app.shared.domain.value_objects.currency import Currency


class TestStockAddedEvent:
    """Test StockAddedEvent domain event."""

    def test_creates_stock_added_event(self):
        """Test creating StockAddedEvent."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        event = StockAddedEvent(stock=stock)

        assert event.stock == stock
        assert isinstance(event.occurred_at, datetime)
        assert event.symbol == "AAPL"
        assert event.name == "Apple Inc."
        assert event.country is None

    def test_stock_added_event_properties(self):
        """Test StockAddedEvent properties."""
        stock = Stock(
            symbol="MSFT",
            name="Microsoft Corporation",
            country="United States",
        )
        event = StockAddedEvent(stock=stock)

        assert event.symbol == "MSFT"
        assert event.name == "Microsoft Corporation"
        assert event.country == "United States"

    def test_stock_added_event_is_frozen(self):
        """Test that StockAddedEvent is immutable."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        event = StockAddedEvent(stock=stock)

        # Should raise FrozenInstanceError on attempt to modify
        with pytest.raises(FrozenInstanceError):
            event.stock = Stock(symbol="MSFT", name="Microsoft")


class TestTradeExecutedEvent:
    """Test TradeExecutedEvent domain event."""

    def test_creates_trade_executed_event(self):
        """Test creating TradeExecutedEvent."""
        trade = Trade(
            symbol="AAPL",
            side=TradeSide.BUY,
            quantity=10.0,
            price=150.0,
            executed_at=datetime.now(),
            order_id="ORD123",
        )
        event = TradeExecutedEvent(trade=trade)

        assert event.trade == trade
        assert isinstance(event.occurred_at, datetime)
        assert event.symbol == "AAPL"
        assert event.side == TradeSide.BUY
        assert event.quantity == 10.0
        assert event.order_id == "ORD123"

    def test_trade_executed_event_properties(self):
        """Test TradeExecutedEvent properties."""
        trade = Trade(
            symbol="MSFT",
            side=TradeSide.SELL,
            quantity=5.0,
            price=300.0,
            executed_at=datetime.now(),
            order_id="ORD456",
            currency=Currency.USD,
        )
        event = TradeExecutedEvent(trade=trade)

        assert event.symbol == "MSFT"
        assert event.side == TradeSide.SELL
        assert event.quantity == 5.0
        assert event.order_id == "ORD456"

    def test_trade_executed_event_is_frozen(self):
        """Test that TradeExecutedEvent is immutable."""
        trade = Trade(
            symbol="AAPL",
            side=TradeSide.BUY,
            quantity=10.0,
            price=150.0,
            executed_at=datetime.now(),
        )
        event = TradeExecutedEvent(trade=trade)

        # Should raise FrozenInstanceError on attempt to modify
        with pytest.raises(FrozenInstanceError):
            event.trade = Trade(
                symbol="MSFT",
                side=TradeSide.BUY,
                quantity=5.0,
                price=300.0,
                executed_at=datetime.now(),
            )


class TestPositionUpdatedEvent:
    """Test PositionUpdatedEvent domain event."""

    def test_creates_position_updated_event(self):
        """Test creating PositionUpdatedEvent."""
        position = Position(symbol="AAPL", quantity=10.0, avg_price=150.0)
        event = PositionUpdatedEvent(position=position)

        assert event.position == position
        assert isinstance(event.occurred_at, datetime)
        assert event.symbol == "AAPL"
        assert event.quantity == 10.0
        assert event.market_value_eur is None

    def test_position_updated_event_properties(self):
        """Test PositionUpdatedEvent properties."""
        position = Position(
            symbol="MSFT",
            quantity=5.0,
            avg_price=300.0,
            market_value_eur=1500.0,
        )
        event = PositionUpdatedEvent(position=position)

        assert event.symbol == "MSFT"
        assert event.quantity == 5.0
        assert event.market_value_eur == 1500.0

    def test_position_updated_event_is_frozen(self):
        """Test that PositionUpdatedEvent is immutable."""
        position = Position(symbol="AAPL", quantity=10.0, avg_price=150.0)
        event = PositionUpdatedEvent(position=position)

        # Should raise FrozenInstanceError on attempt to modify
        with pytest.raises(FrozenInstanceError):
            event.position = Position(symbol="MSFT", quantity=5.0, avg_price=300.0)


class TestRecommendationCreatedEvent:
    """Test RecommendationCreatedEvent domain event."""

    def test_creates_recommendation_created_event(self):
        """Test creating RecommendationCreatedEvent."""
        recommendation = Recommendation(
            symbol="AAPL",
            name="Apple Inc.",
            side=TradeSide.BUY,
            quantity=10,
            estimated_price=150.0,
            estimated_value=1500.0,
            reason="High score",
        )
        event = RecommendationCreatedEvent(recommendation=recommendation)

        assert event.recommendation == recommendation
        assert isinstance(event.occurred_at, datetime)
        assert event.symbol == "AAPL"
        assert event.side == TradeSide.BUY
        assert event.quantity == 10
        assert event.estimated_value == 1500.0

    def test_recommendation_created_event_properties(self):
        """Test RecommendationCreatedEvent properties."""
        recommendation = Recommendation(
            symbol="MSFT",
            name="Microsoft Corporation",
            side=TradeSide.SELL,
            quantity=5,
            estimated_price=300.0,
            estimated_value=1500.0,
            reason="Overweight position",
        )
        event = RecommendationCreatedEvent(recommendation=recommendation)

        assert event.symbol == "MSFT"
        assert event.side == TradeSide.SELL
        assert event.quantity == 5
        assert event.estimated_value == 1500.0

    def test_recommendation_created_event_is_frozen(self):
        """Test that RecommendationCreatedEvent is immutable."""
        recommendation = Recommendation(
            symbol="AAPL",
            name="Apple Inc.",
            side=TradeSide.BUY,
            quantity=10,
            estimated_price=150.0,
            estimated_value=1500.0,
            reason="High score",
        )
        event = RecommendationCreatedEvent(recommendation=recommendation)

        # Should raise FrozenInstanceError on attempt to modify
        with pytest.raises(FrozenInstanceError):
            event.recommendation = Recommendation(
                symbol="MSFT",
                name="Microsoft",
                side=TradeSide.BUY,
                quantity=5,
                estimated_price=300.0,
                estimated_value=1500.0,
                reason="Test",
            )
