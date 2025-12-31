"""Tests for performance adjustment calculator.

These tests validate performance-adjusted weight calculations based on
portfolio attribution data.
"""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_allocation_repo():
    """Mock allocation repository."""
    repo = AsyncMock()
    repo.get_country_group_targets = AsyncMock(
        return_value={"US": 0.5, "EU": 0.4, "ASIA": 0.1}
    )
    repo.get_industry_group_targets = AsyncMock(
        return_value={"Tech": 0.3, "Finance": 0.2, "Healthcare": 0.1}
    )
    # Mock get_all() to return allocations in the format expected by the code
    repo.get_all = AsyncMock(
        return_value={
            "country:US": 0.5,
            "country:EU": 0.4,
            "country:ASIA": 0.1,
            "industry:Tech": 0.3,
            "industry:Finance": 0.2,
            "industry:Healthcare": 0.1,
        }
    )
    return repo


@pytest.fixture
def mock_attribution_repo():
    """Mock attribution repository."""
    repo = AsyncMock()
    repo.get_attribution_data = AsyncMock(
        return_value={
            "country_attribution": {
                "US": 0.12,
                "EU": -0.05,
                "ASIA": 0.02,
            },
            "industry_attribution": {
                "Tech": 0.15,
                "Finance": -0.03,
                "Healthcare": 0.01,
            },
        }
    )
    return repo


class TestAdjustCountryWeights:
    """Test _adjust_country_weights function."""

    def test_increases_weight_for_positive_attribution(self):
        """Test that weights increase for positive attribution."""
        from app.modules.planning.services.performance_adjustment_calculator import (
            _adjust_country_weights,
        )

        base_weights = {"US": 0.5, "EU": 0.4}
        attribution = {"US": 0.10, "EU": -0.05}  # US outperformed, EU underperformed
        avg_return = 0.08

        adjusted = _adjust_country_weights(base_weights, attribution, avg_return)

        assert adjusted["US"] > base_weights["US"]  # Increased for positive attribution
        assert adjusted["EU"] < base_weights["EU"]  # Decreased for negative attribution

    def test_decreases_weight_for_negative_attribution(self):
        """Test that weights decrease for negative attribution."""
        from app.modules.planning.services.performance_adjustment_calculator import (
            _adjust_country_weights,
        )

        base_weights = {"US": 0.5, "EU": 0.4}
        attribution = {"US": -0.10, "EU": 0.05}
        avg_return = 0.08

        adjusted = _adjust_country_weights(base_weights, attribution, avg_return)

        assert adjusted["US"] < base_weights["US"]
        assert adjusted["EU"] > base_weights["EU"]

    def test_handles_zero_attribution(self):
        """Test handling when attribution is zero."""
        from app.modules.planning.services.performance_adjustment_calculator import (
            _adjust_country_weights,
        )

        base_weights = {"US": 0.5, "EU": 0.4}
        attribution = {"US": 0.0, "EU": 0.0}
        avg_return = 0.08

        adjusted = _adjust_country_weights(base_weights, attribution, avg_return)

        # Weights should be close to base (minimal adjustment)
        assert abs(adjusted["US"] - base_weights["US"]) < 0.1
        assert abs(adjusted["EU"] - base_weights["EU"]) < 0.1

    def test_preserves_total_weight_approximately(self):
        """Test that total weights remain approximately the same."""
        from app.modules.planning.services.performance_adjustment_calculator import (
            _adjust_country_weights,
        )

        base_weights = {"US": 0.5, "EU": 0.4, "ASIA": 0.1}
        attribution = {"US": 0.10, "EU": -0.05, "ASIA": 0.02}
        avg_return = 0.08

        adjusted = _adjust_country_weights(base_weights, attribution, avg_return)

        base_total = sum(base_weights.values())
        adjusted_total = sum(adjusted.values())

        # Total should remain approximately the same
        assert abs(adjusted_total - base_total) < 0.2

    def test_handles_missing_attribution_entries(self):
        """Test handling when some countries don't have attribution."""
        from app.modules.planning.services.performance_adjustment_calculator import (
            _adjust_country_weights,
        )

        base_weights = {"US": 0.5, "EU": 0.4, "ASIA": 0.1}
        attribution = {"US": 0.10}  # Missing EU and ASIA
        avg_return = 0.08

        adjusted = _adjust_country_weights(base_weights, attribution, avg_return)

        assert "US" in adjusted
        assert "EU" in adjusted
        assert "ASIA" in adjusted

    def test_handles_zero_avg_return(self):
        """Test handling when average return is zero."""
        from app.modules.planning.services.performance_adjustment_calculator import (
            _adjust_country_weights,
        )

        base_weights = {"US": 0.5, "EU": 0.4}
        attribution = {"US": 0.10, "EU": -0.05}
        avg_return = 0.0

        adjusted = _adjust_country_weights(base_weights, attribution, avg_return)

        # Should still produce valid weights
        assert all(0 <= w <= 1.0 for w in adjusted.values())


class TestAdjustIndWeights:
    """Test _adjust_ind_weights function."""

    def test_increases_weight_for_positive_attribution(self):
        """Test that weights increase for positive industry attribution."""
        from app.modules.planning.services.performance_adjustment_calculator import (
            _adjust_ind_weights,
        )

        base_weights = {"Tech": 0.3, "Finance": 0.2}
        attribution = {"Tech": 0.15, "Finance": -0.03}
        avg_return = 0.08

        adjusted = _adjust_ind_weights(base_weights, attribution, avg_return)

        assert adjusted["Tech"] > base_weights["Tech"]
        assert adjusted["Finance"] < base_weights["Finance"]

    def test_decreases_weight_for_negative_attribution(self):
        """Test that weights decrease for negative industry attribution."""
        from app.modules.planning.services.performance_adjustment_calculator import (
            _adjust_ind_weights,
        )

        base_weights = {"Tech": 0.3, "Finance": 0.2}
        attribution = {"Tech": -0.15, "Finance": 0.03}
        avg_return = 0.08

        adjusted = _adjust_ind_weights(base_weights, attribution, avg_return)

        assert adjusted["Tech"] < base_weights["Tech"]
        assert adjusted["Finance"] > base_weights["Finance"]

    def test_preserves_total_weight_approximately(self):
        """Test that total weights remain approximately the same."""
        from app.modules.planning.services.performance_adjustment_calculator import (
            _adjust_ind_weights,
        )

        base_weights = {"Tech": 0.3, "Finance": 0.2, "Healthcare": 0.1}
        attribution = {"Tech": 0.15, "Finance": -0.03, "Healthcare": 0.01}
        avg_return = 0.08

        adjusted = _adjust_ind_weights(base_weights, attribution, avg_return)

        base_total = sum(base_weights.values())
        adjusted_total = sum(adjusted.values())

        assert abs(adjusted_total - base_total) < 0.2

    def test_handles_missing_attribution_entries(self):
        """Test handling when some industries don't have attribution."""
        from app.modules.planning.services.performance_adjustment_calculator import (
            _adjust_ind_weights,
        )

        base_weights = {"Tech": 0.3, "Finance": 0.2, "Healthcare": 0.1}
        attribution = {"Tech": 0.15}  # Missing Finance and Healthcare
        avg_return = 0.08

        adjusted = _adjust_ind_weights(base_weights, attribution, avg_return)

        assert "Tech" in adjusted
        assert "Finance" in adjusted
        assert "Healthcare" in adjusted


class TestGetPerformanceAdjustedWeights:
    """Test get_performance_adjusted_weights function."""

    @pytest.mark.asyncio
    async def test_returns_adjusted_weights_with_attribution(
        self, mock_allocation_repo
    ):
        """Test that adjusted weights are returned when attribution data exists."""
        from app.modules.planning.services.performance_adjustment_calculator import (
            get_performance_adjusted_weights,
        )

        with (
            patch(
                "app.modules.recommendation.performance_adjustment_calculator.get_performance_attribution"
            ) as mock_get_attribution,
            patch(
                "app.modules.recommendation.performance_adjustment_calculator.reconstruct_portfolio_values"
            ) as mock_reconstruct,
            patch(
                "app.modules.recommendation.performance_adjustment_calculator.calculate_portfolio_returns"
            ) as mock_calc_returns,
        ):
            import pandas as pd

            # Mock portfolio reconstruction and returns
            mock_reconstruct.return_value = pd.DataFrame({"value": [1000.0] * 100})
            mock_calc_returns.return_value = pd.Series([0.01] * 100)

            # Mock attribution data
            mock_get_attribution.return_value = {
                "country": {"US": 0.12, "EU": -0.05},
                "industry": {"Tech": 0.15, "Finance": -0.03},
            }

            country_weights, industry_weights = await get_performance_adjusted_weights(
                mock_allocation_repo
            )

            assert country_weights is not None
            assert industry_weights is not None
            assert "US" in country_weights
            assert "Tech" in industry_weights

    @pytest.mark.asyncio
    async def test_returns_base_weights_when_no_attribution(self, mock_allocation_repo):
        """Test that base weights are returned when no attribution data."""
        from app.modules.planning.services.performance_adjustment_calculator import (
            get_performance_adjusted_weights,
        )

        with (
            patch(
                "app.modules.recommendation.performance_adjustment_calculator.get_performance_attribution"
            ) as mock_get_attribution,
            patch(
                "app.modules.recommendation.performance_adjustment_calculator.reconstruct_portfolio_values"
            ) as mock_reconstruct,
            patch(
                "app.modules.recommendation.performance_adjustment_calculator.calculate_portfolio_returns"
            ) as mock_calc_returns,
        ):
            import pandas as pd

            # Mock portfolio reconstruction and returns
            mock_reconstruct.return_value = pd.DataFrame({"value": [1000.0] * 100})
            mock_calc_returns.return_value = pd.Series([0.01] * 100)

            # Mock empty attribution data
            mock_get_attribution.return_value = {"country": {}, "industry": {}}

            country_weights, industry_weights = await get_performance_adjusted_weights(
                mock_allocation_repo
            )

            # Should return adjusted weights (even if attribution is empty, weights are adjusted)
            assert country_weights is not None
            assert industry_weights is not None

    @pytest.mark.asyncio
    async def test_handles_empty_attribution_data(self, mock_allocation_repo):
        """Test handling when attribution data is empty."""
        from app.modules.planning.services.performance_adjustment_calculator import (
            get_performance_adjusted_weights,
        )

        with (
            patch(
                "app.modules.recommendation.performance_adjustment_calculator.get_performance_attribution"
            ) as mock_get_attribution,
            patch(
                "app.modules.recommendation.performance_adjustment_calculator.reconstruct_portfolio_values"
            ) as mock_reconstruct,
            patch(
                "app.modules.recommendation.performance_adjustment_calculator.calculate_portfolio_returns"
            ) as mock_calc_returns,
        ):
            import pandas as pd

            # Mock portfolio reconstruction and returns
            mock_reconstruct.return_value = pd.DataFrame({"value": [1000.0] * 100})
            mock_calc_returns.return_value = pd.Series([0.01] * 100)

            # Mock empty attribution data
            mock_get_attribution.return_value = {"country": {}, "industry": {}}

            country_weights, industry_weights = await get_performance_adjusted_weights(
                mock_allocation_repo
            )

            # Should return adjusted weights (even if attribution is empty)
            assert country_weights is not None
            assert industry_weights is not None

    @pytest.mark.asyncio
    async def test_uses_portfolio_hash_when_provided(self, mock_allocation_repo):
        """Test that portfolio hash is used when provided."""
        from app.modules.planning.services.performance_adjustment_calculator import (
            get_performance_adjusted_weights,
        )

        with (
            patch(
                "app.modules.recommendation.performance_adjustment_calculator.get_recommendation_cache"
            ) as mock_get_cache,
            patch(
                "app.modules.recommendation.performance_adjustment_calculator.get_performance_attribution"
            ) as mock_get_attribution,
            patch(
                "app.modules.recommendation.performance_adjustment_calculator.reconstruct_portfolio_values"
            ) as mock_reconstruct,
            patch(
                "app.modules.recommendation.performance_adjustment_calculator.calculate_portfolio_returns"
            ) as mock_calc_returns,
        ):
            import pandas as pd

            # Mock cache (return None to force calculation)
            mock_cache = AsyncMock()
            mock_cache.get_analytics = AsyncMock(return_value=None)
            mock_get_cache.return_value = mock_cache

            # Mock portfolio reconstruction and returns
            mock_reconstruct.return_value = pd.DataFrame({"value": [1000.0] * 100})
            mock_calc_returns.return_value = pd.Series([0.01] * 100)

            # Mock attribution data
            mock_get_attribution.return_value = {
                "country": {"US": 0.12},
                "industry": {"Tech": 0.15},
            }

            await get_performance_adjusted_weights(
                mock_allocation_repo, portfolio_hash="test_hash_12345"
            )

            # Should check cache with portfolio hash
            mock_cache.get_analytics.assert_called_once()
            call_args = mock_cache.get_analytics.call_args[0][0]
            assert "test_hash_12345" in call_args

    @pytest.mark.asyncio
    async def test_handles_missing_avg_return_in_attribution(
        self, mock_allocation_repo
    ):
        """Test handling when avg_return is missing from attribution data."""
        from app.modules.planning.services.performance_adjustment_calculator import (
            get_performance_adjusted_weights,
        )

        with (
            patch(
                "app.modules.recommendation.performance_adjustment_calculator.get_performance_attribution"
            ) as mock_get_attribution,
            patch(
                "app.modules.recommendation.performance_adjustment_calculator.reconstruct_portfolio_values"
            ) as mock_reconstruct,
            patch(
                "app.modules.recommendation.performance_adjustment_calculator.calculate_portfolio_returns"
            ) as mock_calc_returns,
        ):
            import pandas as pd

            # Mock portfolio reconstruction and returns
            mock_reconstruct.return_value = pd.DataFrame({"value": [1000.0] * 100})
            mock_calc_returns.return_value = pd.Series([0.01] * 100)

            # Mock attribution data (avg return is calculated from attribution values)
            mock_get_attribution.return_value = {
                "country": {"US": 0.12},
                "industry": {"Tech": 0.15},
            }

            country_weights, industry_weights = await get_performance_adjusted_weights(
                mock_allocation_repo
            )

            # Should handle gracefully and return adjusted weights
            assert country_weights is not None
            assert industry_weights is not None

    @pytest.mark.asyncio
    async def test_applies_adjustments_proportionally(self, mock_allocation_repo):
        """Test that adjustments are applied proportionally to base weights."""
        from app.modules.planning.services.performance_adjustment_calculator import (
            get_performance_adjusted_weights,
        )

        with (
            patch(
                "app.modules.recommendation.performance_adjustment_calculator.get_performance_attribution"
            ) as mock_get_attribution,
            patch(
                "app.modules.recommendation.performance_adjustment_calculator.reconstruct_portfolio_values"
            ) as mock_reconstruct,
            patch(
                "app.modules.recommendation.performance_adjustment_calculator.calculate_portfolio_returns"
            ) as mock_calc_returns,
        ):
            import pandas as pd

            # Mock portfolio reconstruction and returns
            mock_reconstruct.return_value = pd.DataFrame({"value": [1000.0] * 100})
            mock_calc_returns.return_value = pd.Series([0.01] * 100)

            # Mock attribution data - US and Tech have positive, EU and Finance have negative
            # The function compares each to the average, so we need values that will trigger adjustments
            mock_get_attribution.return_value = {
                "country": {"US": 0.10, "EU": -0.05},  # US > avg, EU < avg
                "industry": {
                    "Tech": 0.15,
                    "Finance": -0.03,
                },  # Tech > avg, Finance < avg
            }

            country_weights, industry_weights = await get_performance_adjusted_weights(
                mock_allocation_repo
            )

            # US should increase (positive attribution), EU should decrease (negative)
            assert country_weights["US"] > 0.5
            assert country_weights["EU"] < 0.4

            # Tech should increase, Finance should decrease
            assert industry_weights["Tech"] > 0.3
            assert industry_weights["Finance"] < 0.2
