"""Portfolio application service.

Orchestrates portfolio operations using repositories and domain services.
"""

from app.repositories import (
    PortfolioRepository,
    PositionRepository,
    AllocationRepository,
)
from app.domain.models import AllocationStatus, PortfolioSummary
from app.domain.services.allocation_calculator import parse_industries


class PortfolioService:
    """Application service for portfolio operations."""

    def __init__(
        self,
        portfolio_repo: PortfolioRepository,
        position_repo: PositionRepository,
        allocation_repo: AllocationRepository,
    ):
        self._portfolio_repo = portfolio_repo
        self._position_repo = position_repo
        self._allocation_repo = allocation_repo

    async def get_portfolio_summary(self) -> PortfolioSummary:
        """
        Calculate current portfolio allocation vs targets.

        Returns complete summary with geographic and industry breakdowns.
        """
        # Get allocation targets
        targets = await self._allocation_repo.get_all()

        # Get positions with stock info - use market_value_eur for EUR-converted values
        positions = await self._position_repo.get_with_stock_info()

        # Calculate totals by geography and industry using EUR values
        geo_values = {}
        industry_values = {}
        total_value = 0.0

        for pos in positions:
            # Use stored EUR value if available, otherwise fallback to calculation
            eur_value = pos.get("market_value_eur") or 0
            if eur_value is None or eur_value == 0:
                price = pos.get("current_price") or pos.get("avg_price") or 0
                eur_value = pos.get("quantity", 0) * price

            total_value += eur_value

            geo = pos.get("geography")
            industry_str = pos.get("industry")

            # Geographic allocation (simple - each stock has one geography)
            if geo:
                geo_values[geo] = geo_values.get(geo, 0) + eur_value

            # Industry allocation - proportional split for multi-industry stocks
            industries = parse_industries(industry_str)
            if industries:
                split_value = eur_value / len(industries)
                for ind in industries:
                    industry_values[ind] = industry_values.get(ind, 0) + split_value

        # Get cash balance from latest snapshot
        cash_balance = await self._portfolio_repo.get_latest_cash_balance()

        # Build dynamic geography list from targets + actual positions
        all_geographies = set()

        # Add geographies from targets
        for key in targets:
            if key.startswith("geography:"):
                all_geographies.add(key.split(":", 1)[1])

        # Add geographies from current holdings
        all_geographies.update(geo_values.keys())

        geo_allocations = []
        for geo in sorted(all_geographies):
            # target_pct now stores weight (-1 to +1), not percentage
            weight = targets.get(f"geography:{geo}", 0)
            current_val = geo_values.get(geo, 0)
            current_pct = current_val / total_value if total_value > 0 else 0

            geo_allocations.append(AllocationStatus(
                category="geography",
                name=geo,
                target_pct=weight,  # Now stores weight, not percentage
                current_pct=round(current_pct, 4),
                current_value=round(current_val, 2),
                deviation=round(current_pct - weight, 4),  # Deviation still computed for display
            ))

        # Build dynamic industry list from targets + actual positions
        all_industries = set()

        # Add industries from targets
        for key in targets:
            if key.startswith("industry:"):
                all_industries.add(key.split(":", 1)[1])

        # Add industries from current holdings
        all_industries.update(industry_values.keys())

        industry_allocations = []
        for industry in sorted(all_industries):
            # target_pct now stores weight (-1 to +1), not percentage
            weight = targets.get(f"industry:{industry}", 0)
            current_val = industry_values.get(industry, 0)
            current_pct = current_val / total_value if total_value > 0 else 0

            industry_allocations.append(AllocationStatus(
                category="industry",
                name=industry,
                target_pct=weight,  # Now stores weight, not percentage
                current_pct=round(current_pct, 4),
                current_value=round(current_val, 2),
                deviation=round(current_pct - weight, 4),  # Deviation still computed for display
            ))

        return PortfolioSummary(
            total_value=round(total_value, 2),
            cash_balance=round(cash_balance, 2),
            geographic_allocations=geo_allocations,
            industry_allocations=industry_allocations,
        )

