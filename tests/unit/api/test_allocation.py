"""Tests for allocation API endpoints.

These tests validate allocation target management, group management,
and allocation status endpoints. Comprehensive coverage of all 18 endpoints.
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.domain.models import AllocationStatus, PortfolioSummary


@pytest.fixture
def mock_portfolio_service():
    """Mock portfolio service."""
    service = AsyncMock()
    return service


@pytest.fixture
def mock_alert_service():
    """Mock concentration alert service."""
    service = AsyncMock()
    service.detect_alerts = AsyncMock(return_value=[])
    return service


@pytest.fixture
def mock_allocation_repo():
    """Mock allocation repository."""
    repo = AsyncMock()
    repo.get_country_group_targets = AsyncMock(return_value={})
    repo.get_industry_group_targets = AsyncMock(return_value={})
    repo.upsert = AsyncMock()
    return repo


@pytest.fixture
def mock_grouping_repo():
    """Mock grouping repository."""
    repo = AsyncMock()
    repo.get_country_groups = AsyncMock(return_value={})
    repo.get_industry_groups = AsyncMock(return_value={})
    repo.set_country_group = AsyncMock()
    repo.set_industry_group = AsyncMock()
    repo.delete_country_group = AsyncMock()
    repo.delete_industry_group = AsyncMock()
    repo.get_available_countries = AsyncMock(return_value=[])
    repo.get_available_industries = AsyncMock(return_value=[])
    return repo


class TestGetCurrentAllocation:
    """Test get_current_allocation endpoint."""

    @pytest.mark.asyncio
    async def test_returns_current_allocation(
        self, mock_portfolio_service, mock_alert_service
    ):
        """Test that current allocation is returned with country and industry data."""
        from app.api.allocation import get_current_allocation

        # Setup portfolio summary
        country_alloc = AllocationStatus(
            category="country",
            name="United States",
            target_pct=0.5,
            current_pct=0.6,
            current_value=6000.0,
            deviation=0.1,
        )
        industry_alloc = AllocationStatus(
            category="industry",
            name="Technology",
            target_pct=0.3,
            current_pct=0.35,
            current_value=3500.0,
            deviation=0.05,
        )
        summary = PortfolioSummary(
            total_value=10000.0,
            cash_balance=500.0,
            country_allocations=[country_alloc],
            industry_allocations=[industry_alloc],
        )

        mock_portfolio_service.get_portfolio_summary.return_value = summary

        result = await get_current_allocation(
            mock_portfolio_service, mock_alert_service
        )

        assert result["total_value"] == 10000.0
        assert result["cash_balance"] == 500.0
        assert len(result["country"]) == 1
        assert result["country"][0]["name"] == "United States"
        assert result["country"][0]["target_pct"] == 0.5
        assert result["country"][0]["current_pct"] == 0.6
        assert result["country"][0]["deviation"] == 0.1
        assert len(result["industry"]) == 1
        assert "alerts" in result

    @pytest.mark.asyncio
    async def test_includes_alerts(self, mock_portfolio_service, mock_alert_service):
        """Test that concentration alerts are included."""
        from app.api.allocation import get_current_allocation
        from app.modules.portfolio.services.concentration_alerts import ConcentrationAlert

        summary = PortfolioSummary(
            total_value=10000.0,
            cash_balance=500.0,
            country_allocations=[],
            industry_allocations=[],
        )
        mock_portfolio_service.get_portfolio_summary.return_value = summary

        alert = ConcentrationAlert(
            type="country",
            name="United States",
            current_pct=0.85,
            limit_pct=0.90,
            alert_threshold_pct=0.72,
            severity="warning",
        )
        mock_alert_service.detect_alerts.return_value = [alert]

        result = await get_current_allocation(
            mock_portfolio_service, mock_alert_service
        )

        assert len(result["alerts"]) == 1
        assert result["alerts"][0]["type"] == "country"
        assert result["alerts"][0]["severity"] == "warning"

    @pytest.mark.asyncio
    async def test_handles_empty_allocations(
        self, mock_portfolio_service, mock_alert_service
    ):
        """Test handling of empty allocations."""
        from app.api.allocation import get_current_allocation

        summary = PortfolioSummary(
            total_value=0.0,
            cash_balance=0.0,
            country_allocations=[],
            industry_allocations=[],
        )
        mock_portfolio_service.get_portfolio_summary.return_value = summary

        result = await get_current_allocation(
            mock_portfolio_service, mock_alert_service
        )

        assert result["total_value"] == 0.0
        assert len(result["country"]) == 0
        assert len(result["industry"]) == 0


class TestGetAllocationDeviations:
    """Test get_allocation_deviations endpoint."""

    @pytest.mark.asyncio
    async def test_returns_deviations_with_status(self, mock_portfolio_service):
        """Test that deviations are returned with status indicators."""
        from app.api.allocation import get_allocation_deviations

        # Underweight country
        country_under = AllocationStatus(
            category="country",
            name="EU",
            target_pct=0.4,
            current_pct=0.35,  # 5% underweight
            current_value=3500.0,
            deviation=-0.05,
        )
        # Overweight country
        country_over = AllocationStatus(
            category="country",
            name="US",
            target_pct=0.5,
            current_pct=0.55,  # 5% overweight
            current_value=5500.0,
            deviation=0.05,
        )
        # Balanced industry
        industry_balanced = AllocationStatus(
            category="industry",
            name="Tech",
            target_pct=0.3,
            current_pct=0.31,  # 1% deviation (within 2% threshold)
            current_value=3100.0,
            deviation=0.01,
        )

        summary = PortfolioSummary(
            total_value=10000.0,
            cash_balance=1000.0,
            country_allocations=[country_under, country_over],
            industry_allocations=[industry_balanced],
        )
        mock_portfolio_service.get_portfolio_summary.return_value = summary

        result = await get_allocation_deviations(mock_portfolio_service)

        assert result["country"]["EU"]["status"] == "underweight"
        assert result["country"]["EU"]["need"] == 0.05  # max(0, -(-0.05))
        assert result["country"]["US"]["status"] == "overweight"
        assert result["industry"]["Tech"]["status"] == "balanced"

    @pytest.mark.asyncio
    async def test_calculates_need_correctly(self, mock_portfolio_service):
        """Test that 'need' is calculated correctly (max(0, -deviation))."""
        from app.api.allocation import get_allocation_deviations

        country = AllocationStatus(
            category="country",
            name="EU",
            target_pct=0.4,
            current_pct=0.30,
            current_value=3000.0,
            deviation=-0.10,  # 10% underweight
        )
        summary = PortfolioSummary(
            total_value=10000.0,
            cash_balance=1000.0,
            country_allocations=[country],
            industry_allocations=[],
        )
        mock_portfolio_service.get_portfolio_summary.return_value = summary

        result = await get_allocation_deviations(mock_portfolio_service)

        assert result["country"]["EU"]["need"] == 0.10  # max(0, -(-0.10))
        assert result["country"]["EU"]["deviation"] == -0.10


class TestGetAllocationTargets:
    """Test get_allocation_targets endpoint."""

    @pytest.mark.asyncio
    async def test_returns_country_and_industry_targets(self, mock_allocation_repo):
        """Test that targets for both country and industry are returned."""
        from app.api.allocation import get_allocation_targets

        mock_allocation_repo.get_country_group_targets.return_value = {
            "US": 0.5,
            "EU": 0.4,
        }
        mock_allocation_repo.get_industry_group_targets.return_value = {
            "Technology": 0.3,
            "Finance": 0.2,
        }

        result = await get_allocation_targets(mock_allocation_repo)

        assert result["country"]["US"] == 0.5
        assert result["country"]["EU"] == 0.4
        assert result["industry"]["Technology"] == 0.3
        assert result["industry"]["Finance"] == 0.2

    @pytest.mark.asyncio
    async def test_handles_empty_targets(self, mock_allocation_repo):
        """Test handling of empty targets."""
        from app.api.allocation import get_allocation_targets

        mock_allocation_repo.get_country_group_targets.return_value = {}
        mock_allocation_repo.get_industry_group_targets.return_value = {}

        result = await get_allocation_targets(mock_allocation_repo)

        assert result["country"] == {}
        assert result["industry"] == {}


class TestGetCountryGroups:
    """Test get_country_groups endpoint."""

    @pytest.mark.asyncio
    async def test_returns_country_groups(self, mock_grouping_repo):
        """Test that country groups are returned."""
        from app.api.allocation import get_country_groups

        mock_grouping_repo.get_country_groups.return_value = {
            "US": ["United States", "Canada"],
            "EU": ["Germany", "France"],
        }

        result = await get_country_groups(mock_grouping_repo)

        assert "groups" in result
        assert result["groups"]["US"] == ["United States", "Canada"]
        assert result["groups"]["EU"] == ["Germany", "France"]

    @pytest.mark.asyncio
    async def test_handles_empty_groups(self, mock_grouping_repo):
        """Test handling of empty groups."""
        from app.api.allocation import get_country_groups

        mock_grouping_repo.get_country_groups.return_value = {}

        result = await get_country_groups(mock_grouping_repo)

        assert result["groups"] == {}


class TestGetIndustryGroups:
    """Test get_industry_groups endpoint."""

    @pytest.mark.asyncio
    async def test_returns_industry_groups(self, mock_grouping_repo):
        """Test that industry groups are returned."""
        from app.api.allocation import get_industry_groups

        mock_grouping_repo.get_industry_groups.return_value = {
            "Technology": ["Software", "Hardware"],
            "Finance": ["Banking", "Insurance"],
        }

        result = await get_industry_groups(mock_grouping_repo)

        assert "groups" in result
        assert result["groups"]["Technology"] == ["Software", "Hardware"]

    @pytest.mark.asyncio
    async def test_handles_empty_groups(self, mock_grouping_repo):
        """Test handling of empty groups."""
        from app.api.allocation import get_industry_groups

        mock_grouping_repo.get_industry_groups.return_value = {}

        result = await get_industry_groups(mock_grouping_repo)

        assert result["groups"] == {}


class TestUpdateCountryGroup:
    """Test update_country_group endpoint."""

    @pytest.mark.asyncio
    async def test_creates_or_updates_country_group(self, mock_grouping_repo):
        """Test that country group is created or updated."""
        from app.api.allocation import CountryGroup, update_country_group

        group = CountryGroup(group_name="US", country_names=["United States", "Canada"])

        result = await update_country_group(group, mock_grouping_repo)

        mock_grouping_repo.set_country_group.assert_called_once_with(
            "US", ["United States", "Canada"]
        )
        assert result["group_name"] == "US"
        assert result["country_names"] == ["United States", "Canada"]

    @pytest.mark.asyncio
    async def test_validates_group_name_required(self, mock_grouping_repo):
        """Test that empty group name raises error."""
        from app.api.allocation import CountryGroup, update_country_group

        group = CountryGroup(group_name="", country_names=["United States"])

        with pytest.raises(HTTPException) as exc_info:
            await update_country_group(group, mock_grouping_repo)

        assert exc_info.value.status_code == 400
        assert "Group name is required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_filters_empty_countries(self, mock_grouping_repo):
        """Test that empty country names are filtered out."""
        from app.api.allocation import CountryGroup, update_country_group

        group = CountryGroup(
            group_name="US",
            country_names=["United States", "", "  ", "Canada", "United States"],
        )

        result = await update_country_group(group, mock_grouping_repo)

        # Should filter empty strings and duplicates
        mock_grouping_repo.set_country_group.assert_called_once_with(
            "US", ["United States", "Canada"]
        )
        assert len(result["country_names"]) == 2

    @pytest.mark.asyncio
    async def test_allows_empty_country_list(self, mock_grouping_repo):
        """Test that empty country list is allowed (user can add later)."""
        from app.api.allocation import CountryGroup, update_country_group

        group = CountryGroup(group_name="NEW", country_names=[])

        result = await update_country_group(group, mock_grouping_repo)

        mock_grouping_repo.set_country_group.assert_called_once_with("NEW", [])
        assert result["country_names"] == []

    @pytest.mark.asyncio
    async def test_strips_whitespace_from_group_name(self, mock_grouping_repo):
        """Test that whitespace is stripped from group name."""
        from app.api.allocation import CountryGroup, update_country_group

        group = CountryGroup(group_name="  US  ", country_names=["United States"])

        result = await update_country_group(group, mock_grouping_repo)

        mock_grouping_repo.set_country_group.assert_called_once_with(
            "US", ["United States"]
        )
        assert result["group_name"] == "US"


class TestUpdateIndustryGroup:
    """Test update_industry_group endpoint."""

    @pytest.mark.asyncio
    async def test_creates_or_updates_industry_group(self, mock_grouping_repo):
        """Test that industry group is created or updated."""
        from app.api.allocation import IndustryGroup, update_industry_group

        group = IndustryGroup(
            group_name="Tech", industry_names=["Software", "Hardware"]
        )

        result = await update_industry_group(group, mock_grouping_repo)

        mock_grouping_repo.set_industry_group.assert_called_once_with(
            "Tech", ["Software", "Hardware"]
        )
        assert result["group_name"] == "Tech"

    @pytest.mark.asyncio
    async def test_validates_group_name_required(self, mock_grouping_repo):
        """Test that empty group name raises error."""
        from app.api.allocation import IndustryGroup, update_industry_group

        group = IndustryGroup(group_name="   ", industry_names=["Software"])

        with pytest.raises(HTTPException) as exc_info:
            await update_industry_group(group, mock_grouping_repo)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_filters_empty_industries(self, mock_grouping_repo):
        """Test that empty industry names are filtered out."""
        from app.api.allocation import IndustryGroup, update_industry_group

        group = IndustryGroup(
            group_name="Tech",
            industry_names=["Software", "", "Hardware", "Software"],
        )

        await update_industry_group(group, mock_grouping_repo)

        mock_grouping_repo.set_industry_group.assert_called_once_with(
            "Tech", ["Software", "Hardware"]
        )


class TestDeleteCountryGroup:
    """Test delete_country_group endpoint."""

    @pytest.mark.asyncio
    async def test_deletes_country_group(self, mock_grouping_repo):
        """Test that country group is deleted."""
        from app.api.allocation import delete_country_group

        result = await delete_country_group("US", mock_grouping_repo)

        mock_grouping_repo.delete_country_group.assert_called_once_with("US")
        assert result["deleted"] == "US"


class TestDeleteIndustryGroup:
    """Test delete_industry_group endpoint."""

    @pytest.mark.asyncio
    async def test_deletes_industry_group(self, mock_grouping_repo):
        """Test that industry group is deleted."""
        from app.api.allocation import delete_industry_group

        result = await delete_industry_group("Tech", mock_grouping_repo)

        mock_grouping_repo.delete_industry_group.assert_called_once_with("Tech")
        assert result["deleted"] == "Tech"


class TestGetAvailableCountries:
    """Test get_available_countries endpoint."""

    @pytest.mark.asyncio
    async def test_returns_available_countries(self, mock_grouping_repo):
        """Test that available countries are returned."""
        from app.api.allocation import get_available_countries

        mock_grouping_repo.get_available_countries.return_value = [
            "United States",
            "Germany",
            "France",
        ]

        result = await get_available_countries(mock_grouping_repo)

        assert "countries" in result
        assert len(result["countries"]) == 3
        assert "United States" in result["countries"]

    @pytest.mark.asyncio
    async def test_handles_empty_list(self, mock_grouping_repo):
        """Test handling of empty country list."""
        from app.api.allocation import get_available_countries

        mock_grouping_repo.get_available_countries.return_value = []

        result = await get_available_countries(mock_grouping_repo)

        assert result["countries"] == []


class TestGetAvailableIndustries:
    """Test get_available_industries endpoint."""

    @pytest.mark.asyncio
    async def test_returns_available_industries(self, mock_grouping_repo):
        """Test that available industries are returned."""
        from app.api.allocation import get_available_industries

        mock_grouping_repo.get_available_industries.return_value = [
            "Technology",
            "Finance",
            "Healthcare",
        ]

        result = await get_available_industries(mock_grouping_repo)

        assert "industries" in result
        assert len(result["industries"]) == 3
        assert "Technology" in result["industries"]


class TestGetGroupAllocation:
    """Test get_group_allocation endpoint."""

    @pytest.mark.asyncio
    async def test_returns_group_allocations(
        self, mock_portfolio_service, mock_grouping_repo, mock_allocation_repo
    ):
        """Test that allocations aggregated by groups are returned."""
        from app.api.allocation import get_group_allocation

        # Setup country allocations (individual countries)
        country_alloc1 = AllocationStatus(
            category="country",
            name="United States",
            target_pct=0.3,
            current_pct=0.35,
            current_value=3500.0,
            deviation=0.05,
        )
        country_alloc2 = AllocationStatus(
            category="country",
            name="Canada",
            target_pct=0.2,
            current_pct=0.15,
            current_value=1500.0,
            deviation=-0.05,
        )
        summary = PortfolioSummary(
            total_value=10000.0,
            cash_balance=1000.0,
            country_allocations=[country_alloc1, country_alloc2],
            industry_allocations=[],
        )
        mock_portfolio_service.get_portfolio_summary.return_value = summary

        # Setup groups: US group contains United States and Canada
        mock_grouping_repo.get_country_groups.return_value = {
            "US": ["United States", "Canada"],
        }
        mock_grouping_repo.get_industry_groups.return_value = {}

        # Setup group targets (the function uses saved group targets, not aggregated individual)
        mock_allocation_repo.get_country_group_targets.return_value = {
            "US": 0.5,  # Group target for US group
        }
        mock_allocation_repo.get_industry_group_targets.return_value = {}

        result = await get_group_allocation(
            mock_portfolio_service, mock_grouping_repo, mock_allocation_repo
        )

        assert result["total_value"] == 10000.0
        assert len(result["country"]) > 0
        # US group should aggregate both countries
        us_group = next((g for g in result["country"] if g["name"] == "US"), None)
        assert us_group is not None
        assert us_group["target_pct"] == 0.5  # From saved group target
        assert us_group["current_pct"] == 0.5  # (3500 + 1500) / 10000

    @pytest.mark.asyncio
    async def test_maps_to_other_when_no_group(
        self, mock_portfolio_service, mock_grouping_repo
    ):
        """Test that countries without groups map to 'OTHER'."""
        from app.api.allocation import get_group_allocation

        country_alloc = AllocationStatus(
            category="country",
            name="Unknown Country",
            target_pct=0.1,
            current_pct=0.1,
            current_value=1000.0,
            deviation=0.0,
        )
        summary = PortfolioSummary(
            total_value=10000.0,
            cash_balance=0.0,
            country_allocations=[country_alloc],
            industry_allocations=[],
        )
        mock_portfolio_service.get_portfolio_summary.return_value = summary

        mock_grouping_repo.get_country_groups.return_value = {}
        mock_grouping_repo.get_industry_groups.return_value = {}

        result = await get_group_allocation(mock_portfolio_service, mock_grouping_repo)

        # Should map to OTHER
        other_group = next((g for g in result["country"] if g["name"] == "OTHER"), None)
        assert other_group is not None
        assert other_group["current_pct"] == 0.1

    @pytest.mark.asyncio
    async def test_handles_zero_total_value(
        self, mock_portfolio_service, mock_grouping_repo
    ):
        """Test handling when total value is zero."""
        from app.api.allocation import get_group_allocation

        summary = PortfolioSummary(
            total_value=0.0,
            cash_balance=0.0,
            country_allocations=[],
            industry_allocations=[],
        )
        mock_portfolio_service.get_portfolio_summary.return_value = summary

        mock_grouping_repo.get_country_groups.return_value = {}
        mock_grouping_repo.get_industry_groups.return_value = {}

        result = await get_group_allocation(mock_portfolio_service, mock_grouping_repo)

        assert result["total_value"] == 0.0
        assert len(result["country"]) == 0


class TestUpdateCountryGroupTargets:
    """Test update_country_group_targets endpoint."""

    @pytest.mark.asyncio
    async def test_updates_country_group_targets(
        self, mock_allocation_repo, mock_grouping_repo
    ):
        """Test that country group targets are updated."""
        from app.api.allocation import CountryTargets, update_country_group_targets

        mock_grouping_repo.get_country_groups.return_value = {
            "US": ["United States"],
            "EU": ["Germany"],
        }
        mock_allocation_repo.get_country_group_targets.return_value = {
            "US": 0.5,
            "EU": 0.4,
        }

        targets = CountryTargets(targets={"US": 0.6, "EU": 0.3})

        result = await update_country_group_targets(
            targets, mock_allocation_repo, mock_grouping_repo
        )

        assert mock_allocation_repo.upsert.call_count == 2
        assert "weights" in result
        assert result["weights"]["US"] == 0.5
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_validates_empty_targets(
        self, mock_allocation_repo, mock_grouping_repo
    ):
        """Test that empty targets raise error."""
        from app.api.allocation import CountryTargets, update_country_group_targets

        targets = CountryTargets(targets={})

        with pytest.raises(HTTPException) as exc_info:
            await update_country_group_targets(
                targets, mock_allocation_repo, mock_grouping_repo
            )

        assert exc_info.value.status_code == 400
        assert "No weights provided" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_validates_groups_exist(
        self, mock_allocation_repo, mock_grouping_repo
    ):
        """Test that updating targets requires groups to exist."""
        from app.api.allocation import CountryTargets, update_country_group_targets

        mock_grouping_repo.get_country_groups.return_value = {}
        targets = CountryTargets(targets={"US": 0.5})

        with pytest.raises(HTTPException) as exc_info:
            await update_country_group_targets(
                targets, mock_allocation_repo, mock_grouping_repo
            )

        assert exc_info.value.status_code == 400
        assert "No country groups defined" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_validates_weight_range(
        self, mock_allocation_repo, mock_grouping_repo
    ):
        """Test that weights must be between -1 and 1."""
        from app.api.allocation import CountryTargets, update_country_group_targets

        mock_grouping_repo.get_country_groups.return_value = {"US": ["United States"]}

        # Test weight > 1
        targets = CountryTargets(targets={"US": 1.5})
        with pytest.raises(HTTPException) as exc_info:
            await update_country_group_targets(
                targets, mock_allocation_repo, mock_grouping_repo
            )
        assert exc_info.value.status_code == 400
        assert "must be between -1 and 1" in str(exc_info.value.detail)

        # Test weight < -1
        targets = CountryTargets(targets={"US": -1.5})
        with pytest.raises(HTTPException) as exc_info:
            await update_country_group_targets(
                targets, mock_allocation_repo, mock_grouping_repo
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_filters_zero_targets(self, mock_allocation_repo, mock_grouping_repo):
        """Test that zero targets are filtered from response."""
        from app.api.allocation import CountryTargets, update_country_group_targets

        mock_grouping_repo.get_country_groups.return_value = {
            "US": ["United States"],
            "EU": ["Germany"],
        }
        mock_allocation_repo.get_country_group_targets.return_value = {
            "US": 0.5,
            "EU": 0.0,  # Zero target
        }

        targets = CountryTargets(targets={"US": 0.5, "EU": 0.0})

        result = await update_country_group_targets(
            targets, mock_allocation_repo, mock_grouping_repo
        )

        # Should only return non-zero targets
        assert "EU" not in result["weights"]
        assert result["weights"]["US"] == 0.5
        assert result["count"] == 1


class TestUpdateIndustryGroupTargets:
    """Test update_industry_group_targets endpoint."""

    @pytest.mark.asyncio
    async def test_updates_industry_group_targets(
        self, mock_allocation_repo, mock_grouping_repo
    ):
        """Test that industry group targets are updated."""
        from app.api.allocation import IndustryTargets, update_industry_group_targets

        mock_grouping_repo.get_industry_groups.return_value = {
            "Technology": ["Software"],
            "Finance": ["Banking"],
        }
        mock_allocation_repo.get_industry_group_targets.return_value = {
            "Technology": 0.3,
            "Finance": 0.2,
        }

        targets = IndustryTargets(targets={"Technology": 0.4, "Finance": 0.2})

        result = await update_industry_group_targets(
            targets, mock_allocation_repo, mock_grouping_repo
        )

        assert mock_allocation_repo.upsert.call_count == 2
        assert "weights" in result

    @pytest.mark.asyncio
    async def test_validates_empty_targets(
        self, mock_allocation_repo, mock_grouping_repo
    ):
        """Test that empty targets raise error."""
        from app.api.allocation import IndustryTargets, update_industry_group_targets

        targets = IndustryTargets(targets={})

        with pytest.raises(HTTPException) as exc_info:
            await update_industry_group_targets(
                targets, mock_allocation_repo, mock_grouping_repo
            )

        assert exc_info.value.status_code == 400
        assert "No weights provided" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_validates_groups_exist(
        self, mock_allocation_repo, mock_grouping_repo
    ):
        """Test that updating targets requires groups to exist."""
        from app.api.allocation import IndustryTargets, update_industry_group_targets

        mock_grouping_repo.get_industry_groups.return_value = {}
        targets = IndustryTargets(targets={"Technology": 0.3})

        with pytest.raises(HTTPException) as exc_info:
            await update_industry_group_targets(
                targets, mock_allocation_repo, mock_grouping_repo
            )

        assert exc_info.value.status_code == 400
        assert "No industry groups defined" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_validates_weight_range(
        self, mock_allocation_repo, mock_grouping_repo
    ):
        """Test that weights must be between -1 and 1."""
        from app.api.allocation import IndustryTargets, update_industry_group_targets

        mock_grouping_repo.get_industry_groups.return_value = {
            "Technology": ["Software"]
        }

        targets = IndustryTargets(targets={"Technology": 2.0})

        with pytest.raises(HTTPException) as exc_info:
            await update_industry_group_targets(
                targets, mock_allocation_repo, mock_grouping_repo
            )

        assert exc_info.value.status_code == 400
        assert "must be between -1 and 1" in str(exc_info.value.detail)
