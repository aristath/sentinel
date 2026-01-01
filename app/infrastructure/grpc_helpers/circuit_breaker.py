"""Circuit breaker pattern implementation for gRPC clients."""

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Awaitable, Callable, Optional, Type, TypeVar

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failure threshold exceeded
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""

    failure_threshold: int = 5  # Number of failures before opening
    success_threshold: int = 2  # Number of successes to close from half-open
    timeout: float = 60.0  # Seconds to wait before trying half-open
    expected_exception: Type[Exception] = Exception  # Exception type to catch


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""

    pass


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading failures.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests rejected immediately
    - HALF_OPEN: Testing if service recovered, limited requests allowed

    Example:
        breaker = CircuitBreaker(failure_threshold=5, timeout=60)

        @breaker
        async def call_service():
            return await some_grpc_call()
    """

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        """Initialize circuit breaker."""
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self._lock = asyncio.Lock()
        self._half_open_call_in_progress = False

    @property
    def is_open(self) -> bool:
        """Check if circuit is open."""
        return self.state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed."""
        return self.state == CircuitState.CLOSED

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open."""
        return self.state == CircuitState.HALF_OPEN

    async def call(self, func: Callable[[], Awaitable[T]]) -> T:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Async function to execute

        Returns:
            Result of function call

        Raises:
            CircuitBreakerError: If circuit is open
        """
        # Check state and handle HALF_OPEN specially to prevent race conditions
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    self._half_open_call_in_progress = False
                else:
                    raise CircuitBreakerError("Circuit breaker is OPEN")

            # In HALF_OPEN state, only allow one request at a time
            if self.state == CircuitState.HALF_OPEN:
                if self._half_open_call_in_progress:
                    raise CircuitBreakerError(
                        "Circuit breaker is HALF_OPEN with request in progress"
                    )
                self._half_open_call_in_progress = True

        try:
            # Execute the function (lock released for performance)
            result = await func()

            # Record success
            async with self._lock:
                await self._on_success()
                if self.state != CircuitState.HALF_OPEN:
                    self._half_open_call_in_progress = False

            return result

        except self.config.expected_exception as e:
            # Record failure
            async with self._lock:
                await self._on_failure()
                self._half_open_call_in_progress = False

            raise e

    def __call__(self, func: Callable) -> Callable:
        """Decorator to wrap async functions with circuit breaker."""

        async def wrapper(*args, **kwargs):
            return await self.call(lambda: func(*args, **kwargs))

        return wrapper

    async def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0

        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.success_count = 0

    async def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            # Failed in half-open, go back to open
            self.state = CircuitState.OPEN
        elif self.failure_count >= self.config.failure_threshold:
            # Too many failures, open the circuit
            self.state = CircuitState.OPEN

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try half-open."""
        if self.last_failure_time is None:
            return True

        return (time.time() - self.last_failure_time) >= self.config.timeout

    async def reset(self):
        """Manually reset circuit breaker to closed state."""
        async with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""

    def __init__(self):
        """Initialize registry."""
        self._breakers: dict[str, CircuitBreaker] = {}

    def get_or_create(
        self, name: str, config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """Get or create a circuit breaker by name."""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(config)
        return self._breakers[name]

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name."""
        return self._breakers.get(name)

    def get_all_states(self) -> dict[str, str]:
        """Get current state of all circuit breakers."""
        return {name: breaker.state.value for name, breaker in self._breakers.items()}


# Global registry
_registry = CircuitBreakerRegistry()


def get_circuit_breaker(
    name: str, config: Optional[CircuitBreakerConfig] = None
) -> CircuitBreaker:
    """Get or create a circuit breaker from global registry."""
    return _registry.get_or_create(name, config)


def get_all_circuit_breaker_states() -> dict[str, str]:
    """Get states of all circuit breakers."""
    return _registry.get_all_states()
