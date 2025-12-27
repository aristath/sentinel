"""Repository protocols (interfaces) for dependency injection.

These protocols define the contracts that repositories must implement.
Using protocols allows for better testability and dependency injection
without requiring abstract base classes.
"""

from typing import Dict, List, Optional, Protocol, Set

from app.domain.models import AllocationTarget, Position, Stock, Trade


class IStockRepository(Protocol):
    """Protocol for stock repository operations."""

    async def get_by_symbol(self, symbol: str) -> Optional[Stock]:
        """Get stock by symbol."""
        ...

    async def get_all_active(self) -> List[Stock]:
        """Get all active stocks."""
        ...

    async def get_all(self) -> List[Stock]:
        """Get all stocks (active and inactive)."""
        ...

    async def create(self, stock: Stock) -> None:
        """Create a new stock."""
        ...

    async def update(self, stock: Stock) -> None:
        """Update an existing stock."""
        ...

    async def delete(self, symbol: str) -> None:
        """Delete a stock."""
        ...

    async def get_with_scores(self) -> List[dict]:
        """Get all active stocks with their scores."""
        ...


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

    async def get_total_value(self) -> float:
        """Get total portfolio value."""
        ...

    async def get_with_stock_info(self) -> List[Dict]:
        """Get positions with stock information."""
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

    async def get_last_sell_date(self, symbol: str) -> Optional[str]:
        """Get last sell date for a symbol."""
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

    async def get_geography_targets(self) -> Dict[str, float]:
        """Get geography allocation targets."""
        ...

    async def get_industry_targets(self) -> Dict[str, float]:
        """Get industry allocation targets."""
        ...

    async def upsert(self, target: AllocationTarget) -> None:
        """Insert or update an allocation target."""
        ...

