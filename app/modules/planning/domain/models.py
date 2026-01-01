"""Shared domain models for planning module.

This module contains domain models that are shared across multiple
planning components to avoid circular dependencies.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class ActionCandidate:
    """A candidate action for sequence generation.

    Represents a potential trade action with associated metadata
    for priority-based selection and sequencing.

    Attributes:
        side: Trade direction ("buy" or "sell")
        symbol: Security symbol
        name: Security name for display
        quantity: Number of units to trade
        price: Price per unit
        value_eur: Total value in EUR
        currency: Trading currency
        priority: Higher values indicate higher priority
        reason: Human-readable explanation for this action
        tags: Classification tags (e.g., ["windfall", "underweight_asia"])
    """

    side: str
    symbol: str
    name: str
    quantity: int
    price: float
    value_eur: float
    currency: str
    priority: float  # Higher = more important
    reason: str
    tags: List[str]  # e.g., ["windfall", "averaging_down", "underweight_asia"]
