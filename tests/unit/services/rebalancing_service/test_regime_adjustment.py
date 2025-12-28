"""Tests for regime-based cash reserve adjustment in rebalancing service.

These tests validate that cash reserves are adjusted based on market regime.
CRITICAL: Tests catch real bugs that would cause wrong cash reserve usage.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestRegimeBasedCashReserve:
    """Test regime-based cash reserve adjustment."""

    @pytest.mark.asyncio
    async def test_bull_market_uses_bull_cash_reserve(self):
        """Test that bull market uses bull_cash_reserve setting.

        Bug caught: Wrong cash reserve used in bull market.
        """
        from app.application.services.rebalancing_service import RebalancingService

        # Setup mocks
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[])

        mock_position_repo = AsyncMock()
        mock_position_repo.get_all = AsyncMock(return_value=[])

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "market_regime_detection_enabled": 1.0,  # Enabled
                "market_regime_bull_cash_reserve": 400.0,  # Bull reserve
                "market_regime_bear_cash_reserve": 600.0,  # Bear reserve
                "market_regime_sideways_cash_reserve": 500.0,  # Sideways reserve
                "optimizer_blend": 0.5,
                "optimizer_target_return": 0.11,
                "min_cash_reserve": 500.0,  # Default (should be overridden)
            }.get(key, default)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)

        mock_tradernet_client = MagicMock()
        mock_tradernet_client.is_connected = True
        mock_tradernet_client.get_total_cash_eur = MagicMock(return_value=1000.0)

        # Mock regime detection to return "bull"
        with patch(
            "app.application.services.rebalancing_service.detect_market_regime",
            new_callable=AsyncMock,
        ) as mock_detect_regime:
            mock_detect_regime.return_value = "bull"

            # Mock optimizer
            mock_optimizer = MagicMock()
            mock_optimizer.optimize = AsyncMock()

            with (
                patch(
                    "app.application.services.rebalancing_service.PortfolioOptimizer",
                    return_value=mock_optimizer,
                ),
                patch(
                    "app.application.services.rebalancing_service.SettingsRepository",
                    return_value=mock_settings_repo,
                ),
            ):
                service = RebalancingService(
                    stock_repo=mock_stock_repo,
                    position_repo=mock_position_repo,
                    tradernet_client=mock_tradernet_client,
                    allocation_repo=AsyncMock(),
                )

                # Call get_recommendations
                await service.get_recommendations()

                # Verify optimizer was called with bull cash reserve (400.0)
                call_args = mock_optimizer.optimize.call_args
                assert call_args is not None
                min_cash_reserve = call_args.kwargs.get("min_cash_reserve")
                assert (
                    min_cash_reserve == 400.0
                ), f"Expected 400.0, got {min_cash_reserve}"

    @pytest.mark.asyncio
    async def test_bear_market_uses_bear_cash_reserve(self):
        """Test that bear market uses bear_cash_reserve setting.

        Bug caught: Wrong cash reserve used in bear market.
        """
        from app.application.services.rebalancing_service import RebalancingService

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[])

        mock_position_repo = AsyncMock()
        mock_position_repo.get_all = AsyncMock(return_value=[])

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "market_regime_detection_enabled": 1.0,
                "market_regime_bull_cash_reserve": 400.0,
                "market_regime_bear_cash_reserve": 600.0,  # Bear reserve
                "market_regime_sideways_cash_reserve": 500.0,
                "optimizer_blend": 0.5,
                "optimizer_target_return": 0.11,
                "min_cash_reserve": 500.0,
            }.get(key, default)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)

        mock_tradernet_client = MagicMock()
        mock_tradernet_client.is_connected = True
        mock_tradernet_client.get_total_cash_eur = MagicMock(return_value=1000.0)

        with patch(
            "app.application.services.rebalancing_service.detect_market_regime",
            new_callable=AsyncMock,
        ) as mock_detect_regime:
            mock_detect_regime.return_value = "bear"

            mock_optimizer = MagicMock()
            mock_optimizer.optimize = AsyncMock()

            with (
                patch(
                    "app.application.services.rebalancing_service.PortfolioOptimizer",
                    return_value=mock_optimizer,
                ),
                patch(
                    "app.application.services.rebalancing_service.SettingsRepository",
                    return_value=mock_settings_repo,
                ),
            ):
                service = RebalancingService(
                    stock_repo=mock_stock_repo,
                    position_repo=mock_position_repo,
                    tradernet_client=mock_tradernet_client,
                    allocation_repo=AsyncMock(),
                )

                await service.get_recommendations()

                call_args = mock_optimizer.optimize.call_args
                assert call_args is not None
                min_cash_reserve = call_args.kwargs.get("min_cash_reserve")
                assert (
                    min_cash_reserve == 600.0
                ), f"Expected 600.0, got {min_cash_reserve}"

    @pytest.mark.asyncio
    async def test_sideways_market_uses_sideways_cash_reserve(self):
        """Test that sideways market uses sideways_cash_reserve setting.

        Bug caught: Wrong cash reserve used in sideways market.
        """
        from app.application.services.rebalancing_service import RebalancingService

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[])

        mock_position_repo = AsyncMock()
        mock_position_repo.get_all = AsyncMock(return_value=[])

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "market_regime_detection_enabled": 1.0,
                "market_regime_bull_cash_reserve": 400.0,
                "market_regime_bear_cash_reserve": 600.0,
                "market_regime_sideways_cash_reserve": 500.0,  # Sideways reserve
                "optimizer_blend": 0.5,
                "optimizer_target_return": 0.11,
                "min_cash_reserve": 500.0,
            }.get(key, default)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)

        mock_tradernet_client = MagicMock()
        mock_tradernet_client.is_connected = True
        mock_tradernet_client.get_total_cash_eur = MagicMock(return_value=1000.0)

        with patch(
            "app.application.services.rebalancing_service.detect_market_regime",
            new_callable=AsyncMock,
        ) as mock_detect_regime:
            mock_detect_regime.return_value = "sideways"

            mock_optimizer = MagicMock()
            mock_optimizer.optimize = AsyncMock()

            with (
                patch(
                    "app.application.services.rebalancing_service.PortfolioOptimizer",
                    return_value=mock_optimizer,
                ),
                patch(
                    "app.application.services.rebalancing_service.SettingsRepository",
                    return_value=mock_settings_repo,
                ),
            ):
                service = RebalancingService(
                    stock_repo=mock_stock_repo,
                    position_repo=mock_position_repo,
                    tradernet_client=mock_tradernet_client,
                    allocation_repo=AsyncMock(),
                )

                await service.get_recommendations()

                call_args = mock_optimizer.optimize.call_args
                assert call_args is not None
                min_cash_reserve = call_args.kwargs.get("min_cash_reserve")
                assert (
                    min_cash_reserve == 500.0
                ), f"Expected 500.0, got {min_cash_reserve}"

    @pytest.mark.asyncio
    async def test_disabled_regime_detection_uses_default_cash_reserve(self):
        """Test that default cash reserve is used when regime detection is disabled.

        Bug caught: Regime-adjusted reserve used when feature is disabled.
        """
        from app.application.services.rebalancing_service import RebalancingService

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[])

        mock_position_repo = AsyncMock()
        mock_position_repo.get_all = AsyncMock(return_value=[])

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "market_regime_detection_enabled": 0.0,  # Disabled
                "market_regime_bull_cash_reserve": 400.0,
                "market_regime_bear_cash_reserve": 600.0,
                "market_regime_sideways_cash_reserve": 500.0,
                "optimizer_blend": 0.5,
                "optimizer_target_return": 0.11,
                "min_cash_reserve": 550.0,  # Default (should be used)
            }.get(key, default)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)

        mock_tradernet_client = MagicMock()
        mock_tradernet_client.is_connected = True
        mock_tradernet_client.get_total_cash_eur = MagicMock(return_value=1000.0)

        mock_optimizer = MagicMock()
        mock_optimizer.optimize = AsyncMock()

        with (
            patch(
                "app.application.services.rebalancing_service.PortfolioOptimizer",
                return_value=mock_optimizer,
            ),
            patch(
                "app.application.services.rebalancing_service.SettingsRepository",
                return_value=mock_settings_repo,
            ),
        ):
            service = RebalancingService(
                stock_repo=mock_stock_repo,
                position_repo=mock_position_repo,
                tradernet_client=mock_tradernet_client,
                allocation_repo=AsyncMock(),
            )

            await service.get_recommendations()

            call_args = mock_optimizer.optimize.call_args
            assert call_args is not None
            min_cash_reserve = call_args.kwargs.get("min_cash_reserve")
            assert (
                min_cash_reserve == 550.0
            ), f"Expected 550.0 (default), got {min_cash_reserve}"
