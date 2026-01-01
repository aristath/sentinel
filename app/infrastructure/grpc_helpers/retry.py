"""Retry logic with exponential backoff for gRPC calls."""

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional, Type, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)

# Jitter constants to prevent thundering herd problem
JITTER_MIN_MULTIPLIER = 0.5  # Minimum jitter multiplier (50% of base delay)
JITTER_MAX_MULTIPLIER = 1.5  # Maximum jitter multiplier (150% of base delay)


@dataclass
class RetryConfig:
    """Retry configuration."""

    max_attempts: int = 3
    initial_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple[Type[Exception], ...] = (Exception,)


class RetryExhaustedError(Exception):
    """Raised when all retry attempts are exhausted."""

    pass


async def retry_with_backoff(
    func: Callable[[], Awaitable[T]], config: Optional[RetryConfig] = None
) -> T:
    """
    Retry an async function with exponential backoff.

    Args:
        func: Async function to retry
        config: Retry configuration

    Returns:
        Result of successful function call

    Raises:
        RetryExhaustedError: If all retry attempts fail
    """
    config = config or RetryConfig()
    last_exception: Optional[Exception] = None

    for attempt in range(config.max_attempts):
        try:
            result = await func()
            if attempt > 0:
                logger.info(f"Retry succeeded on attempt {attempt + 1}")
            return result

        except config.retryable_exceptions as e:
            last_exception = e

            if attempt + 1 >= config.max_attempts:
                logger.error(
                    f"All retry attempts exhausted ({config.max_attempts} attempts)"
                )
                break

            # Calculate delay with exponential backoff
            delay = min(
                config.initial_delay * (config.exponential_base**attempt),
                config.max_delay,
            )

            # Add jitter to prevent thundering herd
            if config.jitter:
                delay = delay * (JITTER_MIN_MULTIPLIER + random.random())

            logger.warning(
                f"Attempt {attempt + 1}/{config.max_attempts} failed: {e}. "
                f"Retrying in {delay:.2f}s..."
            )

            await asyncio.sleep(delay)

        except Exception as e:
            # Non-retryable exception
            logger.error(f"Non-retryable exception: {e}")
            raise

    raise RetryExhaustedError(
        f"Failed after {config.max_attempts} attempts"
    ) from last_exception


def with_retry(config: Optional[RetryConfig] = None):
    """
    Decorator to add retry logic to async functions.

    Example:
        @with_retry(RetryConfig(max_attempts=5))
        async def call_service():
            return await grpc_stub.SomeMethod(request)
    """

    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            return await retry_with_backoff(
                lambda: func(*args, **kwargs), config=config
            )

        return wrapper

    return decorator


@dataclass
class RetryStats:
    """Statistics for retry operations."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_retries: int = 0
    max_retries_exhausted: int = 0


class RetryWithStats:
    """Retry wrapper that collects statistics."""

    def __init__(self, config: Optional[RetryConfig] = None):
        """Initialize retry with stats tracking."""
        self.config = config or RetryConfig()
        self.stats = RetryStats()

    async def call(self, func: Callable[[], Awaitable[T]]) -> T:
        """Execute function with retry and collect stats."""
        self.stats.total_calls += 1
        last_exception: Optional[Exception] = None
        retry_count = 0

        for attempt in range(self.config.max_attempts):
            try:
                result = await func()

                if attempt > 0:
                    self.stats.total_retries += retry_count
                    logger.info(
                        f"Retry succeeded on attempt {attempt + 1} "
                        f"after {retry_count} retries"
                    )

                self.stats.successful_calls += 1
                return result

            except self.config.retryable_exceptions as e:
                last_exception = e
                retry_count += 1

                if attempt + 1 >= self.config.max_attempts:
                    logger.error(
                        f"All retry attempts exhausted ({self.config.max_attempts})"
                    )
                    break

                delay = min(
                    self.config.initial_delay * (self.config.exponential_base**attempt),
                    self.config.max_delay,
                )

                if self.config.jitter:
                    delay = delay * (0.5 + random.random())

                logger.warning(
                    f"Attempt {attempt + 1}/{self.config.max_attempts} failed: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )

                await asyncio.sleep(delay)

        self.stats.failed_calls += 1
        self.stats.max_retries_exhausted += 1
        self.stats.total_retries += retry_count

        raise RetryExhaustedError(
            f"Failed after {self.config.max_attempts} attempts"
        ) from last_exception

    def get_stats(self) -> RetryStats:
        """Get retry statistics."""
        return self.stats

    def reset_stats(self):
        """Reset statistics."""
        self.stats = RetryStats()


class RetryRegistry:
    """Registry for managing retry handlers with stats."""

    def __init__(self):
        """Initialize registry."""
        self._handlers: dict[str, RetryWithStats] = {}

    def get_or_create(
        self, name: str, config: Optional[RetryConfig] = None
    ) -> RetryWithStats:
        """Get or create a retry handler by name."""
        if name not in self._handlers:
            self._handlers[name] = RetryWithStats(config)
        return self._handlers[name]

    def get_all_stats(self) -> dict[str, RetryStats]:
        """Get statistics for all retry handlers."""
        return {name: handler.get_stats() for name, handler in self._handlers.items()}


# Global registry
_registry = RetryRegistry()


def get_retry_handler(
    name: str, config: Optional[RetryConfig] = None
) -> RetryWithStats:
    """Get or create a retry handler from global registry."""
    return _registry.get_or_create(name, config)


def get_all_retry_stats() -> dict[str, RetryStats]:
    """Get statistics for all retry handlers."""
    return _registry.get_all_stats()
