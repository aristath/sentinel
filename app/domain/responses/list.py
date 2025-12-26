"""Standard list result types.

Provides consistent return types for operations returning lists.
"""

from dataclasses import dataclass
from typing import Any, Dict, Generic, List, Optional, TypeVar

T = TypeVar("T")


@dataclass
class ListResult(Generic[T]):
    """Standard result for list operations.

    Use this for service methods that return lists of items,
    providing consistent metadata and pagination support.

    Attributes:
        items: List of result items
        total: Total count (may differ from len(items) if paginated)
        metadata: Additional context (pagination info, filters applied, etc.)

    Example:
        result = ListResult(
            items=[item1, item2, item3],
            total=100,
            metadata={"page": 1, "page_size": 10}
        )
    """

    items: List[T]
    total: int
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.total == 0 and self.items:
            self.total = len(self.items)
