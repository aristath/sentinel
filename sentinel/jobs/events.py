"""Event types for the jobs system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class Event(Protocol):
    """Protocol for all events."""

    def type(self) -> str:
        """Return event type identifier."""
        ...


@dataclass
class PricesUpdatedEvent:
    """Emitted when price data has been synced."""

    symbol_count: int
    occurred_at: datetime = field(default_factory=datetime.now)

    def type(self) -> str:
        return "PRICES_UPDATED"


@dataclass
class PortfolioSyncedEvent:
    """Emitted when portfolio has been synced from broker."""

    position_count: int
    occurred_at: datetime = field(default_factory=datetime.now)

    def type(self) -> str:
        return "PORTFOLIO_SYNCED"


@dataclass
class ScoresCalculatedEvent:
    """Emitted when scores have been calculated."""

    symbol_count: int
    occurred_at: datetime = field(default_factory=datetime.now)

    def type(self) -> str:
        return "SCORES_CALCULATED"


@dataclass
class CorrelationUpdatedEvent:
    """Emitted when correlation matrices have been updated."""

    symbol_count: int
    occurred_at: datetime = field(default_factory=datetime.now)

    def type(self) -> str:
        return "CORRELATION_UPDATED"


@dataclass
class RegimeTrainedEvent:
    """Emitted when regime model has been trained."""

    symbol_count: int
    occurred_at: datetime = field(default_factory=datetime.now)

    def type(self) -> str:
        return "REGIME_TRAINED"


@dataclass
class MLRetrainedEvent:
    """Emitted when an ML model has been retrained."""

    symbol: str
    rmse: float
    samples: int
    occurred_at: datetime = field(default_factory=datetime.now)

    def type(self) -> str:
        return "ML_RETRAINED"


class EventPublisher(Protocol):
    """Protocol for publishing events."""

    async def publish(self, event: Event) -> None:
        """Publish an event."""
        ...
