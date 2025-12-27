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
        self, mock_trade_repo, mock_buy_action
    ):
        """Test BUY is allowed when cash is sufficient."""
        from app.jobs.cash_rebalance import _validate_next_action

        pnl_status = {"can_buy": True, "can_sell": True}
        cash_balance = 1000.0
        min_trade_size = 500.0

        result = await _validate_next_action(
            mock_buy_action,
            pnl_status,
            cash_balance,
            min_trade_size,
            mock_trade_repo,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_blocks_buy_when_cash_insufficient(
        self, mock_trade_repo, mock_buy_action
    ):
        """Test BUY is blocked when cash is insufficient."""
        from app.jobs.cash_rebalance import _validate_next_action

        pnl_status = {"can_buy": True, "can_sell": True}
        cash_balance = 400.0
        min_trade_size = 500.0

        result = await _validate_next_action(
            mock_buy_action,
            pnl_status,
            cash_balance,
            min_trade_size,
            mock_trade_repo,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_blocks_buy_when_pnl_guardrail_active(
        self, mock_trade_repo, mock_buy_action
    ):
        """Test BUY is blocked by P&L guardrail."""
        from app.jobs.cash_rebalance import _validate_next_action

        pnl_status = {"can_buy": False, "can_sell": True, "reason": "Daily loss limit"}
        cash_balance = 1000.0
        min_trade_size = 500.0

        result = await _validate_next_action(
            mock_buy_action,
            pnl_status,
            cash_balance,
            min_trade_size,
            mock_trade_repo,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_blocks_sell_when_pnl_guardrail_active(
        self, mock_trade_repo, mock_sell_action
    ):
        """Test SELL is blocked by P&L guardrail."""
        from app.jobs.cash_rebalance import _validate_next_action

        pnl_status = {"can_buy": True, "can_sell": False, "reason": "Max loss reached"}
        cash_balance = 1000.0
        min_trade_size = 500.0

        result = await _validate_next_action(
            mock_sell_action,
            pnl_status,
            cash_balance,
            min_trade_size,
            mock_trade_repo,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_blocks_sell_when_recent_order_exists(
        self, mock_trade_repo, mock_sell_action
    ):
        """Test SELL is blocked when recent sell order exists."""
        from app.jobs.cash_rebalance import _validate_next_action

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
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_allows_sell_when_no_recent_order(
        self, mock_trade_repo, mock_sell_action
    ):
        """Test SELL is allowed when no recent order exists."""
        from app.jobs.cash_rebalance import _validate_next_action

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
            patch("app.domain.services.settings_service.SettingsService") as mock_service,
            patch("app.jobs.cash_rebalance.emit"),
            patch("app.jobs.cash_rebalance.set_processing"),
            patch("app.jobs.cash_rebalance.set_error") as mock_set_error,
            patch("app.jobs.cash_rebalance.clear_processing"),
        ):
            mock_pnl.return_value = ({"status": "ok"}, True)
            mock_get_client.return_value = mock_client
            mock_service.return_value.get_settings.return_value = MagicMock(
                transaction_cost_fixed=5.0,
                transaction_cost_percent=0.1,
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
            patch("app.domain.services.settings_service.SettingsService") as mock_service,
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
            mock_service.return_value.get_settings.return_value = mock_settings
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

        with (
            patch("app.jobs.cash_rebalance.PositionRepository") as mock_pos_repo,
            patch("app.jobs.cash_rebalance.SettingsRepository"),
            patch(
                "app.domain.services.settings_service.SettingsService"
            ) as mock_settings,
            patch("app.jobs.cash_rebalance.cache") as mock_cache,
        ):
            mock_pos_repo.return_value.get_all = AsyncMock(return_value=[])
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

        with (
            patch("app.jobs.cash_rebalance.SettingsRepository"),
            patch("app.jobs.cash_rebalance.PositionRepository") as mock_pos_repo,
            patch(
                "app.domain.services.settings_service.SettingsService"
            ) as mock_settings,
            patch(
                "app.application.services.rebalancing_service.RebalancingService"
            ) as mock_service,
            patch("app.jobs.cash_rebalance.cache") as mock_cache,
        ):
            mock_pos_repo.return_value.get_all = AsyncMock(return_value=[])
            mock_settings.return_value.get_settings = AsyncMock(
                return_value=mock_settings_obj
            )
            mock_service.return_value.get_multi_step_recommendations = AsyncMock(
                return_value=[mock_step]
            )
            mock_service.return_value.get_recommendations = AsyncMock(
                return_value=[mock_rec]
            )
            mock_service.return_value.calculate_sell_recommendations = AsyncMock(
                return_value=[]
            )

            await _refresh_recommendation_cache()

            # Should have set cache multiple times
            assert mock_cache.set.call_count >= 1

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
