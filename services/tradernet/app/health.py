"""Health check endpoint."""

from datetime import datetime

from fastapi import APIRouter

from app.config import settings
from app.service import get_tradernet_service

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    service = get_tradernet_service()

    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": settings.version,
        "timestamp": datetime.utcnow().isoformat(),
        "tradernet_connected": service.is_connected,
    }
