"""Database infrastructure.

This module provides:
- DatabaseManager: Centralized database access
- QueryQueue: Serialized write operations
- Schemas: Database table definitions
"""

from app.core.database.manager import (
    Database,
    DatabaseManager,
    get_db_manager,
    init_databases,
    shutdown_databases,
)
from app.core.database.queue import (
    Priority,
    QueryQueue,
    enqueue,
    get_query_queue,
    init_query_queue,
    shutdown_query_queue,
)

__all__ = [
    # Manager
    "Database",
    "DatabaseManager",
    "get_db_manager",
    "init_databases",
    "shutdown_databases",
    # Queue
    "Priority",
    "QueryQueue",
    "get_query_queue",
    "init_query_queue",
    "shutdown_query_queue",
    "enqueue",
]
