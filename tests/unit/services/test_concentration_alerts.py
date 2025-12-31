"""Tests for concentration alerts service.

These tests validate concentration alert detection for countries, sectors,
and individual positions.
"""

from unittest.mock import AsyncMock

import pytest

from app.domain.models import AllocationStatus, PortfolioSummary


@pytest.fixture
def mock_position_repo():
    """Mock position repository."""
    repo = AsyncMock()
    return repo


class TestDetectAlerts:
    """Test detect_alerts method."""

    @pytest.mark.asyncio
    async def test_detects_country_concentration(self, mock_position_repo):
        """Test that country concentration alerts are detected."""
        from app.modules.allocation.services.concentration_alerts import (
            ConcentrationAlertService,
        )

        portfolio_summary = PortfolioSummary(
            total_value=10000.0,
            cash_balance=1000.0,
            country_allocations=[
                AllocationStatus(
                    category="country",
                    name="United States",
                    target_pct=0.3,
                    current_pct=0.45,  # High concentration
                    current_value=4500.0,
                    deviation=0.15,
                )
            ],
            industry_allocations=[],
        )

        mock_position_repo.get_all.return_value = []

        service = ConcentrationAlertService(position_repo=mock_position_repo)
        alerts = await service.detect_alerts(portfolio_summary)

        assert len(alerts) > 0
        assert any(alert.type == "country" for alert in alerts)

    @pytest.mark.asyncio
    async def test_detects_sector_concentration(self, mock_position_repo):
        """Test that sector concentration alerts are detected."""
        from app.modules.allocation.services.concentration_alerts import (
            ConcentrationAlertService,
        )

        portfolio_summary = PortfolioSummary(
            total_value=10000.0,
            cash_balance=1000.0,
            country_allocations=[],
            industry_allocations=[
                AllocationStatus(
                    category="industry",
                    name="Technology",
                    target_pct=0.3,
                    current_pct=0.35,  # High concentration
                    current_value=3500.0,
                    deviation=0.05,
                )
            ],
        )

        mock_position_repo.get_all.return_value = []

        service = ConcentrationAlertService(position_repo=mock_position_repo)
        alerts = await service.detect_alerts(portfolio_summary)

        assert len(alerts) > 0
        assert any(alert.type == "sector" for alert in alerts)

    @pytest.mark.asyncio
    async def test_detects_position_concentration(self, mock_position_repo):
        """Test that individual position concentration alerts are detected."""
        from app.domain.models import Position
        from app.modules.allocation.services.concentration_alerts import (
            ConcentrationAlertService,
        )

        portfolio_summary = PortfolioSummary(
            total_value=10000.0,
            cash_balance=1000.0,
            country_allocations=[],
            industry_allocations=[],
        )

        # Mock position with high concentration
        mock_position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=30.0,
            market_value_eur=3000.0,  # 30% of portfolio
        )

        mock_position_repo.get_all.return_value = [mock_position]

        service = ConcentrationAlertService(position_repo=mock_position_repo)
        alerts = await service.detect_alerts(portfolio_summary)

        assert len(alerts) > 0
        assert any(alert.type == "position" for alert in alerts)

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_concentration(self, mock_position_repo):
        """Test that empty list is returned when there's no concentration."""
        from app.modules.allocation.services.concentration_alerts import (
            ConcentrationAlertService,
        )

        portfolio_summary = PortfolioSummary(
            total_value=10000.0,
            cash_balance=1000.0,
            country_allocations=[
                AllocationStatus(
                    category="country",
                    name="United States",
                    target_pct=0.3,
                    current_pct=0.15,  # Low concentration
                    current_value=1500.0,
                    deviation=-0.15,
                )
            ],
            industry_allocations=[],
        )

        mock_position_repo.get_all.return_value = []

        service = ConcentrationAlertService(position_repo=mock_position_repo)
        alerts = await service.detect_alerts(portfolio_summary)

        # Should have no alerts for low concentration
        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_handles_empty_portfolio(self, mock_position_repo):
        """Test handling when portfolio is empty."""
        from app.modules.allocation.services.concentration_alerts import (
            ConcentrationAlertService,
        )

        portfolio_summary = PortfolioSummary(
            total_value=0.0,
            cash_balance=0.0,
            country_allocations=[],
            industry_allocations=[],
        )

        mock_position_repo.get_all.return_value = []

        service = ConcentrationAlertService(position_repo=mock_position_repo)
        alerts = await service.detect_alerts(portfolio_summary)

        assert alerts == []

    @pytest.mark.asyncio
    async def test_detects_multiple_alerts(self, mock_position_repo):
        """Test that multiple alerts can be detected."""
        from app.domain.models import Position
        from app.modules.allocation.services.concentration_alerts import (
            ConcentrationAlertService,
        )

        portfolio_summary = PortfolioSummary(
            total_value=10000.0,
            cash_balance=1000.0,
            country_allocations=[
                AllocationStatus(
                    category="country",
                    name="United States",
                    target_pct=0.3,
                    current_pct=0.45,  # High
                    current_value=4500.0,
                    deviation=0.15,
                )
            ],
            industry_allocations=[
                AllocationStatus(
                    category="industry",
                    name="Technology",
                    target_pct=0.3,
                    current_pct=0.35,  # High
                    current_value=3500.0,
                    deviation=0.05,
                )
            ],
        )

        mock_position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=30.0,
            market_value_eur=3000.0,  # High
        )

        mock_position_repo.get_all.return_value = [mock_position]

        service = ConcentrationAlertService(position_repo=mock_position_repo)
        alerts = await service.detect_alerts(portfolio_summary)

        # Should detect multiple alerts
        assert len(alerts) >= 2

    @pytest.mark.asyncio
    async def test_alerts_have_correct_structure(self, mock_position_repo):
        """Test that alerts have the correct structure."""
        from app.modules.allocation.services.concentration_alerts import (
            ConcentrationAlertService,
        )

        portfolio_summary = PortfolioSummary(
            total_value=10000.0,
            cash_balance=1000.0,
            country_allocations=[
                AllocationStatus(
                    category="country",
                    name="United States",
                    target_pct=0.3,
                    current_pct=0.45,
                    current_value=4500.0,
                    deviation=0.15,
                )
            ],
            industry_allocations=[],
        )

        mock_position_repo.get_all.return_value = []

        service = ConcentrationAlertService(position_repo=mock_position_repo)
        alerts = await service.detect_alerts(portfolio_summary)

        if alerts:
            alert = alerts[0]
            assert hasattr(alert, "type")
            assert hasattr(alert, "name")
            assert hasattr(alert, "severity")
            assert hasattr(alert, "current_pct")
            assert hasattr(alert, "limit_pct")
            assert hasattr(alert, "alert_threshold_pct")
            assert alert.type in ["country", "sector", "position"]
            assert alert.severity in ["warning", "critical"]


class TestCalculateSeverity:
    """Test _calculate_severity method."""

    def test_returns_critical_for_high_percentage(self):
        """Test that critical severity is returned for high percentage."""
        from app.modules.allocation.services.concentration_alerts import (
            ConcentrationAlertService,
        )

        service = ConcentrationAlertService(position_repo=AsyncMock())

        # High percentage (>90% of limit) should trigger critical
        # If limit is 0.5 and current is 0.46, that's 92% of limit = critical
        severity = service._calculate_severity(0.46, 0.5)

        assert severity == "critical"

    def test_returns_warning_for_moderate_percentage(self):
        """Test that warning severity is returned for moderate percentage."""
        from app.modules.allocation.services.concentration_alerts import (
            ConcentrationAlertService,
        )

        service = ConcentrationAlertService(position_repo=AsyncMock())

        # Moderate percentage (80-90% of limit) should trigger warning
        # If limit is 0.5 and current is 0.42, that's 84% of limit = warning
        severity = service._calculate_severity(0.42, 0.5)

        assert severity == "warning"

    def test_returns_warning_for_zero_limit(self):
        """Test that warning is returned when limit is zero."""
        from app.modules.allocation.services.concentration_alerts import (
            ConcentrationAlertService,
        )

        service = ConcentrationAlertService(position_repo=AsyncMock())

        severity = service._calculate_severity(0.3, 0.0)

        assert severity == "warning"
