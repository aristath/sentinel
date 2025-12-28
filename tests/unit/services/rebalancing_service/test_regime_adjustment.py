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
        mock_position_repo.get_total_value = AsyncMock(return_value=19000.0)

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "market_regime_detection_enabled": 1.0,  # Enabled
                "market_regime_bull_cash_reserve": 0.02,  # Bull reserve 2%
                "market_regime_bear_cash_reserve": 0.05,  # Bear reserve 5%
                "market_regime_sideways_cash_reserve": 0.03,  # Sideways reserve 3%
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

            # Mock optimizer with proper return value
            mock_optimizer = MagicMock()
            mock_optimization_result = MagicMock()
            mock_optimization_result.success = True
            mock_optimization_result.achieved_expected_return = 0.10
            mock_optimization_result.fallback_used = None
            mock_optimization_result.target_weights = {}
            mock_optimization_result.weight_changes = []
            mock_optimizer.optimize = AsyncMock(return_value=mock_optimization_result)

            # Mock DividendRepository to avoid database access
            mock_dividend_repo = AsyncMock()
            mock_dividend_repo.get_pending_dividends = AsyncMock(return_value={})

            with (
                patch(
                    "app.application.services.optimization.PortfolioOptimizer",
                    return_value=mock_optimizer,
                ),
                patch(
                    "app.repositories.DividendRepository",
                    return_value=mock_dividend_repo,
                ),
            ):
                # Create properly mocked allocation repo
                mock_allocation_repo = AsyncMock()
                mock_allocation_repo.get_all = AsyncMock(return_value={})

                # Create properly mocked db_manager
                mock_db_manager = MagicMock()
                mock_db_manager.state = MagicMock()
                mock_db_manager.state.fetchall = AsyncMock(return_value=[])

                service = RebalancingService(
                    stock_repo=mock_stock_repo,
                    position_repo=mock_position_repo,
                    tradernet_client=mock_tradernet_client,
                    allocation_repo=mock_allocation_repo,
                    portfolio_repo=AsyncMock(),
                    trade_repo=AsyncMock(),
                    settings_repo=mock_settings_repo,
                    recommendation_repo=AsyncMock(),
                    db_manager=mock_db_manager,
                    exchange_rate_service=AsyncMock(),
                )

                # Call get_recommendations
                await service.get_recommendations()

                # Verify optimizer was called with bull cash reserve
                # Portfolio value = 19000 (positions) + 1000 (cash) = 20000
                # Bull reserve = 2% = 20000 * 0.02 = 400, but min is 500
                # Expected = max(400, 500) = 500
                call_args = mock_optimizer.optimize.call_args
                assert call_args is not None
                min_cash_reserve = call_args.kwargs.get("min_cash_reserve")
                assert (
                    min_cash_reserve == 500.0
                ), f"Expected 500.0 (max of 2% of 20000=400 and floor 500), got {min_cash_reserve}"

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
        mock_position_repo.get_total_value = AsyncMock(return_value=19000.0)

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "market_regime_detection_enabled": 1.0,
                "market_regime_bull_cash_reserve": 0.02,  # Bull reserve 2%
                "market_regime_bear_cash_reserve": 0.05,  # Bear reserve 5%
                "market_regime_sideways_cash_reserve": 0.03,  # Sideways reserve 3%
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

            # Mock optimizer with proper return value
            mock_optimizer = MagicMock()
            mock_optimization_result = MagicMock()
            mock_optimization_result.success = True
            mock_optimization_result.achieved_expected_return = 0.10
            mock_optimization_result.fallback_used = None
            mock_optimization_result.target_weights = {}
            mock_optimization_result.weight_changes = []
            mock_optimizer.optimize = AsyncMock(return_value=mock_optimization_result)

            # Mock DividendRepository to avoid database access
            mock_dividend_repo = AsyncMock()
            mock_dividend_repo.get_pending_dividends = AsyncMock(return_value={})

            with (
                patch(
                    "app.application.services.optimization.PortfolioOptimizer",
                    return_value=mock_optimizer,
                ),
                patch(
                    "app.repositories.DividendRepository",
                    return_value=mock_dividend_repo,
                ),
            ):
                # Create properly mocked allocation repo
                mock_allocation_repo = AsyncMock()
                mock_allocation_repo.get_all = AsyncMock(return_value={})

                # Create properly mocked db_manager
                mock_db_manager = MagicMock()
                mock_db_manager.state = MagicMock()
                mock_db_manager.state.fetchall = AsyncMock(return_value=[])

                service = RebalancingService(
                    stock_repo=mock_stock_repo,
                    position_repo=mock_position_repo,
                    tradernet_client=mock_tradernet_client,
                    allocation_repo=mock_allocation_repo,
                    portfolio_repo=AsyncMock(),
                    trade_repo=AsyncMock(),
                    settings_repo=mock_settings_repo,
                    recommendation_repo=AsyncMock(),
                    db_manager=mock_db_manager,
                    exchange_rate_service=AsyncMock(),
                )

                await service.get_recommendations()

                call_args = mock_optimizer.optimize.call_args
                assert call_args is not None
                min_cash_reserve = call_args.kwargs.get("min_cash_reserve")
                # Portfolio value = 19000 (positions) + 1000 (cash) = 20000
                # Bear reserve = 5% = 20000 * 0.05 = 1000
                # Expected = max(1000, 500) = 1000
                assert (
                    min_cash_reserve == 1000.0
                ), f"Expected 1000.0 (5% of 20000), got {min_cash_reserve}"

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
        mock_position_repo.get_total_value = AsyncMock(return_value=19000.0)

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "market_regime_detection_enabled": 1.0,
                "market_regime_bull_cash_reserve": 0.02,  # Bull reserve 2%
                "market_regime_bear_cash_reserve": 0.05,  # Bear reserve 5%
                "market_regime_sideways_cash_reserve": 0.03,  # Sideways reserve 3%
                "optimizer_blend": 0.5,
                "optimizer_target_return": 0.11,
                "min_cash_reserve": 500.0,
            }.get(key, default)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)

        mock_tradernet_client = MagicMock()
        mock_tradernet_client.is_connected = True
        mock_tradernet_client.get_total_cash_eur = MagicMock(return_value=1000.0)

        # Mock portfolio value: 20000 EUR (positions + cash)
        # With 3% sideways reserve: 20000 * 0.03 = 600 EUR
        # Expected = max(600, 500) = 600 EUR
        mock_position_repo.get_total_value = AsyncMock(return_value=19000.0)

        with patch(
            "app.application.services.rebalancing_service.detect_market_regime",
            new_callable=AsyncMock,
        ) as mock_detect_regime:
            mock_detect_regime.return_value = "sideways"

            # Mock optimizer with proper return value
            mock_optimizer = MagicMock()
            mock_optimization_result = MagicMock()
            mock_optimization_result.success = True
            mock_optimization_result.achieved_expected_return = 0.10
            mock_optimization_result.fallback_used = None
            mock_optimization_result.target_weights = {}
            mock_optimization_result.weight_changes = []
            mock_optimizer.optimize = AsyncMock(return_value=mock_optimization_result)

            # Mock DividendRepository to avoid database access
            mock_dividend_repo = AsyncMock()
            mock_dividend_repo.get_pending_dividends = AsyncMock(return_value={})

            with (
                patch(
                    "app.application.services.optimization.PortfolioOptimizer",
                    return_value=mock_optimizer,
                ),
                patch(
                    "app.repositories.DividendRepository",
                    return_value=mock_dividend_repo,
                ),
            ):
                # Create properly mocked allocation repo
                mock_allocation_repo = AsyncMock()
                mock_allocation_repo.get_all = AsyncMock(return_value={})

                # Create properly mocked db_manager
                mock_db_manager = MagicMock()
                mock_db_manager.state = MagicMock()
                mock_db_manager.state.fetchall = AsyncMock(return_value=[])

                service = RebalancingService(
                    stock_repo=mock_stock_repo,
                    position_repo=mock_position_repo,
                    tradernet_client=mock_tradernet_client,
                    allocation_repo=mock_allocation_repo,
                    portfolio_repo=AsyncMock(),
                    trade_repo=AsyncMock(),
                    settings_repo=mock_settings_repo,
                    recommendation_repo=AsyncMock(),
                    db_manager=mock_db_manager,
                    exchange_rate_service=AsyncMock(),
                )

                await service.get_recommendations()

                call_args = mock_optimizer.optimize.call_args
                assert call_args is not None
                min_cash_reserve = call_args.kwargs.get("min_cash_reserve")
                # Portfolio value = 19000 (positions) + 1000 (cash) = 20000
                # Sideways reserve = 3% = 20000 * 0.03 = 600
                # Expected = max(600, 500) = 600
                assert (
                    min_cash_reserve == 600.0
                ), f"Expected 600.0 (3% of 20000), got {min_cash_reserve}"

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
        mock_position_repo.get_total_value = AsyncMock(return_value=19000.0)

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

        # Mock DividendRepository to avoid database access
        mock_dividend_repo = AsyncMock()
        mock_dividend_repo.get_pending_dividends = AsyncMock(return_value={})

        with (
            patch(
                "app.application.services.optimization.PortfolioOptimizer",
                return_value=mock_optimizer,
            ),
            patch(
                "app.repositories.DividendRepository",
                return_value=mock_dividend_repo,
            ),
        ):
            # Create properly mocked allocation repo
            mock_allocation_repo = AsyncMock()
            mock_allocation_repo.get_all = AsyncMock(return_value={})

            # Create properly mocked db_manager
            mock_db_manager = MagicMock()
            mock_db_manager.state = MagicMock()
            mock_db_manager.state.fetchall = AsyncMock(return_value=[])

            service = RebalancingService(
                stock_repo=mock_stock_repo,
                position_repo=mock_position_repo,
                tradernet_client=mock_tradernet_client,
                allocation_repo=mock_allocation_repo,
                portfolio_repo=AsyncMock(),
                trade_repo=AsyncMock(),
                settings_repo=mock_settings_repo,
                recommendation_repo=AsyncMock(),
                db_manager=mock_db_manager,
                exchange_rate_service=AsyncMock(),
            )

            await service.get_recommendations()

            call_args = mock_optimizer.optimize.call_args
            assert call_args is not None
            min_cash_reserve = call_args.kwargs.get("min_cash_reserve")
            assert (
                min_cash_reserve == 550.0
            ), f"Expected 550.0 (default), got {min_cash_reserve}"
