"""Portfolio context builder for rebalancing operations.

Builds PortfolioContext objects for use in scoring and recommendation generation.
"""

import logging
from typing import Dict

from app.domain.repositories.protocols import (
    IAllocationRepository,
    IPositionRepository,
    IStockRepository,
)
from app.domain.scoring import PortfolioContext
from app.infrastructure.database.manager import DatabaseManager

logger = logging.getLogger(__name__)


async def build_portfolio_context(
    position_repo: IPositionRepository,
    stock_repo: IStockRepository,
    allocation_repo: IAllocationRepository,
    db_manager: DatabaseManager,
) -> PortfolioContext:
    """Build portfolio context for scoring.

    Args:
        position_repo: Repository for positions
        stock_repo: Repository for stocks
        allocation_repo: Repository for allocations
        db_manager: Database manager for accessing scores

    Returns:
        PortfolioContext with all portfolio metadata needed for scoring
    """
    positions = await position_repo.get_all()
    stocks = await stock_repo.get_all_active()
    allocations = await allocation_repo.get_all()
    total_value = await position_repo.get_total_value()

    # Build allocation weight maps
    geo_weights: Dict[str, float] = {}
    industry_weights: Dict[str, float] = {}
    for key, target_pct in allocations.items():
        parts = key.split(":", 1)
        if len(parts) == 2:
            alloc_type, name = parts
            if alloc_type == "geography":
                geo_weights[name] = target_pct
            elif alloc_type == "industry":
                industry_weights[name] = target_pct

    # Build stock metadata maps
    position_map = {p.symbol: p.market_value_eur or 0 for p in positions}
    stock_geographies = {s.symbol: s.geography for s in stocks}
    stock_industries = {s.symbol: s.industry for s in stocks if s.industry}
    stock_scores: Dict[str, float] = {}

    # Get existing scores
    score_rows = await db_manager.state.fetchall(
        "SELECT symbol, quality_score FROM scores"
    )
    for row in score_rows:
        if row["quality_score"]:
            stock_scores[row["symbol"]] = row["quality_score"]

    return PortfolioContext(
        geo_weights=geo_weights,
        industry_weights=industry_weights,
        positions=position_map,
        total_value=total_value if total_value > 0 else 1.0,
        stock_geographies=stock_geographies,
        stock_industries=stock_industries,
        stock_scores=stock_scores,
    )
