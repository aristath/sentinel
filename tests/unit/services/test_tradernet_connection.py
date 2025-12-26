"""Unit tests for TradernetConnectionHelper."""

import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi import HTTPException

from app.services.tradernet_connection import ensure_tradernet_connected
from app.infrastructure.external.tradernet import TradernetClient


@pytest.mark.asyncio
async def test_ensure_tradernet_connected_already_connected():
    """Test ensuring connection when already connected."""
    mock_client = MagicMock(spec=TradernetClient)
    mock_client.is_connected = True
    
    result = await ensure_tradernet_connected(client=mock_client)
    
    assert result is mock_client
    mock_client.connect.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_tradernet_connected_connects_successfully():
    """Test ensuring connection when not connected but connects successfully."""
    mock_client = MagicMock(spec=TradernetClient)
    mock_client.is_connected = False
    mock_client.connect.return_value = True
    
    result = await ensure_tradernet_connected(client=mock_client)
    
    assert result is mock_client
    mock_client.connect.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_tradernet_connected_fails_raises_exception():
    """Test ensuring connection when connection fails and raise_on_error=True."""
    mock_client = MagicMock(spec=TradernetClient)
    mock_client.is_connected = False
    mock_client.connect.return_value = False
    
    with pytest.raises(HTTPException) as exc_info:
        await ensure_tradernet_connected(client=mock_client, raise_on_error=True)
    
    assert exc_info.value.status_code == 503
    assert "Failed to connect" in exc_info.value.detail


@pytest.mark.asyncio
async def test_ensure_tradernet_connected_fails_returns_none():
    """Test ensuring connection when connection fails and raise_on_error=False."""
    mock_client = MagicMock(spec=TradernetClient)
    mock_client.is_connected = False
    mock_client.connect.return_value = False
    
    result = await ensure_tradernet_connected(client=mock_client, raise_on_error=False)
    
    assert result is None


@pytest.mark.asyncio
async def test_ensure_tradernet_connected_uses_default_client(monkeypatch):
    """Test ensuring connection when no client provided (uses default)."""
    mock_client = MagicMock(spec=TradernetClient)
    mock_client.is_connected = True
    
    def mock_get_client():
        return mock_client
    
    monkeypatch.setattr("app.services.tradernet_connection.get_tradernet_client", mock_get_client)
    
    result = await ensure_tradernet_connected()
    
    assert result is mock_client

