"""Tests for cash rebalance job.

These tests validate the drip execution strategy that executes
one trade per cycle with proper P&L guardrails.
CRITICAL: This is the core trading execution job.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCheckPnlGuardrails:
    """Test P&L guardrail checks."""

    @pytest.mark.asyncio
    async def test_allows_trading_when_pnl_ok(self):
        """Test that trading is allowed when P&L status is OK."""
        from app.jobs.cash_rebalance import _check_pnl_guardrails

        mock_tracker = AsyncMock()
        mock_tracker.get_trading_status.return_value = {
            "status": "ok",
            "pnl_display": "+€50.00",
            "can_buy": True,
            "can_sell": True,
            "reason": None,
        }

        with patch(
            "app.jobs.cash_rebalance.get_daily_pnl_tracker",
            return_value=mock_tracker,
        ):
            pnl_status, can_trade = await _check_pnl_guardrails()

        assert can_trade is True
        assert pnl_status["status"] == "ok"

    @pytest.mark.asyncio
    async def test_blocks_trading_when_halted(self):
        """Test that trading is blocked when P&L status is halted."""
        from app.jobs.cash_rebalance import _check_pnl_guardrails

        mock_tracker = AsyncMock()
        mock_tracker.get_trading_status.return_value = {
            "status": "halted",
            "pnl_display": "-€500.00",
            "can_buy": False,
            "can_sell": False,
            "reason": "Daily loss limit exceeded",
        }

        with patch(
            "app.jobs.cash_rebalance.get_daily_pnl_tracker",
            return_value=mock_tracker,
        ):
            with patch("app.jobs.cash_rebalance.emit"):
                with patch("app.jobs.cash_rebalance.set_error"):
                    pnl_status, can_trade = await _check_pnl_guardrails()

        assert can_trade is False
        assert pnl_status["status"] == "halted"


class TestValidateNextAction:
    """Test next action validation."""

    @pytest.fixture
    def mock_trade_repo(self):
        """Create mock trade repository."""
        return AsyncMock()

    @pytest.fixture
    def mock_settings_repo(self):
        """Create mock settings repository."""
        from app.repositories import SettingsRepository

        repo = AsyncMock(spec=SettingsRepository)
        return repo

    @pytest.fixture
    def mock_buy_action(self):
        """Create mock BUY action."""
        from app.domain.value_objects.trade_side import TradeSide

        action = MagicMock()
        action.side = TradeSide.BUY
        action.symbol = "AAPL"
        return action

    @pytest.fixture
    def mock_sell_action(self):
        """Create mock SELL action."""
        from app.domain.value_objects.trade_side import TradeSide

        action = MagicMock()
        action.side = TradeSide.SELL
        action.symbol = "AAPL"
        return action

    @pytest.mark.asyncio
    async def test_allows_buy_when_cash_sufficient(
        self, mock_trade_repo, mock_settings_repo, mock_buy_action
    ):
        """Test BUY is allowed when cash is sufficient."""
        from unittest.mock import patch

        from app.jobs.cash_rebalance import _validate_next_action

        with patch(
            "app.jobs.cash_rebalance.TradeFrequencyService"
        ) as mock_freq_service:
            mock_freq_service_instance = AsyncMock()
            mock_freq_service_instance.can_execute_trade = AsyncMock(
                return_value=(True, None)
            )
            mock_freq_service.return_value = mock_freq_service_instance

            pnl_status = {"can_buy": True, "can_sell": True}
            cash_balance = 1000.0
            min_trade_size = 500.0

            result = await _validate_next_action(
                mock_buy_action,
                pnl_status,
                cash_balance,
                min_trade_size,
                mock_trade_repo,
                mock_settings_repo,
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_blocks_buy_when_cash_insufficient(
        self, mock_trade_repo, mock_settings_repo, mock_buy_action
    ):
        """Test BUY is blocked when cash is insufficient."""
        from unittest.mock import patch

        from app.jobs.cash_rebalance import _validate_next_action

        with patch(
            "app.jobs.cash_rebalance.TradeFrequencyService"
        ) as mock_freq_service:
            mock_freq_service_instance = AsyncMock()
            mock_freq_service_instance.can_execute_trade = AsyncMock(
                return_value=(True, None)
            )
            mock_freq_service.return_value = mock_freq_service_instance

            pnl_status = {"can_buy": True, "can_sell": True}
            cash_balance = 400.0
            min_trade_size = 500.0

            result = await _validate_next_action(
                mock_buy_action,
                pnl_status,
                cash_balance,
                min_trade_size,
                mock_trade_repo,
                mock_settings_repo,
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_blocks_buy_when_pnl_guardrail_active(
        self, mock_trade_repo, mock_settings_repo, mock_buy_action
    ):
        """Test BUY is blocked by P&L guardrail."""
        from unittest.mock import patch

        from app.jobs.cash_rebalance import _validate_next_action

        with patch(
            "app.jobs.cash_rebalance.TradeFrequencyService"
        ) as mock_freq_service:
            mock_freq_service_instance = AsyncMock()
            mock_freq_service_instance.can_execute_trade = AsyncMock(
                return_value=(True, None)
            )
            mock_freq_service.return_value = mock_freq_service_instance

            pnl_status = {
                "can_buy": False,
                "can_sell": True,
                "reason": "Daily loss limit",
            }
            cash_balance = 1000.0
            min_trade_size = 500.0

            result = await _validate_next_action(
                mock_buy_action,
                pnl_status,
                cash_balance,
                min_trade_size,
                mock_trade_repo,
                mock_settings_repo,
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_blocks_sell_when_pnl_guardrail_active(
        self, mock_trade_repo, mock_settings_repo, mock_sell_action
    ):
        """Test SELL is blocked by P&L guardrail."""
        from unittest.mock import patch

        from app.jobs.cash_rebalance import _validate_next_action

        with patch(
            "app.jobs.cash_rebalance.TradeFrequencyService"
        ) as mock_freq_service:
            mock_freq_service_instance = AsyncMock()
            mock_freq_service_instance.can_execute_trade = AsyncMock(
                return_value=(True, None)
            )
            mock_freq_service.return_value = mock_freq_service_instance

            pnl_status = {
                "can_buy": True,
                "can_sell": False,
                "reason": "Max loss reached",
            }
            cash_balance = 1000.0
            min_trade_size = 500.0

            result = await _validate_next_action(
                mock_sell_action,
                pnl_status,
                cash_balance,
                min_trade_size,
                mock_trade_repo,
                mock_settings_repo,
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_blocks_sell_when_recent_order_exists(
        self, mock_trade_repo, mock_settings_repo, mock_sell_action
    ):
        """Test SELL is blocked when recent sell order exists."""
        from unittest.mock import patch

        from app.jobs.cash_rebalance import _validate_next_action

        with patch(
            "app.jobs.cash_rebalance.TradeFrequencyService"
        ) as mock_freq_service:
            mock_freq_service_instance = AsyncMock()
            mock_freq_service_instance.can_execute_trade = AsyncMock(
                return_value=(True, None)
            )
            mock_freq_service.return_value = mock_freq_service_instance

            pnl_status = {"can_buy": True, "can_sell": True}
            cash_balance = 1000.0
            min_trade_size = 500.0
            mock_trade_repo.has_recent_sell_order.return_value = True

            result = await _validate_next_action(
                mock_sell_action,
                pnl_status,
                cash_balance,
                min_trade_size,
                mock_trade_repo,
                mock_settings_repo,
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_allows_sell_when_no_recent_order(
        self, mock_trade_repo, mock_settings_repo, mock_sell_action
    ):
        """Test SELL is allowed when no recent order exists."""
        from unittest.mock import patch

        from app.jobs.cash_rebalance import _validate_next_action

        with patch(
            "app.jobs.cash_rebalance.TradeFrequencyService"
        ) as mock_freq_service:
            mock_freq_service_instance = AsyncMock()
            mock_freq_service_instance.can_execute_trade = AsyncMock(
                return_value=(True, None)
            )
            mock_freq_service.return_value = mock_freq_service_instance

            pnl_status = {"can_buy": True, "can_sell": True}
            cash_balance = 1000.0
            min_trade_size = 500.0
            mock_trade_repo.has_recent_sell_order.return_value = False

            result = await _validate_next_action(
                mock_sell_action,
                pnl_status,
                cash_balance,
                min_trade_size,
                mock_trade_repo,
                mock_settings_repo,
            )

            assert result is True


class TestCheckAndRebalanceInternal:
    """Test the internal rebalance function."""

    @pytest.mark.asyncio
    async def test_returns_early_when_pnl_halted(self):
        """Test that rebalance returns early when P&L is halted."""
        from app.jobs.cash_rebalance import _check_and_rebalance_internal

        with (
            patch("app.jobs.sync_trades.sync_trades"),
            patch("app.jobs.daily_sync.sync_portfolio"),
            patch("app.jobs.cash_rebalance._check_pnl_guardrails") as mock_pnl,
            patch("app.jobs.cash_rebalance.emit"),
            patch("app.jobs.cash_rebalance.set_processing"),
            patch("app.jobs.cash_rebalance.clear_processing"),
        ):
            mock_pnl.return_value = ({"status": "halted"}, False)

            await _check_and_rebalance_internal()

            # Should not proceed to get recommendations

    @pytest.mark.asyncio
    async def test_returns_early_when_no_connection(self):
        """Test that rebalance returns early when broker not connected."""
        from app.jobs.cash_rebalance import _check_and_rebalance_internal

        mock_client = MagicMock()
        mock_client.is_connected = False
        mock_client.connect.return_value = False

        with (
            patch("app.jobs.sync_trades.sync_trades"),
            patch("app.jobs.daily_sync.sync_portfolio"),
            patch("app.jobs.cash_rebalance._check_pnl_guardrails") as mock_pnl,
            patch("app.jobs.cash_rebalance.get_tradernet_client") as mock_get_client,
            patch("app.jobs.cash_rebalance.SettingsRepository"),
            patch(
                "app.domain.services.settings_service.SettingsService"
            ) as mock_service,
            patch("app.jobs.cash_rebalance.emit"),
            patch("app.jobs.cash_rebalance.set_processing"),
            patch("app.jobs.cash_rebalance.set_error") as mock_set_error,
            patch("app.jobs.cash_rebalance.clear_processing"),
        ):
            mock_pnl.return_value = ({"status": "ok"}, True)
            mock_get_client.return_value = mock_client
            mock_service.return_value.get_settings = AsyncMock(
                return_value=MagicMock(
                    transaction_cost_fixed=5.0,
                    transaction_cost_percent=0.1,
                )
            )

            await _check_and_rebalance_internal()

            mock_set_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_early_when_no_action(self):
        """Test that rebalance returns early when no action recommended."""
        from app.jobs.cash_rebalance import _check_and_rebalance_internal

        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.get_total_cash_eur.return_value = 1000.0

        mock_settings = MagicMock()
        mock_settings.transaction_cost_fixed = 5.0
        mock_settings.transaction_cost_percent = 0.1

        with (
            patch("app.jobs.sync_trades.sync_trades"),
            patch("app.jobs.daily_sync.sync_portfolio"),
            patch("app.jobs.cash_rebalance._check_pnl_guardrails") as mock_pnl,
            patch("app.jobs.cash_rebalance.get_tradernet_client") as mock_get_client,
            patch("app.jobs.cash_rebalance.SettingsRepository"),
            patch(
                "app.domain.services.settings_service.SettingsService"
            ) as mock_service,
            patch("app.jobs.cash_rebalance.PositionRepository") as mock_pos_repo,
            patch("app.jobs.cash_rebalance.TradeRepository"),
            patch("app.jobs.cash_rebalance._get_next_holistic_action") as mock_action,
            patch("app.jobs.cash_rebalance._refresh_recommendation_cache"),
            patch("app.jobs.cash_rebalance.emit"),
            patch("app.jobs.cash_rebalance.set_processing"),
            patch("app.jobs.cash_rebalance.clear_processing"),
        ):
            mock_pnl.return_value = ({"status": "ok"}, True)
            mock_get_client.return_value = mock_client
            mock_service.return_value.get_settings = AsyncMock(
                return_value=mock_settings
            )
            mock_pos_repo.return_value.get_all.return_value = []
            mock_action.return_value = None

            await _check_and_rebalance_internal()


class TestGetNextHolisticAction:
    """Test getting next action from holistic planner."""

    @pytest.mark.asyncio
    async def test_returns_cached_action(self):
        """Test returning cached action when available."""
        from app.jobs.cash_rebalance import _get_next_holistic_action

        cached_data = {
            "steps": [
                {
                    "side": "BUY",
                    "symbol": "AAPL.US",
                    "name": "Apple Inc",
                    "quantity": 10,
                    "estimated_price": 150.0,
                    "estimated_value": 1500.0,
                    "currency": "USD",
                    "reason": "High score",
                }
            ]
        }

        mock_settings_obj = MagicMock()
        mock_settings_obj.to_dict.return_value = {}

        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.get_cash_balances.return_value = []

        with (
            patch("app.jobs.cash_rebalance.PositionRepository") as mock_pos_repo,
            patch("app.jobs.cash_rebalance.SettingsRepository"),
            patch("app.jobs.cash_rebalance.StockRepository") as mock_stock_repo,
            patch("app.jobs.cash_rebalance.AllocationRepository") as mock_alloc_repo,
            patch(
                "app.jobs.cash_rebalance.get_tradernet_client",
                return_value=mock_client,
            ),
            patch(
                "app.domain.services.settings_service.SettingsService"
            ) as mock_settings,
            patch("app.jobs.cash_rebalance.cache") as mock_cache,
        ):
            mock_pos_repo.return_value.get_all = AsyncMock(return_value=[])
            mock_stock_repo.return_value.get_all_active = AsyncMock(return_value=[])
            mock_alloc_repo.return_value.get_all = AsyncMock(return_value=[])
            mock_settings.return_value.get_settings = AsyncMock(
                return_value=mock_settings_obj
            )
            mock_cache.get.return_value = cached_data

            result = await _get_next_holistic_action()

            assert result is not None
            assert result.symbol == "AAPL.US"


class TestRefreshRecommendationCache:
    """Test refreshing recommendation cache."""

    @pytest.mark.asyncio
    async def test_refreshes_cache_successfully(self):
        """Test successful cache refresh."""
        from app.jobs.cash_rebalance import _refresh_recommendation_cache

        mock_step = MagicMock()
        mock_step.step = 1
        mock_step.side = "BUY"
        mock_step.symbol = "AAPL.US"
        mock_step.name = "Apple"
        mock_step.quantity = 10
        mock_step.estimated_price = 150.0
        mock_step.estimated_value = 1500.0
        mock_step.currency = "USD"
        mock_step.reason = "High score"
        mock_step.portfolio_score_before = 0.5
        mock_step.portfolio_score_after = 0.6
        mock_step.score_change = 0.1
        mock_step.available_cash_before = 2000.0
        mock_step.available_cash_after = 500.0

        mock_rec = MagicMock()
        mock_rec.symbol = "MSFT.US"
        mock_rec.estimated_value = 1000.0

        mock_settings_obj = MagicMock()
        mock_settings_obj.to_dict.return_value = {}

        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.get_cash_balances.return_value = []

        with (
            patch("app.jobs.cash_rebalance.SettingsRepository"),
            patch("app.jobs.cash_rebalance.PositionRepository") as mock_pos_repo,
            patch("app.jobs.cash_rebalance.StockRepository") as mock_stock_repo,
            patch("app.jobs.cash_rebalance.AllocationRepository") as mock_alloc_repo,
            patch(
                "app.jobs.cash_rebalance.get_tradernet_client",
                return_value=mock_client,
            ),
            patch(
                "app.domain.services.settings_service.SettingsService"
            ) as mock_settings,
            patch(
                "app.application.services.rebalancing_service.RebalancingService"
            ) as mock_service,
            patch("app.jobs.cash_rebalance.cache") as mock_cache,
        ):
            mock_pos_repo.return_value.get_all = AsyncMock(return_value=[])
            mock_stock_repo.return_value.get_all_active = AsyncMock(return_value=[])
            mock_alloc_repo.return_value.get_all = AsyncMock(return_value=[])
            mock_settings.return_value.get_settings = AsyncMock(
                return_value=mock_settings_obj
            )
            mock_service.return_value.get_recommendations = AsyncMock(
                return_value=[mock_step]
            )

            await _refresh_recommendation_cache()

            # Should have set cache exactly once (primary key only)
            assert mock_cache.set.call_count == 1

    @pytest.mark.asyncio
    async def test_handles_error_silently(self):
        """Test that errors are handled silently."""
        from app.jobs.cash_rebalance import _refresh_recommendation_cache

        with (
            patch("app.jobs.cash_rebalance.SettingsRepository"),
            patch(
                "app.jobs.cash_rebalance.PositionRepository",
                side_effect=Exception("DB error"),
            ),
        ):
            # Should not raise
            await _refresh_recommendation_cache()


class TestCheckAndRebalance:
    """Test main rebalance function."""

    @pytest.mark.asyncio
    async def test_uses_file_lock(self):
        """Test that file lock is used."""
        from app.jobs.cash_rebalance import check_and_rebalance

        with (
            patch("app.jobs.cash_rebalance.file_lock") as mock_lock,
            patch(
                "app.jobs.cash_rebalance._check_and_rebalance_internal"
            ) as mock_internal,
        ):
            mock_lock.return_value.__aenter__ = AsyncMock()
            mock_lock.return_value.__aexit__ = AsyncMock()

            await check_and_rebalance()

            mock_lock.assert_called_once_with("rebalance", timeout=600.0)
            mock_internal.assert_called_once()


class TestEventDrivenRebalancing:
    """Test event-driven rebalancing integration."""

    @pytest.mark.asyncio
    async def test_skips_rebalancing_when_no_triggers_met(self):
        """Test that rebalancing is skipped when no triggers are met.

        Bug caught: Rebalancing runs unnecessarily, causing excessive trading.
        """
        from app.domain.models import Position
        from app.domain.value_objects.currency import Currency
        from app.jobs.cash_rebalance import _check_and_rebalance_internal

        # Setup: No drift, no cash accumulation
        positions = [
            Position(
                symbol="AAPL",
                quantity=100,
                avg_price=150.0,
                currency=Currency.EUR,
                current_price=150.0,
                market_value_eur=15000.0,
                cost_basis_eur=15000.0,
            )
        ]
        # Note: AAPL is 20% target, current is 20% (no drift). Portfolio = 75000
        cash_balance = 100.0  # Below threshold

        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.get_total_cash_eur.return_value = cash_balance

        mock_settings = MagicMock()
        mock_settings.transaction_cost_fixed = 2.0
        mock_settings.transaction_cost_percent = 0.002

        with (
            patch("app.jobs.sync_trades.sync_trades"),
            patch("app.jobs.daily_sync.sync_portfolio"),
            patch("app.jobs.cash_rebalance._check_pnl_guardrails") as mock_pnl,
            patch("app.jobs.cash_rebalance.get_tradernet_client") as mock_get_client,
            patch("app.jobs.cash_rebalance.SettingsRepository") as mock_settings_repo,
            patch(
                "app.domain.services.settings_service.SettingsService"
            ) as mock_service,
            patch("app.jobs.cash_rebalance.PositionRepository") as mock_pos_repo,
            patch("app.jobs.cash_rebalance.TradeRepository"),
            patch("app.jobs.cash_rebalance.StockRepository") as mock_stock_repo,
            patch("app.jobs.cash_rebalance._get_next_holistic_action") as mock_action,
            patch("app.jobs.cash_rebalance._refresh_recommendation_cache"),
            patch("app.jobs.cash_rebalance.emit"),
            patch("app.jobs.cash_rebalance.set_processing"),
            patch("app.jobs.cash_rebalance.clear_processing"),
            patch(
                "app.domain.services.rebalancing_triggers.check_rebalance_triggers",
                new=AsyncMock(return_value=(False, "no triggers met")),
            ) as mock_check_triggers,
        ):
            mock_pnl.return_value = ({"status": "ok"}, True)
            mock_get_client.return_value = mock_client
            mock_service.return_value.get_settings = AsyncMock(
                return_value=mock_settings
            )
            mock_pos_repo.return_value.get_all = AsyncMock(return_value=positions)
            mock_stock_repo.return_value.get_all_active = AsyncMock(return_value=[])
            mock_action.return_value = None

            # Mock settings: event-driven enabled
            async def get_float(key, default):
                return {
                    "event_driven_rebalancing_enabled": 1.0,
                }.get(key, default)

            mock_settings_repo.return_value.get_float = AsyncMock(side_effect=get_float)

            await _check_and_rebalance_internal()

            # Verify trigger check was called
            mock_check_triggers.assert_called_once()
            # Verify _get_next_holistic_action was NOT called (skipped)
            mock_action.assert_not_called()

    @pytest.mark.asyncio
    async def test_proceeds_when_triggers_met(self):
        """Test that rebalancing proceeds when triggers are met.

        Bug caught: Rebalancing skipped even when triggers indicate need.
        """
        from app.domain.models import Position
        from app.domain.value_objects.currency import Currency
        from app.jobs.cash_rebalance import _check_and_rebalance_internal

        positions = [
            Position(
                symbol="AAPL",
                quantity=100,
                avg_price=150.0,
                currency=Currency.EUR,
                current_price=165.0,
                market_value_eur=16500.0,
                cost_basis_eur=15000.0,
            )
        ]
        # Note: Target allocation for AAPL is 20%

        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.get_total_cash_eur.return_value = 1000.0

        mock_settings = MagicMock()
        mock_settings.transaction_cost_fixed = 2.0
        mock_settings.transaction_cost_percent = 0.002

        mock_action = MagicMock()
        mock_action.symbol = "AAPL"
        mock_action.side = "BUY"

        with (
            patch("app.jobs.sync_trades.sync_trades"),
            patch("app.jobs.daily_sync.sync_portfolio"),
            patch("app.jobs.cash_rebalance._check_pnl_guardrails") as mock_pnl,
            patch("app.jobs.cash_rebalance.get_tradernet_client") as mock_get_client,
            patch("app.jobs.cash_rebalance.SettingsRepository") as mock_settings_repo,
            patch(
                "app.domain.services.settings_service.SettingsService"
            ) as mock_service,
            patch("app.jobs.cash_rebalance.PositionRepository") as mock_pos_repo,
            patch("app.jobs.cash_rebalance.TradeRepository") as mock_trade_repo,
            patch("app.jobs.cash_rebalance.StockRepository") as mock_stock_repo,
            patch(
                "app.jobs.cash_rebalance._get_next_holistic_action"
            ) as mock_get_action,
            patch("app.jobs.cash_rebalance._validate_next_action") as mock_validate,
            patch("app.jobs.cash_rebalance._execute_trade"),
            patch("app.jobs.cash_rebalance._refresh_recommendation_cache"),
            patch("app.jobs.cash_rebalance.emit"),
            patch("app.jobs.cash_rebalance.set_processing"),
            patch("app.jobs.cash_rebalance.clear_processing"),
            patch(
                "app.domain.services.rebalancing_triggers.check_rebalance_triggers"
            ) as mock_check_triggers,
        ):
            mock_pnl.return_value = (
                {"status": "ok", "can_buy": True, "can_sell": True},
                True,
            )
            mock_get_client.return_value = mock_client
            mock_service.return_value.get_settings = AsyncMock(
                return_value=mock_settings
            )
            mock_pos_repo.return_value.get_all = AsyncMock(return_value=positions)
            mock_stock_repo.return_value.get_all_active = AsyncMock(return_value=[])
            mock_get_action.return_value = mock_action
            mock_validate.return_value = True
            mock_trade_repo.return_value.has_recent_sell_order = AsyncMock(
                return_value=False
            )

            # Mock trigger check: triggers met
            mock_check_triggers.return_value = (True, "position drift detected")

            # Mock settings: event-driven enabled
            async def get_float(key, default):
                return {
                    "event_driven_rebalancing_enabled": 1.0,
                }.get(key, default)

            mock_settings_repo.return_value.get_float = AsyncMock(side_effect=get_float)

            await _check_and_rebalance_internal()

            # Verify trigger check was called
            mock_check_triggers.assert_called_once()
            # Verify _get_next_holistic_action WAS called (proceeded)
            mock_get_action.assert_called_once()

    @pytest.mark.asyncio
    async def test_proceeds_when_feature_disabled(self):
        """Test that rebalancing proceeds when feature is disabled (existing behavior).

        Bug caught: Rebalancing skipped when feature disabled, breaking existing behavior.
        """
        from app.domain.models import Position
        from app.domain.value_objects.currency import Currency
        from app.jobs.cash_rebalance import _check_and_rebalance_internal

        positions = [
            Position(
                symbol="AAPL",
                quantity=100,
                avg_price=150.0,
                currency=Currency.EUR,
                current_price=150.0,
                market_value_eur=15000.0,
                cost_basis_eur=15000.0,
            )
        ]

        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.get_total_cash_eur.return_value = 1000.0

        mock_settings = MagicMock()
        mock_settings.transaction_cost_fixed = 2.0
        mock_settings.transaction_cost_percent = 0.002

        mock_action = MagicMock()
        mock_action.symbol = "AAPL"
        mock_action.side = "BUY"

        with (
            patch("app.jobs.sync_trades.sync_trades"),
            patch("app.jobs.daily_sync.sync_portfolio"),
            patch("app.jobs.cash_rebalance._check_pnl_guardrails") as mock_pnl,
            patch("app.jobs.cash_rebalance.get_tradernet_client") as mock_get_client,
            patch("app.jobs.cash_rebalance.SettingsRepository") as mock_settings_repo,
            patch(
                "app.domain.services.settings_service.SettingsService"
            ) as mock_service,
            patch("app.jobs.cash_rebalance.PositionRepository") as mock_pos_repo,
            patch("app.jobs.cash_rebalance.TradeRepository") as mock_trade_repo,
            patch("app.jobs.cash_rebalance.StockRepository") as mock_stock_repo,
            patch(
                "app.jobs.cash_rebalance._get_next_holistic_action"
            ) as mock_get_action,
            patch("app.jobs.cash_rebalance._validate_next_action") as mock_validate,
            patch("app.jobs.cash_rebalance._execute_trade"),
            patch("app.jobs.cash_rebalance._refresh_recommendation_cache"),
            patch("app.jobs.cash_rebalance.emit"),
            patch("app.jobs.cash_rebalance.set_processing"),
            patch("app.jobs.cash_rebalance.clear_processing"),
            patch(
                "app.domain.services.rebalancing_triggers.check_rebalance_triggers"
            ) as mock_check_triggers,
        ):
            mock_pnl.return_value = (
                {"status": "ok", "can_buy": True, "can_sell": True},
                True,
            )
            mock_get_client.return_value = mock_client
            mock_service.return_value.get_settings = AsyncMock(
                return_value=mock_settings
            )
            mock_pos_repo.return_value.get_all = AsyncMock(return_value=positions)
            mock_stock_repo.return_value.get_all_active = AsyncMock(return_value=[])
            mock_get_action.return_value = mock_action
            mock_validate.return_value = True
            mock_trade_repo.return_value.has_recent_sell_order = AsyncMock(
                return_value=False
            )

            # Mock settings: event-driven DISABLED
            async def get_float(key, default):
                return {
                    "event_driven_rebalancing_enabled": 0.0,  # Disabled
                }.get(key, default)

            mock_settings_repo.return_value.get_float = AsyncMock(side_effect=get_float)

            await _check_and_rebalance_internal()

            # Verify trigger check was NOT called (feature disabled)
            mock_check_triggers.assert_not_called()
            # Verify _get_next_holistic_action WAS called (existing behavior)
            mock_get_action.assert_called_once()

    @pytest.mark.asyncio
    async def test_respects_enabled_setting(self):
        """Test that settings integration works correctly.

        Bug caught: Ignores user setting, always checks triggers.
        """
        from app.domain.models import Position
        from app.domain.value_objects.currency import Currency
        from app.jobs.cash_rebalance import _check_and_rebalance_internal

        positions = [
            Position(
                symbol="AAPL",
                quantity=100,
                avg_price=150.0,
                currency=Currency.EUR,
                current_price=150.0,
                market_value_eur=15000.0,
                cost_basis_eur=15000.0,
            )
        ]

        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.get_total_cash_eur.return_value = 1000.0

        mock_settings = MagicMock()
        mock_settings.transaction_cost_fixed = 2.0
        mock_settings.transaction_cost_percent = 0.002

        mock_action = MagicMock()
        mock_action.symbol = "AAPL"
        mock_action.side = "BUY"

        with (
            patch("app.jobs.sync_trades.sync_trades"),
            patch("app.jobs.daily_sync.sync_portfolio"),
            patch("app.jobs.cash_rebalance._check_pnl_guardrails") as mock_pnl,
            patch("app.jobs.cash_rebalance.get_tradernet_client") as mock_get_client,
            patch("app.jobs.cash_rebalance.SettingsRepository") as mock_settings_repo,
            patch(
                "app.domain.services.settings_service.SettingsService"
            ) as mock_service,
            patch("app.jobs.cash_rebalance.PositionRepository") as mock_pos_repo,
            patch("app.jobs.cash_rebalance.TradeRepository") as mock_trade_repo,
            patch("app.jobs.cash_rebalance.StockRepository") as mock_stock_repo,
            patch(
                "app.jobs.cash_rebalance._get_next_holistic_action"
            ) as mock_get_action,
            patch("app.jobs.cash_rebalance._validate_next_action") as mock_validate,
            patch("app.jobs.cash_rebalance._execute_trade"),
            patch("app.jobs.cash_rebalance._refresh_recommendation_cache"),
            patch("app.jobs.cash_rebalance.emit"),
            patch("app.jobs.cash_rebalance.set_processing"),
            patch("app.jobs.cash_rebalance.clear_processing"),
            patch(
                "app.domain.services.rebalancing_triggers.check_rebalance_triggers"
            ) as mock_check_triggers,
        ):
            mock_pnl.return_value = (
                {"status": "ok", "can_buy": True, "can_sell": True},
                True,
            )
            mock_get_client.return_value = mock_client
            mock_service.return_value.get_settings = AsyncMock(
                return_value=mock_settings
            )
            mock_pos_repo.return_value.get_all = AsyncMock(return_value=positions)
            mock_stock_repo.return_value.get_all_active = AsyncMock(return_value=[])
            mock_get_action.return_value = mock_action
            mock_validate.return_value = True
            mock_trade_repo.return_value.has_recent_sell_order = AsyncMock(
                return_value=False
            )

            # Mock settings: event-driven enabled
            async def get_float(key, default):
                return {
                    "event_driven_rebalancing_enabled": 1.0,
                }.get(key, default)

            mock_settings_repo.return_value.get_float = AsyncMock(side_effect=get_float)

            await _check_and_rebalance_internal()

            # Verify settings were checked
            assert mock_settings_repo.return_value.get_float.called
            # Verify trigger check was called (when enabled)
            mock_check_triggers.assert_called_once()
