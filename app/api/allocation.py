"""Allocation target management API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.infrastructure.dependencies import (
    get_allocation_repository,
    get_portfolio_repository,
    get_position_repository,
)
from app.domain.repositories import (
    AllocationRepository,
    PortfolioRepository,
    PositionRepository,
)
from app.application.services.portfolio_service import PortfolioService

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
async def get_allocation_targets(
    allocation_repo: AllocationRepository = Depends(get_allocation_repository),
):
    """Get all allocation targets (geography and industry)."""
    targets = await allocation_repo.get_all()

    geography = {}
    industry = {}

    for key, value in targets.items():
        if key.startswith("geography:"):
            name = key.split(":", 1)[1]
            geography[name] = value
        elif key.startswith("industry:"):
            name = key.split(":", 1)[1]
            industry[name] = value

    return {
        "geography": geography,
        "industry": industry,
    }


@router.put("/targets/geography")
async def update_geography_targets(
    targets: GeographyTargets,
    allocation_repo: AllocationRepository = Depends(get_allocation_repository),
):
    """
    Update geography allocation weights.

    Accepts dynamic geography names with weight values (-1 to +1).
    Weight scale:
    - -1 = Avoid/underweight this region
    -  0 = Neutral (default)
    - +1 = Prioritize/overweight this region
    """
    from app.domain.repositories import AllocationTarget

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
        target = AllocationTarget(
            type="geography",
            name=name,
            target_pct=weight,
        )
        await allocation_repo.upsert(target)

    # Fetch and return current weights
    geo_targets = await allocation_repo.get_by_type("geography")
    result = {t.name: t.target_pct for t in geo_targets}

    return {
        "weights": result,
        "count": len(result),
    }


@router.put("/targets/industry")
async def update_industry_targets(
    targets: IndustryTargets,
    allocation_repo: AllocationRepository = Depends(get_allocation_repository),
):
    """
    Update industry allocation weights.

    Accepts dynamic industry names with weight values (-1 to +1).
    Weight scale:
    - -1 = Avoid/underweight this industry
    -  0 = Neutral (default)
    - +1 = Prioritize/overweight this industry
    """
    from app.domain.repositories import AllocationTarget

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
        target = AllocationTarget(
            type="industry",
            name=name,
            target_pct=weight,
        )
        await allocation_repo.upsert(target)

    # Fetch and return current weights
    industry_targets = await allocation_repo.get_by_type("industry")
    result = {t.name: t.target_pct for t in industry_targets}

    return {
        "weights": result,
        "count": len(result),
    }


@router.get("/current")
async def get_current_allocation(
    portfolio_repo: PortfolioRepository = Depends(get_portfolio_repository),
    position_repo: PositionRepository = Depends(get_position_repository),
    allocation_repo: AllocationRepository = Depends(get_allocation_repository),
):
    """Get current allocation vs targets for both geography and industry."""
    portfolio_service = PortfolioService(
        portfolio_repo,
        position_repo,
        allocation_repo,
    )
    summary = await portfolio_service.get_portfolio_summary()

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
async def get_allocation_deviations(
    portfolio_repo: PortfolioRepository = Depends(get_portfolio_repository),
    position_repo: PositionRepository = Depends(get_position_repository),
    allocation_repo: AllocationRepository = Depends(get_allocation_repository),
):
    """
    Get allocation deviation scores for rebalancing decisions.

    Negative deviation = underweight (needs buying)
    Positive deviation = overweight
    """
    portfolio_service = PortfolioService(
        portfolio_repo,
        position_repo,
        allocation_repo,
    )
    summary = await portfolio_service.get_portfolio_summary()

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
