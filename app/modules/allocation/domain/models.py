"""Allocation domain models."""

from dataclasses import dataclass


@dataclass
class AllocationTarget:
    """Target allocation for country_group or industry_group (not individual countries/industries)."""

    type: str  # 'country_group' or 'industry_group'
    name: str  # Group name (e.g., 'US', 'EU', 'Technology')
    target_pct: float  # Weight from -1.0 to 1.0
