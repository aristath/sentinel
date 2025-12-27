"""Tests for trades API endpoints.

These tests validate trade execution and history endpoints.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.domain.models import Trade
from app.domain.value_objects.trade_side import TradeSide


class TestTradeRequestValidation:
    """Test TradeRequest validation."""

    def test_validates_symbol(self):
        """Test that symbol is validated and normalized."""
        from app.api.trades import TradeRequest

        request = TradeRequest(symbol="  aapl.us  ", side=TradeSide.BUY, quantity=10)

        assert request.symbol == "AAPL.US"

    def test_validates_quantity_positive(self):
        """Test that quantity must be positive."""
        from pydantic import ValidationError

        from app.api.trades import TradeRequest

        with pytest.raises(ValidationError):
            TradeRequest(symbol="AAPL.US", side=TradeSide.BUY, quantity=0)

    def test_validates_quantity_max(self):
        """Test that quantity has upper limit."""
        from pydantic import ValidationError

        from app.api.trades import TradeRequest

        with pytest.raises(ValidationError):
            TradeRequest(symbol="AAPL.US", side=TradeSide.BUY, quantity=2000000)

    def test_accepts_valid_request(self):
        """Test that valid request is accepted."""
        from app.api.trades import TradeRequest

        request = TradeRequest(symbol="AAPL.US", side=TradeSide.BUY, quantity=100)

        assert request.symbol == "AAPL.US"
        assert request.side == TradeSide.BUY
        assert request.quantity == 100


class TestGetTrades:
    """Test get trades endpoint."""

    @pytest.mark.asyncio
    async def test_returns_trade_history(self):
        """Test returning trade history."""
        from app.api.trades import get_trades

        mock_trades = [
            Trade(
                id=1,
                symbol="AAPL.US",
                side="BUY",
                quantity=10,
                price=150.0,
                executed_at=datetime(2024, 1, 15, 10, 0, 0),
                order_id="ORD123",
            )
        ]

        mock_repo = AsyncMock()
        mock_repo.get_history = AsyncMock(return_value=mock_trades)

        result = await get_trades(mock_repo, limit=50)

        assert len(result) == 1
        assert result[0]["symbol"] == "AAPL.US"
        assert result[0]["side"] == "BUY"
        mock_repo.get_history.assert_called_once_with(limit=50)


class TestExecuteTrade:
    """Test execute trade endpoint."""

    @pytest.mark.asyncio
    async def test_raises_404_for_unknown_stock(self):
        """Test raising 404 when stock not found."""
        from app.api.trades import TradeRequest, execute_trade

        request = TradeRequest(symbol="UNKNOWN", side=TradeSide.BUY, quantity=10)

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_symbol = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await execute_trade(
                trade=request,
                stock_repo=mock_stock_repo,
                trade_repo=AsyncMock(),
                position_repo=AsyncMock(),
                safety_service=AsyncMock(),
                trade_execution_service=AsyncMock(),
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_executes_trade_successfully(self):
        """Test successful trade execution."""
        from app.api.trades import TradeRequest, execute_trade

        request = TradeRequest(symbol="AAPL.US", side=TradeSide.BUY, quantity=10)

        mock_stock = MagicMock()
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_symbol = AsyncMock(return_value=mock_stock)

        mock_trade_result = MagicMock()
        mock_trade_result.price = 150.0
        mock_trade_result.order_id = "ORD456"

        mock_client = MagicMock()
        mock_client.place_order.return_value = mock_trade_result

        mock_safety_service = AsyncMock()
        mock_trade_execution_service = AsyncMock()

        with (
            patch(
                "app.api.trades.ensure_tradernet_connected",
                new_callable=AsyncMock,
                return_value=mock_client,
            ),
            patch("app.api.trades.get_cache_invalidation_service") as mock_cache,
        ):
            mock_cache.return_value = MagicMock()

            result = await execute_trade(
                trade=request,
                stock_repo=mock_stock_repo,
                trade_repo=AsyncMock(),
                position_repo=AsyncMock(),
                safety_service=mock_safety_service,
                trade_execution_service=mock_trade_execution_service,
            )

        assert result["status"] == "success"
        assert result["order_id"] == "ORD456"

    @pytest.mark.asyncio
    async def test_raises_500_on_trade_failure(self):
        """Test raising 500 when trade execution fails."""
        from app.api.trades import TradeRequest, execute_trade

        request = TradeRequest(symbol="AAPL.US", side=TradeSide.BUY, quantity=10)

        mock_stock = MagicMock()
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_symbol = AsyncMock(return_value=mock_stock)

        mock_client = MagicMock()
        mock_client.place_order.return_value = None  # Trade failed

        mock_safety_service = AsyncMock()

        with patch(
            "app.api.trades.ensure_tradernet_connected",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await execute_trade(
                    trade=request,
                    stock_repo=mock_stock_repo,
                    trade_repo=AsyncMock(),
                    position_repo=AsyncMock(),
                    safety_service=mock_safety_service,
                    trade_execution_service=AsyncMock(),
                )

        assert exc_info.value.status_code == 500


class TestGetAllocation:
    """Test get allocation endpoint."""

    @pytest.mark.asyncio
    async def test_returns_allocation_data(self):
        """Test returning allocation data."""
        from app.api.trades import get_allocation

        mock_geo_alloc = MagicMock()
        mock_geo_alloc.name = "US"
        mock_geo_alloc.target_pct = 50.0
        mock_geo_alloc.current_pct = 45.0
        mock_geo_alloc.current_value = 4500.0
        mock_geo_alloc.deviation = -5.0

        mock_summary = MagicMock()
        mock_summary.total_value = 10000.0
        mock_summary.cash_balance = 1000.0
        mock_summary.geographic_allocations = [mock_geo_alloc]
        mock_summary.industry_allocations = []

        mock_service = AsyncMock()
        mock_service.get_portfolio_summary = AsyncMock(return_value=mock_summary)

        result = await get_allocation(mock_service)

        assert result["total_value"] == 10000.0
        assert result["cash_balance"] == 1000.0
        assert len(result["geographic"]) == 1
        assert result["geographic"][0]["name"] == "US"
