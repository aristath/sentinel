"""Tests for jobs/registry.py - Job registry implementation."""

import pytest
from datetime import timedelta

from sentinel.jobs.types import BaseJob
from sentinel.jobs.registry import Registry, RetryConfig


class MockJob(BaseJob):
    """Test job implementation."""

    async def execute(self) -> None:
        pass


@pytest.fixture
def registry():
    """Create a fresh registry for each test."""
    return Registry()


def job_factory(params: dict) -> MockJob:
    """Factory function for test jobs."""
    return MockJob(
        _id=params.get('id', 'test:job'),
        _job_type='test',
    )


@pytest.mark.asyncio
async def test_register_stores_factory(registry):
    """Register should store the factory."""
    await registry.register('test', job_factory)
    assert registry.is_registered('test')


@pytest.mark.asyncio
async def test_register_stores_retry_config(registry):
    """Register should store retry config."""
    config = RetryConfig(max_retries=5)
    await registry.register('test', job_factory, config)

    stored = registry.get_retry_config('test')
    assert stored.max_retries == 5


@pytest.mark.asyncio
async def test_create_returns_job_from_factory(registry):
    """Create should return job from factory."""
    await registry.register('test', job_factory)

    job = await registry.create('test', {'id': 'custom:id'})
    assert job.id() == 'custom:id'


@pytest.mark.asyncio
async def test_create_raises_for_unknown_type(registry):
    """Create should raise for unknown job type."""
    with pytest.raises(ValueError, match="Unknown job type"):
        await registry.create('nonexistent')


@pytest.mark.asyncio
async def test_get_retry_config_returns_registered(registry):
    """get_retry_config should return registered config."""
    config = RetryConfig(max_retries=10, initial_interval=timedelta(seconds=60))
    await registry.register('test', job_factory, config)

    stored = registry.get_retry_config('test')
    assert stored.max_retries == 10
    assert stored.initial_interval == timedelta(seconds=60)


@pytest.mark.asyncio
async def test_get_retry_config_returns_default(registry):
    """get_retry_config should return default for unregistered types."""
    config = registry.get_retry_config('nonexistent')
    assert config.max_retries == 3  # default


@pytest.mark.asyncio
async def test_is_registered(registry):
    """is_registered should return correct status."""
    assert not registry.is_registered('test')

    await registry.register('test', job_factory)
    assert registry.is_registered('test')


@pytest.mark.asyncio
async def test_list_types(registry):
    """list_types should return all registered types."""
    await registry.register('type1', job_factory)
    await registry.register('type2', job_factory)
    await registry.register('type3', job_factory)

    types = registry.list_types()
    assert set(types) == {'type1', 'type2', 'type3'}


def test_retry_config_default():
    """RetryConfig.default should return sensible defaults."""
    config = RetryConfig.default()
    assert config.max_retries == 3
    assert config.initial_interval == timedelta(seconds=30)
    assert config.max_cooloff == timedelta(minutes=5)


def test_retry_config_for_sync():
    """RetryConfig.for_sync should have more retries."""
    config = RetryConfig.for_sync()
    assert config.max_retries == 5


def test_retry_config_for_analytics():
    """RetryConfig.for_analytics should have longer cooloff."""
    config = RetryConfig.for_analytics()
    assert config.max_cooloff == timedelta(minutes=30)


def test_retry_config_infinite():
    """RetryConfig.infinite should have unlimited retries."""
    config = RetryConfig.infinite()
    assert config.max_retries == -1
