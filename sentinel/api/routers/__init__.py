"""API routers for Sentinel.

Each router handles a specific domain of the API.
"""

from sentinel.api.routers.settings import led_router
from sentinel.api.routers.settings import router as settings_router

__all__ = [
    "settings_router",
    "led_router",
]
