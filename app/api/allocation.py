"""Allocation target management API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import aiosqlite
from app.database import get_db

router = APIRouter()


class AllocationTarget(BaseModel):
    """Single allocation target."""
    name: str
    target_pct: float  # Now stores weight: -1.0 to +1.0


class GeographyTargets(BaseModel):
    """
    Dynamic geography allocation weights.

    Accepts any geography names as keys with weight values (-1 to +1).
    Example: {"EU": 0.5, "ASIA": -0.5, "US": 0.0}

    Weight scale:
    - -1 = Avoid/underweight this region
    -  0 = Neutral (default)
    - +1 = Prioritize/overweight this region
    """
    targets: dict[str, float]


class IndustryTargets(BaseModel):
    """
    Dynamic industry allocation weights.

    Accepts any industry names as keys with weight values (-1 to +1).
    Example: {"Technology": 0.8, "Defense": 0.2, "Industrial": -0.3}

    Weight scale:
    - -1 = Avoid/underweight this industry
    -  0 = Neutral (default)
    - +1 = Prioritize/overweight this industry
    """
    targets: dict[str, float]


@router.get("/targets")
async def get_allocation_targets(db: aiosqlite.Connection = Depends(get_db)):
    """Get all allocation targets (geography and industry)."""
    cursor = await db.execute(
        "SELECT type, name, target_pct FROM allocation_targets ORDER BY type, name"
    )
    rows = await cursor.fetchall()

    geography = {}
    industry = {}

    for row in rows:
        if row["type"] == "geography":
            geography[row["name"]] = row["target_pct"]
        elif row["type"] == "industry":
            industry[row["name"]] = row["target_pct"]

    return {
        "geography": geography,
        "industry": industry,
    }


@router.put("/targets/geography")
async def update_geography_targets(
    targets: GeographyTargets,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Update geography allocation weights.

    Accepts dynamic geography names with weight values (-1 to +1).
    Weight scale:
    - -1 = Avoid/underweight this region
    -  0 = Neutral (default)
    - +1 = Prioritize/overweight this region
    """
    updates = targets.targets

    if not updates:
        raise HTTPException(status_code=400, detail="No weights provided")

    # Validate weights are between -1 and 1
    for name, weight in updates.items():
        if weight < -1 or weight > 1:
            raise HTTPException(
                status_code=400,
                detail=f"Weight for {name} must be between -1 and 1"
            )

    # Update/insert all weights (including 0 = neutral)
    for name, weight in updates.items():
        await db.execute(
            """
            INSERT OR REPLACE INTO allocation_targets (type, name, target_pct)
            VALUES ('geography', ?, ?)
            """,
            (name, weight)
        )

    await db.commit()

    # Fetch and return current weights
    cursor = await db.execute(
        "SELECT name, target_pct FROM allocation_targets WHERE type = 'geography'"
    )
    rows = await cursor.fetchall()

    result = {row["name"]: row["target_pct"] for row in rows}

    return {
        "weights": result,
        "count": len(result),
    }


@router.put("/targets/industry")
async def update_industry_targets(
    targets: IndustryTargets,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Update industry allocation weights.

    Accepts dynamic industry names with weight values (-1 to +1).
    Weight scale:
    - -1 = Avoid/underweight this industry
    -  0 = Neutral (default)
    - +1 = Prioritize/overweight this industry
    """
    updates = targets.targets

    if not updates:
        raise HTTPException(status_code=400, detail="No weights provided")

    # Validate weights are between -1 and 1
    for name, weight in updates.items():
        if weight < -1 or weight > 1:
            raise HTTPException(
                status_code=400,
                detail=f"Weight for {name} must be between -1 and 1"
            )

    # Update/insert all weights (including 0 = neutral)
    for name, weight in updates.items():
        await db.execute(
            """
            INSERT OR REPLACE INTO allocation_targets (type, name, target_pct)
            VALUES ('industry', ?, ?)
            """,
            (name, weight)
        )

    await db.commit()

    # Fetch and return current weights
    cursor = await db.execute(
        "SELECT name, target_pct FROM allocation_targets WHERE type = 'industry'"
    )
    rows = await cursor.fetchall()

    result = {row["name"]: row["target_pct"] for row in rows}

    return {
        "weights": result,
        "count": len(result),
    }


@router.get("/current")
async def get_current_allocation(db: aiosqlite.Connection = Depends(get_db)):
    """Get current allocation vs targets for both geography and industry."""
    from app.services.allocator import get_portfolio_summary

    summary = await get_portfolio_summary(db)

    return {
        "total_value": summary.total_value,
        "cash_balance": summary.cash_balance,
        "geography": [
            {
                "name": a.name,
                "target_pct": a.target_pct,
                "current_pct": a.current_pct,
                "current_value": a.current_value,
                "deviation": a.deviation,
            }
            for a in summary.geographic_allocations
        ],
        "industry": [
            {
                "name": a.name,
                "target_pct": a.target_pct,
                "current_pct": a.current_pct,
                "current_value": a.current_value,
                "deviation": a.deviation,
            }
            for a in summary.industry_allocations
        ],
    }


@router.get("/deviations")
async def get_allocation_deviations(db: aiosqlite.Connection = Depends(get_db)):
    """
    Get allocation deviation scores for rebalancing decisions.

    Negative deviation = underweight (needs buying)
    Positive deviation = overweight
    """
    from app.services.allocator import get_portfolio_summary

    summary = await get_portfolio_summary(db)

    geo_deviations = {
        a.name: {
            "deviation": a.deviation,
            "need": max(0, -a.deviation),  # Positive value for underweight
            "status": "underweight" if a.deviation < -0.02 else (
                "overweight" if a.deviation > 0.02 else "balanced"
            ),
        }
        for a in summary.geographic_allocations
    }

    industry_deviations = {
        a.name: {
            "deviation": a.deviation,
            "need": max(0, -a.deviation),
            "status": "underweight" if a.deviation < -0.02 else (
                "overweight" if a.deviation > 0.02 else "balanced"
            ),
        }
        for a in summary.industry_allocations
    }

    return {
        "geography": geo_deviations,
        "industry": industry_deviations,
    }
