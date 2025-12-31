"""Security-related domain events."""

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.events.base import DomainEvent
from app.domain.models import Security


@dataclass(frozen=True)
class SecurityAddedEvent(DomainEvent):
    """Event raised when a security is added to the universe.

    This event represents a business event: a new security (equity, ETF, ETC, mutual fund)
    has been added to the investment universe.
    """

    security: Security
    occurred_at: datetime = field(default_factory=datetime.now)

    @property
    def symbol(self) -> str:
        """Security symbol."""
        return self.security.symbol

    @property
    def name(self) -> str:
        """Security name."""
        return self.security.name

    @property
    def country(self) -> str | None:
        """Security country."""
        return self.security.country
