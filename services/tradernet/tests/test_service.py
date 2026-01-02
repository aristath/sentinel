"""Service logic tests."""

import pytest

from app.service import TradernetService


@pytest.fixture
def service():
    """Create service instance."""
    return TradernetService()


def test_service_initialization(service):
    """Test service initializes correctly."""
    assert service is not None
    assert hasattr(service, "connect")
    assert hasattr(service, "is_connected")


def test_service_not_connected_initially(service):
    """Test service is not connected initially."""
    assert service.is_connected is False


def test_connection_without_credentials(service, monkeypatch):
    """Test connection fails without credentials."""
    monkeypatch.setenv("TRADERNET_API_KEY", "")
    monkeypatch.setenv("TRADERNET_API_SECRET", "")

    result = service.connect()
    assert result is False
    assert service.is_connected is False


def test_ensure_connected_raises(service):
    """Test _ensure_connected raises when not connected."""
    with pytest.raises(ConnectionError):
        service._ensure_connected()


def test_get_pending_order_totals_empty(service):
    """Test pending order totals with no orders."""
    # Mock get_pending_orders to return empty list
    service.get_pending_orders = lambda: []

    totals = service.get_pending_order_totals()
    assert totals == {}


def test_has_pending_order_for_symbol(service):
    """Test checking pending orders for symbol."""
    from app.models import PendingOrder

    # Mock get_pending_orders
    service.get_pending_orders = lambda: [
        PendingOrder(
            id="1",
            symbol="AAPL.US",
            side="BUY",
            quantity=10.0,
            price=175.50,
            currency="USD"
        )
    ]

    assert service.has_pending_order_for_symbol("AAPL.US") is True
    assert service.has_pending_order_for_symbol("TSLA.US") is False
