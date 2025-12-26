"""Rate limiting middleware for API endpoints."""

import logging
import time
from collections import defaultdict
from typing import Optional

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory rate limiting middleware.

    Tracks requests per IP address and endpoint.
    """

    def __init__(
        self,
        app,
        max_requests: Optional[int] = None,
        window_seconds: Optional[int] = None,
        trade_max: Optional[int] = None,
        trade_window: Optional[int] = None,
    ):
        from app.config import settings

        super().__init__(app)
        self.max_requests = max_requests or settings.rate_limit_max_requests
        self.window_seconds = window_seconds or settings.rate_limit_window_seconds
        self.trade_max = trade_max or settings.rate_limit_trade_max
        self.trade_window = trade_window or settings.rate_limit_trade_window
        # Store request timestamps: (ip, path) -> [timestamps]
        self._request_history: dict[tuple[str, str], list[float]] = defaultdict(list)
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # Clean up old entries every 5 minutes

    async def dispatch(self, request: Request, call_next):
        # Clean up old entries periodically
        current_time = time.time()
        if current_time - self._last_cleanup > self._cleanup_interval:
            self._cleanup_old_entries(current_time)
            self._last_cleanup = current_time

        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        # Skip rate limiting for internal endpoints (LED display, static files)
        if path.startswith("/api/status/led") or path.startswith("/static"):
            return await call_next(request)

        # Check rate limit for trade execution endpoints
        if path.startswith("/api/trades/execute") or path.startswith(
            "/api/trades/rebalance/execute"
        ):
            # Stricter limits for trade execution
            key = (client_ip, "trade_execution")
            now = time.time()

            # Remove old requests outside the window
            self._request_history[key] = [
                ts for ts in self._request_history[key] if now - ts < self.trade_window
            ]

            # Check if limit exceeded
            if len(self._request_history[key]) >= self.trade_max:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": f"Rate limit exceeded: Maximum {self.trade_max} trade executions per {self.trade_window} seconds"
                    },
                )

            # Record this request
            self._request_history[key].append(now)

        # General rate limiting for other endpoints
        else:
            key = (client_ip, path)
            now = time.time()

            # Remove old requests outside the window
            self._request_history[key] = [
                ts
                for ts in self._request_history[key]
                if now - ts < self.window_seconds
            ]

            # Check if limit exceeded
            if len(self._request_history[key]) >= self.max_requests:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": f"Rate limit exceeded: Maximum {self.max_requests} requests per {self.window_seconds} seconds"
                    },
                )

            # Record this request
            self._request_history[key].append(now)

        response = await call_next(request)
        return response

    def _cleanup_old_entries(self, current_time: float):
        """Remove entries older than the window."""
        cutoff = current_time - max(self.window_seconds, 300)  # At least 5 minutes

        keys_to_remove = []
        for key, timestamps in self._request_history.items():
            filtered = [ts for ts in timestamps if ts > cutoff]
            if filtered:
                self._request_history[key] = filtered
            else:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._request_history[key]

