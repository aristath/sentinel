"""Tests for TradeFactory."""

from datetime import datetime

from app.domain.factories.trade_factory import TradeFactory
from app.domain.value_objects.trade_side import TradeSide
from app.shared.domain.value_objects.currency import Currency


class TestTradeFactory:
    """Test TradeFactory creation methods."""

    def test_create_from_execution(self):
        """Test creating trade from execution result."""
        trade = TradeFactory.create_from_execution(
            symbol="AAPL.US",
            side=TradeSide.BUY,
            quantity=10.0,
            price=150.0,
            order_id="ORD123",
            executed_at=datetime(2024, 1, 15, 10, 30, 0),
            currency=Currency.USD,
            currency_rate=1.05,
        )

        assert trade.symbol == "AAPL.US"
        assert trade.side == TradeSide.BUY
        assert trade.quantity == 10.0
        assert trade.price == 150.0
        assert trade.order_id == "ORD123"
        assert trade.currency == Currency.USD
        assert trade.currency_rate == 1.05
        assert trade.value_eur == (10.0 * 150.0) / 1.05  # Converted to EUR
        assert trade.source == "tradernet"

    def test_create_from_execution_calculates_eur_value(self):
        """Test that EUR value is calculated correctly."""
        # USD trade
        trade = TradeFactory.create_from_execution(
            symbol="AAPL.US",
            side=TradeSide.BUY,
            quantity=10.0,
            price=150.0,
            order_id="ORD123",
            executed_at=datetime.now(),
            currency=Currency.USD,
            currency_rate=1.05,
        )
        expected_eur = (10.0 * 150.0) / 1.05
        assert abs(trade.value_eur - expected_eur) < 0.01

        # EUR trade (rate = 1.0)
        trade_eur = TradeFactory.create_from_execution(
            symbol="ASML.NL",
            side=TradeSide.BUY,
            quantity=5.0,
            price=200.0,
            order_id="ORD124",
            executed_at=datetime.now(),
            currency=Currency.EUR,
            currency_rate=1.0,
        )
        assert trade_eur.value_eur == 1000.0

    def test_create_from_execution_without_currency_rate(self):
        """Test creating trade without currency rate (assumes EUR)."""
        trade = TradeFactory.create_from_execution(
            symbol="ASML.NL",
            side=TradeSide.BUY,
            quantity=5.0,
            price=200.0,
            order_id="ORD125",
            executed_at=datetime.now(),
            currency=Currency.EUR,
        )

        assert trade.currency_rate is None
        assert trade.value_eur == 1000.0  # No conversion needed

    def test_create_from_sync(self):
        """Test creating trade from broker sync data."""
        trade = TradeFactory.create_from_sync(
            symbol="MSFT.US",
            side="BUY",  # String, will be converted
            quantity=20.0,
            price=300.0,
            executed_at="2024-01-15T10:30:00",
            order_id="BROKER123",
            currency="USD",  # String, will be converted
            currency_rate=1.05,
        )

        assert trade.symbol == "MSFT.US"
        assert trade.side == TradeSide.BUY
        assert trade.quantity == 20.0
        assert trade.price == 300.0
        assert trade.order_id == "BROKER123"
        assert trade.currency == Currency.USD
        assert trade.currency_rate == 1.05
        assert trade.source == "tradernet"

    def test_create_from_sync_converts_strings(self):
        """Test that create_from_sync converts string side and currency."""
        trade = TradeFactory.create_from_sync(
            symbol="AAPL.US",
            side="SELL",
            quantity=10.0,
            price=150.0,
            executed_at=datetime.now().isoformat(),
            order_id="ORD126",
            currency="HKD",
            currency_rate=8.5,
        )

        assert trade.side == TradeSide.SELL
        assert trade.currency == Currency.HKD
