"""Repository protocols (interfaces) for dependency injection.

These protocols define the contracts that repositories must implement.
Using protocols allows for better testability and dependency injection
without requiring abstract base classes.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, Set

from app.domain.models import Position, Security, Trade

# AllocationTarget moved to modules/allocation/domain/models.py
# Backward compatibility import (temporary - will be removed in Phase 5)
from app.modules.allocation.domain.models import AllocationTarget


class ISecurityRepository(Protocol):
    """Protocol for security repository operations (stocks, ETFs, ETCs, mutual funds)."""

    async def get_by_symbol(self, symbol: str) -> Optional[Security]:
        """Get security by symbol."""
        ...

    async def get_by_isin(self, isin: str) -> Optional[Security]:
        """Get security by ISIN."""
        ...

    async def get_by_identifier(self, identifier: str) -> Optional[Security]:
        """Get security by symbol or ISIN."""
        ...

    async def get_all_active(self) -> List[Security]:
        """Get all active securities."""
        ...

    async def get_all(self) -> List[Security]:
        """Get all securities (active and inactive)."""
        ...

    async def create(self, security: Security) -> None:
        """Create a new security."""
        ...

    async def update(self, symbol: str, **updates: Any) -> None:
        """Update an existing security by symbol with field updates."""
        ...

    async def delete(self, symbol: str) -> None:
        """Delete a security."""
        ...

    async def get_with_scores(self) -> List[dict]:
        """Get all active securities with their scores."""
        ...


# Backward compatibility alias
ISecurityRepository = ISecurityRepository


class IPositionRepository(Protocol):
    """Protocol for position repository operations."""

    async def get_by_symbol(self, symbol: str) -> Optional[Position]:
        """Get position by symbol."""
        ...

    async def get_all(self) -> List[Position]:
        """Get all positions."""
        ...

    async def upsert(self, position: Position) -> None:
        """Insert or update a position."""
        ...

    async def update_last_sold_at(self, symbol: str) -> None:
        """Update last_sold_at timestamp for a position."""
        ...

    async def get_count(self) -> int:
        """Get count of positions in database."""
        ...

    async def get_total_value(self) -> float:
        """Get total portfolio value."""
        ...

    async def get_with_security_info(self) -> List[Dict]:
        """Get positions with security information."""
        ...


class ITradeRepository(Protocol):
    """Protocol for trade repository operations."""

    async def create(self, trade: Trade) -> None:
        """Create a new trade record."""
        ...

    async def get_by_order_id(self, order_id: str) -> Optional[Trade]:
        """Get trade by order ID."""
        ...

    async def exists(self, order_id: str) -> bool:
        """Check if trade with order_id exists."""
        ...

    async def get_first_buy_date(self, symbol: str) -> Optional[str]:
        """Get first buy date for a symbol."""
        ...

    async def get_last_buy_date(self, symbol: str) -> Optional[str]:
        """Get the most recent buy date for a symbol (when current position was last established)."""
        ...

    async def get_last_sell_date(self, symbol: str) -> Optional[str]:
        """Get last sell date for a symbol."""
        ...

    async def get_last_transaction_date(self, symbol: str) -> Optional[str]:
        """Get the date of the most recent transaction (BUY or SELL) for a symbol."""
        ...

    async def get_recent_trades(self, symbol: str, days: int = 30) -> List[Trade]:
        """Get recent trades for a symbol."""
        ...

    async def get_history(self, limit: int = 50) -> List[Trade]:
        """Get trade history."""
        ...

    async def get_recently_bought_symbols(self, days: int = 30) -> Set[str]:
        """Get symbols that were bought recently."""
        ...

    async def has_recent_sell_order(self, symbol: str, hours: int = 2) -> bool:
        """Check if there was a recent sell order for a symbol."""
        ...

    async def get_last_trade_timestamp(self) -> Optional[datetime]:
        """Get timestamp of the most recent trade."""
        ...

    async def get_trade_count_today(self) -> int:
        """Count trades executed today."""
        ...

    async def get_trade_count_this_week(self) -> int:
        """Count trades executed in the last 7 days."""
        ...


class ISettingsRepository(Protocol):
    """Protocol for settings repository operations."""

    async def get(self, key: str) -> Optional[str]:
        """Get a setting value by key."""
        ...

    async def set(
        self, key: str, value: str, description: Optional[str] = None
    ) -> None:
        """Set a setting value."""
        ...

    async def get_all(self) -> Dict[str, str]:
        """Get all settings as a dictionary."""
        ...

    async def get_float(self, key: str, default: float = 0.0) -> float:
        """Get a setting value as float."""
        ...

    async def get_int(self, key: str, default: int = 0) -> int:
        """Get a setting value as integer."""
        ...

    async def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a setting value as boolean."""
        ...

    async def set_float(self, key: str, value: float) -> None:
        """Set a setting value as float."""
        ...

    async def set_int(self, key: str, value: int) -> None:
        """Set a setting value as integer."""
        ...

    async def set_bool(self, key: str, value: bool) -> None:
        """Set a setting value as boolean."""
        ...

    async def delete(self, key: str) -> None:
        """Delete a setting."""
        ...


class IAllocationRepository(Protocol):
    """Protocol for allocation repository operations."""

    async def get_all(self) -> Dict[str, float]:
        """Get all allocation targets as dict with key 'type:name'."""
        ...

    async def get_by_type(self, target_type: str) -> List[AllocationTarget]:
        """Get allocation targets by type (geography or industry)."""
        ...

    async def get_country_group_targets(self) -> Dict[str, float]:
        """Get country group allocation targets (group name -> target_pct)."""
        ...

    async def get_industry_group_targets(self) -> Dict[str, float]:
        """Get industry group allocation targets (group name -> target_pct)."""
        ...

    async def upsert(self, target: AllocationTarget) -> None:
        """Insert or update an allocation target."""
        ...
