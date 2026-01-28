"""Core types and protocols for the jobs system."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntEnum
from typing import Optional, Protocol, runtime_checkable


class MarketTiming(IntEnum):
    """When a job can execute relative to market hours."""

    ANY_TIME = 0
    AFTER_MARKET_CLOSE = 1
    DURING_MARKET_OPEN = 2
    ALL_MARKETS_CLOSED = 3


@runtime_checkable
class Job(Protocol):
    """Protocol defining the interface for all jobs."""

    def id(self) -> str:
        """Unique identifier for this job instance."""
        ...

    def type(self) -> str:
        """Job type (e.g., 'sync:portfolio')."""
        ...

    async def execute(self) -> None:
        """Execute the job's work."""
        ...

    def dependencies(self) -> list[str]:
        """List of job IDs that must complete before this job."""
        ...

    def timeout(self) -> timedelta:
        """Maximum time allowed for execution."""
        ...

    def market_timing(self) -> MarketTiming:
        """When this job can execute relative to market hours."""
        ...

    def subject(self) -> str:
        """Optional subject (e.g., symbol for per-security jobs)."""
        ...


@dataclass
class BaseJob(ABC):
    """Abstract base class for job implementations."""

    _id: str
    _job_type: str
    _dependencies: list[str] = field(default_factory=list)
    _timeout: timedelta = field(default_factory=lambda: timedelta(minutes=5))
    _market_timing: MarketTiming = MarketTiming.ANY_TIME
    _subject: str = ""

    def id(self) -> str:
        """Return job ID."""
        return self._id

    def type(self) -> str:
        """Return job type."""
        return self._job_type

    def dependencies(self) -> list[str]:
        """Return list of dependency job IDs."""
        return self._dependencies

    def timeout(self) -> timedelta:
        """Return execution timeout."""
        return self._timeout

    def market_timing(self) -> MarketTiming:
        """Return market timing constraint."""
        return self._market_timing

    def subject(self) -> str:
        """Return job subject (e.g., symbol)."""
        return self._subject

    @abstractmethod
    async def execute(self) -> None:
        """Execute the job. Must be implemented by subclasses."""
        raise NotImplementedError


@dataclass
class JobWrapper:
    """Wraps a job with execution metadata (kept for API compatibility)."""

    job: Job
    enqueued_at: datetime = field(default_factory=datetime.now)
