"""Pydantic models for request/response validation."""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Literal, Any
from datetime import datetime


class ServiceResponse(BaseModel):
    """Standard response format for all endpoints."""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SectorConstraint(BaseModel):
    """Sector constraint definition for portfolio optimization."""

    sector_mapper: Dict[str, str] = Field(
        ...,
        description="Maps symbol to sector name, e.g., {'AAPL': 'US', 'ASML': 'EU'}"
    )
    sector_lower: Dict[str, float] = Field(
        ...,
        description="Minimum allocation per sector, e.g., {'US': 0.20, 'EU': 0.40}"
    )
    sector_upper: Dict[str, float] = Field(
        ...,
        description="Maximum allocation per sector, e.g., {'US': 0.40, 'EU': 0.60}"
    )


class TimeSeriesData(BaseModel):
    """Time series data structure for returns or prices."""

    dates: List[str] = Field(..., description="ISO format dates, e.g., ['2025-01-01', '2025-01-02']")
    data: Dict[str, List[float]] = Field(
        ...,
        description="Symbol to values mapping, e.g., {'AAPL': [0.01, -0.02, ...], ...}"
    )


class MeanVarianceRequest(BaseModel):
    """Request model for Mean-Variance optimization."""

    expected_returns: Dict[str, float] = Field(
        ...,
        description="Expected annual returns per symbol (as decimal), e.g., {'AAPL': 0.12}"
    )
    covariance_matrix: List[List[float]] = Field(
        ...,
        description="Covariance matrix as nested list, must match symbols order"
    )
    symbols: List[str] = Field(..., description="Ordered list of symbols matching matrix")
    weight_bounds: List[List[float]] = Field(
        ...,
        description="Weight bounds per symbol [[min, max], ...], e.g., [[0.02, 0.10], [0.01, 0.08]]"
    )
    sector_constraints: Optional[List[SectorConstraint]] = Field(
        default=[],
        description="Optional sector constraints (0-2 constraints typically)"
    )
    strategy: Literal["efficient_return", "min_volatility", "efficient_risk", "max_sharpe"] = Field(
        ...,
        description="Optimization strategy to use"
    )
    target_return: Optional[float] = Field(
        default=None,
        description="Required for 'efficient_return' strategy, e.g., 0.11 for 11%"
    )
    target_volatility: Optional[float] = Field(
        default=None,
        description="Required for 'efficient_risk' strategy, e.g., 0.15 for 15%"
    )


class HRPRequest(BaseModel):
    """Request model for Hierarchical Risk Parity optimization."""

    returns: TimeSeriesData = Field(..., description="Daily returns time series")


class CovarianceRequest(BaseModel):
    """Request model for covariance matrix calculation."""

    prices: TimeSeriesData = Field(..., description="Daily prices time series")


class OptimizationResult(BaseModel):
    """Result structure for optimization endpoints."""

    weights: Dict[str, float] = Field(..., description="Optimized portfolio weights (as decimals)")
    strategy_used: str = Field(..., description="Strategy that succeeded")
    constraint_level: Optional[str] = Field(
        default=None,
        description="Constraint level used: 'full', 'relaxed', or 'none'"
    )
    attempts: Optional[int] = Field(default=None, description="Number of optimization attempts")
    achieved_return: Optional[float] = Field(default=None, description="Expected annual return achieved")
    achieved_volatility: Optional[float] = Field(default=None, description="Expected volatility achieved")
