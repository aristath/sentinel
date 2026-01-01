"""Unit tests for Retry logic."""

import asyncio

import pytest

from app.infrastructure.resilience.retry import (
    RetryConfig,
    RetryExhaustedError,
    RetryWithStats,
    get_retry_handler,
    retry_with_backoff,
    with_retry,
)


@pytest.mark.asyncio
async def test_retry_success_on_first_attempt():
    """Test successful call on first attempt doesn't retry."""
    call_count = 0

    async def successful_call():
        nonlocal call_count
        call_count += 1
        return "success"

    result = await retry_with_backoff(successful_call, RetryConfig(max_attempts=3))

    assert result == "success"
    assert call_count == 1


@pytest.mark.asyncio
async def test_retry_success_after_failures():
    """Test successful call after some failures."""
    call_count = 0

    async def flaky_call():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Temporary failure")
        return "success"

    result = await retry_with_backoff(flaky_call, RetryConfig(max_attempts=5))

    assert result == "success"
    assert call_count == 3


@pytest.mark.asyncio
async def test_retry_exhausted_after_max_attempts():
    """Test retry exhausted after max attempts."""
    call_count = 0

    async def always_failing():
        nonlocal call_count
        call_count += 1
        raise Exception("Always fails")

    with pytest.raises(RetryExhaustedError, match="Failed after 3 attempts"):
        await retry_with_backoff(always_failing, RetryConfig(max_attempts=3))

    assert call_count == 3


@pytest.mark.asyncio
async def test_retry_exponential_backoff():
    """Test exponential backoff delays."""
    call_times = []

    async def failing_call():
        call_times.append(asyncio.get_event_loop().time())
        raise Exception("Fail")

    config = RetryConfig(
        max_attempts=3,
        initial_delay=0.1,
        exponential_base=2.0,
        jitter=False,  # Disable jitter for predictable timing
    )

    with pytest.raises(RetryExhaustedError):
        await retry_with_backoff(failing_call, config)

    # Verify exponential backoff
    assert len(call_times) == 3

    # First retry should be after initial_delay (0.1s)
    # Second retry should be after initial_delay * base (0.2s)
    delay1 = call_times[1] - call_times[0]
    delay2 = call_times[2] - call_times[1]

    assert 0.08 < delay1 < 0.15  # ~0.1s with some tolerance
    assert 0.18 < delay2 < 0.25  # ~0.2s with some tolerance


@pytest.mark.asyncio
async def test_retry_with_jitter():
    """Test retry with jitter adds randomness."""
    call_times = []

    async def failing_call():
        call_times.append(asyncio.get_event_loop().time())
        raise Exception("Fail")

    config = RetryConfig(
        max_attempts=3, initial_delay=0.1, exponential_base=2.0, jitter=True
    )

    with pytest.raises(RetryExhaustedError):
        await retry_with_backoff(failing_call, config)

    assert len(call_times) == 3

    # With jitter, delays should vary (between 0.5x and 1.5x base delay)
    delay1 = call_times[1] - call_times[0]
    assert 0.05 < delay1 < 0.15


@pytest.mark.asyncio
async def test_retry_max_delay():
    """Test retry respects max delay."""
    call_times = []

    async def failing_call():
        call_times.append(asyncio.get_event_loop().time())
        raise Exception("Fail")

    config = RetryConfig(
        max_attempts=5,
        initial_delay=1.0,
        exponential_base=10.0,  # Would give huge delays
        max_delay=0.2,  # But cap at 0.2s
        jitter=False,
    )

    with pytest.raises(RetryExhaustedError):
        await retry_with_backoff(failing_call, config)

    # All delays should be capped at max_delay
    for i in range(1, len(call_times)):
        delay = call_times[i] - call_times[i - 1]
        assert delay <= 0.25  # max_delay + small tolerance


@pytest.mark.asyncio
async def test_retry_decorator():
    """Test with_retry decorator."""
    call_count = 0

    @with_retry(RetryConfig(max_attempts=3))
    async def flaky_function():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise Exception("Temporary failure")
        return "success"

    result = await flaky_function()

    assert result == "success"
    assert call_count == 2


@pytest.mark.asyncio
async def test_retry_only_retries_specified_exceptions():
    """Test retry only retries configured exceptions."""

    async def raises_value_error():
        raise ValueError("Should not retry")

    config = RetryConfig(max_attempts=3, retryable_exceptions=(IOError,))

    # ValueError is not in retryable_exceptions, should fail immediately
    with pytest.raises(ValueError, match="Should not retry"):
        await retry_with_backoff(raises_value_error, config)


@pytest.mark.asyncio
async def test_retry_with_stats():
    """Test RetryWithStats collects statistics."""
    retry_stats = RetryWithStats(RetryConfig(max_attempts=3))

    call_count = 0

    async def flaky_call():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise Exception("Temporary failure")
        return "success"

    result = await retry_stats.call(flaky_call)

    assert result == "success"
    assert retry_stats.stats.total_calls == 1
    assert retry_stats.stats.successful_calls == 1
    assert retry_stats.stats.total_retries == 1


@pytest.mark.asyncio
async def test_retry_with_stats_failure():
    """Test RetryWithStats tracks failures."""
    retry_stats = RetryWithStats(RetryConfig(max_attempts=2))

    async def always_failing():
        raise Exception("Always fails")

    with pytest.raises(RetryExhaustedError):
        await retry_stats.call(always_failing)

    assert retry_stats.stats.total_calls == 1
    assert retry_stats.stats.failed_calls == 1
    assert retry_stats.stats.max_retries_exhausted == 1


@pytest.mark.asyncio
async def test_retry_handler_registry():
    """Test retry handler registry."""
    handler1 = get_retry_handler("service_1")
    handler2 = get_retry_handler("service_1")

    # Same name should return same instance
    assert handler1 is handler2

    handler3 = get_retry_handler("service_2")

    # Different name should return different instance
    assert handler1 is not handler3


@pytest.mark.asyncio
async def test_retry_reset_stats():
    """Test resetting retry statistics."""
    retry_stats = RetryWithStats(RetryConfig(max_attempts=2))

    async def failing_call():
        raise Exception("Fail")

    with pytest.raises(RetryExhaustedError):
        await retry_stats.call(failing_call)

    assert retry_stats.stats.total_calls == 1

    retry_stats.reset_stats()

    assert retry_stats.stats.total_calls == 0
    assert retry_stats.stats.failed_calls == 0
