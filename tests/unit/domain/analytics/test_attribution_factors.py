"""Tests for factor attribution calculations.

These tests validate factor attribution analysis which identifies which
factors (country, industry) contributed most to portfolio returns.
"""

from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest


class TestGetFactorAttribution:
    """Test get_factor_attribution function."""

    @pytest.mark.asyncio
    async def test_returns_zero_for_empty_returns(self):
        """Test that empty returns series returns zero contributions."""
        from app.modules.analytics.domain.attribution.factors import (
            get_factor_attribution,
        )

        returns = pd.Series(dtype=float)
        result = await get_factor_attribution(returns, "2024-01-01", "2024-01-31")

        assert result == {
            "country_contribution": 0.0,
            "industry_contribution": 0.0,
            "total_return": 0.0,
        }

    @pytest.mark.asyncio
    async def test_calculates_contributions_correctly(self):
        """Test that factor contributions are calculated correctly."""
        from app.modules.analytics.domain.attribution.factors import (
            get_factor_attribution,
        )

        # Mock returns
        returns = pd.Series(
            [0.01, 0.02, -0.01],
            index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
        )

        # Mock performance attribution
        mock_attribution = {
            "country": {"US": 0.10, "DE": 0.05},  # Two countries
            "industry": {"Technology": 0.08, "Finance": 0.06},  # Two industries
        }

        with patch(
            "app.modules.analytics.domain.attribution.factors.get_performance_attribution",
            new_callable=AsyncMock,
        ) as mock_perf_attrib:
            with patch("empyrical.annual_return", return_value=0.12):
                mock_perf_attrib.return_value = mock_attribution

                result = await get_factor_attribution(
                    returns, "2024-01-01", "2024-01-31"
                )

                assert result["total_return"] == 0.12
                # Country contribution = average of (0.10, 0.05) = 0.075
                assert result["country_contribution"] == pytest.approx(0.075, abs=0.001)
                # Industry contribution = average of (0.08, 0.06) = 0.07
                assert result["industry_contribution"] == pytest.approx(0.07, abs=0.001)

    @pytest.mark.asyncio
    async def test_handles_empty_attribution(self):
        """Test handling when performance attribution returns empty data."""
        from app.modules.analytics.domain.attribution.factors import (
            get_factor_attribution,
        )

        returns = pd.Series([0.01], index=pd.to_datetime(["2024-01-01"]))

        mock_attribution = {"country": {}, "industry": {}}

        with patch(
            "app.modules.analytics.domain.attribution.factors.get_performance_attribution",
            new_callable=AsyncMock,
        ) as mock_perf_attrib:
            with patch("empyrical.annual_return", return_value=0.05):
                mock_perf_attrib.return_value = mock_attribution

                result = await get_factor_attribution(
                    returns, "2024-01-01", "2024-01-31"
                )

                assert result["total_return"] == 0.05
                assert result["country_contribution"] == 0.0
                assert result["industry_contribution"] == 0.0

    @pytest.mark.asyncio
    async def test_handles_non_finite_total_return(self):
        """Test handling when empyrical returns non-finite total return."""
        from app.modules.analytics.domain.attribution.factors import (
            get_factor_attribution,
        )

        returns = pd.Series([0.01], index=pd.to_datetime(["2024-01-01"]))

        mock_attribution = {"country": {"US": 0.10}, "industry": {}}

        with patch(
            "app.modules.analytics.domain.attribution.factors.get_performance_attribution",
            new_callable=AsyncMock,
        ) as mock_perf_attrib:
            with patch("empyrical.annual_return", return_value=float("inf")):
                mock_perf_attrib.return_value = mock_attribution

                result = await get_factor_attribution(
                    returns, "2024-01-01", "2024-01-31"
                )

                # Non-finite total return should be converted to 0.0
                assert result["total_return"] == 0.0

    @pytest.mark.asyncio
    async def test_handles_non_finite_contributions(self):
        """Test handling when contributions are non-finite."""
        from app.modules.analytics.domain.attribution.factors import (
            get_factor_attribution,
        )

        returns = pd.Series([0.01], index=pd.to_datetime(["2024-01-01"]))

        # Mock attribution with values that would cause non-finite average
        mock_attribution = {
            "country": {"US": float("inf")},
            "industry": {"Tech": float("nan")},
        }

        with patch(
            "app.modules.analytics.domain.attribution.factors.get_performance_attribution",
            new_callable=AsyncMock,
        ) as mock_perf_attrib:
            with patch("empyrical.annual_return", return_value=0.05):
                mock_perf_attrib.return_value = mock_attribution

                result = await get_factor_attribution(
                    returns, "2024-01-01", "2024-01-31"
                )

                # Non-finite contributions should be converted to 0.0
                assert result["country_contribution"] == 0.0
                assert result["industry_contribution"] == 0.0

    @pytest.mark.asyncio
    async def test_calculates_single_category_contribution(self):
        """Test calculation when only one category has attribution."""
        from app.modules.analytics.domain.attribution.factors import (
            get_factor_attribution,
        )

        returns = pd.Series([0.01], index=pd.to_datetime(["2024-01-01"]))

        mock_attribution = {
            "country": {"US": 0.10},  # Only one country
            "industry": {},  # No industries
        }

        with patch(
            "app.modules.analytics.domain.attribution.factors.get_performance_attribution",
            new_callable=AsyncMock,
        ) as mock_perf_attrib:
            with patch("empyrical.annual_return", return_value=0.05):
                mock_perf_attrib.return_value = mock_attribution

                result = await get_factor_attribution(
                    returns, "2024-01-01", "2024-01-31"
                )

                assert result["country_contribution"] == 0.10
                assert result["industry_contribution"] == 0.0

    @pytest.mark.asyncio
    async def test_calculates_negative_contributions(self):
        """Test calculation when contributions are negative."""
        from app.modules.analytics.domain.attribution.factors import (
            get_factor_attribution,
        )

        returns = pd.Series(
            [-0.01, -0.02],
            index=pd.to_datetime(["2024-01-01", "2024-01-02"]),
        )

        mock_attribution = {
            "country": {"US": -0.05, "DE": -0.03},
            "industry": {"Tech": -0.04},
        }

        with patch(
            "app.modules.analytics.domain.attribution.factors.get_performance_attribution",
            new_callable=AsyncMock,
        ) as mock_perf_attrib:
            with patch("empyrical.annual_return", return_value=-0.08):
                mock_perf_attrib.return_value = mock_attribution

                result = await get_factor_attribution(
                    returns, "2024-01-01", "2024-01-31"
                )

                assert result["total_return"] == -0.08
                # Average of -0.05 and -0.03 = -0.04
                assert result["country_contribution"] == pytest.approx(-0.04, abs=0.001)
                assert result["industry_contribution"] == pytest.approx(
                    -0.04, abs=0.001
                )
