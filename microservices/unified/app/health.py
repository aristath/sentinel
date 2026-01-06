"""Health check endpoint for unified microservice."""

import logging
from datetime import datetime

from app.config import settings
from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check(request: Request):
    """Unified health check endpoint.

    Returns basic service health information.
    """
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": settings.version,
        "timestamp": datetime.utcnow().isoformat(),
    }
