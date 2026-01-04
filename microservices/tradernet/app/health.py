"""Health check endpoint."""

import logging
from datetime import datetime

from app.config import settings
from app.service import get_tradernet_service
from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

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
        # Test connection with provided credentials by calling user_info
        # This is a lightweight operation that verifies credentials work
        try:
            # Create a client and test with user_info
            # This will raise on invalid credentials
            from tradernet import TraderNetAPI

            test_client = TraderNetAPI(api_key, api_secret)
            # This will raise an exception if credentials are invalid
            test_client.user_info()
            tradernet_connected = True
        except Exception as e:
            logger.debug(f"Tradernet connection test failed: {e}")
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
