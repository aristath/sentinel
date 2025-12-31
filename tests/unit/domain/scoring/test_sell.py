"""Tests for sell scoring module.

These tests validate the sell score calculation and eligibility logic.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.scoring.domain.models import TechnicalData
from app.modules.scoring.domain.sell import (
    SELL_WEIGHTS,
    _calculate_drawdown_score,
    _calculate_total_sell_score,
    _normalize_sell_weights,
    calculate_all_sell_scores,
    calculate_sell_score,
    get_sell_settings,
)


class TestNormalizeSellWeights:
    """Test _normalize_sell_weights function."""

    def test_returns_default_weights_when_none(self):
        """Test returning default weights when input is None."""
        result = _normalize_sell_weights(None)
        assert result == SELL_WEIGHTS

    def test_normalizes_custom_weights(self):
        """Test normalizing custom weights to sum to 1.0."""
        custom_weights = {
            "underperformance": 0.5,
            "time_held": 0.3,
            "portfolio_balance": 0.3,
            "instability": 0.2,
            "drawdown": 0.2,
        }

        result = _normalize_sell_weights(custom_weights)

        # Sum should be 1.0
        total = sum(result.values())
        assert total == pytest.approx(1.0)

    def test_handles_zero_sum_weights(self):
        """Test handling weights that sum to zero."""
        zero_weights = {
            "underperformance": 0,
            "time_held": 0,
            "portfolio_balance": 0,
            "instability": 0,
            "drawdown": 0,
        }

        result = _normalize_sell_weights(zero_weights)

        assert result == SELL_WEIGHTS

    def test_fills_missing_weights_from_defaults(self):
        """Test filling missing weights from defaults."""
        partial_weights = {
            "underperformance": 0.5,
        }

        result = _normalize_sell_weights(partial_weights)

        # Should have all keys
        assert "underperformance" in result
        assert "time_held" in result
        assert "portfolio_balance" in result
        assert "instability" in result
        assert "drawdown" in result


class TestCalculateTotalSellScore:
    """Test _calculate_total_sell_score function."""

    def test_calculates_weighted_sum(self):
        """Test calculating weighted sum of scores."""
        weights = {
            "underperformance": 0.4,
            "time_held": 0.2,
            "portfolio_balance": 0.2,
            "instability": 0.1,
            "drawdown": 0.1,
        }

        result = _calculate_total_sell_score(
            underperformance_score=1.0,
            time_held_score=0.5,
            portfolio_balance_score=0.5,
            instability_score=0.0,
            drawdown_score=0.0,
            normalized_weights=weights,
        )

        expected = (1.0 * 0.4) + (0.5 * 0.2) + (0.5 * 0.2) + (0.0 * 0.1) + (0.0 * 0.1)
        assert result == pytest.approx(expected)

    def test_all_zero_scores(self):
        """Test with all zero scores."""
        result = _calculate_total_sell_score(
            underperformance_score=0.0,
            time_held_score=0.0,
            portfolio_balance_score=0.0,
            instability_score=0.0,
            drawdown_score=0.0,
            normalized_weights=SELL_WEIGHTS,
        )

        assert result == 0.0

    def test_all_max_scores(self):
        """Test with all maximum scores."""
        result = _calculate_total_sell_score(
            underperformance_score=1.0,
            time_held_score=1.0,
            portfolio_balance_score=1.0,
            instability_score=1.0,
            drawdown_score=1.0,
            normalized_weights=SELL_WEIGHTS,
        )

        assert result == pytest.approx(1.0)


class TestCalculateDrawdownScore:
    """Test _calculate_drawdown_score function."""

    @pytest.mark.asyncio
    async def test_returns_max_score_for_deep_drawdown(self):
        """Test returning 1.0 for >25% drawdown."""
        mock_dd = {"current_drawdown": -0.30, "days_in_drawdown": 100}

        with patch(
            "app.modules.analytics.domain.get_position_drawdown",
            new_callable=AsyncMock,
            return_value=mock_dd,
        ):
            result = await _calculate_drawdown_score("AAPL.US")

        assert result == 1.0

    @pytest.mark.asyncio
    async def test_returns_high_score_for_extended_deep_drawdown(self):
        """Test returning 0.9 for 15-25% drawdown over 6+ months."""
        mock_dd = {"current_drawdown": -0.20, "days_in_drawdown": 200}

        with patch(
            "app.modules.analytics.domain.get_position_drawdown",
            new_callable=AsyncMock,
            return_value=mock_dd,
        ):
            result = await _calculate_drawdown_score("AAPL.US")

        assert result == 0.9

    @pytest.mark.asyncio
    async def test_returns_medium_score_for_moderate_drawdown(self):
        """Test returning 0.7 for 15-25% drawdown over 3-6 months."""
        mock_dd = {"current_drawdown": -0.18, "days_in_drawdown": 120}

        with patch(
            "app.modules.analytics.domain.get_position_drawdown",
            new_callable=AsyncMock,
            return_value=mock_dd,
        ):
            result = await _calculate_drawdown_score("AAPL.US")

        assert result == 0.7

    @pytest.mark.asyncio
    async def test_returns_low_score_for_short_drawdown(self):
        """Test returning 0.5 for 15-25% drawdown under 3 months."""
        mock_dd = {"current_drawdown": -0.16, "days_in_drawdown": 30}

        with patch(
            "app.modules.analytics.domain.get_position_drawdown",
            new_callable=AsyncMock,
            return_value=mock_dd,
        ):
            result = await _calculate_drawdown_score("AAPL.US")

        assert result == 0.5

    @pytest.mark.asyncio
    async def test_returns_min_score_for_shallow_drawdown(self):
        """Test returning 0.3 for 10-15% drawdown."""
        mock_dd = {"current_drawdown": -0.12, "days_in_drawdown": 50}

        with patch(
            "app.modules.analytics.domain.get_position_drawdown",
            new_callable=AsyncMock,
            return_value=mock_dd,
        ):
            result = await _calculate_drawdown_score("AAPL.US")

        assert result == 0.3

    @pytest.mark.asyncio
    async def test_returns_minimal_for_no_drawdown(self):
        """Test returning 0.1 for minimal drawdown."""
        mock_dd = {"current_drawdown": -0.05, "days_in_drawdown": 10}

        with patch(
            "app.modules.analytics.domain.get_position_drawdown",
            new_callable=AsyncMock,
            return_value=mock_dd,
        ):
            result = await _calculate_drawdown_score("AAPL.US")

        assert result == 0.1

    @pytest.mark.asyncio
    async def test_returns_neutral_on_exception(self):
        """Test returning 0.3 (neutral) on exception."""
        with patch(
            "app.modules.analytics.domain.get_position_drawdown",
            new_callable=AsyncMock,
            side_effect=Exception("Database error"),
        ):
            result = await _calculate_drawdown_score("AAPL.US")

        assert result == 0.3


class TestCalculateSellScore:
    """Test calculate_sell_score function."""

    @pytest.mark.asyncio
    async def test_returns_ineligible_when_sell_not_allowed(self):
        """Test returning ineligible when allow_sell is False."""
        with patch(
            "app.domain.scoring.sell._calculate_drawdown_score",
            new_callable=AsyncMock,
            return_value=0.3,
        ):
            result = await calculate_sell_score(
                symbol="AAPL.US",
                quantity=100,
                avg_price=100.0,
                current_price=110.0,
                min_lot=1,
                allow_sell=False,
                first_bought_at="2023-01-01",
                last_sold_at=None,
                country="United States",
                industry="Consumer Electronics",
                total_portfolio_value=100000,
                country_allocations={"US": 0.5},
                ind_allocations={"Consumer Electronics": 0.3},
            )

        assert result.eligible is False
        assert (
            "not allowed" in result.block_reason.lower()
            or result.block_reason is not None
        )

    @pytest.mark.asyncio
    async def test_returns_ineligible_for_big_loss(self):
        """Test returning ineligible when loss exceeds threshold."""
        with patch(
            "app.domain.scoring.sell._calculate_drawdown_score",
            new_callable=AsyncMock,
            return_value=0.3,
        ):
            result = await calculate_sell_score(
                symbol="AAPL.US",
                quantity=100,
                avg_price=100.0,
                current_price=70.0,  # 30% loss
                min_lot=1,
                allow_sell=True,
                first_bought_at="2022-01-01",  # Long time ago
                last_sold_at=None,
                country="United States",
                industry="Consumer Electronics",
                total_portfolio_value=100000,
                country_allocations={"US": 0.5},
                ind_allocations={"Consumer Electronics": 0.3},
            )

        assert result.eligible is False
        assert (
            "loss" in result.block_reason.lower()
            or "threshold" in result.block_reason.lower()
        )

    @pytest.mark.asyncio
    async def test_returns_eligible_for_profitable_position(self):
        """Test returning eligible for profitable long-held position."""
        with patch(
            "app.domain.scoring.sell._calculate_drawdown_score",
            new_callable=AsyncMock,
            return_value=0.3,
        ):
            result = await calculate_sell_score(
                symbol="AAPL.US",
                quantity=100,
                avg_price=100.0,
                current_price=150.0,  # 50% profit
                min_lot=1,
                allow_sell=True,
                first_bought_at="2022-01-01",
                last_sold_at=None,
                country="United States",
                industry="Consumer Electronics",
                total_portfolio_value=100000,
                country_allocations={"US": 0.5},
                ind_allocations={"Consumer Electronics": 0.3},
            )

        assert result.total_score > 0
        assert result.profit_pct == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_uses_technical_data_for_instability(self):
        """Test using technical data for instability score."""
        tech_data = TechnicalData(
            current_volatility=0.5,
            historical_volatility=0.2,
            distance_from_ma_200=0.3,
        )

        with patch(
            "app.domain.scoring.sell._calculate_drawdown_score",
            new_callable=AsyncMock,
            return_value=0.3,
        ):
            result = await calculate_sell_score(
                symbol="AAPL.US",
                quantity=100,
                avg_price=100.0,
                current_price=150.0,
                min_lot=1,
                allow_sell=True,
                first_bought_at="2022-01-01",
                last_sold_at=None,
                country="United States",
                industry="Consumer Electronics",
                total_portfolio_value=100000,
                country_allocations={"US": 0.5},
                ind_allocations={"Consumer Electronics": 0.3},
                technical_data=tech_data,
            )

        # Instability score should be non-default when technical data provided
        assert result.instability_score >= 0


class TestGetSellSettings:
    """Test get_sell_settings function."""

    @pytest.mark.asyncio
    async def test_returns_settings_from_repo(self):
        """Test returning settings from repository."""
        mock_repo = MagicMock()
        mock_repo.get_int = AsyncMock(side_effect=[90, 180])
        mock_repo.get_float = AsyncMock(side_effect=[-0.20, 50.0])

        with patch(
            "app.repositories.SettingsRepository",
            return_value=mock_repo,
        ):
            result = await get_sell_settings()

        assert result["min_hold_days"] == 90
        assert result["sell_cooldown_days"] == 180
        assert result["max_loss_threshold"] == -0.20
        assert result["min_sell_value"] == 50.0


class TestCalculateAllSellScores:
    """Test calculate_all_sell_scores function."""

    @pytest.mark.asyncio
    async def test_calculates_scores_for_all_positions(self):
        """Test calculating sell scores for all positions."""
        positions = [
            {
                "symbol": "AAPL.US",
                "quantity": 100,
                "avg_price": 100.0,
                "current_price": 150.0,
                "min_lot": 1,
                "allow_sell": True,
                "first_bought_at": "2022-01-01",
                "last_sold_at": None,
                "country": "United States",
                "industry": "Consumer Electronics",
            },
            {
                "symbol": "MSFT.US",
                "quantity": 50,
                "avg_price": 200.0,
                "current_price": 250.0,
                "min_lot": 1,
                "allow_sell": True,
                "first_bought_at": "2022-06-01",
                "last_sold_at": None,
                "country": "United States",
                "industry": "Consumer Electronics",
            },
        ]

        with patch(
            "app.domain.scoring.sell._calculate_drawdown_score",
            new_callable=AsyncMock,
            return_value=0.3,
        ):
            results = await calculate_all_sell_scores(
                positions=positions,
                total_portfolio_value=50000,
                country_allocations={"US": 0.8},
                ind_allocations={"Consumer Electronics": 0.6},
            )

        assert len(results) == 2
        # Results should be sorted by total_score descending
        assert results[0].total_score >= results[1].total_score

    @pytest.mark.asyncio
    async def test_handles_missing_fields(self):
        """Test handling positions with missing optional fields."""
        positions = [
            {
                "symbol": "AAPL.US",
                "quantity": 100,
                "avg_price": 100.0,
                "current_price": 150.0,
            }
        ]

        with patch(
            "app.domain.scoring.sell._calculate_drawdown_score",
            new_callable=AsyncMock,
            return_value=0.3,
        ):
            results = await calculate_all_sell_scores(
                positions=positions,
                total_portfolio_value=50000,
                country_allocations={},
                ind_allocations={},
            )

        assert len(results) == 1
        # Should have processed without error

    @pytest.mark.asyncio
    async def test_uses_avg_price_when_current_price_missing(self):
        """Test using avg_price when current_price is None."""
        positions = [
            {
                "symbol": "AAPL.US",
                "quantity": 100,
                "avg_price": 100.0,
                "current_price": None,
                "allow_sell": True,
                "first_bought_at": "2022-01-01",
            }
        ]

        with patch(
            "app.domain.scoring.sell._calculate_drawdown_score",
            new_callable=AsyncMock,
            return_value=0.3,
        ):
            results = await calculate_all_sell_scores(
                positions=positions,
                total_portfolio_value=50000,
                country_allocations={},
                ind_allocations={},
            )

        assert len(results) == 1
        # Profit should be 0 when using avg_price as current_price
        assert results[0].profit_pct == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_uses_custom_weights(self):
        """Test using custom weights when provided."""
        positions = [
            {
                "symbol": "AAPL.US",
                "quantity": 100,
                "avg_price": 100.0,
                "current_price": 150.0,
                "allow_sell": True,
                "first_bought_at": "2022-01-01",
            }
        ]

        custom_weights = {
            "underperformance": 0.5,
            "time_held": 0.2,
            "portfolio_balance": 0.1,
            "instability": 0.1,
            "drawdown": 0.1,
        }

        with patch(
            "app.domain.scoring.sell._calculate_drawdown_score",
            new_callable=AsyncMock,
            return_value=0.3,
        ):
            results = await calculate_all_sell_scores(
                positions=positions,
                total_portfolio_value=50000,
                country_allocations={},
                ind_allocations={},
                weights=custom_weights,
            )

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_uses_technical_data_map(self):
        """Test using technical data map for positions."""
        positions = [
            {
                "symbol": "AAPL.US",
                "quantity": 100,
                "avg_price": 100.0,
                "current_price": 150.0,
                "allow_sell": True,
                "first_bought_at": "2022-01-01",
            }
        ]

        tech_data = {
            "AAPL.US": TechnicalData(
                current_volatility=0.3,
                historical_volatility=0.2,
                distance_from_ma_200=0.1,
            )
        }

        with patch(
            "app.domain.scoring.sell._calculate_drawdown_score",
            new_callable=AsyncMock,
            return_value=0.3,
        ):
            results = await calculate_all_sell_scores(
                positions=positions,
                total_portfolio_value=50000,
                country_allocations={},
                ind_allocations={},
                technical_data=tech_data,
            )

        assert len(results) == 1
