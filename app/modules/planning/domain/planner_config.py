"""Planning configuration domain models."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PlannerConfig:
    """A named planner configuration.

    Attributes:
        id: Unique identifier (UUID)
        name: Human-readable name/title (e.g., "Aggressive Growth Strategy")
        toml_config: TOML configuration string
        bucket_id: Associated bucket (None for templates)
        created_at: Creation timestamp (ISO format)
        updated_at: Last update timestamp (ISO format)
    """

    id: str
    name: str
    toml_config: str
    bucket_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class PlannerConfigHistory:
    """Historical version of a planner configuration (for backup/versioning).

    Attributes:
        id: Unique identifier for this history entry (UUID)
        planner_config_id: ID of the planner config this is a backup of
        name: Name at the time of save
        toml_config: TOML configuration at the time of save
        saved_at: Timestamp when this version was saved (ISO format)
    """

    id: str
    planner_config_id: str
    name: str
    toml_config: str
    saved_at: str
