"""Health check endpoint."""

from datetime import datetime
from typing import Optional

from app.config import settings
from app.service import get_tradernet_service
from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health_check(request: Request):
    """Health check endpoint.

    If credentials are provided in headers, tests the connection.
    Otherwise, returns service status only.
    """
    service = get_tradernet_service()

    # Check if credentials are provided in headers
    api_key = request.headers.get("X-Tradernet-API-Key")
    api_secret = request.headers.get("X-Tradernet-API-Secret")

    tradernet_connected = False
    if api_key and api_secret:
        # Test connection with provided credentials by trying to get portfolio
        # This is a lightweight operation that verifies credentials work
        try:
            # Use get_portfolio as a test - it requires valid credentials
            positions = service.get_portfolio(api_key=api_key, api_secret=api_secret)
            tradernet_connected = True
        except Exception:
            tradernet_connected = False
    else:
        # Fall back to startup connection status (backward compatibility)
        tradernet_connected = service.is_connected

    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": settings.version,
        "timestamp": datetime.utcnow().isoformat(),
        "tradernet_connected": tradernet_connected,
    }
