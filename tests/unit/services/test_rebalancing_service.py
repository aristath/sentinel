"""Tests for rebalancing service.

These tests validate the rebalancing service logic including
trade amount calculations, risk parity sizing, and recommendation building.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCalculateMinTradeAmount:
    """Test minimum trade amount calculation based on transaction costs."""

    def test_standard_fees(self):
        """Test with standard Freedom24 fee structure (€2 + 0.2%)."""
        from app.application.services.rebalancing_service import (
            calculate_min_trade_amount,
        )

        # €2 fixed + 0.2% variable, 1% max cost ratio
        min_amount = calculate_min_trade_amount(2.0, 0.002, 0.01)

        # Expected: 2.0 / (0.01 - 0.002) = 2.0 / 0.008 = 250
        assert min_amount == 250.0

    def test_higher_fixed_cost(self):
        """Test with higher fixed cost."""
        from app.application.services.rebalancing_service import (
            calculate_min_trade_amount,
        )

        min_amount = calculate_min_trade_amount(5.0, 0.002, 0.01)

        # 5.0 / 0.008 = 625
        assert min_amount == 625.0

    def test_lower_max_cost_ratio(self):
        """Test with stricter cost requirement (0.5%)."""
        from app.application.services.rebalancing_service import (
            calculate_min_trade_amount,
        )

        min_amount = calculate_min_trade_amount(2.0, 0.002, 0.005)

        # 2.0 / (0.005 - 0.002) = 2.0 / 0.003 ≈ 666.67
        assert min_amount == pytest.approx(666.67, rel=0.01)

    def test_variable_cost_exceeds_max_ratio(self):
        """Test when variable cost alone exceeds max ratio."""
        from app.application.services.rebalancing_service import (
            calculate_min_trade_amount,
        )

        # Variable cost (1.5%) exceeds max ratio (1%)
        min_amount = calculate_min_trade_amount(2.0, 0.015, 0.01)

        # Should return high minimum (1000)
        assert min_amount == 1000.0

    def test_zero_variable_cost(self):
        """Test with only fixed cost."""
        from app.application.services.rebalancing_service import (
            calculate_min_trade_amount,
        )

        min_amount = calculate_min_trade_amount(3.0, 0.0, 0.01)

        # 3.0 / 0.01 = 300
        assert min_amount == 300.0


class TestCalculateRiskParityAmount:
    """Test risk parity trade amount calculation."""

    def test_average_volatility_average_score(self):
        """Test with average volatility and average score."""
        from app.application.services.rebalancing_service import (
            _calculate_risk_parity_amount,
        )

        # Target volatility is 0.15, stock vol is 0.15, score is 0.5
        amount = _calculate_risk_parity_amount(
            base_trade_amount=1000.0, stock_vol=0.15, total_score=0.5
        )

        # vol_weight = 0.15/0.15 = 1.0
        # score_adj = 1.0 + (0.5 - 0.5) * 0.2 = 1.0
        # result = 1000 * 1.0 * 1.0 = 1000
        assert amount == 1000.0

    def test_high_volatility_reduces_amount(self):
        """Test that high volatility reduces trade amount."""
        from app.application.services.rebalancing_service import (
            _calculate_risk_parity_amount,
        )

        # Higher volatility (0.30) should reduce the amount
        amount = _calculate_risk_parity_amount(
            base_trade_amount=1000.0, stock_vol=0.30, total_score=0.5
        )

        # vol_weight = 0.15/0.30 = 0.5
        assert amount == pytest.approx(500.0, rel=0.01)

    def test_low_volatility_increases_amount(self):
        """Test that low volatility increases trade amount (up to cap)."""
        from app.application.services.rebalancing_service import (
            _calculate_risk_parity_amount,
        )

        # Lower volatility (0.075) should increase amount (capped at 2.0)
        amount = _calculate_risk_parity_amount(
            base_trade_amount=1000.0, stock_vol=0.075, total_score=0.5
        )

        # vol_weight = 0.15/0.075 = 2.0 (at cap)
        assert amount == pytest.approx(2000.0, rel=0.01)

    def test_high_score_increases_amount(self):
        """Test that high score increases trade amount."""
        from app.application.services.rebalancing_service import (
            _calculate_risk_parity_amount,
        )

        amount = _calculate_risk_parity_amount(
            base_trade_amount=1000.0, stock_vol=0.15, total_score=0.8
        )

        # score_adj = 1.0 + (0.8 - 0.5) * 0.2 = 1.06
        assert amount > 1000.0

    def test_low_score_decreases_amount(self):
        """Test that low score decreases trade amount."""
        from app.application.services.rebalancing_service import (
            _calculate_risk_parity_amount,
        )

        amount = _calculate_risk_parity_amount(
            base_trade_amount=1000.0, stock_vol=0.15, total_score=0.2
        )

        # score_adj = 1.0 + (0.2 - 0.5) * 0.2 = 0.94
        assert amount < 1000.0

    def test_very_low_volatility_caps_weight(self):
        """Test that very low volatility caps at MAX_VOL_WEIGHT (2.0)."""
        from app.application.services.rebalancing_service import (
            _calculate_risk_parity_amount,
        )

        # Extremely low volatility that would give weight > 2.0
        amount = _calculate_risk_parity_amount(
            base_trade_amount=1000.0, stock_vol=0.01, total_score=0.5
        )

        # vol_weight should be capped at 2.0
        assert amount == pytest.approx(2000.0, rel=0.01)


class TestCheckPositionCap:
    """Test position cap checking."""

    def test_below_cap_returns_true(self):
        """Test position below cap returns True."""
        from app.application.services.rebalancing_service import _check_position_cap

        context = MagicMock()
        context.positions = {"AAPL.US": 1000}
        context.total_value = 50000

        # Adding 500 to 1000 = 1500 out of 50500 = ~3%
        result = _check_position_cap("AAPL.US", 500, context)

        assert result is True

    def test_at_cap_returns_true(self):
        """Test position exactly at cap returns True."""
        from app.application.services.rebalancing_service import _check_position_cap
        from app.domain.constants import MAX_POSITION_PCT

        context = MagicMock()
        context.positions = {"AAPL.US": 0}
        context.total_value = 100000

        # Calculate amount that would be exactly at cap
        max_amount = MAX_POSITION_PCT * 100000
        result = _check_position_cap("AAPL.US", max_amount, context)

        # At exactly max cap - should be true
        # new_position_value / total_after = max_amount / (100000 + max_amount)
        # Need: max_amount / (100000 + max_amount) <= MAX_POSITION_PCT
        assert result is True

    def test_above_cap_returns_false(self):
        """Test position above cap returns False."""
        from app.application.services.rebalancing_service import _check_position_cap

        context = MagicMock()
        context.positions = {"AAPL.US": 10000}
        context.total_value = 50000

        # Adding 10000 to 10000 = 20000 out of 60000 = 33%
        # MAX_POSITION_PCT is 0.2 (20%), so this exceeds it
        result = _check_position_cap("AAPL.US", 10000, context)

        assert result is False

    def test_new_position_within_cap(self):
        """Test new position (not in portfolio) within cap."""
        from app.application.services.rebalancing_service import _check_position_cap

        context = MagicMock()
        context.positions = {}  # Symbol not in portfolio
        context.total_value = 100000

        # New position of 5000 = 5% of 105000
        result = _check_position_cap("MSFT.US", 5000, context)

        assert result is True

    def test_zero_total_value(self):
        """Test with zero total value (edge case)."""
        from app.application.services.rebalancing_service import _check_position_cap

        context = MagicMock()
        context.positions = {}
        context.total_value = 0

        # Any trade when total is 0 would be 100% of new portfolio
        result = _check_position_cap("AAPL.US", 1000, context)

        # 1000 / 1000 = 100% > MAX_POSITION_PCT
        assert result is False


class TestCalculateFinalScore:
    """Test final priority score calculation."""

    def test_high_quality_and_opportunity(self):
        """Test with high quality and opportunity scores."""
        from app.application.services.rebalancing_service import _calculate_final_score

        score = _calculate_final_score(
            quality_score=0.9,
            opportunity_score=0.8,
            analyst_score=0.7,
            score_change=3.0,
        )

        # base_score = 0.9*0.35 + 0.8*0.35 + 0.7*0.05 = 0.315 + 0.28 + 0.035 = 0.63
        # normalized_score_change = (3.0 + 5) / 10 = 0.8
        # final = 0.63 * 0.75 + 0.8 * 0.25 = 0.4725 + 0.2 = 0.6725
        assert score == pytest.approx(0.6725, abs=0.001)

    def test_low_scores(self):
        """Test with low scores."""
        from app.application.services.rebalancing_service import _calculate_final_score

        score = _calculate_final_score(
            quality_score=0.3,
            opportunity_score=0.2,
            analyst_score=0.4,
            score_change=-2.0,
        )

        # All scores are low, result should be low
        assert score < 0.5

    def test_negative_score_change_clamped(self):
        """Test that very negative score change is clamped to 0."""
        from app.application.services.rebalancing_service import _calculate_final_score

        score = _calculate_final_score(
            quality_score=0.5,
            opportunity_score=0.5,
            analyst_score=0.5,
            score_change=-10.0,  # Very negative
        )

        # normalized_score_change = max(0, min(1, (-10 + 5) / 10)) = max(0, -0.5) = 0
        # base_score = 0.5*0.35 + 0.5*0.35 + 0.5*0.05 = 0.375
        # final = 0.375 * 0.75 + 0 * 0.25 = 0.28125
        assert score == pytest.approx(0.28125, abs=0.001)

    def test_high_score_change_clamped(self):
        """Test that very high score change is clamped to 1."""
        from app.application.services.rebalancing_service import _calculate_final_score

        score = _calculate_final_score(
            quality_score=0.5,
            opportunity_score=0.5,
            analyst_score=0.5,
            score_change=10.0,  # Very high
        )

        # normalized_score_change = min(1, (10 + 5) / 10) = min(1, 1.5) = 1
        # base_score = 0.375
        # final = 0.375 * 0.75 + 1 * 0.25 = 0.28125 + 0.25 = 0.53125
        assert score == pytest.approx(0.53125, abs=0.001)


class TestBuildReasonString:
    """Test reason string building for recommendations."""

    def test_high_quality_only(self):
        """Test reason with high quality score only."""
        from app.application.services.rebalancing_service import _build_reason_string

        reason = _build_reason_string(
            quality_score=0.8, opportunity_score=0.5, score_change=0.2, multiplier=1.0
        )

        assert "high quality" in reason
        assert "buy opportunity" not in reason

    def test_high_opportunity_only(self):
        """Test reason with high opportunity score only."""
        from app.application.services.rebalancing_service import _build_reason_string

        reason = _build_reason_string(
            quality_score=0.5, opportunity_score=0.8, score_change=0.2, multiplier=1.0
        )

        assert "buy opportunity" in reason
        assert "high quality" not in reason

    def test_both_high_scores(self):
        """Test reason with both high scores."""
        from app.application.services.rebalancing_service import _build_reason_string

        reason = _build_reason_string(
            quality_score=0.8, opportunity_score=0.8, score_change=0.2, multiplier=1.0
        )

        assert "high quality" in reason
        assert "buy opportunity" in reason

    def test_includes_score_change(self):
        """Test that significant score change is included."""
        from app.application.services.rebalancing_service import _build_reason_string

        reason = _build_reason_string(
            quality_score=0.5, opportunity_score=0.5, score_change=1.5, multiplier=1.0
        )

        assert "↑1.5 portfolio" in reason

    def test_includes_multiplier(self):
        """Test that non-default multiplier is included."""
        from app.application.services.rebalancing_service import _build_reason_string

        reason = _build_reason_string(
            quality_score=0.5, opportunity_score=0.5, score_change=0.2, multiplier=1.5
        )

        assert "1.5x mult" in reason

    def test_default_reason_when_nothing_special(self):
        """Test that 'good score' is returned when no criteria met."""
        from app.application.services.rebalancing_service import _build_reason_string

        reason = _build_reason_string(
            quality_score=0.5, opportunity_score=0.5, score_change=0.2, multiplier=1.0
        )

        assert reason == "good score"


class TestBuildSellReasonString:
    """Test sell reason string building."""

    def test_profit_reason(self):
        """Test reason includes profit when profit_pct > 30%."""
        from app.application.services.rebalancing_service import (
            _build_sell_reason_string,
        )

        mock_score = MagicMock()
        mock_score.profit_pct = 0.50  # 50% profit
        mock_score.underperformance_score = 0.3
        mock_score.time_held_score = 0.3
        mock_score.portfolio_balance_score = 0.3
        mock_score.instability_score = 0.3
        mock_score.total_score = 0.7

        reason = _build_sell_reason_string(mock_score)

        assert "profit 50.0%" in reason

    def test_loss_reason(self):
        """Test reason includes loss when profit_pct < 0."""
        from app.application.services.rebalancing_service import (
            _build_sell_reason_string,
        )

        mock_score = MagicMock()
        mock_score.profit_pct = -0.10  # 10% loss
        mock_score.underperformance_score = 0.3
        mock_score.time_held_score = 0.3
        mock_score.portfolio_balance_score = 0.3
        mock_score.instability_score = 0.3
        mock_score.total_score = 0.5

        reason = _build_sell_reason_string(mock_score)

        assert "loss -10.0%" in reason

    def test_underperforming_reason(self):
        """Test reason includes underperforming when score >= 0.7."""
        from app.application.services.rebalancing_service import (
            _build_sell_reason_string,
        )

        mock_score = MagicMock()
        mock_score.profit_pct = 0.15  # Not trigger profit or loss
        mock_score.underperformance_score = 0.8  # High underperformance
        mock_score.time_held_score = 0.3
        mock_score.portfolio_balance_score = 0.3
        mock_score.instability_score = 0.3
        mock_score.total_score = 0.6

        reason = _build_sell_reason_string(mock_score)

        assert "underperforming" in reason

    def test_time_held_reason(self):
        """Test reason includes time held when score >= 0.8."""
        from app.application.services.rebalancing_service import (
            _build_sell_reason_string,
        )

        mock_score = MagicMock()
        mock_score.profit_pct = 0.15
        mock_score.underperformance_score = 0.3
        mock_score.time_held_score = 0.85  # High time held
        mock_score.days_held = 365
        mock_score.portfolio_balance_score = 0.3
        mock_score.instability_score = 0.3
        mock_score.total_score = 0.6

        reason = _build_sell_reason_string(mock_score)

        assert "held 365 days" in reason

    def test_overweight_reason(self):
        """Test reason includes overweight when portfolio_balance_score >= 0.7."""
        from app.application.services.rebalancing_service import (
            _build_sell_reason_string,
        )

        mock_score = MagicMock()
        mock_score.profit_pct = 0.15
        mock_score.underperformance_score = 0.3
        mock_score.time_held_score = 0.3
        mock_score.portfolio_balance_score = 0.8  # High balance score
        mock_score.instability_score = 0.3
        mock_score.total_score = 0.6

        reason = _build_sell_reason_string(mock_score)

        assert "overweight" in reason

    def test_instability_reason(self):
        """Test reason includes instability when score >= 0.6."""
        from app.application.services.rebalancing_service import (
            _build_sell_reason_string,
        )

        mock_score = MagicMock()
        mock_score.profit_pct = 0.15
        mock_score.underperformance_score = 0.3
        mock_score.time_held_score = 0.3
        mock_score.portfolio_balance_score = 0.3
        mock_score.instability_score = 0.7  # High instability
        mock_score.total_score = 0.6

        reason = _build_sell_reason_string(mock_score)

        assert "high instability" in reason

    def test_always_includes_sell_score(self):
        """Test that sell score is always included."""
        from app.application.services.rebalancing_service import (
            _build_sell_reason_string,
        )

        mock_score = MagicMock()
        mock_score.profit_pct = 0.15
        mock_score.underperformance_score = 0.3
        mock_score.time_held_score = 0.3
        mock_score.portfolio_balance_score = 0.3
        mock_score.instability_score = 0.3
        mock_score.total_score = 0.65

        reason = _build_sell_reason_string(mock_score)

        assert "sell score: 0.65" in reason


class TestApplyRebalancingBandFilter:
    """Test rebalancing band filter.

    The function filters sell candidates to only keep those where
    the geography or industry is overweight beyond the rebalance band.
    """

    def test_filters_small_deviations(self):
        """Test that small deviations are filtered out."""
        from app.application.services.rebalancing_service import (
            _apply_rebalancing_band_filter,
        )

        # Score object with symbol
        mock_score = MagicMock()
        mock_score.symbol = "SAP.EU"

        # Position dict that matches the score
        position_dicts = [{"symbol": "SAP.EU", "geography": "EU", "industry": "Tech"}]

        # Current 33% EU, target 35% - only 2% over, within 5% band
        geo_allocations = {"EU": 0.33}
        target_geo_weights = {"EU": 0.35}
        ind_allocations = {"Tech": 0.5}
        target_ind_weights = {"Tech": 0.5}

        filtered = _apply_rebalancing_band_filter(
            [mock_score],
            position_dicts,
            geo_allocations,
            ind_allocations,
            target_geo_weights,
            target_ind_weights,
        )

        # Within band - should be filtered out
        assert len(filtered) == 0

    def test_keeps_large_geo_deviations(self):
        """Test that large geography deviations are kept."""
        from app.application.services.rebalancing_service import (
            _apply_rebalancing_band_filter,
        )

        mock_score = MagicMock()
        mock_score.symbol = "AAPL.US"

        position_dicts = [{"symbol": "AAPL.US", "geography": "US", "industry": "Tech"}]

        # US at 50% with target 35% - 15% over, exceeds 5% band
        geo_allocations = {"US": 0.50}
        target_geo_weights = {"US": 0.35}
        ind_allocations = {"Tech": 0.5}
        target_ind_weights = {"Tech": 0.5}

        filtered = _apply_rebalancing_band_filter(
            [mock_score],
            position_dicts,
            geo_allocations,
            ind_allocations,
            target_geo_weights,
            target_ind_weights,
        )

        assert len(filtered) == 1
        assert filtered[0].symbol == "AAPL.US"

    def test_skips_if_no_matching_position(self):
        """Test that scores without matching positions are skipped."""
        from app.application.services.rebalancing_service import (
            _apply_rebalancing_band_filter,
        )

        mock_score = MagicMock()
        mock_score.symbol = "MISSING.US"

        position_dicts = [{"symbol": "OTHER.US", "geography": "US", "industry": "Tech"}]

        geo_allocations = {"US": 0.50}
        target_geo_weights = {"US": 0.35}
        ind_allocations = {}
        target_ind_weights = {}

        filtered = _apply_rebalancing_band_filter(
            [mock_score],
            position_dicts,
            geo_allocations,
            ind_allocations,
            target_geo_weights,
            target_ind_weights,
        )

        # No matching position - skipped
        assert len(filtered) == 0

    def test_industry_deviation_triggers_inclusion(self):
        """Test that large industry deviation triggers inclusion."""
        from app.application.services.rebalancing_service import (
            _apply_rebalancing_band_filter,
        )

        mock_score = MagicMock()
        mock_score.symbol = "XOM.US"

        position_dicts = [{"symbol": "XOM.US", "geography": "US", "industry": "Energy"}]

        # No geo deviation
        geo_allocations = {"US": 0.35}
        target_geo_weights = {"US": 0.35}
        # Large industry deviation: Energy at 30% with target 10%
        ind_allocations = {"Energy": 0.30}
        target_ind_weights = {"Energy": 0.10}

        filtered = _apply_rebalancing_band_filter(
            [mock_score],
            position_dicts,
            geo_allocations,
            ind_allocations,
            target_geo_weights,
            target_ind_weights,
        )

        # Industry 20% over target > 5% band
        assert len(filtered) == 1


class TestConvertCachedRecommendations:
    """Test converting cached recommendations to Recommendation objects."""

    @pytest.mark.asyncio
    async def test_converts_basic_recommendation(self):
        """Test converting a basic cached recommendation."""
        from app.application.services.rebalancing_service import (
            _convert_cached_recommendations,
        )
        from app.domain.value_objects.trade_side import TradeSide

        cached = [
            {
                "symbol": "AAPL.US",
                "name": "Apple Inc",
                "quantity": 10,
                "current_price": 150.0,
                "amount": 1500.0,
                "reason": "high quality",
                "geography": "US",
                "industry": "Technology",
                "currency": "USD",
                "priority": 0.85,
                "current_portfolio_score": 70.0,
                "new_portfolio_score": 72.5,
            }
        ]

        result = await _convert_cached_recommendations(cached, limit=5)

        assert len(result) == 1
        rec = result[0]
        assert rec.symbol == "AAPL.US"
        assert rec.name == "Apple Inc"
        assert rec.side == TradeSide.BUY
        assert rec.quantity == 10
        assert rec.estimated_price == 150.0
        assert rec.estimated_value == 1500.0

    @pytest.mark.asyncio
    async def test_respects_limit(self):
        """Test that limit is respected."""
        from app.application.services.rebalancing_service import (
            _convert_cached_recommendations,
        )

        cached = [
            {
                "symbol": f"STOCK{i}.US",
                "name": f"Stock {i}",
                "reason": "test",
                "geography": "US",
                "currency": "USD",
                "quantity": 1,  # Domain model requires positive quantity
                "current_price": 100.0,  # Domain model requires positive price
                "amount": 100.0,
            }
            for i in range(10)
        ]

        result = await _convert_cached_recommendations(cached, limit=3)

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_uses_default_currency_when_missing(self):
        """Test that EUR is used as default when currency is missing."""
        from app.application.services.rebalancing_service import (
            _convert_cached_recommendations,
        )

        cached = [
            {
                "symbol": "MSFT.US",
                "name": "Microsoft",
                "reason": "good score",
                "geography": "US",
                "quantity": 5,
                "current_price": 100.0,  # Domain model requires positive price
                "amount": 500.0,
                # No currency specified
            }
        ]

        result = await _convert_cached_recommendations(cached, limit=5)

        assert len(result) == 1
        rec = result[0]
        # Default currency should be EUR (Currency enum)
        from app.domain.value_objects.currency import Currency

        assert rec.currency == Currency.EUR


class TestPrepareCacheData:
    """Test cache data preparation.

    _prepare_cache_data expects a list of dicts with specific keys.
    """

    def test_prepares_candidate_data(self):
        """Test preparing candidate data for cache."""
        from app.application.services.rebalancing_service import _prepare_cache_data

        # The function expects a list of dicts, not objects
        mock_new_score = MagicMock()
        mock_new_score.total = 72.5

        candidate = {
            "symbol": "AAPL.US",
            "name": "Apple Inc",
            "trade_value": 1400.0,
            "final_score": 0.85,
            "reason": "high quality",
            "geography": "US",
            "industry": "Technology",
            "price": 150.0,
            "quantity": 10,
            "new_score": mock_new_score,
            "score_change": 2.5,
        }

        result = _prepare_cache_data([candidate])

        assert len(result) == 1
        data = result[0]
        assert data["symbol"] == "AAPL.US"
        assert data["name"] == "Apple Inc"
        assert data["amount"] == 1400.0
        assert data["quantity"] == 10
        assert data["priority"] == 0.85
        assert data["new_portfolio_score"] == 72.5
        assert data["score_change"] == 2.5


class TestPrepareSellCacheData:
    """Test sell cache data preparation.

    _prepare_sell_cache_data expects:
    - eligible_sells: list of score objects with .symbol, .suggested_sell_quantity,
      .suggested_sell_value, .total_score
    - position_dicts: list of position dicts
    """

    def test_prepares_sell_data(self):
        """Test preparing sell recommendation data for cache."""
        from app.application.services.rebalancing_service import (
            _prepare_sell_cache_data,
        )

        mock_score = MagicMock()
        mock_score.symbol = "AAPL.US"
        mock_score.suggested_sell_quantity = 5
        mock_score.suggested_sell_value = 700.0
        mock_score.total_score = 0.65

        position_dicts = [
            {
                "symbol": "AAPL.US",
                "name": "Apple Inc",
                "current_price": 155.0,
                "currency": "USD",
            }
        ]

        result = _prepare_sell_cache_data([mock_score], position_dicts)

        assert len(result) == 1
        data = result[0]
        assert data["symbol"] == "AAPL.US"
        assert data["name"] == "Apple Inc"
        assert data["quantity"] == 5
        assert data["estimated_value"] == 700.0
        assert data["estimated_price"] == 155.0
        assert data["priority"] == 0.65

    def test_skips_if_no_matching_position(self):
        """Test that scores without matching positions are skipped."""
        from app.application.services.rebalancing_service import (
            _prepare_sell_cache_data,
        )

        mock_score = MagicMock()
        mock_score.symbol = "MSFT.US"
        mock_score.suggested_sell_quantity = 3
        mock_score.suggested_sell_value = 950.0
        mock_score.total_score = 0.5

        position_dicts = [
            {
                "symbol": "AAPL.US",
                "name": "Apple",
                "current_price": 155.0,
                "currency": "USD",
            }
        ]  # MSFT not in list

        result = _prepare_sell_cache_data([mock_score], position_dicts)

        # No matching position - skipped
        assert len(result) == 0

    def test_uses_avg_price_as_fallback(self):
        """Test that avg_price is used if current_price is missing."""
        from app.application.services.rebalancing_service import (
            _prepare_sell_cache_data,
        )

        mock_score = MagicMock()
        mock_score.symbol = "AAPL.US"
        mock_score.suggested_sell_quantity = 5
        mock_score.suggested_sell_value = 700.0
        mock_score.total_score = 0.65

        position_dicts = [
            {
                "symbol": "AAPL.US",
                "name": "Apple Inc",
                "avg_price": 140.0,  # No current_price
                "currency": "USD",
            }
        ]

        result = _prepare_sell_cache_data([mock_score], position_dicts)

        assert len(result) == 1
        data = result[0]
        assert data["estimated_price"] == 140.0


class TestGetStockVolatility:
    """Test stock volatility retrieval."""

    @pytest.mark.asyncio
    async def test_returns_volatility_from_metrics(self):
        """Test returning volatility from risk metrics."""
        from app.application.services.rebalancing_service import _get_stock_volatility

        mock_metrics = {"volatility": 0.25}

        with patch(
            "app.domain.analytics.get_position_risk_metrics",
            new_callable=AsyncMock,
            return_value=mock_metrics,
        ):
            result = await _get_stock_volatility("AAPL.US")

        assert result == 0.25

    @pytest.mark.asyncio
    async def test_returns_default_on_exception(self):
        """Test returning default volatility on exception."""
        from app.application.services.rebalancing_service import (
            DEFAULT_VOLATILITY,
            _get_stock_volatility,
        )

        with patch(
            "app.domain.analytics.get_position_risk_metrics",
            new_callable=AsyncMock,
            side_effect=Exception("Database error"),
        ):
            result = await _get_stock_volatility("AAPL.US")

        assert result == DEFAULT_VOLATILITY

    @pytest.mark.asyncio
    async def test_returns_default_when_volatility_missing(self):
        """Test returning default when volatility key missing."""
        from app.application.services.rebalancing_service import (
            DEFAULT_VOLATILITY,
            _get_stock_volatility,
        )

        mock_metrics = {"other_metric": 0.5}  # No volatility key

        with patch(
            "app.domain.analytics.get_position_risk_metrics",
            new_callable=AsyncMock,
            return_value=mock_metrics,
        ):
            result = await _get_stock_volatility("AAPL.US")

        assert result == DEFAULT_VOLATILITY


class TestBuildAllocationMaps:
    """Test allocation map building."""

    def test_builds_geography_allocations(self):
        """Test building geography allocation map."""
        from app.application.services.rebalancing_service import _build_allocation_maps

        position_dicts = [
            {"geography": "US", "industry": "Tech", "market_value_eur": 5000},
            {"geography": "US", "industry": "Finance", "market_value_eur": 3000},
            {"geography": "EU", "industry": "Tech", "market_value_eur": 2000},
        ]

        geo, ind = _build_allocation_maps(position_dicts, 10000)

        assert geo["US"] == pytest.approx(0.8)  # 8000/10000
        assert geo["EU"] == pytest.approx(0.2)  # 2000/10000

    def test_builds_industry_allocations(self):
        """Test building industry allocation map."""
        from app.application.services.rebalancing_service import _build_allocation_maps

        position_dicts = [
            {"geography": "US", "industry": "Tech", "market_value_eur": 6000},
            {"geography": "EU", "industry": "Finance", "market_value_eur": 4000},
        ]

        geo, ind = _build_allocation_maps(position_dicts, 10000)

        assert ind["Tech"] == pytest.approx(0.6)
        assert ind["Finance"] == pytest.approx(0.4)

    def test_handles_missing_geography(self):
        """Test handling positions with missing geography."""
        from app.application.services.rebalancing_service import _build_allocation_maps

        position_dicts = [
            {"geography": "US", "industry": "Tech", "market_value_eur": 5000},
            {"geography": None, "industry": "Finance", "market_value_eur": 5000},
        ]

        geo, ind = _build_allocation_maps(position_dicts, 10000)

        assert "US" in geo
        assert geo["US"] == pytest.approx(0.5)
        # None geography should not be in the map
        assert None not in geo

    def test_handles_missing_industry(self):
        """Test handling positions with missing industry."""
        from app.application.services.rebalancing_service import _build_allocation_maps

        position_dicts = [
            {"geography": "US", "industry": None, "market_value_eur": 5000},
            {"geography": "EU", "industry": "Tech", "market_value_eur": 5000},
        ]

        geo, ind = _build_allocation_maps(position_dicts, 10000)

        assert "Tech" in ind
        assert ind["Tech"] == pytest.approx(0.5)
        assert None not in ind

    def test_handles_missing_market_value(self):
        """Test handling positions with missing market value."""
        from app.application.services.rebalancing_service import _build_allocation_maps

        position_dicts = [
            {"geography": "US", "industry": "Tech", "market_value_eur": None},
            {"geography": "EU", "industry": "Finance", "market_value_eur": 10000},
        ]

        geo, ind = _build_allocation_maps(position_dicts, 10000)

        assert geo["US"] == pytest.approx(0.0)
        assert geo["EU"] == pytest.approx(1.0)


class TestGetTargetAllocations:
    """Test target allocation retrieval."""

    @pytest.mark.asyncio
    async def test_extracts_geography_allocations(self):
        """Test extracting geography allocations from repo."""
        from app.application.services.rebalancing_service import _get_target_allocations

        mock_repo = AsyncMock()
        mock_repo.get_all = AsyncMock(
            return_value={
                "geography:US": 0.35,
                "geography:EU": 0.35,
                "geography:OTHER": 0.30,
                "industry:Tech": 0.5,
            }
        )

        geo, ind = await _get_target_allocations(mock_repo)

        assert geo["US"] == 0.35
        assert geo["EU"] == 0.35
        assert geo["OTHER"] == 0.30

    @pytest.mark.asyncio
    async def test_extracts_industry_allocations(self):
        """Test extracting industry allocations from repo."""
        from app.application.services.rebalancing_service import _get_target_allocations

        mock_repo = AsyncMock()
        mock_repo.get_all = AsyncMock(
            return_value={
                "geography:US": 0.5,
                "industry:Tech": 0.4,
                "industry:Finance": 0.3,
                "industry:Energy": 0.3,
            }
        )

        geo, ind = await _get_target_allocations(mock_repo)

        assert ind["Tech"] == 0.4
        assert ind["Finance"] == 0.3
        assert ind["Energy"] == 0.3

    @pytest.mark.asyncio
    async def test_handles_empty_allocations(self):
        """Test handling empty allocation repository."""
        from app.application.services.rebalancing_service import _get_target_allocations

        mock_repo = AsyncMock()
        mock_repo.get_all = AsyncMock(return_value={})

        geo, ind = await _get_target_allocations(mock_repo)

        assert geo == {}
        assert ind == {}
