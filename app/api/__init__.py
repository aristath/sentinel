# API routers
from app.api import (
    allocation,
    cash_flows,
    charts,
    multi_step_recommendations,
    optimizer,
    portfolio,
    recommendations,
    status,
    stocks,
    trades,
)

__all__ = [
    "portfolio",
    "stocks",
    "trades",
    "status",
    "allocation",
    "cash_flows",
    "charts",
    "recommendations",
    "multi_step_recommendations",
    "optimizer",
]
