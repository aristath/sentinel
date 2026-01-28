"""Job registry for factories and retry configuration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable

from sentinel.jobs.types import Job


@dataclass
class RetryConfig:
    """Configuration for job retry behavior."""

    max_retries: int = 3
    initial_interval: timedelta = timedelta(seconds=30)
    max_cooloff: timedelta = timedelta(minutes=5)

    @staticmethod
    def default() -> "RetryConfig":
        """Default retry configuration."""
        return RetryConfig()

    @staticmethod
    def for_sync() -> "RetryConfig":
        """Retry configuration for sync jobs (more retries)."""
        return RetryConfig(
            max_retries=5,
            initial_interval=timedelta(seconds=30),
        )

    @staticmethod
    def for_analytics() -> "RetryConfig":
        """Retry configuration for analytics jobs (longer cooloff)."""
        return RetryConfig(
            max_retries=3,
            initial_interval=timedelta(minutes=1),
            max_cooloff=timedelta(minutes=30),
        )

    @staticmethod
    def infinite() -> "RetryConfig":
        """Infinite retry configuration."""
        return RetryConfig(
            max_retries=-1,
            initial_interval=timedelta(0),
            max_cooloff=timedelta(minutes=5),
        )


JobFactory = Callable[[dict[str, Any]], Job]


class Registry:
    """Registry of job types and their factories."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._factories: dict[str, JobFactory] = {}
        self._configs: dict[str, RetryConfig] = {}

    async def register(
        self,
        job_type: str,
        factory: JobFactory,
        config: RetryConfig = None,
    ) -> None:
        """Register a job type with its factory and retry config."""
        async with self._lock:
            self._factories[job_type] = factory
            self._configs[job_type] = config or RetryConfig.default()

    async def create(self, job_type: str, params: dict[str, Any] = None) -> Job:
        """Create a job instance from its type and parameters."""
        async with self._lock:
            factory = self._factories.get(job_type)
            if not factory:
                raise ValueError(f"Unknown job type: {job_type}")
            return factory(params or {})

    def get_retry_config(self, job_type: str) -> RetryConfig:
        """Get retry configuration for a job type."""
        return self._configs.get(job_type, RetryConfig.default())

    def is_registered(self, job_type: str) -> bool:
        """Check if a job type is registered."""
        return job_type in self._factories

    def list_types(self) -> list[str]:
        """List all registered job types."""
        return list(self._factories.keys())
