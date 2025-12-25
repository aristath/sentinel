"""Tests for domain events."""

import pytest
from datetime import datetime
from app.domain.events import (
    DomainEvent,
    TradeExecutedEvent,
    PositionUpdatedEvent,
    RecommendationCreatedEvent,
    StockAddedEvent,
    DomainEventBus,
)
from app.domain.models import Trade, Position, Recommendation, Stock
from app.domain.value_objects.trade_side import TradeSide
from app.domain.value_objects.currency import Currency
from app.domain.value_objects.recommendation_status import RecommendationStatus


class TestDomainEvents:
    """Test domain event base class and specific events."""

    def test_domain_event_base(self):
        """Test that DomainEvent is a base class."""
        # DomainEvent is abstract - test with a concrete subclass
        from app.domain.events.stock_events import StockAddedEvent
        from app.domain.models import Stock
        from app.domain.value_objects.currency import Currency
        
        stock = Stock(symbol="AAPL.US", name="Apple Inc.", geography="US", currency=Currency.USD)
        event = StockAddedEvent(stock=stock)
        assert event.occurred_at is not None

    def test_trade_executed_event(self):
        """Test TradeExecutedEvent creation."""
        trade = Trade(
            symbol="AAPL.US",
            side=TradeSide.BUY,
            quantity=10.0,
            price=150.0,
            executed_at=datetime.now(),
            order_id="ORD123",
            currency=Currency.USD,
        )
        
        event = TradeExecutedEvent(trade=trade)
        
        assert event.trade == trade
        assert event.symbol == "AAPL.US"
        assert event.side == TradeSide.BUY
        assert event.quantity == 10.0
        assert event.occurred_at is not None

    def test_position_updated_event(self):
        """Test PositionUpdatedEvent creation."""
        position = Position(
            symbol="AAPL.US",
            quantity=10.0,
            avg_price=150.0,
            currency=Currency.USD,
        )
        
        event = PositionUpdatedEvent(position=position)
        
        assert event.position == position
        assert event.symbol == "AAPL.US"
        assert event.quantity == 10.0

    def test_recommendation_created_event(self):
        """Test RecommendationCreatedEvent creation."""
        recommendation = Recommendation(
            symbol="AAPL.US",
            name="Apple Inc.",
            side=TradeSide.BUY,
            quantity=10,
            estimated_price=150.0,
            estimated_value=1500.0,
            reason="High score",
            geography="US",
            currency=Currency.USD,
        )
        
        event = RecommendationCreatedEvent(recommendation=recommendation)
        
        assert event.recommendation == recommendation
        assert event.symbol == "AAPL.US"
        assert event.side == TradeSide.BUY

    def test_stock_added_event(self):
        """Test StockAddedEvent creation."""
        stock = Stock(
            symbol="AAPL.US",
            name="Apple Inc.",
            geography="US",
            currency=Currency.USD,
        )
        
        event = StockAddedEvent(stock=stock)
        
        assert event.stock == stock
        assert event.symbol == "AAPL.US"


class TestDomainEventBus:
    """Test domain event bus."""

    def test_subscribe_and_publish(self):
        """Test subscribing to events and publishing them."""
        bus = DomainEventBus()
        events_received = []
        
        def handler(event: DomainEvent):
            events_received.append(event)
        
        bus.subscribe(TradeExecutedEvent, handler)
        
        trade = Trade(
            symbol="AAPL.US",
            side=TradeSide.BUY,
            quantity=10.0,
            price=150.0,
            executed_at=datetime.now(),
            currency=Currency.USD,
        )
        event = TradeExecutedEvent(trade=trade)
        
        bus.publish(event)
        
        assert len(events_received) == 1
        assert events_received[0] == event

    def test_multiple_handlers(self):
        """Test that multiple handlers receive the same event."""
        bus = DomainEventBus()
        handler1_events = []
        handler2_events = []
        
        def handler1(event: DomainEvent):
            handler1_events.append(event)
        
        def handler2(event: DomainEvent):
            handler2_events.append(event)
        
        bus.subscribe(TradeExecutedEvent, handler1)
        bus.subscribe(TradeExecutedEvent, handler2)
        
        trade = Trade(
            symbol="AAPL.US",
            side=TradeSide.BUY,
            quantity=10.0,
            price=150.0,
            executed_at=datetime.now(),
            currency=Currency.USD,
        )
        event = TradeExecutedEvent(trade=trade)
        
        bus.publish(event)
        
        assert len(handler1_events) == 1
        assert len(handler2_events) == 1

    def test_unsubscribe(self):
        """Test unsubscribing from events."""
        bus = DomainEventBus()
        events_received = []
        
        def handler(event: DomainEvent):
            events_received.append(event)
        
        bus.subscribe(TradeExecutedEvent, handler)
        bus.unsubscribe(TradeExecutedEvent, handler)
        
        trade = Trade(
            symbol="AAPL.US",
            side=TradeSide.BUY,
            quantity=10.0,
            price=150.0,
            executed_at=datetime.now(),
            currency=Currency.USD,
        )
        event = TradeExecutedEvent(trade=trade)
        
        bus.publish(event)
        
        assert len(events_received) == 0

    def test_handler_exception_does_not_stop_others(self):
        """Test that handler exceptions don't stop other handlers."""
        bus = DomainEventBus()
        handler1_called = False
        handler2_called = False
        
        def handler1(event: DomainEvent):
            nonlocal handler1_called
            handler1_called = True
            raise ValueError("Handler error")
        
        def handler2(event: DomainEvent):
            nonlocal handler2_called
            handler2_called = True
        
        bus.subscribe(TradeExecutedEvent, handler1)
        bus.subscribe(TradeExecutedEvent, handler2)
        
        trade = Trade(
            symbol="AAPL.US",
            side=TradeSide.BUY,
            quantity=10.0,
            price=150.0,
            executed_at=datetime.now(),
            currency=Currency.USD,
        )
        event = TradeExecutedEvent(trade=trade)
        
        # Should not raise exception
        bus.publish(event)
        
        assert handler1_called is True
        assert handler2_called is True

