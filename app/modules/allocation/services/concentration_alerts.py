"""Concentration alert detection service.

Detects when portfolio allocations approach hard concentration limits.
"""

from dataclasses import dataclass
from typing import List

from app.domain.models import PortfolioSummary
from app.domain.repositories.protocols import IPositionRepository
from app.modules.scoring.domain.constants import (
    COUNTRY_ALERT_THRESHOLD,
    MAX_COUNTRY_CONCENTRATION,
    MAX_POSITION_CONCENTRATION,
    MAX_SECTOR_CONCENTRATION,
    POSITION_ALERT_THRESHOLD,
    SECTOR_ALERT_THRESHOLD,
)


@dataclass
class ConcentrationAlert:
    """Alert for approaching concentration limit."""

    type: str  # "country", "sector", "position"
    name: str  # Country/sector name or security symbol
    current_pct: float
    limit_pct: float
    alert_threshold_pct: float
    severity: str  # "warning" (80-90% of limit), "critical" (90-100% of limit)


class ConcentrationAlertService:
    """Service to detect concentration limit alerts."""

    def __init__(self, position_repo: IPositionRepository):
        self._position_repo = position_repo

    async def detect_alerts(
        self, portfolio_summary: PortfolioSummary
    ) -> List[ConcentrationAlert]:
        """
        Detect all concentration alerts from portfolio summary.

        Args:
            portfolio_summary: Current portfolio allocation summary

        Returns:
            List of ConcentrationAlert objects
        """
        alerts: List[ConcentrationAlert] = []

        total_value = portfolio_summary.total_value
        if total_value <= 0:
            return alerts

        # Check country allocations
        for country_alloc in portfolio_summary.country_allocations:
            current_pct = country_alloc.current_pct
            if current_pct >= COUNTRY_ALERT_THRESHOLD:
                severity = self._calculate_severity(
                    current_pct, MAX_COUNTRY_CONCENTRATION
                )
                alerts.append(
                    ConcentrationAlert(
                        type="country",
                        name=country_alloc.name,
                        current_pct=current_pct,
                        limit_pct=MAX_COUNTRY_CONCENTRATION,
                        alert_threshold_pct=COUNTRY_ALERT_THRESHOLD,
                        severity=severity,
                    )
                )

        # Check industry/sector allocations
        for industry_alloc in portfolio_summary.industry_allocations:
            current_pct = industry_alloc.current_pct
            if current_pct >= SECTOR_ALERT_THRESHOLD:
                severity = self._calculate_severity(
                    current_pct, MAX_SECTOR_CONCENTRATION
                )
                alerts.append(
                    ConcentrationAlert(
                        type="sector",
                        name=industry_alloc.name,
                        current_pct=current_pct,
                        limit_pct=MAX_SECTOR_CONCENTRATION,
                        alert_threshold_pct=SECTOR_ALERT_THRESHOLD,
                        severity=severity,
                    )
                )

        # Check position concentrations
        positions = await self._position_repo.get_all()
        for position in positions:
            if (
                position.market_value_eur
                and position.market_value_eur > 0
                and total_value > 0
            ):
                position_pct = position.market_value_eur / total_value
                if position_pct >= POSITION_ALERT_THRESHOLD:
                    severity = self._calculate_severity(
                        position_pct, MAX_POSITION_CONCENTRATION
                    )
                    alerts.append(
                        ConcentrationAlert(
                            type="position",
                            name=position.symbol,
                            current_pct=position_pct,
                            limit_pct=MAX_POSITION_CONCENTRATION,
                            alert_threshold_pct=POSITION_ALERT_THRESHOLD,
                            severity=severity,
                        )
                    )

        return alerts

    def _calculate_severity(self, current_pct: float, limit_pct: float) -> str:
        """
        Calculate alert severity based on percentage of limit.

        Args:
            current_pct: Current allocation percentage
            limit_pct: Maximum allowed percentage

        Returns:
            "warning" if 80-90% of limit, "critical" if 90-100% of limit
        """
        if limit_pct <= 0:
            return "warning"

        pct_of_limit = current_pct / limit_pct
        if pct_of_limit >= 0.90:
            return "critical"
        else:
            return "warning"
