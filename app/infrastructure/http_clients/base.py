"""Base HTTP client with retry and circuit breaker support."""

import logging
from typing import Any, Dict, Optional

import httpx

from app.infrastructure.grpc_helpers.circuit_breaker import get_circuit_breaker
from app.infrastructure.grpc_helpers.retry import get_retry_handler

logger = logging.getLogger(__name__)


class BaseHTTPClient:
    """
    Base HTTP client with resilience features.

    Provides:
    - Automatic retries with exponential backoff
    - Circuit breaker pattern for fault tolerance
    - Request/response logging
    - Timeout management
    """

    def __init__(
        self,
        base_url: str,
        service_name: str,
        timeout: float = 30.0,
    ):
        """
        Initialize HTTP client.

        Args:
            base_url: Base URL for the service (e.g., "http://localhost:8001")
            service_name: Name of the service (for circuit breaker/retry tracking)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.service_name = service_name
        self.timeout = timeout

        # Get circuit breaker and retry handler for this service
        self.circuit_breaker = get_circuit_breaker(service_name)
        self.retry_handler = get_retry_handler(service_name)

        # Create HTTP client
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
        )

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Make an HTTP request with retry and circuit breaker.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path (relative to base_url)
            **kwargs: Additional arguments for httpx.request

        Returns:
            HTTP response

        Raises:
            httpx.HTTPError: On HTTP errors after retries exhausted
        """

        async def _do_request():
            logger.debug(f"{method} {self.base_url}{path}")
            response = await self.client.request(method, path, **kwargs)
            response.raise_for_status()
            return response

        # Execute with circuit breaker and retry
        return await self.circuit_breaker.call(
            lambda: self.retry_handler.call(_do_request)
        )

    async def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Make a GET request.

        Args:
            path: Request path
            params: Query parameters
            **kwargs: Additional arguments

        Returns:
            HTTP response
        """
        return await self._request("GET", path, params=params, **kwargs)

    async def post(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Make a POST request.

        Args:
            path: Request path
            json: JSON body
            **kwargs: Additional arguments

        Returns:
            HTTP response
        """
        return await self._request("POST", path, json=json, **kwargs)

    async def put(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Make a PUT request.

        Args:
            path: Request path
            json: JSON body
            **kwargs: Additional arguments

        Returns:
            HTTP response
        """
        return await self._request("PUT", path, json=json, **kwargs)

    async def delete(
        self,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Make a DELETE request.

        Args:
            path: Request path
            **kwargs: Additional arguments

        Returns:
            HTTP response
        """
        return await self._request("DELETE", path, **kwargs)
