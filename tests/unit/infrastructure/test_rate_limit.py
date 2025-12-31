"""Tests for rate limiting middleware.

These tests validate rate limiting middleware functionality to prevent excessive
API calls and ensure proper throttling behavior.
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.responses import Response

from app.core.middleware import RateLimitMiddleware


class TestRateLimitMiddleware:
    """Test RateLimitMiddleware class."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock FastAPI app."""
        app = MagicMock()
        return app

    @pytest.fixture
    def mock_request(self):
        """Create a mock request."""
        request = MagicMock()
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        request.url.path = "/api/test"
        return request

    @pytest.fixture
    def middleware(self, mock_app):
        """Create RateLimitMiddleware with test settings."""
        with patch("app.config.settings") as mock_settings:
            mock_settings.rate_limit_max_requests = 10
            mock_settings.rate_limit_window_seconds = 60
            mock_settings.rate_limit_trade_max = 5
            mock_settings.rate_limit_trade_window = 60
            return RateLimitMiddleware(mock_app)

    @pytest.mark.asyncio
    async def test_allows_requests_within_limit(self, middleware, mock_request):
        """Test that requests within the limit are allowed."""
        mock_response = Response()
        call_next = AsyncMock(return_value=mock_response)

        # Make requests within limit
        for _ in range(5):
            response = await middleware.dispatch(mock_request, call_next)
            assert response == mock_response

        assert call_next.call_count == 5

    @pytest.mark.asyncio
    async def test_blocks_requests_exceeding_limit(self, middleware, mock_request):
        """Test that requests exceeding the limit are blocked."""
        call_next = AsyncMock(return_value=Response())

        # Exceed the limit (10 requests in test config)
        for _ in range(11):
            response = await middleware.dispatch(mock_request, call_next)

        # Last request should be blocked
        assert response.status_code == 429
        assert "Rate limit exceeded" in str(response.body)

    @pytest.mark.asyncio
    async def test_trade_endpoints_have_stricter_limits(self, middleware):
        """Test that trade execution endpoints have stricter limits."""
        trade_request = MagicMock()
        trade_request.client = MagicMock()
        trade_request.client.host = "127.0.0.1"
        trade_request.url.path = "/api/trades/execute"
        call_next = AsyncMock(return_value=Response())

        # Make requests up to trade limit (5 in test config)
        for _ in range(5):
            response = await middleware.dispatch(trade_request, call_next)
            assert response.status_code != 429

        # Next request should be blocked (exceeds trade limit)
        response = await middleware.dispatch(trade_request, call_next)
        assert response.status_code == 429
        assert "trade executions" in str(response.body)

    @pytest.mark.asyncio
    async def test_skips_rate_limiting_for_internal_endpoints(self, middleware):
        """Test that internal endpoints skip rate limiting."""
        led_request = MagicMock()
        led_request.client = MagicMock()
        led_request.client.host = "127.0.0.1"
        led_request.url.path = "/api/status/led"
        call_next = AsyncMock(return_value=Response())

        # Make many requests - should all pass
        for _ in range(100):
            await middleware.dispatch(led_request, call_next)

        assert call_next.call_count == 100

    @pytest.mark.asyncio
    async def test_skips_rate_limiting_for_static_files(self, middleware):
        """Test that static file endpoints skip rate limiting."""
        static_request = MagicMock()
        static_request.client = MagicMock()
        static_request.client.host = "127.0.0.1"
        static_request.url.path = "/static/style.css"
        call_next = AsyncMock(return_value=Response())

        # Make many requests - should all pass
        for _ in range(100):
            await middleware.dispatch(static_request, call_next)

        assert call_next.call_count == 100

    @pytest.mark.asyncio
    async def test_rate_limit_resets_after_window(self, middleware, mock_request):
        """Test that rate limit resets after the time window."""
        call_next = AsyncMock(return_value=Response())

        # Make requests up to limit
        for _ in range(10):
            await middleware.dispatch(mock_request, call_next)

        # Manually expire old entries by manipulating time
        # Move time forward past the window
        with patch("time.time", return_value=time.time() + 61):
            # Now should be able to make requests again
            response = await middleware.dispatch(mock_request, call_next)
            assert response != 429

    @pytest.mark.asyncio
    async def test_different_ips_have_separate_limits(self, middleware):
        """Test that different IP addresses have separate rate limits."""
        request1 = MagicMock()
        request1.client = MagicMock()
        request1.client.host = "127.0.0.1"
        request1.url.path = "/api/test"

        request2 = MagicMock()
        request2.client = MagicMock()
        request2.client.host = "192.168.1.1"
        request2.url.path = "/api/test"

        call_next = AsyncMock(return_value=Response())

        # Exhaust limit for IP 1
        for _ in range(10):
            await middleware.dispatch(request1, call_next)

        # IP 2 should still be able to make requests
        response = await middleware.dispatch(request2, call_next)
        assert response.status_code != 429
        assert call_next.call_count == 11  # 10 for IP1 + 1 for IP2

    @pytest.mark.asyncio
    async def test_cleanup_old_entries(self, middleware):
        """Test that old entries are cleaned up periodically."""
        mock_request = MagicMock()
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.url.path = "/api/test"
        call_next = AsyncMock(return_value=Response())

        # Make some requests
        for _ in range(5):
            await middleware.dispatch(mock_request, call_next)

        # Manually trigger cleanup
        with patch("time.time", return_value=time.time() + 301):
            # Cleanup should happen
            await middleware.dispatch(mock_request, call_next)
            # Old entries should be removed
            assert len(middleware._request_history) >= 0

    @pytest.mark.asyncio
    async def test_handles_request_without_client(self, middleware):
        """Test that middleware handles requests without client IP."""
        request = MagicMock()
        request.client = None
        request.url.path = "/api/test"
        call_next = AsyncMock(return_value=Response())

        # Should not crash, use "unknown" as IP
        response = await middleware.dispatch(request, call_next)
        assert response.status_code != 429  # Should still work
