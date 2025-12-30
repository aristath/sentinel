"""Tests for rebalancing triggers service.

These tests validate rebalancing trigger detection, including position drift
and cash threshold triggers.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.models import Position
from app.domain.value_objects.currency import Currency


class TestCheckRebalanceTriggers:
    """Test check_rebalance_triggers function."""

    @pytest.fixture
    def mock_settings_repo(self):
        """Mock SettingsRepository."""
        repo = AsyncMock()
        repo.get_float = AsyncMock(return_value=0.0)
        return repo

    @pytest.mark.asyncio
    async def test_returns_false_when_no_triggers(self, mock_settings_repo):
        """Test that False is returned when no rebalancing triggers are met."""
        from app.domain.services.rebalancing_triggers import check_rebalance_triggers

        positions = []
        target_allocations = {}
        total_portfolio_value = 100000.0
        cash_balance = 10000.0

        should_rebalance, reason = await check_rebalance_triggers(
            positions,
            target_allocations,
            total_portfolio_value,
            cash_balance,
            mock_settings_repo,
        )

        assert should_rebalance is False
        assert reason == "no triggers met"

    @pytest.mark.asyncio
    async def test_triggers_on_position_drift(self, mock_settings_repo):
        """Test that rebalance is triggered when positions drift from targets."""
        from app.domain.services.rebalancing_triggers import check_rebalance_triggers

        # Create a position that's significantly overweight
        positions = [
            Position(
                symbol="AAPL",
                quantity=1000.0,
                avg_price=100.0,
                market_value_eur=100000.0,  # 100% of portfolio (way over target)
            )
        ]
        target_allocations = {"AAPL": 0.05}  # Target is only 5%
        total_portfolio_value = 100000.0
        cash_balance = 0.0

        # Mock settings to allow drift check
        async def get_float_side_effect(key, default):
            if key == "rebalance_drift_threshold":
                return 0.10  # 10% threshold
            return default

        mock_settings_repo.get_float.side_effect = get_float_side_effect

        should_rebalance, reason = await check_rebalance_triggers(
            positions,
            target_allocations,
            total_portfolio_value,
            cash_balance,
            mock_settings_repo,
        )

        # Should trigger due to significant drift (100% vs 5% target)
        assert should_rebalance is True
        assert "drift" in reason.lower() or "overweight" in reason.lower()

    @pytest.mark.asyncio
    async def test_triggers_on_cash_threshold_exceeded(self, mock_settings_repo):
        """Test that rebalance is triggered when cash exceeds threshold."""
        from app.domain.services.rebalancing_triggers import check_rebalance_triggers

        positions = []
        target_allocations = {}
        total_portfolio_value = 100000.0
        cash_balance = 30000.0  # 30% cash (exceeds typical threshold)

        # Mock settings
        async def get_float_side_effect(key, default):
            if key == "rebalance_cash_threshold":
                return 0.20  # 20% threshold
            return default

        mock_settings_repo.get_float.side_effect = get_float_side_effect

        should_rebalance, reason = await check_rebalance_triggers(
            positions,
            target_allocations,
            total_portfolio_value,
            cash_balance,
            mock_settings_repo,
        )

        # Should trigger when cash > threshold
        assert should_rebalance is True
        assert "cash" in reason.lower()

    @pytest.mark.asyncio
    async def test_no_trigger_when_cash_below_threshold(self, mock_settings_repo):
        """Test that rebalance is not triggered when cash is below threshold."""
        from app.domain.services.rebalancing_triggers import check_rebalance_triggers

        positions = []
        target_allocations = {}
        total_portfolio_value = 100000.0
        cash_balance = 5000.0  # 5% cash (below threshold)

        async def get_float_side_effect(key, default):
            if key == "rebalance_cash_threshold":
                return 0.20  # 20% threshold
            return default

        mock_settings_repo.get_float.side_effect = get_float_side_effect

        should_rebalance, reason = await check_rebalance_triggers(
            positions,
            target_allocations,
            total_portfolio_value,
            cash_balance,
            mock_settings_repo,
        )

        # Should not trigger when cash < threshold
        assert should_rebalance is False
        assert reason == "no triggers met"

    @pytest.mark.asyncio
    async def test_handles_zero_portfolio_value(self, mock_settings_repo):
        """Test handling when portfolio value is zero."""
        from app.domain.services.rebalancing_triggers import check_rebalance_triggers

        positions = []
        target_allocations = {}
        total_portfolio_value = 0.0
        cash_balance = 0.0

        should_rebalance, reason = await check_rebalance_triggers(
            positions,
            target_allocations,
            total_portfolio_value,
            cash_balance,
            mock_settings_repo,
        )

        # Should handle gracefully
        assert isinstance(should_rebalance, bool)
        assert isinstance(reason, str)

    @pytest.mark.asyncio
    async def test_handles_zero_cash_balance(self, mock_settings_repo):
        """Test handling when cash balance is zero."""
        from app.domain.services.rebalancing_triggers import check_rebalance_triggers

        positions = []
        target_allocations = {}
        total_portfolio_value = 100000.0
        cash_balance = 0.0

        should_rebalance, reason = await check_rebalance_triggers(
            positions,
            target_allocations,
            total_portfolio_value,
            cash_balance,
            mock_settings_repo,
        )

        # Should handle gracefully
        assert isinstance(should_rebalance, bool)
        assert isinstance(reason, str)

    @pytest.mark.asyncio
    async def test_handles_missing_settings_repo(self):
        """Test handling when settings_repo is None."""
        from app.domain.services.rebalancing_triggers import check_rebalance_triggers

        positions = []
        target_allocations = {}
        total_portfolio_value = 100000.0
        cash_balance = 10000.0

        should_rebalance, reason = await check_rebalance_triggers(
            positions,
            target_allocations,
            total_portfolio_value,
            cash_balance,
            settings_repo=None,
        )

        # Should handle gracefully
        assert isinstance(should_rebalance, bool)
        assert isinstance(reason, str)

    @pytest.mark.asyncio
    async def test_handles_empty_positions_and_targets(self, mock_settings_repo):
        """Test handling when positions and targets are empty."""
        from app.domain.services.rebalancing_triggers import check_rebalance_triggers

        positions = []
        target_allocations = {}
        total_portfolio_value = 100000.0
        cash_balance = 10000.0

        should_rebalance, reason = await check_rebalance_triggers(
            positions,
            target_allocations,
            total_portfolio_value,
            cash_balance,
            mock_settings_repo,
        )

        # Should not trigger when there's nothing to rebalance
        assert should_rebalance is False

    @pytest.mark.asyncio
    async def test_handles_positions_without_market_value(self, mock_settings_repo):
        """Test handling when positions have None market_value_eur."""
        from app.domain.services.rebalancing_triggers import check_rebalance_triggers

        positions = [
            Position(
                symbol="AAPL",
                quantity=100.0,
                avg_price=100.0,
                market_value_eur=None,  # Missing market value
            )
        ]
        target_allocations = {"AAPL": 0.10}
        total_portfolio_value = 100000.0
        cash_balance = 10000.0

        should_rebalance, reason = await check_rebalance_triggers(
            positions,
            target_allocations,
            total_portfolio_value,
            cash_balance,
            mock_settings_repo,
        )

        # Should handle gracefully (may skip positions without market value)
        assert isinstance(should_rebalance, bool)
        assert isinstance(reason, str)
