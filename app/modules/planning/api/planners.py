"""Planner configuration API endpoints."""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.modules.planning.services.planner_config_service import PlannerConfigService
from app.modules.planning.services.planner_loader import get_planner_loader

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================


class CreatePlannerRequest(BaseModel):
    """Request to create a new planner configuration."""

    name: str = Field(..., description="Human-readable name")
    toml_config: str = Field(..., description="TOML configuration string")
    bucket_id: Optional[str] = Field(None, description="Associated bucket ID")


class UpdatePlannerRequest(BaseModel):
    """Request to update a planner configuration."""

    name: Optional[str] = Field(None, description="New name")
    toml_config: Optional[str] = Field(None, description="New TOML configuration")


class ValidateTomlRequest(BaseModel):
    """Request to validate TOML configuration."""

    toml: str = Field(..., description="TOML string to validate")


class PlannerConfigResponse(BaseModel):
    """Response model for a planner configuration."""

    id: str
    name: str
    toml_config: str
    bucket_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PlannerConfigHistoryResponse(BaseModel):
    """Response model for planner config history entry."""

    id: str
    planner_config_id: str
    name: str
    toml_config: str
    saved_at: str


class ValidationResponse(BaseModel):
    """Response model for TOML validation."""

    valid: bool
    error: Optional[str] = None


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/planners", response_model=List[PlannerConfigResponse])
async def list_planners():
    """List all planner configurations."""
    service = PlannerConfigService()
    configs = await service.get_all()
    return configs


@router.get("/planners/{config_id}", response_model=PlannerConfigResponse)
async def get_planner(config_id: str):
    """Get a specific planner configuration."""
    service = PlannerConfigService()
    config = await service.get_by_id(config_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Planner configuration {config_id} not found",
        )

    return config


@router.post(
    "/planners",
    response_model=PlannerConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_planner(request: CreatePlannerRequest):
    """Create a new planner configuration."""
    service = PlannerConfigService()

    result = await service.create(
        name=request.name, toml_config=request.toml_config, bucket_id=request.bucket_id
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"]
        )

    return result["config"]


@router.put("/planners/{config_id}", response_model=PlannerConfigResponse)
async def update_planner(config_id: str, request: UpdatePlannerRequest):
    """Update a planner configuration (creates backup automatically)."""
    service = PlannerConfigService()

    result = await service.update(
        config_id=config_id, name=request.name, toml_config=request.toml_config
    )

    if not result["success"]:
        if "not found" in result["error"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=result["error"]
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"]
        )

    return result["config"]


@router.delete("/planners/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_planner(config_id: str):
    """Delete a planner configuration."""
    service = PlannerConfigService()

    result = await service.delete(config_id)

    if not result["success"]:
        if "not found" in result["error"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=result["error"]
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"]
        )


@router.post("/planners/validate", response_model=ValidationResponse)
async def validate_toml(request: ValidateTomlRequest):
    """Validate TOML configuration without saving."""
    service = PlannerConfigService()

    validation = await service.validate_toml(request.toml)

    return {"valid": validation["valid"], "error": validation["error"]}


@router.get(
    "/planners/{config_id}/history", response_model=List[PlannerConfigHistoryResponse]
)
async def get_planner_history(config_id: str):
    """Get version history for a planner configuration."""
    service = PlannerConfigService()

    # Verify config exists
    config = await service.get_by_id(config_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Planner configuration {config_id} not found",
        )

    history = await service.get_history(config_id)
    return history


@router.post("/planners/{config_id}/apply")
async def apply_planner(config_id: str):
    """Apply/hot-reload a planner configuration for its bucket."""
    loader = get_planner_loader()

    result = await loader.apply_config(config_id)

    if not result["success"]:
        if "not found" in result["error"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=result["error"]
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"]
        )

    return {
        "message": f"Planner configuration applied successfully for bucket {result['bucket_id']}",
        "bucket_id": result["bucket_id"],
    }
