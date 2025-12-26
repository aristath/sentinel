"""Portfolio application service.

Orchestrates portfolio operations using repositories and domain services.
"""

from app.domain.models import AllocationStatus, PortfolioSummary
from app.domain.repositories.protocols import IAllocationRepository, IPositionRepository
from app.domain.services.allocation_calculator import parse_industries
from app.repositories import PortfolioRepository


class PortfolioService:
    """Application service for portfolio operations."""

    def __init__(
        self,
        portfolio_repo: PortfolioRepository,
        position_repo: IPositionRepository,
        allocation_repo: IAllocationRepository,
    ):
        self._portfolio_repo = portfolio_repo
        self._position_repo = position_repo
        self._allocation_repo = allocation_repo

    def _calculate_position_value(self, pos: dict) -> float:
        """Calculate EUR value for a position."""
        eur_value = pos.get("market_value_eur") or 0
        if eur_value is None or eur_value == 0:
            price = pos.get("current_price") or pos.get("avg_price") or 0
            eur_value = pos.get("quantity", 0) * price
        return eur_value

    def _aggregate_position_values(
        self, positions: list[dict]
    ) -> tuple[dict[str, float], dict[str, float], float]:
        """Aggregate position values by geography and industry."""
        geo_values = {}
        industry_values = {}
        total_value = 0.0

        for pos in positions:
            eur_value = self._calculate_position_value(pos)
            total_value += eur_value

            geo = pos.get("geography")
            if geo:
                geo_values[geo] = geo_values.get(geo, 0) + eur_value

            industry_str = pos.get("industry")
            industries = parse_industries(industry_str) if industry_str else []
            if industries:
                split_value = eur_value / len(industries)
                for ind in industries:
                    industry_values[ind] = industry_values.get(ind, 0) + split_value

        return geo_values, industry_values, total_value

    def _build_geo_allocations(
        self, targets: dict, geo_values: dict[str, float], total_value: float
    ) -> list[AllocationStatus]:
        """Build geographic allocation status list."""
        all_geographies = set()
        for key in targets:
            if key.startswith("geography:"):
                all_geographies.add(key.split(":", 1)[1])
        all_geographies.update(geo_values.keys())

        geo_allocations = []
        for geo in sorted(all_geographies):
            weight = targets.get(f"geography:{geo}", 0)
            current_val = geo_values.get(geo, 0)
            current_pct = current_val / total_value if total_value > 0 else 0

            geo_allocations.append(
                AllocationStatus(
                    category="geography",
                    name=geo,
                    target_pct=weight,
                    current_pct=round(current_pct, 4),
                    current_value=round(current_val, 2),
                    deviation=round(current_pct - weight, 4),
                )
            )
        return geo_allocations

    def _build_industry_allocations(
        self, targets: dict, industry_values: dict[str, float], total_value: float
    ) -> list[AllocationStatus]:
        """Build industry allocation status list."""
        all_industries = set()
        for key in targets:
            if key.startswith("industry:"):
                all_industries.add(key.split(":", 1)[1])
        all_industries.update(industry_values.keys())

        industry_allocations = []
        for industry in sorted(all_industries):
            weight = targets.get(f"industry:{industry}", 0)
            current_val = industry_values.get(industry, 0)
            current_pct = current_val / total_value if total_value > 0 else 0

            industry_allocations.append(
                AllocationStatus(
                    category="industry",
                    name=industry,
                    target_pct=weight,
                    current_pct=round(current_pct, 4),
                    current_value=round(current_val, 2),
                    deviation=round(current_pct - weight, 4),
                )
            )
        return industry_allocations

    async def get_portfolio_summary(self) -> PortfolioSummary:
        """
        Calculate current portfolio allocation vs targets.

        Returns complete summary with geographic and industry breakdowns.
        """
        targets = await self._allocation_repo.get_all()
        positions = await self._position_repo.get_with_stock_info()

        geo_values, industry_values, total_value = self._aggregate_position_values(
            positions
        )

        cash_balance = await self._portfolio_repo.get_latest_cash_balance()

        geo_allocations = self._build_geo_allocations(targets, geo_values, total_value)
        industry_allocations = self._build_industry_allocations(
            targets, industry_values, total_value
        )

        return PortfolioSummary(
            total_value=round(total_value, 2),
            cash_balance=round(cash_balance, 2),
            geographic_allocations=geo_allocations,
            industry_allocations=industry_allocations,
        )
