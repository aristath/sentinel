"""Tests for rebalancing trigger checker.

These tests validate event-driven rebalancing trigger logic.
CRITICAL: Tests catch real bugs that would cause unnecessary trading or missed opportunities.
"""

from contextlib import contextmanager
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.models import Position, Stock
from app.domain.value_objects.currency import Currency


def create_position(
    symbol: str,
    quantity: float,
    avg_price: float,
    current_price: Optional[float] = None,
) -> Position:
    """Helper to create position."""
    if current_price is None:
        current_price = avg_price

    market_value = quantity * current_price
    cost_basis = quantity * avg_price
    unrealized_pnl = market_value - cost_basis
    unrealized_pnl_pct = (unrealized_pnl / cost_basis) if cost_basis > 0 else 0.0

    return Position(
        symbol=symbol,
        quantity=quantity,
        avg_price=avg_price,
        currency=Currency.EUR,
        current_price=current_price,
        market_value_eur=market_value,
        cost_basis_eur=cost_basis,
        unrealized_pnl=unrealized_pnl,
        unrealized_pnl_pct=unrealized_pnl_pct,
    )


def create_stock(symbol: str) -> Stock:
    """Helper to create stock."""
    return Stock(
        symbol=symbol,
        name=f"{symbol} Inc.",
        currency=Currency.EUR,
    )


@contextmanager
def mock_rebalancing_triggers_dependencies(
    mock_settings_repo=None,
    mock_position_repo=None,
    mock_tradernet_client=None,
):
    """Context manager to set up all mocks for rebalancing triggers."""
    # Default mocks
    if mock_settings_repo is None:
        mock_settings_repo = AsyncMock()
    if mock_position_repo is None:
        mock_position_repo = AsyncMock()
    if mock_tradernet_client is None:
        mock_tradernet_client = MagicMock()

    # Setup default settings
    async def get_float(key, default):
        defaults = {
            "event_driven_rebalancing_enabled": 1.0,
            "rebalance_position_drift_threshold": 0.05,
            "rebalance_cash_threshold_multiplier": 2.0,
            "transaction_cost_fixed": 2.0,
            "transaction_cost_percent": 0.002,
        }
        return defaults.get(key, default)

    mock_settings_repo.get_float = AsyncMock(side_effect=get_float)

    with (
        patch(
            "app.domain.services.rebalancing_triggers.SettingsRepository",
            return_value=mock_settings_repo,
        ),
        patch(
            "app.domain.services.rebalancing_triggers.PositionRepository",
            return_value=mock_position_repo,
        ),
        patch(
            "app.domain.services.rebalancing_triggers.get_tradernet_client",
            return_value=mock_tradernet_client,
        ),
    ):
        yield {
            "settings_repo": mock_settings_repo,
            "position_repo": mock_position_repo,
            "tradernet_client": mock_tradernet_client,
        }


class TestPositionDriftDetection:
    """Test position drift detection logic."""

    @pytest.mark.asyncio
    async def test_detects_position_drift_above_threshold(self):
        """Test that position drift above threshold is detected.

        Bug caught: Drift not detected, unnecessary rebalancing skipped.
        """
        from app.domain.services.rebalancing_triggers import check_rebalance_triggers

        # Position with 10% drift (above 5% threshold)
        positions = [
            create_position("AAPL", quantity=100, avg_price=150.0, current_price=165.0),
        ]
        target_allocations = {"AAPL": 0.20}  # 20% target
        total_portfolio_value = (
            10000.0  # AAPL value = 16500, but portfolio = 10000 (drift)
        )

        mock_position_repo = AsyncMock()
        mock_position_repo.get_all = AsyncMock(return_value=positions)

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "event_driven_rebalancing_enabled": 1.0,
                "rebalance_position_drift_threshold": 0.05,  # 5%
            }.get(key, default)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)

        # Mock portfolio context
        with mock_rebalancing_triggers_dependencies(
            mock_position_repo=mock_position_repo,
            mock_settings_repo=mock_settings_repo,
        ):
            should_rebalance, reason = await check_rebalance_triggers(
                positions=positions,
                target_allocations=target_allocations,
                total_portfolio_value=total_portfolio_value,
                cash_balance=0.0,
            )

        # Verify drift was detected
        assert should_rebalance is True
        assert "drift" in reason.lower()

    @pytest.mark.asyncio
    async def test_ignores_position_drift_below_threshold(self):
        """Test that small position drifts are ignored.

        Bug caught: Triggers on tiny drifts, causing excessive trading.
        """
        from app.domain.services.rebalancing_triggers import check_rebalance_triggers

        # Position with 2% drift (below 5% threshold)
        positions = [
            create_position("AAPL", quantity=100, avg_price=150.0, current_price=153.0),
        ]
        target_allocations = {"AAPL": 0.20}
        total_portfolio_value = 7650.0  # Small drift

        mock_position_repo = AsyncMock()
        mock_position_repo.get_all = AsyncMock(return_value=positions)

        with mock_rebalancing_triggers_dependencies(
            mock_position_repo=mock_position_repo,
        ):
            should_rebalance, reason = await check_rebalance_triggers(
                positions=positions,
                target_allocations=target_allocations,
                total_portfolio_value=total_portfolio_value,
                cash_balance=0.0,
            )

        # Verify drift was NOT detected (below threshold)
        assert should_rebalance is False

    @pytest.mark.asyncio
    async def test_exactly_at_drift_threshold_triggers(self):
        """Test that drift exactly at threshold triggers.

        Bug caught: Off-by-one at threshold.
        """
        from app.domain.services.rebalancing_triggers import check_rebalance_triggers

        # Position exactly at 5% drift threshold
        positions = [
            create_position("AAPL", quantity=100, avg_price=100.0, current_price=105.0),
        ]
        target_allocations = {"AAPL": 0.20}
        total_portfolio_value = 5000.0  # Exactly 5% drift

        mock_position_repo = AsyncMock()
        mock_position_repo.get_all = AsyncMock(return_value=positions)

        with mock_rebalancing_triggers_dependencies(
            mock_position_repo=mock_position_repo,
        ):
            should_rebalance, reason = await check_rebalance_triggers(
                positions=positions,
                target_allocations=target_allocations,
                total_portfolio_value=total_portfolio_value,
                cash_balance=0.0,
            )

        # Verify drift was detected (>= threshold)
        assert should_rebalance is True


class TestCashAccumulationDetection:
    """Test cash accumulation detection logic."""

    @pytest.mark.asyncio
    async def test_detects_cash_above_threshold(self):
        """Test that cash above threshold is detected.

        Bug caught: Cash not deployed, opportunity lost.
        """
        from app.domain.services.rebalancing_triggers import check_rebalance_triggers

        positions = []
        target_allocations = {}
        total_portfolio_value = 10000.0
        cash_balance = 500.0  # Above threshold (2.0 × 250 = 500)

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "event_driven_rebalancing_enabled": 1.0,
                "rebalance_cash_threshold_multiplier": 2.0,
                "transaction_cost_fixed": 2.0,
                "transaction_cost_percent": 0.002,
            }.get(key, default)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)

        with mock_rebalancing_triggers_dependencies(
            mock_settings_repo=mock_settings_repo,
        ):
            should_rebalance, reason = await check_rebalance_triggers(
                positions=positions,
                target_allocations=target_allocations,
                total_portfolio_value=total_portfolio_value,
                cash_balance=cash_balance,
            )

        # Verify cash accumulation was detected
        assert should_rebalance is True
        assert "cash" in reason.lower()

    @pytest.mark.asyncio
    async def test_ignores_cash_below_threshold(self):
        """Test that cash below threshold is ignored.

        Bug caught: Rebalances with insufficient cash.
        """
        from app.domain.services.rebalancing_triggers import check_rebalance_triggers

        positions = []
        target_allocations = {}
        total_portfolio_value = 10000.0
        cash_balance = 100.0  # Below threshold

        with mock_rebalancing_triggers_dependencies():
            should_rebalance, reason = await check_rebalance_triggers(
                positions=positions,
                target_allocations=target_allocations,
                total_portfolio_value=total_portfolio_value,
                cash_balance=cash_balance,
            )

        # Verify cash accumulation was NOT detected
        assert should_rebalance is False


class TestMultipleTriggers:
    """Test multiple trigger scenarios."""

    @pytest.mark.asyncio
    async def test_any_trigger_met_returns_true(self):
        """Test that any trigger being met returns True.

        Bug caught: Requires all triggers instead of any.
        """
        from app.domain.services.rebalancing_triggers import check_rebalance_triggers

        # Both drift and cash triggers met
        positions = [
            create_position("AAPL", quantity=100, avg_price=150.0, current_price=165.0),
        ]
        target_allocations = {"AAPL": 0.20}
        total_portfolio_value = 10000.0
        cash_balance = 500.0

        mock_position_repo = AsyncMock()
        mock_position_repo.get_all = AsyncMock(return_value=positions)

        with mock_rebalancing_triggers_dependencies(
            mock_position_repo=mock_position_repo,
        ):
            should_rebalance, reason = await check_rebalance_triggers(
                positions=positions,
                target_allocations=target_allocations,
                total_portfolio_value=total_portfolio_value,
                cash_balance=cash_balance,
            )

        # Verify rebalancing is triggered (any trigger met)
        assert should_rebalance is True

    @pytest.mark.asyncio
    async def test_no_triggers_met_returns_false(self):
        """Test that no triggers being met returns False.

        Bug caught: Triggers when nothing changed.
        """
        from app.domain.services.rebalancing_triggers import check_rebalance_triggers

        # No drift, no cash accumulation
        positions = [
            create_position("AAPL", quantity=100, avg_price=150.0, current_price=150.0),
        ]
        target_allocations = {"AAPL": 0.20}
        total_portfolio_value = 15000.0  # No drift
        cash_balance = 100.0  # Below threshold

        mock_position_repo = AsyncMock()
        mock_position_repo.get_all = AsyncMock(return_value=positions)

        with mock_rebalancing_triggers_dependencies(
            mock_position_repo=mock_position_repo,
        ):
            should_rebalance, reason = await check_rebalance_triggers(
                positions=positions,
                target_allocations=target_allocations,
                total_portfolio_value=total_portfolio_value,
                cash_balance=cash_balance,
            )

        # Verify rebalancing is NOT triggered
        assert should_rebalance is False


class TestSettingsIntegration:
    """Test settings integration."""

    @pytest.mark.asyncio
    async def test_respects_enabled_flag(self):
        """Test that triggers are not checked when disabled.

        Bug caught: Triggers checked when disabled.
        """
        from app.domain.services.rebalancing_triggers import check_rebalance_triggers

        positions = [
            create_position("AAPL", quantity=100, avg_price=150.0, current_price=165.0),
        ]
        target_allocations = {"AAPL": 0.20}
        total_portfolio_value = 10000.0

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "event_driven_rebalancing_enabled": 0.0,  # Disabled
                "rebalance_position_drift_threshold": 0.05,
            }.get(key, default)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)

        with mock_rebalancing_triggers_dependencies(
            mock_settings_repo=mock_settings_repo,
        ):
            should_rebalance, reason = await check_rebalance_triggers(
                positions=positions,
                target_allocations=target_allocations,
                total_portfolio_value=total_portfolio_value,
                cash_balance=0.0,
            )

        # When disabled, should always return False (skip trigger check)
        assert should_rebalance is False

    @pytest.mark.asyncio
    async def test_uses_custom_drift_threshold(self):
        """Test that custom drift threshold is used.

        Bug caught: Ignores user settings.
        """
        from app.domain.services.rebalancing_triggers import check_rebalance_triggers

        # Position with 3% drift
        positions = [
            create_position("AAPL", quantity=100, avg_price=100.0, current_price=103.0),
        ]
        target_allocations = {"AAPL": 0.20}
        total_portfolio_value = 5000.0  # 3% drift

        mock_position_repo = AsyncMock()
        mock_position_repo.get_all = AsyncMock(return_value=positions)

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "event_driven_rebalancing_enabled": 1.0,
                "rebalance_position_drift_threshold": 0.02,  # Custom 2% threshold
            }.get(key, default)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)

        with mock_rebalancing_triggers_dependencies(
            mock_position_repo=mock_position_repo,
            mock_settings_repo=mock_settings_repo,
        ):
            should_rebalance, reason = await check_rebalance_triggers(
                positions=positions,
                target_allocations=target_allocations,
                total_portfolio_value=total_portfolio_value,
                cash_balance=0.0,
            )

        # Verify drift was detected (above custom 2% threshold)
        assert should_rebalance is True


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_portfolio_handles_gracefully(self):
        """Test that empty portfolio is handled gracefully.

        Bug caught: Crashes on empty positions.
        """
        from app.domain.services.rebalancing_triggers import check_rebalance_triggers

        positions = []
        target_allocations = {}
        total_portfolio_value = 0.0
        cash_balance = 0.0

        with mock_rebalancing_triggers_dependencies():
            # Should not raise exception
            should_rebalance, reason = await check_rebalance_triggers(
                positions=positions,
                target_allocations=target_allocations,
                total_portfolio_value=total_portfolio_value,
                cash_balance=cash_balance,
            )

        # Empty portfolio should not trigger rebalancing
        assert should_rebalance is False

    @pytest.mark.asyncio
    async def test_zero_cash_balance_handles_gracefully(self):
        """Test that zero cash balance is handled gracefully.

        Bug caught: Division by zero or crash.
        """
        from app.domain.services.rebalancing_triggers import check_rebalance_triggers

        positions = [
            create_position("AAPL", quantity=100, avg_price=150.0),
        ]
        target_allocations = {"AAPL": 0.20}
        total_portfolio_value = 15000.0
        cash_balance = 0.0

        mock_position_repo = AsyncMock()
        mock_position_repo.get_all = AsyncMock(return_value=positions)

        with mock_rebalancing_triggers_dependencies(
            mock_position_repo=mock_position_repo,
        ):
            # Should not raise exception
            should_rebalance, reason = await check_rebalance_triggers(
                positions=positions,
                target_allocations=target_allocations,
                total_portfolio_value=total_portfolio_value,
                cash_balance=cash_balance,
            )

        # Zero cash should not trigger (below threshold)
        assert should_rebalance is False
