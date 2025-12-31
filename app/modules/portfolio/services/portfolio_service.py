"""Portfolio application service.

Orchestrates portfolio operations using repositories and domain services.
"""

from app.domain.models import AllocationStatus, PortfolioSummary
from app.domain.repositories.protocols import (
    IAllocationRepository,
    IPositionRepository,
    IStockRepository,
)
from app.domain.services.allocation_calculator import parse_industries
from app.modules.portfolio.database.portfolio_repository import PortfolioRepository


class PortfolioService:
    """Application service for portfolio operations."""

    def __init__(
        self,
        portfolio_repo: PortfolioRepository,
        position_repo: IPositionRepository,
        allocation_repo: IAllocationRepository,
        stock_repo: IStockRepository,
    ):
        self._portfolio_repo = portfolio_repo
        self._position_repo = position_repo
        self._allocation_repo = allocation_repo
        self._stock_repo = stock_repo

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
        """Aggregate position values by country and industry."""
        country_values: dict[str, float] = {}
        industry_values: dict[str, float] = {}
        total_value = 0.0

        for pos in positions:
            eur_value = self._calculate_position_value(pos)
            total_value += eur_value

            country = pos.get("country")
            if country:
                country_values[country] = country_values.get(country, 0) + eur_value

            industry_str = pos.get("industry")
            industries = parse_industries(industry_str) if industry_str else []
            if industries:
                split_value = eur_value / len(industries)
                for ind in industries:
                    industry_values[ind] = industry_values.get(ind, 0) + split_value

        return country_values, industry_values, total_value

    def _build_country_allocations(
        self,
        targets: dict,
        country_values: dict[str, float],
        total_value: float,
        all_stock_countries: set[str] | None = None,
    ) -> list[AllocationStatus]:
        """Build country allocation status list."""
        all_countries = set()
        for key in targets:
            if key.startswith("country:"):
                all_countries.add(key.split(":", 1)[1])
        all_countries.update(country_values.keys())
        # Include all countries from stock universe
        if all_stock_countries:
            all_countries.update(all_stock_countries)

        country_allocations = []
        for country in sorted(all_countries):
            weight = targets.get(f"country:{country}", 0)
            current_val = country_values.get(country, 0)
            current_pct = current_val / total_value if total_value > 0 else 0

            country_allocations.append(
                AllocationStatus(
                    category="country",
                    name=country,
                    target_pct=weight,
                    current_pct=round(current_pct, 4),
                    current_value=round(current_val, 2),
                    deviation=round(current_pct - weight, 4),
                )
            )
        return country_allocations

    def _build_industry_allocations(
        self,
        targets: dict,
        industry_values: dict[str, float],
        total_value: float,
        all_stock_industries: set[str] | None = None,
    ) -> list[AllocationStatus]:
        """Build industry allocation status list."""
        all_industries = set()
        for key in targets:
            if key.startswith("industry:"):
                all_industries.add(key.split(":", 1)[1])
        all_industries.update(industry_values.keys())
        # Include all industries from stock universe
        if all_stock_industries:
            all_industries.update(all_stock_industries)

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

        country_values, industry_values, total_value = self._aggregate_position_values(
            positions
        )

        # Get all countries and industries from active stocks in the universe
        all_stocks = await self._stock_repo.get_all_active()
        all_stock_countries = set()
        all_stock_industries = set()
        for stock in all_stocks:
            if stock.country:
                all_stock_countries.add(stock.country)
            if stock.industry:
                industries = parse_industries(stock.industry)
                all_stock_industries.update(industries)

        # Get cash balance from actual Tradernet balances (more accurate than snapshot)
        # Fallback to snapshot if Tradernet is not connected
        cash_balance = 0.0
        try:
            from app.infrastructure.external.tradernet_connection import (
                ensure_tradernet_connected,
            )

            client = await ensure_tradernet_connected(raise_on_error=False)
            if client:
                from app.core.database.manager import get_db_manager
                from app.infrastructure.dependencies import get_exchange_rate_service

                db_manager = get_db_manager()
                exchange_rate_service = get_exchange_rate_service(db_manager)
                cash_balances = client.get_cash_balances()
                amounts_by_currency = {b.currency: b.amount for b in cash_balances}
                amounts_in_eur = await exchange_rate_service.batch_convert_to_eur(
                    amounts_by_currency
                )
                cash_balance = sum(amounts_in_eur.values())
            else:
                # Fallback to snapshot if Tradernet not connected
                cash_balance = await self._portfolio_repo.get_latest_cash_balance()
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                f"Failed to get cash balance from Tradernet: {e}, using snapshot"
            )
            # Fallback to snapshot on error
            cash_balance = await self._portfolio_repo.get_latest_cash_balance()

        country_allocations = self._build_country_allocations(
            targets, country_values, total_value, all_stock_countries
        )
        industry_allocations = self._build_industry_allocations(
            targets, industry_values, total_value, all_stock_industries
        )

        return PortfolioSummary(
            total_value=round(total_value, 2),
            cash_balance=round(cash_balance, 2),
            country_allocations=country_allocations,
            industry_allocations=industry_allocations,
        )
