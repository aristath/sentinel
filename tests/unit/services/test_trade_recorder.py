"""Tests for trade recorder service.

These tests validate trade recording functionality, including duplicate checking,
currency handling, and position updates after sells.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.models import Trade
from app.modules.trading.services.trade_execution.trade_recorder import record_trade


class TestRecordTrade:
    """Test record_trade function."""

    @pytest.fixture
    def mock_trade_repo(self):
        """Mock TradeRepository."""
        repo = AsyncMock()
        repo.exists = AsyncMock(return_value=False)
        repo.create = AsyncMock()
        return repo

    @pytest.fixture
    def mock_position_repo(self):
        """Mock PositionRepository."""
        repo = AsyncMock()
        return repo

    @pytest.fixture
    def mock_exchange_rate_service(self):
        """Mock ExchangeRateService."""
        service = AsyncMock()
        service.get_rate = AsyncMock(return_value=1.0)
        return service

    @pytest.mark.asyncio
    async def test_records_trade_successfully(
        self, mock_trade_repo, mock_position_repo, mock_exchange_rate_service
    ):
        """Test that a trade is recorded successfully."""
        with (
            patch(
                "app.modules.trading.services.trade_execution.trade_recorder.TradeFactory"
            ) as mock_factory,
            patch(
                "app.modules.trading.services.trade_execution.trade_recorder.get_event_bus"
            ) as mock_event_bus,
        ):
            mock_trade = MagicMock(spec=Trade)
            mock_trade.side = MagicMock()
            mock_trade.side.is_sell.return_value = False
            mock_factory.create_from_execution.return_value = mock_trade

            mock_bus = MagicMock()
            mock_event_bus.return_value = mock_bus

            result = await record_trade(
                symbol="AAPL",
                side="BUY",
                quantity=10.0,
                price=150.0,
                trade_repo=mock_trade_repo,
                position_repo=mock_position_repo,
                exchange_rate_service=mock_exchange_rate_service,
                order_id="ORDER123",
            )

            assert result == mock_trade
            mock_trade_repo.create.assert_called_once()
            mock_bus.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_duplicate_order_id(
        self, mock_trade_repo, mock_position_repo, mock_exchange_rate_service
    ):
        """Test that duplicate order_id is skipped."""
        mock_trade_repo.exists.return_value = True  # Duplicate exists

        result = await record_trade(
            symbol="AAPL",
            side="BUY",
            quantity=10.0,
            price=150.0,
            trade_repo=mock_trade_repo,
            position_repo=mock_position_repo,
            exchange_rate_service=mock_exchange_rate_service,
            order_id="ORDER123",
        )

        assert result is None
        mock_trade_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_trade_without_order_id(
        self, mock_trade_repo, mock_position_repo, mock_exchange_rate_service
    ):
        """Test that trade without order_id is skipped."""
        result = await record_trade(
            symbol="AAPL",
            side="BUY",
            quantity=10.0,
            price=150.0,
            trade_repo=mock_trade_repo,
            position_repo=mock_position_repo,
            exchange_rate_service=mock_exchange_rate_service,
            order_id=None,  # No order_id
        )

        assert result is None
        mock_trade_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_trade_with_empty_order_id(
        self, mock_trade_repo, mock_position_repo, mock_exchange_rate_service
    ):
        """Test that trade with empty order_id is skipped."""
        result = await record_trade(
            symbol="AAPL",
            side="BUY",
            quantity=10.0,
            price=150.0,
            trade_repo=mock_trade_repo,
            position_repo=mock_position_repo,
            exchange_rate_service=mock_exchange_rate_service,
            order_id="   ",  # Empty/whitespace order_id
        )

        assert result is None
        mock_trade_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_uses_estimated_price_when_price_zero(
        self, mock_trade_repo, mock_position_repo, mock_exchange_rate_service
    ):
        """Test that estimated_price is used when price is zero."""
        with (
            patch(
                "app.modules.trading.services.trade_execution.trade_recorder.TradeFactory"
            ) as mock_factory,
            patch(
                "app.modules.trading.services.trade_execution.trade_recorder.get_event_bus"
            ) as mock_event_bus,
        ):
            mock_trade = MagicMock(spec=Trade)
            mock_trade.side = MagicMock()
            mock_trade.side.is_sell.return_value = False
            mock_factory.create_from_execution.return_value = mock_trade

            mock_bus = MagicMock()
            mock_event_bus.return_value = mock_bus

            await record_trade(
                symbol="AAPL",
                side="BUY",
                quantity=10.0,
                price=0.0,  # Zero price
                trade_repo=mock_trade_repo,
                position_repo=mock_position_repo,
                exchange_rate_service=mock_exchange_rate_service,
                order_id="ORDER123",
                estimated_price=150.0,  # Use estimated
            )

            # Verify TradeFactory was called with estimated_price
            call_args = mock_factory.create_from_execution.call_args
            assert call_args is not None
            # Should use estimated_price (150.0) instead of price (0.0)
            assert call_args.kwargs.get("price") == 150.0

    @pytest.mark.asyncio
    async def test_updates_position_after_sell(
        self, mock_trade_repo, mock_position_repo, mock_exchange_rate_service
    ):
        """Test that position is updated after a sell trade."""
        with (
            patch(
                "app.modules.trading.services.trade_execution.trade_recorder.TradeFactory"
            ) as mock_factory,
            patch(
                "app.modules.trading.services.trade_execution.trade_recorder.get_event_bus"
            ) as mock_event_bus,
        ):
            mock_trade = MagicMock(spec=Trade)
            mock_trade.side = MagicMock()
            mock_trade.side.is_sell.return_value = True  # SELL trade
            mock_factory.create_from_execution.return_value = mock_trade

            mock_bus = MagicMock()
            mock_event_bus.return_value = mock_bus

            await record_trade(
                symbol="AAPL",
                side="SELL",
                quantity=10.0,
                price=150.0,
                trade_repo=mock_trade_repo,
                position_repo=mock_position_repo,
                exchange_rate_service=mock_exchange_rate_service,
                order_id="ORDER123",
            )

            # Should update position after sell
            mock_position_repo.update_last_sold_at.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_currency_conversion(
        self, mock_trade_repo, mock_position_repo, mock_exchange_rate_service
    ):
        """Test that currency is handled correctly."""
        mock_exchange_rate_service.get_rate.return_value = 1.1  # USD to EUR rate

        with (
            patch(
                "app.modules.trading.services.trade_execution.trade_recorder.TradeFactory"
            ) as mock_factory,
            patch(
                "app.modules.trading.services.trade_execution.trade_recorder.get_event_bus"
            ) as mock_event_bus,
        ):
            mock_trade = MagicMock(spec=Trade)
            mock_trade.side = MagicMock()
            mock_trade.side.is_sell.return_value = False
            mock_factory.create_from_execution.return_value = mock_trade

            mock_bus = MagicMock()
            mock_event_bus.return_value = mock_bus

            await record_trade(
                symbol="AAPL",
                side="BUY",
                quantity=10.0,
                price=150.0,
                trade_repo=mock_trade_repo,
                position_repo=mock_position_repo,
                exchange_rate_service=mock_exchange_rate_service,
                order_id="ORDER123",
                currency="USD",
            )

            # Should get exchange rate for currency
            mock_exchange_rate_service.get_rate.assert_called()

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(
        self, mock_trade_repo, mock_position_repo, mock_exchange_rate_service
    ):
        """Test that exceptions are handled gracefully."""
        mock_trade_repo.create.side_effect = Exception("Database error")

        result = await record_trade(
            symbol="AAPL",
            side="BUY",
            quantity=10.0,
            price=150.0,
            trade_repo=mock_trade_repo,
            position_repo=mock_position_repo,
            exchange_rate_service=mock_exchange_rate_service,
            order_id="ORDER123",
        )

        # Should return None on error, not raise
        assert result is None

    @pytest.mark.asyncio
    async def test_publishes_trade_executed_event(
        self, mock_trade_repo, mock_position_repo, mock_exchange_rate_service
    ):
        """Test that TradeExecutedEvent is published."""
        with (
            patch(
                "app.modules.trading.services.trade_execution.trade_recorder.TradeFactory"
            ) as mock_factory,
            patch(
                "app.modules.trading.services.trade_execution.trade_recorder.get_event_bus"
            ) as mock_event_bus,
            patch(
                "app.modules.trading.services.trade_execution.trade_recorder.TradeExecutedEvent"
            ) as mock_event_class,
        ):
            mock_trade = MagicMock(spec=Trade)
            mock_trade.side = MagicMock()
            mock_trade.side.is_sell.return_value = False
            mock_factory.create_from_execution.return_value = mock_trade

            mock_bus = MagicMock()
            mock_event_bus.return_value = mock_bus

            mock_event = MagicMock()
            mock_event_class.return_value = mock_event

            await record_trade(
                symbol="AAPL",
                side="BUY",
                quantity=10.0,
                price=150.0,
                trade_repo=mock_trade_repo,
                position_repo=mock_position_repo,
                exchange_rate_service=mock_exchange_rate_service,
                order_id="ORDER123",
            )

            # Should publish event
            mock_bus.publish.assert_called_once()
            mock_event_class.assert_called_once()
