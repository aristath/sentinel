"""Tradernet connection helper - ensures consistent connection handling."""

import logging
from fastapi import HTTPException
from app.infrastructure.external.tradernet import TradernetClient, get_tradernet_client

logger = logging.getLogger(__name__)


async def ensure_tradernet_connected(
    client: TradernetClient = None,
    raise_on_error: bool = True
) -> TradernetClient:
    """
    Ensure Tradernet client is connected, connecting if necessary.
    
    Args:
        client: Tradernet client instance (default: gets from get_tradernet_client())
        raise_on_error: If True, raise HTTPException on connection failure
        
    Returns:
        Connected TradernetClient instance
        
    Raises:
        HTTPException: If raise_on_error=True and connection fails
    """
    if client is None:
        client = get_tradernet_client()
    
    if not client.is_connected:
        if not client.connect():
            error_msg = "Failed to connect to Tradernet"
            logger.error(error_msg)
            if raise_on_error:
                raise HTTPException(status_code=503, detail=error_msg)
            return None
    
    return client

