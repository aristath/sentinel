"""Unit tests for CircuitBreaker."""

import asyncio

import pytest

from app.infrastructure.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitState,
    get_circuit_breaker,
)


@pytest.mark.asyncio
async def test_circuit_breaker_closed_state_success():
    """Test circuit breaker in CLOSED state with successful calls."""
    breaker = CircuitBreaker(CircuitBreakerConfig(failure_threshold=3))

    async def successful_call():
        return "success"

    result = await breaker.call(successful_call)

    assert result == "success"
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_threshold():
    """Test circuit breaker opens after failure threshold."""
    breaker = CircuitBreaker(CircuitBreakerConfig(failure_threshold=3))

    async def failing_call():
        raise Exception("Service down")

    # First 3 failures should open the circuit
    for i in range(3):
        with pytest.raises(Exception):
            await breaker.call(failing_call)

    assert breaker.state == CircuitState.OPEN
    assert breaker.failure_count == 3


@pytest.mark.asyncio
async def test_circuit_breaker_blocks_calls_when_open():
    """Test circuit breaker blocks calls when OPEN."""
    breaker = CircuitBreaker(CircuitBreakerConfig(failure_threshold=2))

    async def failing_call():
        raise Exception("Service down")

    # Open the circuit
    for i in range(2):
        with pytest.raises(Exception):
            await breaker.call(failing_call)

    assert breaker.state == CircuitState.OPEN

    # Should now reject with CircuitBreakerError
    with pytest.raises(CircuitBreakerError, match="Circuit breaker is OPEN"):
        await breaker.call(failing_call)


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_transition():
    """Test circuit breaker transitions to HALF_OPEN after timeout."""
    breaker = CircuitBreaker(
        CircuitBreakerConfig(failure_threshold=2, timeout=0.1, success_threshold=1)
    )

    async def failing_call():
        raise Exception("Service down")

    # Open the circuit
    for i in range(2):
        with pytest.raises(Exception):
            await breaker.call(failing_call)

    assert breaker.state == CircuitState.OPEN

    # Wait for timeout
    await asyncio.sleep(0.15)

    # Next call should transition to HALF_OPEN then CLOSED after success
    async def successful_call():
        return "success"

    result = await breaker.call(successful_call)

    assert result == "success"
    assert breaker.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_allows_one_request():
    """Test HALF_OPEN state only allows one request at a time."""
    breaker = CircuitBreaker(CircuitBreakerConfig(failure_threshold=2, timeout=0.1))

    async def failing_call():
        raise Exception("Service down")

    # Open the circuit
    for i in range(2):
        with pytest.raises(Exception):
            await breaker.call(failing_call)

    await asyncio.sleep(0.15)

    # Create a slow call to keep HALF_OPEN state
    async def slow_call():
        await asyncio.sleep(0.2)
        return "success"

    # Start first call (will be in progress)
    task1 = asyncio.create_task(breaker.call(slow_call))

    # Give it time to start
    await asyncio.sleep(0.05)

    # Second call should be rejected
    with pytest.raises(CircuitBreakerError, match="HALF_OPEN with request in progress"):
        await breaker.call(slow_call)

    # Wait for first call to finish
    result = await task1
    assert result == "success"


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_failure_reopens():
    """Test HALF_OPEN state reopens on failure."""
    breaker = CircuitBreaker(CircuitBreakerConfig(failure_threshold=2, timeout=0.1))

    async def failing_call():
        raise Exception("Service down")

    # Open the circuit
    for i in range(2):
        with pytest.raises(Exception):
            await breaker.call(failing_call)

    await asyncio.sleep(0.15)

    # Attempt recovery call that fails
    with pytest.raises(Exception):
        await breaker.call(failing_call)

    # Should be back to OPEN
    assert breaker.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_circuit_breaker_reset():
    """Test circuit breaker manual reset."""
    breaker = CircuitBreaker(CircuitBreakerConfig(failure_threshold=2))

    async def failing_call():
        raise Exception("Service down")

    # Open the circuit
    for i in range(2):
        with pytest.raises(Exception):
            await breaker.call(failing_call)

    assert breaker.state == CircuitState.OPEN

    # Reset
    await breaker.reset()

    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0


@pytest.mark.asyncio
async def test_circuit_breaker_registry():
    """Test circuit breaker registry functionality."""
    breaker1 = get_circuit_breaker("test_service_1")
    breaker2 = get_circuit_breaker("test_service_1")

    # Same name should return same instance
    assert breaker1 is breaker2

    breaker3 = get_circuit_breaker("test_service_2")

    # Different name should return different instance
    assert breaker1 is not breaker3


@pytest.mark.asyncio
async def test_circuit_breaker_success_resets_failure_count():
    """Test successful calls reset failure count in CLOSED state."""
    breaker = CircuitBreaker(CircuitBreakerConfig(failure_threshold=3))

    async def failing_call():
        raise Exception("Service down")

    async def successful_call():
        return "success"

    # 2 failures
    for i in range(2):
        with pytest.raises(Exception):
            await breaker.call(failing_call)

    assert breaker.failure_count == 2

    # Success should reset count
    await breaker.call(successful_call)

    assert breaker.failure_count == 0
    assert breaker.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_success_count():
    """Test HALF_OPEN requires configured number of successes to close."""
    breaker = CircuitBreaker(
        CircuitBreakerConfig(failure_threshold=2, timeout=0.1, success_threshold=1)
    )

    async def failing_call():
        raise Exception("Service down")

    async def successful_call():
        return "success"

    # Open the circuit
    for i in range(2):
        with pytest.raises(Exception):
            await breaker.call(failing_call)

    await asyncio.sleep(0.15)

    # Single success with success_threshold=1 should transition to CLOSED
    result = await breaker.call(successful_call)
    assert result == "success"
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0
