"""Health check endpoint for unified microservice."""

import logging
from datetime import datetime

from app.config import settings
from app.services.tradernet_service import get_tradernet_service
from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check(request: Request):
    """Unified health check endpoint.

    Returns basic service health information including Tradernet connection status.
    """
    # Check Tradernet connection status
    tradernet_service = get_tradernet_service()
    tradernet_connected = tradernet_service.is_connected

    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": settings.version,
        "timestamp": datetime.utcnow().isoformat(),
        "tradernet_connected": tradernet_connected,
    }
