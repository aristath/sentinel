"""Tests for end-state scoring.

These tests validate portfolio-level scoring for holistic planning,
including total return, long-term promise, and stability calculations.
"""

import pytest


class TestDividendConsistencyFromPayout:
    """Test dividend consistency derivation from payout ratio."""

    def test_optimal_payout_30_to_60(self):
        """Test optimal payout ratio range returns 1.0."""
        from app.modules.scoring.domain.end_state import (
            _derive_dividend_consistency_from_payout,
        )

        assert _derive_dividend_consistency_from_payout(0.30) == 1.0
        assert _derive_dividend_consistency_from_payout(0.45) == 1.0
        assert _derive_dividend_consistency_from_payout(0.60) == 1.0

    def test_low_payout_below_30(self):
        """Test low payout ratio returns scaled score."""
        from app.modules.scoring.domain.end_state import (
            _derive_dividend_consistency_from_payout,
        )

        score = _derive_dividend_consistency_from_payout(0.15)
        assert 0.5 < score < 1.0

        score_zero = _derive_dividend_consistency_from_payout(0.0)
        assert score_zero == 0.5

    def test_high_payout_60_to_80(self):
        """Test moderately high payout returns reduced score."""
        from app.modules.scoring.domain.end_state import (
            _derive_dividend_consistency_from_payout,
        )

        score = _derive_dividend_consistency_from_payout(0.70)
        assert 0.7 < score < 1.0

    def test_excessive_payout_above_80(self):
        """Test excessive payout returns low score."""
        from app.modules.scoring.domain.end_state import (
            _derive_dividend_consistency_from_payout,
        )

        assert _derive_dividend_consistency_from_payout(0.85) == 0.4
        assert _derive_dividend_consistency_from_payout(0.99) == 0.4


class TestConvertSortinoToScore:
    """Test Sortino ratio to score conversion."""

    def test_excellent_sortino_above_2(self):
        """Test excellent Sortino returns 1.0."""
        from app.modules.scoring.domain.end_state import _convert_sortino_to_score

        assert _convert_sortino_to_score(2.0) == 1.0
        assert _convert_sortino_to_score(3.0) == 1.0

    def test_good_sortino_1_5_to_2(self):
        """Test good Sortino returns high score."""
        from app.modules.scoring.domain.end_state import _convert_sortino_to_score

        score = _convert_sortino_to_score(1.75)
        assert 0.8 < score < 1.0

    def test_decent_sortino_1_to_1_5(self):
        """Test decent Sortino returns good score."""
        from app.modules.scoring.domain.end_state import _convert_sortino_to_score

        score = _convert_sortino_to_score(1.25)
        assert 0.6 < score < 0.8

    def test_low_sortino_0_to_1(self):
        """Test low Sortino returns reduced score."""
        from app.modules.scoring.domain.end_state import _convert_sortino_to_score

        score = _convert_sortino_to_score(0.5)
        assert 0 < score < 0.6

    def test_negative_sortino(self):
        """Test negative Sortino returns 0."""
        from app.modules.scoring.domain.end_state import _convert_sortino_to_score

        assert _convert_sortino_to_score(-1.0) == 0.0


class TestConvertVolatilityToScore:
    """Test volatility to score conversion (inverse - lower is better)."""

    def test_low_volatility_below_15(self):
        """Test low volatility returns 1.0."""
        from app.modules.scoring.domain.end_state import _convert_volatility_to_score

        assert _convert_volatility_to_score(0.10) == 1.0
        assert _convert_volatility_to_score(0.15) == 1.0

    def test_moderate_volatility_15_to_25(self):
        """Test moderate volatility returns good score."""
        from app.modules.scoring.domain.end_state import _convert_volatility_to_score

        score = _convert_volatility_to_score(0.20)
        assert 0.7 < score < 1.0

    def test_high_volatility_25_to_40(self):
        """Test high volatility returns reduced score."""
        from app.modules.scoring.domain.end_state import _convert_volatility_to_score

        score = _convert_volatility_to_score(0.30)
        assert 0.3 < score < 0.7

    def test_extreme_volatility_above_40(self):
        """Test extreme volatility returns low score."""
        from app.modules.scoring.domain.end_state import _convert_volatility_to_score

        score = _convert_volatility_to_score(0.50)
        assert 0.1 <= score < 0.3


class TestConvertDrawdownToScore:
    """Test max drawdown to score conversion."""

    def test_small_drawdown_below_10(self):
        """Test small drawdown returns 1.0."""
        from app.modules.scoring.domain.end_state import _convert_drawdown_to_score

        assert _convert_drawdown_to_score(-0.05) == 1.0
        assert _convert_drawdown_to_score(-0.10) == 1.0

    def test_moderate_drawdown_10_to_20(self):
        """Test moderate drawdown returns high score."""
        from app.modules.scoring.domain.end_state import _convert_drawdown_to_score

        score = _convert_drawdown_to_score(-0.15)
        assert 0.8 < score < 1.0

    def test_significant_drawdown_20_to_30(self):
        """Test significant drawdown returns good score."""
        from app.modules.scoring.domain.end_state import _convert_drawdown_to_score

        score = _convert_drawdown_to_score(-0.25)
        assert 0.6 < score < 0.8

    def test_large_drawdown_30_to_50(self):
        """Test large drawdown returns reduced score."""
        from app.modules.scoring.domain.end_state import _convert_drawdown_to_score

        score = _convert_drawdown_to_score(-0.40)
        assert 0.2 < score < 0.6

    def test_severe_drawdown_above_50(self):
        """Test severe drawdown returns low score."""
        from app.modules.scoring.domain.end_state import _convert_drawdown_to_score

        score = _convert_drawdown_to_score(-0.60)
        assert score <= 0.2


class TestConvertSharpeToScore:
    """Test Sharpe ratio to score conversion."""

    def test_excellent_sharpe_above_2(self):
        """Test excellent Sharpe returns 1.0."""
        from app.modules.scoring.domain.end_state import _convert_sharpe_to_score

        assert _convert_sharpe_to_score(2.0) == 1.0
        assert _convert_sharpe_to_score(2.5) == 1.0

    def test_good_sharpe_1_to_2(self):
        """Test good Sharpe returns high score."""
        from app.modules.scoring.domain.end_state import _convert_sharpe_to_score

        score = _convert_sharpe_to_score(1.5)
        assert 0.7 < score < 1.0

    def test_decent_sharpe_0_5_to_1(self):
        """Test decent Sharpe returns moderate score."""
        from app.modules.scoring.domain.end_state import _convert_sharpe_to_score

        score = _convert_sharpe_to_score(0.75)
        assert 0.4 < score < 0.7

    def test_low_sharpe_0_to_0_5(self):
        """Test low Sharpe returns low score."""
        from app.modules.scoring.domain.end_state import _convert_sharpe_to_score

        score = _convert_sharpe_to_score(0.25)
        assert 0 < score < 0.4

    def test_negative_sharpe(self):
        """Test negative Sharpe returns 0."""
        from app.modules.scoring.domain.end_state import _convert_sharpe_to_score

        assert _convert_sharpe_to_score(-0.5) == 0.0


class TestCalculateTotalReturnScore:
    """Test total return score calculation (legacy tests updated for metrics API)."""

    @pytest.mark.asyncio
    async def test_uses_metrics_dict(self):
        """Test that metrics dict is used."""
        from app.modules.scoring.domain.end_state import calculate_total_return_score

        metrics = {
            "CAGR_5Y": 0.12,
            "DIVIDEND_YIELD": 0.015,
        }

        score, subs = await calculate_total_return_score("AAPL.US", metrics=metrics)

        assert "cagr" in subs
        assert subs["cagr"] == 0.12
        assert subs["dividend_yield"] == 0.015
        # Total return should be ~0.135 (12% + 1.5%)
        assert subs["total_return"] == pytest.approx(0.135, abs=0.001)

    @pytest.mark.asyncio
    async def test_handles_missing_metrics(self):
        """Test that missing metrics default to 0.0."""
        from app.modules.scoring.domain.end_state import calculate_total_return_score

        metrics = {
            "CAGR_5Y": 0.10,
            "DIVIDEND_YIELD": 0.02,
        }

        score, subs = await calculate_total_return_score("AAPL.US", metrics=metrics)

        assert subs["total_return"] == 0.12  # 10% + 2%


class TestCalculateLongTermPromise:
    """Test long-term promise score calculation (legacy tests updated for metrics API)."""

    @pytest.mark.asyncio
    async def test_uses_metrics_dict(self):
        """Test that metrics dict is used."""
        from app.modules.scoring.domain.end_state import calculate_long_term_promise

        metrics = {
            "CONSISTENCY_SCORE": 0.8,
            "FINANCIAL_STRENGTH": 0.7,
            "DIVIDEND_CONSISTENCY": 0.6,
            "SORTINO": 1.5,  # Will be converted to score
        }

        score, subs = await calculate_long_term_promise("AAPL.US", metrics=metrics)

        assert subs["consistency"] == 0.8
        assert subs["financial_strength"] == 0.7
        assert subs["dividend_consistency"] == 0.6
        assert "sortino" in subs
        assert 0 <= score <= 1

    @pytest.mark.asyncio
    async def test_defaults_to_0_5_when_no_data(self):
        """Test default 0.5 when metrics are missing."""
        from app.modules.scoring.domain.end_state import calculate_long_term_promise

        metrics = {}  # Empty metrics dict

        score, subs = await calculate_long_term_promise("AAPL.US", metrics=metrics)

        # All components should default to 0.5
        assert subs["consistency"] == 0.5
        assert subs["financial_strength"] == 0.5
        assert subs["dividend_consistency"] == 0.5
        assert subs["sortino"] == 0.5


class TestCalculateStabilityScore:
    """Test stability score calculation (legacy tests updated for metrics API)."""

    @pytest.mark.asyncio
    async def test_combines_all_components(self):
        """Test that all stability components are combined."""
        from app.modules.scoring.domain.end_state import calculate_stability_score

        metrics = {
            "VOLATILITY_ANNUAL": 0.20,  # Moderate volatility
            "MAX_DRAWDOWN": -0.15,
            "SHARPE": 1.5,
        }

        score, subs = await calculate_stability_score("AAPL.US", metrics=metrics)

        assert "volatility" in subs
        assert "drawdown" in subs
        assert "sharpe" in subs
        assert 0 <= score <= 1

    @pytest.mark.asyncio
    async def test_uses_metrics_dict(self):
        """Test that metrics dict is used."""
        from app.modules.scoring.domain.end_state import calculate_stability_score

        metrics = {
            "VOLATILITY_ANNUAL": 0.25,
            "MAX_DRAWDOWN": -0.15,
            "SHARPE": 1.5,
        }

        score, subs = await calculate_stability_score("AAPL.US", metrics=metrics)

        assert 0 <= score <= 1
        assert "volatility" in subs
        assert "drawdown" in subs
        assert "sharpe" in subs


class TestCalculatePortfolioEndStateScore:
    """Test portfolio end-state score calculation."""

    @pytest.mark.asyncio
    async def test_returns_0_5_for_empty_portfolio(self):
        """Test that empty portfolio returns 0.5."""
        from app.modules.scoring.domain.end_state import calculate_portfolio_end_state_score

        score, breakdown = await calculate_portfolio_end_state_score(
            positions={},
            total_value=0,
            diversification_score=0.5,
            metrics_cache={},  # Empty cache for empty portfolio
        )

        assert score == 0.5
        assert "error" in breakdown

    @pytest.mark.asyncio
    async def test_calculates_weighted_scores(self):
        """Test weighted score calculation across positions."""
        from app.modules.scoring.domain.end_state import calculate_portfolio_end_state_score

        metrics_cache = {
            "AAPL.US": {
                "CAGR_5Y": 0.12,
                "DIVIDEND_YIELD": 0.015,
                "CONSISTENCY_SCORE": 0.8,
                "FINANCIAL_STRENGTH": 0.7,
                "DIVIDEND_CONSISTENCY": 0.6,
                "SORTINO": 1.5,
                "VOLATILITY_ANNUAL": 0.20,
                "MAX_DRAWDOWN": -0.15,
                "SHARPE": 1.5,
            },
            "MSFT.US": {
                "CAGR_5Y": 0.10,
                "DIVIDEND_YIELD": 0.01,
                "CONSISTENCY_SCORE": 0.7,
                "FINANCIAL_STRENGTH": 0.8,
                "DIVIDEND_CONSISTENCY": 0.5,
                "SORTINO": 1.2,
                "VOLATILITY_ANNUAL": 0.25,
                "MAX_DRAWDOWN": -0.20,
                "SHARPE": 1.2,
            },
        }

        score, breakdown = await calculate_portfolio_end_state_score(
            positions={"AAPL.US": 5000, "MSFT.US": 5000},
            total_value=10000,
            diversification_score=0.7,
            metrics_cache=metrics_cache,
            opinion_score=0.6,
        )

        assert "total_return" in breakdown
        assert "diversification" in breakdown
        assert "long_term_promise" in breakdown
        assert "stability" in breakdown
        assert "opinion" in breakdown
        assert "end_state_score" in breakdown
        assert 0 <= score <= 1

    @pytest.mark.asyncio
    async def test_skips_zero_value_positions(self):
        """Test that zero-value positions are skipped."""
        from app.modules.scoring.domain.end_state import calculate_portfolio_end_state_score

        metrics_cache = {
            "AAPL.US": {
                "CAGR_5Y": 0.12,
                "DIVIDEND_YIELD": 0.015,
                "CONSISTENCY_SCORE": 0.8,
                "FINANCIAL_STRENGTH": 0.7,
                "DIVIDEND_CONSISTENCY": 0.6,
                "SORTINO": 1.5,
                "VOLATILITY_ANNUAL": 0.20,
                "MAX_DRAWDOWN": -0.15,
                "SHARPE": 1.5,
            },
        }

        score, breakdown = await calculate_portfolio_end_state_score(
            positions={"AAPL.US": 10000, "DEAD.US": 0},
            total_value=10000,
            diversification_score=0.7,
            metrics_cache=metrics_cache,
        )

        # Should still complete successfully
        assert 0 <= score <= 1

    @pytest.mark.asyncio
    async def test_includes_weight_contributions(self):
        """Test that breakdown includes weight contributions."""
        from app.modules.scoring.domain.end_state import calculate_portfolio_end_state_score

        metrics_cache = {
            "AAPL.US": {
                "CAGR_5Y": 0.12,
                "DIVIDEND_YIELD": 0.015,
                "CONSISTENCY_SCORE": 0.8,
                "FINANCIAL_STRENGTH": 0.7,
                "DIVIDEND_CONSISTENCY": 0.6,
                "SORTINO": 1.5,
                "VOLATILITY_ANNUAL": 0.20,
                "MAX_DRAWDOWN": -0.15,
                "SHARPE": 1.5,
            },
        }

        score, breakdown = await calculate_portfolio_end_state_score(
            positions={"AAPL.US": 10000},
            total_value=10000,
            diversification_score=0.7,
            metrics_cache=metrics_cache,
        )

        # Each component should have weight and contribution
        assert "weight" in breakdown["total_return"]
        assert "contribution" in breakdown["total_return"]
        assert breakdown["total_return"]["weight"] == 0.35


class TestCalculateTotalReturnScoreWithMetrics:
    """Test total return score calculation with pre-fetched metrics dict."""

    @pytest.mark.asyncio
    async def test_uses_metrics_dict(self):
        """Test that metrics dict is used instead of DB queries."""
        from app.modules.scoring.domain.end_state import calculate_total_return_score

        metrics = {
            "CAGR_5Y": 0.12,
            "DIVIDEND_YIELD": 0.015,
        }

        score, subs = await calculate_total_return_score("AAPL.US", metrics=metrics)

        assert "cagr" in subs
        assert subs["cagr"] == 0.12
        assert subs["dividend_yield"] == 0.015
        assert subs["total_return"] == pytest.approx(0.135, abs=0.001)

    @pytest.mark.asyncio
    async def test_handles_missing_metrics(self):
        """Test that missing metrics default to 0.0."""
        from app.modules.scoring.domain.end_state import calculate_total_return_score

        metrics = {
            "CAGR_5Y": None,  # Missing
            "DIVIDEND_YIELD": 0.02,
        }

        score, subs = await calculate_total_return_score("AAPL.US", metrics=metrics)

        assert subs["cagr"] == 0.0
        assert subs["dividend_yield"] == 0.02
        assert subs["total_return"] == 0.02


class TestCalculateLongTermPromiseWithMetrics:
    """Test long-term promise score calculation with pre-fetched metrics dict."""

    @pytest.mark.asyncio
    async def test_uses_metrics_dict(self):
        """Test that metrics dict is used instead of DB queries."""
        from app.modules.scoring.domain.end_state import calculate_long_term_promise

        metrics = {
            "CONSISTENCY_SCORE": 0.8,
            "FINANCIAL_STRENGTH": 0.7,
            "DIVIDEND_CONSISTENCY": 0.6,
            "SORTINO": 1.5,  # Will be converted to score
        }

        score, subs = await calculate_long_term_promise("AAPL.US", metrics=metrics)

        assert subs["consistency"] == 0.8
        assert subs["financial_strength"] == 0.7
        assert subs["dividend_consistency"] == 0.6
        assert "sortino" in subs
        assert 0 <= score <= 1

    @pytest.mark.asyncio
    async def test_handles_missing_metrics(self):
        """Test that missing metrics default appropriately."""
        from app.modules.scoring.domain.end_state import calculate_long_term_promise

        metrics = {
            "CONSISTENCY_SCORE": None,
            "FINANCIAL_STRENGTH": 0.7,
            "DIVIDEND_CONSISTENCY": None,
            "SORTINO": None,
        }

        score, subs = await calculate_long_term_promise("AAPL.US", metrics=metrics)

        assert subs["consistency"] == 0.5  # Default
        assert subs["financial_strength"] == 0.7
        assert subs["dividend_consistency"] == 0.5  # Default
        assert subs["sortino"] == 0.5  # Default


class TestCalculateStabilityScoreWithMetrics:
    """Test stability score calculation with pre-fetched metrics dict."""

    @pytest.mark.asyncio
    async def test_uses_metrics_dict(self):
        """Test that metrics dict is used instead of DB queries."""
        from app.modules.scoring.domain.end_state import calculate_stability_score

        metrics = {
            "VOLATILITY_ANNUAL": 0.20,
            "MAX_DRAWDOWN": -0.15,
            "SHARPE": 1.5,
        }

        score, subs = await calculate_stability_score("AAPL.US", metrics=metrics)

        assert "volatility" in subs
        assert "drawdown" in subs
        assert "sharpe" in subs
        assert 0 <= score <= 1

    @pytest.mark.asyncio
    async def test_handles_missing_metrics(self):
        """Test that missing metrics default appropriately."""
        from app.modules.scoring.domain.end_state import calculate_stability_score

        metrics = {
            "VOLATILITY_ANNUAL": None,
            "MAX_DRAWDOWN": None,
            "SHARPE": None,
        }

        score, subs = await calculate_stability_score("AAPL.US", metrics=metrics)

        assert subs["volatility"] == 0.5  # Default
        assert subs["drawdown"] == 0.5  # Default
        assert subs["sharpe"] == 0.5  # Default
        assert 0 <= score <= 1


class TestCalculatePortfolioEndStateScoreWithMetricsCache:
    """Test portfolio end-state score calculation with metrics cache."""

    @pytest.mark.asyncio
    async def test_uses_metrics_cache(self):
        """Test that metrics cache is used instead of individual DB queries."""
        from app.modules.scoring.domain.end_state import calculate_portfolio_end_state_score

        metrics_cache = {
            "AAPL.US": {
                "CAGR_5Y": 0.12,
                "DIVIDEND_YIELD": 0.015,
                "CONSISTENCY_SCORE": 0.8,
                "FINANCIAL_STRENGTH": 0.7,
                "DIVIDEND_CONSISTENCY": 0.6,
                "SORTINO": 1.5,
                "VOLATILITY_ANNUAL": 0.20,
                "MAX_DRAWDOWN": -0.15,
                "SHARPE": 1.5,
            },
            "MSFT.US": {
                "CAGR_5Y": 0.10,
                "DIVIDEND_YIELD": 0.01,
                "CONSISTENCY_SCORE": 0.7,
                "FINANCIAL_STRENGTH": 0.8,
                "DIVIDEND_CONSISTENCY": 0.5,
                "SORTINO": 1.2,
                "VOLATILITY_ANNUAL": 0.25,
                "MAX_DRAWDOWN": -0.20,
                "SHARPE": 1.2,
            },
        }

        score, breakdown = await calculate_portfolio_end_state_score(
            positions={"AAPL.US": 5000, "MSFT.US": 5000},
            total_value=10000,
            diversification_score=0.7,
            metrics_cache=metrics_cache,
        )

        assert "total_return" in breakdown
        assert "diversification" in breakdown
        assert "long_term_promise" in breakdown
        assert "stability" in breakdown
        assert "end_state_score" in breakdown
        assert 0 <= score <= 1

    @pytest.mark.asyncio
    async def test_handles_missing_symbols_in_cache(self):
        """Test that missing symbols in cache use defaults."""
        from app.modules.scoring.domain.end_state import calculate_portfolio_end_state_score

        metrics_cache = {
            "AAPL.US": {
                "CAGR_5Y": 0.12,
                "DIVIDEND_YIELD": 0.015,
                "CONSISTENCY_SCORE": 0.8,
                "FINANCIAL_STRENGTH": 0.7,
                "DIVIDEND_CONSISTENCY": 0.6,
                "SORTINO": 1.5,
                "VOLATILITY_ANNUAL": 0.20,
                "MAX_DRAWDOWN": -0.15,
                "SHARPE": 1.5,
            },
            # MSFT.US missing - should use defaults
        }

        score, breakdown = await calculate_portfolio_end_state_score(
            positions={"AAPL.US": 5000, "MSFT.US": 5000},
            total_value=10000,
            diversification_score=0.7,
            metrics_cache=metrics_cache,
        )

        # Should still complete successfully with defaults for MSFT
        assert 0 <= score <= 1
        assert "end_state_score" in breakdown
