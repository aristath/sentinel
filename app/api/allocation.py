"""Allocation target management API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.repositories import (
    AllocationRepository,
    PortfolioRepository,
    PositionRepository,
)
from app.domain.models import AllocationTarget
from app.application.services.portfolio_service import PortfolioService

router = APIRouter()


class GeographyTargets(BaseModel):
    """Dynamic geography allocation weights."""
    targets: dict[str, float]


class IndustryTargets(BaseModel):
    """Dynamic industry allocation weights."""
    targets: dict[str, float]


@router.get("/targets")
async def get_allocation_targets():
    """Get all allocation targets (geography and industry)."""
    allocation_repo = AllocationRepository()
    targets = await allocation_repo.get_all()

    geography = {}
    industry = {}

    for target in targets:
        if target.category == "geography":
            geography[target.name] = target.target_pct
        elif target.category == "industry":
            industry[target.name] = target.target_pct

    return {
        "geography": geography,
        "industry": industry,
    }


@router.put("/targets/geography")
async def update_geography_targets(targets: GeographyTargets):
    """Update geography allocation weights."""
    allocation_repo = AllocationRepository()
    updates = targets.targets

    if not updates:
        raise HTTPException(status_code=400, detail="No weights provided")

    for name, weight in updates.items():
        if weight < -1 or weight > 1:
            raise HTTPException(
                status_code=400,
                detail=f"Weight for {name} must be between -1 and 1"
            )

    for name, weight in updates.items():
        target = AllocationTarget(
            category="geography",
            name=name,
            target_pct=weight,
        )
        await allocation_repo.upsert(target)

    geo_targets = await allocation_repo.get_by_type("geography")
    result = {t.name: t.target_pct for t in geo_targets}

    return {
        "weights": result,
        "count": len(result),
    }


@router.put("/targets/industry")
async def update_industry_targets(targets: IndustryTargets):
    """Update industry allocation weights."""
    allocation_repo = AllocationRepository()
    updates = targets.targets

    if not updates:
        raise HTTPException(status_code=400, detail="No weights provided")

    for name, weight in updates.items():
        if weight < -1 or weight > 1:
            raise HTTPException(
                status_code=400,
                detail=f"Weight for {name} must be between -1 and 1"
            )

    for name, weight in updates.items():
        target = AllocationTarget(
            category="industry",
            name=name,
            target_pct=weight,
        )
        await allocation_repo.upsert(target)

    industry_targets = await allocation_repo.get_by_type("industry")
    result = {t.name: t.target_pct for t in industry_targets}

    return {
        "weights": result,
        "count": len(result),
    }


@router.get("/current")
async def get_current_allocation():
    """Get current allocation vs targets for both geography and industry."""
    portfolio_repo = PortfolioRepository()
    position_repo = PositionRepository()
    allocation_repo = AllocationRepository()

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
async def get_allocation_deviations():
    """Get allocation deviation scores for rebalancing decisions."""
    portfolio_repo = PortfolioRepository()
    position_repo = PositionRepository()
    allocation_repo = AllocationRepository()

    portfolio_service = PortfolioService(
        portfolio_repo,
        position_repo,
        allocation_repo,
    )
    summary = await portfolio_service.get_portfolio_summary()

    geo_deviations = {
        a.name: {
            "deviation": a.deviation,
            "need": max(0, -a.deviation),
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
