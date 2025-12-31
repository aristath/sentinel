"""Rate limiting middleware for API endpoints."""

from app.core.middleware.rate_limit import RateLimitMiddleware

__all__ = ["RateLimitMiddleware"]
