"""Unit tests for TradeSafetyService."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.application.services.trade_safety_service import TradeSafetyService
from app.domain.value_objects.trade_side import TradeSide
from app.infrastructure.external.tradernet import TradernetClient
from app.repositories import PositionRepository, TradeRepository


@pytest.fixture
def mock_trade_repo():
    """Mock TradeRepository."""
    repo = MagicMock(spec=TradeRepository)
    repo.has_recent_sell_order = AsyncMock(return_value=False)
    repo.get_recently_bought_symbols = AsyncMock(return_value=set())
    return repo


@pytest.fixture
def mock_position_repo():
    """Mock PositionRepository."""
    repo = MagicMock(spec=PositionRepository)
    return repo


@pytest.fixture
def mock_client():
    """Mock TradernetClient."""
    client = MagicMock(spec=TradernetClient)
    client.has_pending_order_for_symbol = MagicMock(return_value=False)
    return client


@pytest.fixture
def safety_service(mock_trade_repo, mock_position_repo):
    """Create TradeSafetyService instance."""
    return TradeSafetyService(mock_trade_repo, mock_position_repo)


@pytest.mark.asyncio
async def test_check_pending_orders_no_pending(safety_service, mock_client):
    """Test checking pending orders when none exist."""
    result = await safety_service.check_pending_orders(
        "AAPL.US", TradeSide.BUY, mock_client
    )
    assert result is False
    mock_client.has_pending_order_for_symbol.assert_called_once_with("AAPL.US")


@pytest.mark.asyncio
async def test_check_pending_orders_broker_has_pending(safety_service, mock_client):
    """Test checking pending orders when broker has pending."""
    mock_client.has_pending_order_for_symbol.return_value = True
    result = await safety_service.check_pending_orders(
        "AAPL.US", TradeSide.BUY, mock_client
    )
    assert result is True


@pytest.mark.asyncio
async def test_check_pending_orders_recent_sell_in_db(
    safety_service, mock_client, mock_trade_repo
):
    """Test checking pending orders when recent SELL exists in database."""
    mock_trade_repo.has_recent_sell_order.return_value = True
    result = await safety_service.check_pending_orders(
        "AAPL.US", TradeSide.SELL, mock_client
    )
    assert result is True
    mock_trade_repo.has_recent_sell_order.assert_called_once_with("AAPL.US", hours=2)


@pytest.mark.asyncio
async def test_check_cooldown_not_in_cooldown(safety_service, mock_trade_repo):
    """Test cooldown check when symbol is not in cooldown."""
    mock_trade_repo.get_recently_bought_symbols.return_value = set()
    is_cooldown, error = await safety_service.check_cooldown("AAPL.US", TradeSide.BUY)
    assert is_cooldown is False
    assert error is None


@pytest.mark.asyncio
async def test_check_cooldown_in_cooldown(safety_service, mock_trade_repo):
    """Test cooldown check when symbol is in cooldown."""
    mock_trade_repo.get_recently_bought_symbols.return_value = {"AAPL.US"}
    is_cooldown, error = await safety_service.check_cooldown("AAPL.US", TradeSide.BUY)
    assert is_cooldown is True
    assert "cooldown period active" in error


@pytest.mark.asyncio
async def test_check_cooldown_ignores_sell(safety_service):
    """Test that cooldown check is skipped for SELL orders."""
    is_cooldown, error = await safety_service.check_cooldown("AAPL.US", TradeSide.SELL)
    assert is_cooldown is False
    assert error is None


@pytest.mark.asyncio
async def test_validate_sell_position_sufficient(safety_service, mock_position_repo):
    """Test SELL position validation when position is sufficient."""
    from app.domain.models import Position

    position = Position(symbol="AAPL.US", quantity=100.0, avg_price=150.0)
    mock_position_repo.get_by_symbol = AsyncMock(return_value=position)

    is_valid, error = await safety_service.validate_sell_position("AAPL.US", 50.0)
    assert is_valid is True
    assert error is None


@pytest.mark.asyncio
async def test_validate_sell_position_insufficient(safety_service, mock_position_repo):
    """Test SELL position validation when position is insufficient."""
    from app.domain.models import Position

    position = Position(symbol="AAPL.US", quantity=100.0, avg_price=150.0)
    mock_position_repo.get_by_symbol = AsyncMock(return_value=position)

    is_valid, error = await safety_service.validate_sell_position("AAPL.US", 150.0)
    assert is_valid is False
    assert "exceeds position" in error


@pytest.mark.asyncio
async def test_validate_sell_position_no_position(safety_service, mock_position_repo):
    """Test SELL position validation when no position exists."""
    mock_position_repo.get_by_symbol = AsyncMock(return_value=None)

    is_valid, error = await safety_service.validate_sell_position("AAPL.US", 50.0)
    assert is_valid is False
    assert "No position found" in error


@pytest.mark.asyncio
async def test_validate_trade_success(safety_service, mock_client):
    """Test full trade validation when all checks pass."""
    is_valid, error = await safety_service.validate_trade(
        "AAPL.US", TradeSide.BUY, 10.0, mock_client, raise_on_error=False
    )
    assert is_valid is True
    assert error is None


@pytest.mark.asyncio
async def test_validate_trade_raises_on_error(
    safety_service, mock_client, mock_trade_repo
):
    """Test that validate_trade raises HTTPException when raise_on_error=True."""
    mock_trade_repo.get_recently_bought_symbols.return_value = {"AAPL.US"}

    with pytest.raises(HTTPException) as exc_info:
        await safety_service.validate_trade(
            "AAPL.US", TradeSide.BUY, 10.0, mock_client, raise_on_error=True
        )

    assert exc_info.value.status_code == 400
