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
from app.repositories import GroupingRepository

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
    total_value = await position_repo.get_total_value()

    # Load group targets directly (already at group level)
    country_weights = await allocation_repo.get_country_group_targets()
    industry_weights = await allocation_repo.get_industry_group_targets()

    # Build group mappings (country -> group, industry -> group)
    grouping_repo = GroupingRepository()
    country_groups = await grouping_repo.get_country_groups()
    industry_groups = await grouping_repo.get_industry_groups()

    # Build reverse mappings: country -> group, industry -> group
    country_to_group: Dict[str, str] = {}
    for group_name, country_names in country_groups.items():
        for country_name in country_names:
            country_to_group[country_name] = group_name

    industry_to_group: Dict[str, str] = {}
    for group_name, industry_names in industry_groups.items():
        for industry_name in industry_names:
            industry_to_group[industry_name] = group_name

    # Build stock metadata maps
    position_map = {p.symbol: p.market_value_eur or 0 for p in positions}
    stock_countries = {s.symbol: s.country for s in stocks if s.country}
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
        country_weights=country_weights,
        industry_weights=industry_weights,
        positions=position_map,
        total_value=total_value if total_value > 0 else 1.0,
        stock_countries=stock_countries,
        stock_industries=stock_industries,
        stock_scores=stock_scores,
        country_to_group=country_to_group,
        industry_to_group=industry_to_group,
    )
