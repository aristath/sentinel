"""Tests for optimizer API endpoints.

These tests validate portfolio optimization status retrieval and optimization
execution. Critical for portfolio rebalancing recommendations.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.optimization.api.optimizer import (
    _optimization_result_to_dict,
    get_optimizer_status,
    run_optimization,
    update_optimization_cache,
)
from app.modules.optimization.services.portfolio_optimizer import (
    OptimizationResult,
    WeightChange,
)


@pytest.fixture
def mock_settings_repo():
    """Mock settings repository."""
    return AsyncMock()


@pytest.fixture
def mock_settings_service():
    """Mock settings service."""
    return AsyncMock()


@pytest.fixture
def mock_stock_repo():
    """Mock stock repository."""
    return AsyncMock()


@pytest.fixture
def mock_position_repo():
    """Mock position repository."""
    return AsyncMock()


@pytest.fixture
def mock_dividend_repo():
    """Mock dividend repository."""
    return AsyncMock()


@pytest.fixture
def mock_settings():
    """Mock settings object."""
    settings = MagicMock()
    settings.optimizer_blend = 0.5
    settings.optimizer_target_return = 0.11
    settings.min_cash_reserve = 500.0
    settings.transaction_cost_fixed = 2.0
    settings.transaction_cost_percent = 0.002
    return settings


@pytest.fixture
def sample_optimization_result():
    """Sample optimization result."""
    weight_changes = [
        WeightChange(
            symbol="AAPL",
            current_weight=0.10,
            target_weight=0.15,
            change=0.05,
        ),
        WeightChange(
            symbol="GOOGL",
            current_weight=0.08,
            target_weight=0.12,
            change=0.04,
        ),
        WeightChange(
            symbol="MSFT",
            current_weight=0.12,
            target_weight=0.08,
            change=-0.04,
        ),
    ]

    return OptimizationResult(
        timestamp=datetime(2024, 1, 15, 10, 30, 0),
        target_return=0.11,
        achieved_expected_return=0.105,
        blend_used=0.5,
        fallback_used=None,
        target_weights={"AAPL": 0.15, "GOOGL": 0.12, "MSFT": 0.08},
        weight_changes=weight_changes,
        high_correlations=[{"symbol1": "AAPL", "symbol2": "MSFT", "correlation": 0.85}],
        constraints_summary={"min_weight": 0.01, "max_weight": 0.25},
        success=True,
        error=None,
    )


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset the module-level cache before each test."""
    import app.modules.optimization.api.optimizer as optimizer_module

    optimizer_module._last_optimization_result = None
    optimizer_module._last_optimization_time = None
    yield
    # Clean up after test
    optimizer_module._last_optimization_result = None
    optimizer_module._last_optimization_time = None


@pytest.fixture(autouse=True)
def mock_grouping_repo():
    """Auto-mock GroupingRepository for all tests in this file.

    The GroupingRepository was added to optimizer.py but tests weren't updated.
    This fixture ensures all tests have it mocked without modifying each test.
    """
    with patch("app.api.optimizer.GroupingRepository"):
        yield


class TestGetOptimizerStatus:
    """Test the GET /optimizer endpoint."""

    @pytest.mark.asyncio
    async def test_returns_status_without_cache(self, mock_settings):
        """Test that status is returned when no optimization has run."""
        with patch("app.api.optimizer.SettingsRepository") as mock_repo_class:
            with patch("app.api.optimizer.SettingsService") as mock_service_class:
                # Setup mocks
                mock_repo = AsyncMock()
                mock_repo_class.return_value = mock_repo

                mock_service = AsyncMock()
                mock_service.get_settings.return_value = mock_settings
                mock_service_class.return_value = mock_service

                with patch(
                    "app.modules.rebalancing.services.rebalancing_service.calculate_min_trade_amount",
                    return_value=285.71,
                ):
                    result = await get_optimizer_status()

                assert result["status"] == "ready"
                assert result["last_run"] is None
                assert result["settings"]["optimizer_blend"] == 0.5
                assert result["settings"]["optimizer_target_return"] == 0.11
                assert result["settings"]["min_cash_reserve"] == 500.0
                assert result["settings"]["min_trade_amount"] == 285.71

    @pytest.mark.asyncio
    async def test_returns_status_with_cached_result(self, mock_settings):
        """Test that cached optimization result is included."""
        import app.modules.optimization.api.optimizer as optimizer_module

        # Setup cache
        cached_result = {
            "success": True,
            "target_return_pct": 11.0,
            "achieved_return_pct": 10.5,
        }
        cached_time = datetime(2024, 1, 15, 10, 30, 0)

        optimizer_module._last_optimization_result = cached_result
        optimizer_module._last_optimization_time = cached_time

        with patch("app.api.optimizer.SettingsRepository") as mock_repo_class:
            with patch("app.api.optimizer.SettingsService") as mock_service_class:
                mock_repo = AsyncMock()
                mock_repo_class.return_value = mock_repo

                mock_service = AsyncMock()
                mock_service.get_settings.return_value = mock_settings
                mock_service_class.return_value = mock_service

                with patch(
                    "app.modules.rebalancing.services.rebalancing_service.calculate_min_trade_amount",
                    return_value=285.71,
                ):
                    result = await get_optimizer_status()

                assert result["last_run"] == cached_result
                assert result["last_run_time"] == "2024-01-15T10:30:00"

    @pytest.mark.asyncio
    async def test_calculates_min_trade_amount(self, mock_settings):
        """Test that min trade amount is calculated from transaction costs."""
        with patch("app.api.optimizer.SettingsRepository") as mock_repo_class:
            with patch("app.api.optimizer.SettingsService") as mock_service_class:
                mock_repo = AsyncMock()
                mock_repo_class.return_value = mock_repo

                mock_service = AsyncMock()
                mock_service.get_settings.return_value = mock_settings
                mock_service_class.return_value = mock_service

                with patch(
                    "app.modules.rebalancing.services.rebalancing_service.calculate_min_trade_amount"
                ) as mock_calc:
                    mock_calc.return_value = 285.71

                    result = await get_optimizer_status()

                    mock_calc.assert_called_once_with(2.0, 0.002)
                    assert result["settings"]["min_trade_amount"] == 285.71


class TestRunOptimization:
    """Test the POST /optimizer/run endpoint."""

    @pytest.mark.asyncio
    async def test_run_optimization_success(
        self, mock_settings, sample_optimization_result
    ):
        """Test successful optimization run."""
        # Setup mocks
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL"
        mock_stock.yahoo_symbol = "AAPL"

        mock_position = MagicMock()
        mock_position.symbol = "AAPL"
        mock_position.quantity = 10
        mock_position.market_value_eur = 1500.0

        with patch("app.api.optimizer.SettingsRepository") as mock_repo_class:
            with patch("app.api.optimizer.SettingsService") as mock_service_class:
                with patch("app.api.optimizer.StockRepository") as mock_stock_class:
                    with patch(
                        "app.api.optimizer.PositionRepository"
                    ) as mock_position_class:
                        with patch(
                            "app.api.optimizer.DividendRepository"
                        ) as mock_dividend_class:
                            with patch("app.api.optimizer.yahoo") as mock_yahoo:
                                with patch(
                                    "app.api.optimizer.TradernetClient"
                                ) as mock_client_class:
                                    with patch(
                                        "app.api.optimizer.PortfolioOptimizer"
                                    ) as mock_optimizer_class:
                                        with patch(
                                            "app.api.optimizer.AllocationRepository"
                                        ) as mock_allocation_repo_class:
                                            # Setup repository mocks
                                            mock_settings_repo = AsyncMock()
                                            mock_repo_class.return_value = (
                                                mock_settings_repo
                                            )

                                            # Setup allocation_repo mock
                                            mock_allocation_repo = AsyncMock()
                                            mock_allocation_repo.get_country_group_targets.return_value = {
                                                "United States": 50.0,  # 50% -> 0.5
                                                "Germany": 30.0,  # 30% -> 0.3
                                            }
                                            mock_allocation_repo.get_industry_group_targets.return_value = {
                                                "Consumer Electronics": 40.0,  # 40% -> 0.4
                                            }
                                            mock_allocation_repo_class.return_value = (
                                                mock_allocation_repo
                                            )

                                            mock_service = AsyncMock()
                                            mock_service.get_settings.return_value = (
                                                mock_settings
                                            )
                                            mock_service_class.return_value = (
                                                mock_service
                                            )

                                            mock_stock_repo = AsyncMock()
                                            mock_stock_repo.get_all.return_value = [
                                                mock_stock
                                            ]
                                            mock_stock_class.return_value = (
                                                mock_stock_repo
                                            )

                                            mock_position_repo = AsyncMock()
                                            mock_position_repo.get_all.return_value = [
                                                mock_position
                                            ]
                                            mock_position_class.return_value = (
                                                mock_position_repo
                                            )

                                            mock_dividend_repo = AsyncMock()
                                            mock_dividend_repo.get_pending_bonuses.return_value = (
                                                {}
                                            )
                                            mock_dividend_class.return_value = (
                                                mock_dividend_repo
                                            )

                                            # Setup Yahoo Finance mock
                                            mock_yahoo.get_batch_quotes.return_value = {
                                                "AAPL": 150.0
                                            }

                                            # Setup Tradernet mock
                                            mock_client = MagicMock()
                                            mock_client.get_total_cash_eur.return_value = (
                                                5000.0
                                            )
                                            mock_client_class.shared.return_value = (
                                                mock_client
                                            )

                                            # Setup optimizer mock
                                            mock_optimizer = AsyncMock()
                                            mock_optimizer.optimize.return_value = (
                                                sample_optimization_result
                                            )
                                            mock_optimizer_class.return_value = (
                                                mock_optimizer
                                            )

                                            result = await run_optimization()

        assert result["success"] is True
        assert "result" in result
        assert "timestamp" in result
        assert result["result"]["success"] is True
        assert result["result"]["target_return_pct"] == 11.0
        assert result["result"]["achieved_return_pct"] == 10.5

    @pytest.mark.asyncio
    async def test_run_optimization_no_stocks(self, mock_settings):
        """Test error when no stocks in universe."""
        with patch("app.api.optimizer.SettingsRepository") as mock_repo_class:
            with patch("app.api.optimizer.SettingsService") as mock_service_class:
                with patch("app.api.optimizer.StockRepository") as mock_stock_class:
                    with patch(
                        "app.api.optimizer.PositionRepository"
                    ) as mock_position_class:
                        mock_settings_repo = AsyncMock()
                        mock_repo_class.return_value = mock_settings_repo

                        mock_service = AsyncMock()
                        mock_service.get_settings.return_value = mock_settings
                        mock_service_class.return_value = mock_service

                        mock_stock_repo = AsyncMock()
                        mock_stock_repo.get_all.return_value = []  # No stocks
                        mock_stock_class.return_value = mock_stock_repo

                        mock_position_repo = AsyncMock()
                        mock_position_class.return_value = mock_position_repo

                        with pytest.raises(HTTPException) as exc_info:
                            await run_optimization()

                        assert exc_info.value.status_code == 400
                        assert "No stocks in universe" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_run_optimization_caches_result(
        self, mock_settings, sample_optimization_result
    ):
        """Test that optimization result is cached."""
        import app.modules.optimization.api.optimizer as optimizer_module

        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL"
        mock_stock.yahoo_symbol = "AAPL"

        with patch("app.api.optimizer.SettingsRepository") as mock_repo_class:
            with patch("app.api.optimizer.SettingsService") as mock_service_class:
                with patch("app.api.optimizer.StockRepository") as mock_stock_class:
                    with patch(
                        "app.api.optimizer.PositionRepository"
                    ) as mock_position_class:
                        with patch(
                            "app.api.optimizer.DividendRepository"
                        ) as mock_dividend_class:
                            with patch("app.api.optimizer.yahoo") as mock_yahoo:
                                with patch(
                                    "app.api.optimizer.TradernetClient"
                                ) as mock_client_class:
                                    with patch(
                                        "app.api.optimizer.PortfolioOptimizer"
                                    ) as mock_optimizer_class:
                                        with patch(
                                            "app.api.optimizer.AllocationRepository"
                                        ) as mock_allocation_repo_class:
                                            # Setup mocks (abbreviated)
                                            mock_settings_repo = AsyncMock()
                                            mock_repo_class.return_value = (
                                                mock_settings_repo
                                            )

                                            # Setup allocation_repo mock
                                            mock_allocation_repo = AsyncMock()
                                            mock_allocation_repo.get_country_group_targets.return_value = (
                                                {}
                                            )
                                            mock_allocation_repo.get_industry_group_targets.return_value = (
                                                {}
                                            )
                                            mock_allocation_repo_class.return_value = (
                                                mock_allocation_repo
                                            )

                                            mock_service = AsyncMock()
                                            mock_service.get_settings.return_value = (
                                                mock_settings
                                            )
                                            mock_service_class.return_value = (
                                                mock_service
                                            )

                                            mock_stock_repo = AsyncMock()
                                            mock_stock_repo.get_all.return_value = [
                                                mock_stock
                                            ]
                                            mock_stock_class.return_value = (
                                                mock_stock_repo
                                            )

                                            mock_position_repo = AsyncMock()
                                            mock_position_repo.get_all.return_value = []
                                            mock_position_class.return_value = (
                                                mock_position_repo
                                            )

                                            mock_dividend_repo = AsyncMock()
                                            mock_dividend_repo.get_pending_bonuses.return_value = (
                                                {}
                                            )
                                            mock_dividend_class.return_value = (
                                                mock_dividend_repo
                                            )

                                            mock_yahoo.get_batch_quotes.return_value = (
                                                {}
                                            )

                                            mock_client = MagicMock()
                                            mock_client.get_total_cash_eur.return_value = (
                                                5000.0
                                            )
                                            mock_client_class.shared.return_value = (
                                                mock_client
                                            )

                                            mock_optimizer = AsyncMock()
                                            mock_optimizer.optimize.return_value = (
                                                sample_optimization_result
                                            )
                                            mock_optimizer_class.return_value = (
                                                mock_optimizer
                                            )

                                            await run_optimization()

        # Verify cache was updated
        assert optimizer_module._last_optimization_result is not None
        assert optimizer_module._last_optimization_time is not None

    @pytest.mark.asyncio
    async def test_run_optimization_handles_tradernet_error(
        self, mock_settings, sample_optimization_result
    ):
        """Test that Tradernet errors are handled gracefully."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL"
        mock_stock.yahoo_symbol = "AAPL"

        with patch("app.api.optimizer.SettingsRepository") as mock_repo_class:
            with patch("app.api.optimizer.SettingsService") as mock_service_class:
                with patch("app.api.optimizer.StockRepository") as mock_stock_class:
                    with patch(
                        "app.api.optimizer.PositionRepository"
                    ) as mock_position_class:
                        with patch(
                            "app.api.optimizer.DividendRepository"
                        ) as mock_dividend_class:
                            with patch("app.api.optimizer.yahoo") as mock_yahoo:
                                with patch(
                                    "app.api.optimizer.TradernetClient"
                                ) as mock_client_class:
                                    with patch(
                                        "app.api.optimizer.PortfolioOptimizer"
                                    ) as mock_optimizer_class:
                                        with patch(
                                            "app.api.optimizer.AllocationRepository"
                                        ) as mock_allocation_repo_class:
                                            # Setup mocks
                                            mock_settings_repo = AsyncMock()
                                            mock_repo_class.return_value = (
                                                mock_settings_repo
                                            )

                                            # Setup allocation_repo mock
                                            mock_allocation_repo = AsyncMock()
                                            mock_allocation_repo.get_country_group_targets.return_value = (
                                                {}
                                            )
                                            mock_allocation_repo.get_industry_group_targets.return_value = (
                                                {}
                                            )
                                            mock_allocation_repo_class.return_value = (
                                                mock_allocation_repo
                                            )

                                            mock_service = AsyncMock()
                                            mock_service.get_settings.return_value = (
                                                mock_settings
                                            )
                                            mock_service_class.return_value = (
                                                mock_service
                                            )

                                            mock_stock_repo = AsyncMock()
                                            mock_stock_repo.get_all.return_value = [
                                                mock_stock
                                            ]
                                            mock_stock_class.return_value = (
                                                mock_stock_repo
                                            )

                                            mock_position_repo = AsyncMock()
                                            mock_position_repo.get_all.return_value = []
                                            mock_position_class.return_value = (
                                                mock_position_repo
                                            )

                                            mock_dividend_repo = AsyncMock()
                                            mock_dividend_repo.get_pending_bonuses.return_value = (
                                                {}
                                            )
                                            mock_dividend_class.return_value = (
                                                mock_dividend_repo
                                            )

                                            mock_yahoo.get_batch_quotes.return_value = (
                                                {}
                                            )

                                            # Tradernet fails
                                            mock_client_class.shared.side_effect = (
                                                Exception("API error")
                                            )

                                            mock_optimizer = AsyncMock()
                                            mock_optimizer.optimize.return_value = (
                                                sample_optimization_result
                                            )
                                            mock_optimizer_class.return_value = (
                                                mock_optimizer
                                            )

                                            result = await run_optimization()

        # Should succeed with 0 cash balance
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_run_optimization_passes_all_parameters(
        self, mock_settings, sample_optimization_result
    ):
        """Test that all parameters are passed to optimizer."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL"
        mock_stock.yahoo_symbol = "AAPL"

        mock_position = MagicMock()
        mock_position.symbol = "AAPL"

        with patch("app.api.optimizer.SettingsRepository") as mock_repo_class:
            with patch("app.api.optimizer.SettingsService") as mock_service_class:
                with patch("app.api.optimizer.StockRepository") as mock_stock_class:
                    with patch(
                        "app.api.optimizer.PositionRepository"
                    ) as mock_position_class:
                        with patch(
                            "app.api.optimizer.DividendRepository"
                        ) as mock_dividend_class:
                            with patch("app.api.optimizer.yahoo") as mock_yahoo:
                                with patch(
                                    "app.api.optimizer.TradernetClient"
                                ) as mock_client_class:
                                    with patch(
                                        "app.api.optimizer.PortfolioOptimizer"
                                    ) as mock_optimizer_class:
                                        with patch(
                                            "app.api.optimizer.AllocationRepository"
                                        ) as mock_allocation_repo_class:
                                            # Setup mocks
                                            mock_settings_repo = AsyncMock()
                                            mock_repo_class.return_value = (
                                                mock_settings_repo
                                            )

                                            # Setup allocation_repo mock
                                            # Returns fractions (0-1), already in correct format
                                            mock_allocation_repo = AsyncMock()
                                            mock_allocation_repo.get_country_group_targets.return_value = {
                                                "United States": 0.5,  # Already 0.5 (50%)
                                                "Germany": 0.3,  # Already 0.3 (30%)
                                            }
                                            mock_allocation_repo.get_industry_group_targets.return_value = {
                                                "Consumer Electronics": 0.4,  # Already 0.4 (40%)
                                            }
                                            mock_allocation_repo_class.return_value = (
                                                mock_allocation_repo
                                            )

                                            # Expected values (already fractions, not converted)
                                            country_targets = {
                                                "United States": 0.5,
                                                "Germany": 0.3,
                                            }
                                            ind_targets = {"Consumer Electronics": 0.4}

                                            mock_service = AsyncMock()
                                            mock_service.get_settings.return_value = (
                                                mock_settings
                                            )
                                            mock_service_class.return_value = (
                                                mock_service
                                            )

                                            mock_stock_repo = AsyncMock()
                                            mock_stock_repo.get_all.return_value = [
                                                mock_stock
                                            ]
                                            mock_stock_class.return_value = (
                                                mock_stock_repo
                                            )

                                            mock_position_repo = AsyncMock()
                                            mock_position_repo.get_all.return_value = [
                                                mock_position
                                            ]
                                            mock_position_class.return_value = (
                                                mock_position_repo
                                            )

                                            dividend_bonuses = {"AAPL": 100.0}
                                            mock_dividend_repo = AsyncMock()
                                            mock_dividend_repo.get_pending_bonuses.return_value = (
                                                dividend_bonuses
                                            )
                                            mock_dividend_class.return_value = (
                                                mock_dividend_repo
                                            )

                                            mock_yahoo.get_batch_quotes.return_value = {
                                                "AAPL": 150.0
                                            }

                                            mock_client = MagicMock()
                                            mock_client.get_total_cash_eur.return_value = (
                                                5000.0
                                            )
                                            mock_client_class.shared.return_value = (
                                                mock_client
                                            )

                                            mock_optimizer = AsyncMock()
                                            mock_optimizer.optimize.return_value = (
                                                sample_optimization_result
                                            )
                                            mock_optimizer_class.return_value = (
                                                mock_optimizer
                                            )

                                            await run_optimization()

                                            # Verify optimizer.optimize was called with correct params
                                            call_kwargs = (
                                                mock_optimizer.optimize.call_args.kwargs
                                            )
                                            assert call_kwargs["stocks"] == [mock_stock]
                                            assert "AAPL" in call_kwargs["positions"]
                                            assert call_kwargs["cash_balance"] == 5000.0
                                            assert call_kwargs["blend"] == 0.5
                                            assert call_kwargs["target_return"] == 0.11
                                            # Verify targets are passed as-is (already fractions, not divided by 100)
                                            assert (
                                                call_kwargs["country_targets"]
                                                == country_targets
                                            )
                                            assert (
                                                call_kwargs["ind_targets"]
                                                == ind_targets
                                            )
                                            assert (
                                                call_kwargs["min_cash_reserve"] == 500.0
                                            )
                                            assert (
                                                call_kwargs["dividend_bonuses"]
                                                == dividend_bonuses
                                            )

    @pytest.mark.asyncio
    async def test_run_optimization_calculates_portfolio_value(
        self, mock_settings, sample_optimization_result
    ):
        """Test that portfolio value is calculated correctly."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL"
        mock_stock.yahoo_symbol = "AAPL"

        mock_position1 = MagicMock()
        mock_position1.symbol = "AAPL"
        mock_position1.quantity = 10
        mock_position1.market_value_eur = 1500.0

        mock_position2 = MagicMock()
        mock_position2.symbol = "GOOGL"
        mock_position2.quantity = 5
        mock_position2.market_value_eur = 2500.0

        with patch("app.api.optimizer.SettingsRepository") as mock_repo_class:
            with patch("app.api.optimizer.SettingsService") as mock_service_class:
                with patch("app.api.optimizer.StockRepository") as mock_stock_class:
                    with patch(
                        "app.api.optimizer.PositionRepository"
                    ) as mock_position_class:
                        with patch(
                            "app.api.optimizer.DividendRepository"
                        ) as mock_dividend_class:
                            with patch("app.api.optimizer.yahoo") as mock_yahoo:
                                with patch(
                                    "app.api.optimizer.TradernetClient"
                                ) as mock_client_class:
                                    with patch(
                                        "app.api.optimizer.PortfolioOptimizer"
                                    ) as mock_optimizer_class:
                                        with patch(
                                            "app.api.optimizer.AllocationRepository"
                                        ) as mock_allocation_repo_class:
                                            # Setup mocks
                                            mock_settings_repo = AsyncMock()
                                            mock_repo_class.return_value = (
                                                mock_settings_repo
                                            )

                                            # Setup allocation_repo mock
                                            mock_allocation_repo = AsyncMock()
                                            mock_allocation_repo.get_country_group_targets.return_value = (
                                                {}
                                            )
                                            mock_allocation_repo.get_industry_group_targets.return_value = (
                                                {}
                                            )
                                            mock_allocation_repo_class.return_value = (
                                                mock_allocation_repo
                                            )

                                            mock_service = AsyncMock()
                                            mock_service.get_settings.return_value = (
                                                mock_settings
                                            )
                                            mock_service_class.return_value = (
                                                mock_service
                                            )

                                            mock_stock_repo = AsyncMock()
                                            mock_stock_repo.get_all.return_value = [
                                                mock_stock
                                            ]
                                            mock_stock_class.return_value = (
                                                mock_stock_repo
                                            )

                                            mock_position_repo = AsyncMock()
                                            mock_position_repo.get_all.return_value = [
                                                mock_position1,
                                                mock_position2,
                                            ]
                                            mock_position_class.return_value = (
                                                mock_position_repo
                                            )

                                            mock_dividend_repo = AsyncMock()
                                            mock_dividend_repo.get_pending_bonuses.return_value = (
                                                {}
                                            )
                                            mock_dividend_class.return_value = (
                                                mock_dividend_repo
                                            )

                                            mock_yahoo.get_batch_quotes.return_value = {
                                                "AAPL": 150.0,
                                                "GOOGL": 500.0,
                                            }

                                            mock_client = MagicMock()
                                            mock_client.get_total_cash_eur.return_value = (
                                                1000.0
                                            )
                                            mock_client_class.shared.return_value = (
                                                mock_client
                                            )

                                            mock_optimizer = AsyncMock()
                                            mock_optimizer.optimize.return_value = (
                                                sample_optimization_result
                                            )
                                            mock_optimizer_class.return_value = (
                                                mock_optimizer
                                            )

                                            await run_optimization()

                                            # Verify portfolio value includes positions + cash
                                            # Positions: 1500 + 2500 = 4000
                                            # Cash: 1000
                                            # Total: 5000
                                            call_kwargs = (
                                                mock_optimizer.optimize.call_args.kwargs
                                            )
                                            assert (
                                                call_kwargs["portfolio_value"] == 5000.0
                                            )


class TestOptimizationResultToDict:
    """Test the _optimization_result_to_dict helper function."""

    def test_converts_result_with_top_changes(self, sample_optimization_result):
        """Test conversion of result with top weight changes."""
        portfolio_value = 10000.0

        result_dict = _optimization_result_to_dict(
            sample_optimization_result, portfolio_value
        )

        assert result_dict["success"] is True
        assert result_dict["error"] is None
        assert result_dict["target_return_pct"] == 11.0
        assert result_dict["achieved_return_pct"] == 10.5
        assert result_dict["blend_used"] == 0.5
        assert result_dict["fallback_used"] is None
        assert result_dict["total_stocks_optimized"] == 3

        # Check top adjustments
        assert len(result_dict["top_adjustments"]) == 3
        top = result_dict["top_adjustments"][0]
        assert top["symbol"] == "AAPL"
        assert top["current_pct"] == 10.0
        assert top["target_pct"] == 15.0
        assert top["change_pct"] == 5.0
        assert top["change_eur"] == 500.0  # 0.05 * 10000
        assert top["direction"] == "buy"

    def test_converts_result_with_sell_recommendation(self):
        """Test conversion with sell recommendation."""
        weight_changes = [
            WeightChange(
                symbol="MSFT",
                current_weight=0.15,
                target_weight=0.10,
                change=-0.05,
            ),
        ]

        result = OptimizationResult(
            timestamp=datetime.now(),
            target_return=0.11,
            achieved_expected_return=0.105,
            blend_used=0.5,
            fallback_used=None,
            target_weights={"MSFT": 0.10},
            weight_changes=weight_changes,
            high_correlations=[],
            constraints_summary={},
            success=True,
            error=None,
        )

        result_dict = _optimization_result_to_dict(result, 10000.0)

        top = result_dict["top_adjustments"][0]
        assert top["direction"] == "sell"
        assert top["change_pct"] == -5.0
        assert top["change_eur"] == -500.0

    def test_converts_result_with_next_action(self, sample_optimization_result):
        """Test that next action is formatted correctly."""
        result_dict = _optimization_result_to_dict(sample_optimization_result, 10000.0)

        assert result_dict["next_action"] == "Buy AAPL ~€500"

    def test_converts_result_with_sell_next_action(self):
        """Test next action for sell recommendation."""
        weight_changes = [
            WeightChange(
                symbol="MSFT",
                current_weight=0.15,
                target_weight=0.10,
                change=-0.05,
            ),
        ]

        result = OptimizationResult(
            timestamp=datetime.now(),
            target_return=0.11,
            achieved_expected_return=0.105,
            blend_used=0.5,
            fallback_used=None,
            target_weights={"MSFT": 0.10},
            weight_changes=weight_changes,
            high_correlations=[],
            constraints_summary={},
            success=True,
            error=None,
        )

        result_dict = _optimization_result_to_dict(result, 10000.0)

        assert result_dict["next_action"] == "Sell MSFT ~€500"

    def test_converts_result_no_weight_changes(self):
        """Test conversion when no weight changes exist."""
        result = OptimizationResult(
            timestamp=datetime.now(),
            target_return=0.11,
            achieved_expected_return=0.105,
            blend_used=0.5,
            fallback_used=None,
            target_weights={},
            weight_changes=[],
            high_correlations=[],
            constraints_summary={},
            success=True,
            error=None,
        )

        result_dict = _optimization_result_to_dict(result, 10000.0)

        assert result_dict["top_adjustments"] == []
        assert result_dict["next_action"] is None

    def test_converts_result_with_error(self):
        """Test conversion of failed result."""
        result = OptimizationResult(
            timestamp=datetime.now(),
            target_return=0.11,
            achieved_expected_return=None,
            blend_used=0.5,
            fallback_used="max_sharpe",
            target_weights={},
            weight_changes=[],
            high_correlations=[],
            constraints_summary={},
            success=False,
            error="Optimization failed",
        )

        result_dict = _optimization_result_to_dict(result, 10000.0)

        assert result_dict["success"] is False
        assert result_dict["error"] == "Optimization failed"
        assert result_dict["achieved_return_pct"] is None
        assert result_dict["fallback_used"] == "max_sharpe"

    def test_limits_to_top_5_changes(self):
        """Test that only top 5 changes are included."""
        weight_changes = [
            WeightChange(f"STOCK{i}", 0.1, 0.15, 0.05 - i * 0.01) for i in range(10)
        ]

        result = OptimizationResult(
            timestamp=datetime.now(),
            target_return=0.11,
            achieved_expected_return=0.105,
            blend_used=0.5,
            fallback_used=None,
            target_weights={f"STOCK{i}": 0.15 for i in range(10)},
            weight_changes=weight_changes,
            high_correlations=[],
            constraints_summary={},
            success=True,
            error=None,
        )

        result_dict = _optimization_result_to_dict(result, 10000.0)

        assert len(result_dict["top_adjustments"]) == 5
        assert result_dict["total_stocks_optimized"] == 10

    def test_includes_high_correlations(self, sample_optimization_result):
        """Test that high correlations are included."""
        result_dict = _optimization_result_to_dict(sample_optimization_result, 10000.0)

        assert len(result_dict["high_correlations"]) == 1
        assert result_dict["high_correlations"][0]["symbol1"] == "AAPL"
        assert result_dict["high_correlations"][0]["correlation"] == 0.85

    def test_includes_constraints_summary(self, sample_optimization_result):
        """Test that constraints summary is included."""
        result_dict = _optimization_result_to_dict(sample_optimization_result, 10000.0)

        assert result_dict["constraints"] == {
            "min_weight": 0.01,
            "max_weight": 0.25,
        }


class TestUpdateOptimizationCache:
    """Test the update_optimization_cache function."""

    def test_updates_cache(self, sample_optimization_result):
        """Test that cache is updated correctly."""
        import app.modules.optimization.api.optimizer as optimizer_module

        portfolio_value = 10000.0

        update_optimization_cache(sample_optimization_result, portfolio_value)

        assert optimizer_module._last_optimization_result is not None
        assert optimizer_module._last_optimization_time is not None

        # Verify the cached result
        cached = optimizer_module._last_optimization_result
        assert cached["success"] is True
        assert cached["target_return_pct"] == 11.0

    def test_updates_cache_timestamp(self, sample_optimization_result):
        """Test that timestamp is set when cache is updated."""
        import app.modules.optimization.api.optimizer as optimizer_module

        before_time = datetime.now()

        update_optimization_cache(sample_optimization_result, 10000.0)

        after_time = datetime.now()

        cached_time = optimizer_module._last_optimization_time
        assert cached_time is not None
        assert before_time <= cached_time <= after_time


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_handles_positions_without_prices(
        self, mock_settings, sample_optimization_result
    ):
        """Test handling positions that don't have current prices."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL"
        mock_stock.yahoo_symbol = "AAPL"

        mock_position = MagicMock()
        mock_position.symbol = "AAPL"
        mock_position.quantity = 10
        mock_position.market_value_eur = 1500.0

        with patch("app.api.optimizer.SettingsRepository") as mock_repo_class:
            with patch("app.api.optimizer.SettingsService") as mock_service_class:
                with patch("app.api.optimizer.StockRepository") as mock_stock_class:
                    with patch(
                        "app.api.optimizer.PositionRepository"
                    ) as mock_position_class:
                        with patch(
                            "app.api.optimizer.DividendRepository"
                        ) as mock_dividend_class:
                            with patch("app.api.optimizer.yahoo") as mock_yahoo:
                                with patch(
                                    "app.api.optimizer.TradernetClient"
                                ) as mock_client_class:
                                    with patch(
                                        "app.api.optimizer.PortfolioOptimizer"
                                    ) as mock_optimizer_class:
                                        with patch(
                                            "app.api.optimizer.AllocationRepository"
                                        ) as mock_allocation_repo_class:
                                            # Setup mocks
                                            mock_settings_repo = AsyncMock()
                                            mock_repo_class.return_value = (
                                                mock_settings_repo
                                            )

                                            # Setup allocation_repo mock
                                            mock_allocation_repo = AsyncMock()
                                            mock_allocation_repo.get_country_group_targets.return_value = (
                                                {}
                                            )
                                            mock_allocation_repo.get_industry_group_targets.return_value = (
                                                {}
                                            )
                                            mock_allocation_repo_class.return_value = (
                                                mock_allocation_repo
                                            )

                                            mock_service = AsyncMock()
                                            mock_service.get_settings.return_value = (
                                                mock_settings
                                            )
                                            mock_service_class.return_value = (
                                                mock_service
                                            )

                                            mock_stock_repo = AsyncMock()
                                            mock_stock_repo.get_all.return_value = [
                                                mock_stock
                                            ]
                                            mock_stock_class.return_value = (
                                                mock_stock_repo
                                            )

                                            mock_position_repo = AsyncMock()
                                            mock_position_repo.get_all.return_value = [
                                                mock_position
                                            ]
                                            mock_position_class.return_value = (
                                                mock_position_repo
                                            )

                                            mock_dividend_repo = AsyncMock()
                                            mock_dividend_repo.get_pending_bonuses.return_value = (
                                                {}
                                            )
                                            mock_dividend_class.return_value = (
                                                mock_dividend_repo
                                            )

                                            # No price available
                                            mock_yahoo.get_batch_quotes.return_value = (
                                                {}
                                            )

                                            mock_client = MagicMock()
                                            mock_client.get_total_cash_eur.return_value = (
                                                1000.0
                                            )
                                            mock_client_class.shared.return_value = (
                                                mock_client
                                            )

                                            mock_optimizer = AsyncMock()
                                            mock_optimizer.optimize.return_value = (
                                                sample_optimization_result
                                            )
                                            mock_optimizer_class.return_value = (
                                                mock_optimizer
                                            )

                                            result = await run_optimization()

                                            # Should use market_value_eur fallback
                                            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_handles_position_with_zero_quantity(
        self, mock_settings, sample_optimization_result
    ):
        """Test handling positions with zero quantity."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL"
        mock_stock.yahoo_symbol = "AAPL"

        mock_position = MagicMock()
        mock_position.symbol = "AAPL"
        mock_position.quantity = 0  # Zero quantity
        mock_position.market_value_eur = None

        with patch("app.api.optimizer.SettingsRepository") as mock_repo_class:
            with patch("app.api.optimizer.SettingsService") as mock_service_class:
                with patch("app.api.optimizer.StockRepository") as mock_stock_class:
                    with patch(
                        "app.api.optimizer.PositionRepository"
                    ) as mock_position_class:
                        with patch(
                            "app.api.optimizer.DividendRepository"
                        ) as mock_dividend_class:
                            with patch("app.api.optimizer.yahoo") as mock_yahoo:
                                with patch(
                                    "app.api.optimizer.TradernetClient"
                                ) as mock_client_class:
                                    with patch(
                                        "app.api.optimizer.PortfolioOptimizer"
                                    ) as mock_optimizer_class:
                                        with patch(
                                            "app.api.optimizer.AllocationRepository"
                                        ) as mock_allocation_repo_class:
                                            # Setup mocks
                                            mock_settings_repo = AsyncMock()
                                            mock_repo_class.return_value = (
                                                mock_settings_repo
                                            )

                                            # Setup allocation_repo mock
                                            mock_allocation_repo = AsyncMock()
                                            mock_allocation_repo.get_country_group_targets.return_value = (
                                                {}
                                            )
                                            mock_allocation_repo.get_industry_group_targets.return_value = (
                                                {}
                                            )
                                            mock_allocation_repo_class.return_value = (
                                                mock_allocation_repo
                                            )

                                            mock_service = AsyncMock()
                                            mock_service.get_settings.return_value = (
                                                mock_settings
                                            )
                                            mock_service_class.return_value = (
                                                mock_service
                                            )

                                            mock_stock_repo = AsyncMock()
                                            mock_stock_repo.get_all.return_value = [
                                                mock_stock
                                            ]
                                            mock_stock_class.return_value = (
                                                mock_stock_repo
                                            )

                                            mock_position_repo = AsyncMock()
                                            mock_position_repo.get_all.return_value = [
                                                mock_position
                                            ]
                                            mock_position_class.return_value = (
                                                mock_position_repo
                                            )

                                            mock_dividend_repo = AsyncMock()
                                            mock_dividend_repo.get_pending_bonuses.return_value = (
                                                {}
                                            )
                                            mock_dividend_class.return_value = (
                                                mock_dividend_repo
                                            )

                                            mock_yahoo.get_batch_quotes.return_value = (
                                                {}
                                            )

                                            mock_client = MagicMock()
                                            mock_client.get_total_cash_eur.return_value = (
                                                5000.0
                                            )
                                            mock_client_class.shared.return_value = (
                                                mock_client
                                            )

                                            mock_optimizer = AsyncMock()
                                            mock_optimizer.optimize.return_value = (
                                                sample_optimization_result
                                            )
                                            mock_optimizer_class.return_value = (
                                                mock_optimizer
                                            )

                                            result = await run_optimization()

                                            # Should handle gracefully with 0 value
                                            assert result["success"] is True

    def test_handles_none_achieved_return(self):
        """Test conversion when achieved return is None."""
        result = OptimizationResult(
            timestamp=datetime.now(),
            target_return=0.11,
            achieved_expected_return=None,
            blend_used=0.5,
            fallback_used="hrp",
            target_weights={},
            weight_changes=[],
            high_correlations=[],
            constraints_summary={},
            success=True,
            error=None,
        )

        result_dict = _optimization_result_to_dict(result, 10000.0)

        assert result_dict["achieved_return_pct"] is None

    def test_handles_large_change_value(self):
        """Test formatting of large change values."""
        weight_changes = [
            WeightChange(
                symbol="AAPL",
                current_weight=0.10,
                target_weight=0.30,
                change=0.20,
            ),
        ]

        result = OptimizationResult(
            timestamp=datetime.now(),
            target_return=0.11,
            achieved_expected_return=0.105,
            blend_used=0.5,
            fallback_used=None,
            target_weights={"AAPL": 0.30},
            weight_changes=weight_changes,
            high_correlations=[],
            constraints_summary={},
            success=True,
            error=None,
        )

        # Large portfolio value
        result_dict = _optimization_result_to_dict(result, 100000.0)

        # Change: 0.20 * 100000 = 20000
        assert result_dict["next_action"] == "Buy AAPL ~€20,000"


class TestOptimizerUsesAllocationRepo:
    """Test that optimizer API uses allocation_repo instead of settings."""

    @pytest.mark.asyncio
    async def test_uses_allocation_repo_for_country_targets(
        self, mock_settings, sample_optimization_result
    ):
        """Test that allocation_repo.get_country_group_targets() is used instead of settings."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL"
        mock_stock.yahoo_symbol = "AAPL"

        mock_position = MagicMock()
        mock_position.symbol = "AAPL"

        with patch("app.api.optimizer.SettingsRepository") as mock_settings_repo_class:
            with patch("app.api.optimizer.SettingsService") as mock_service_class:
                with patch("app.api.optimizer.StockRepository") as mock_stock_class:
                    with patch(
                        "app.api.optimizer.PositionRepository"
                    ) as mock_position_class:
                        with patch(
                            "app.api.optimizer.AllocationRepository"
                        ) as mock_allocation_repo_class:
                            with patch(
                                "app.api.optimizer.DividendRepository"
                            ) as mock_dividend_class:
                                with patch("app.api.optimizer.yahoo") as mock_yahoo:
                                    with patch(
                                        "app.api.optimizer.TradernetClient"
                                    ) as mock_client_class:
                                        with patch(
                                            "app.api.optimizer.PortfolioOptimizer"
                                        ) as mock_optimizer_class:
                                            # Setup mocks
                                            mock_settings_repo = AsyncMock()
                                            mock_settings_repo_class.return_value = (
                                                mock_settings_repo
                                            )

                                            mock_service = AsyncMock()
                                            mock_service.get_settings.return_value = (
                                                mock_settings
                                            )
                                            mock_service_class.return_value = (
                                                mock_service
                                            )

                                            # Setup allocation_repo mock
                                            # Returns fractions (0-1), already in correct format
                                            mock_allocation_repo = AsyncMock()
                                            mock_allocation_repo.get_country_group_targets.return_value = {
                                                "United States": 0.5,  # Already 0.5 (50%)
                                                "Germany": 0.3,  # Already 0.3 (30%)
                                            }
                                            mock_allocation_repo.get_industry_group_targets.return_value = {
                                                "Technology": 0.4,  # Already 0.4 (40%)
                                            }
                                            mock_allocation_repo_class.return_value = (
                                                mock_allocation_repo
                                            )

                                            mock_stock_repo = AsyncMock()
                                            mock_stock_repo.get_all.return_value = [
                                                mock_stock
                                            ]
                                            mock_stock_class.return_value = (
                                                mock_stock_repo
                                            )

                                            mock_position_repo = AsyncMock()
                                            mock_position_repo.get_all.return_value = [
                                                mock_position
                                            ]
                                            mock_position_class.return_value = (
                                                mock_position_repo
                                            )

                                            mock_dividend_repo = AsyncMock()
                                            mock_dividend_repo.get_pending_bonuses.return_value = (
                                                {}
                                            )
                                            mock_dividend_class.return_value = (
                                                mock_dividend_repo
                                            )

                                            mock_yahoo.get_batch_quotes.return_value = {
                                                "AAPL": 150.0
                                            }

                                            mock_client = MagicMock()
                                            mock_client.get_total_cash_eur.return_value = (
                                                5000.0
                                            )
                                            mock_client_class.shared.return_value = (
                                                mock_client
                                            )

                                            mock_optimizer = AsyncMock()
                                            mock_optimizer.optimize.return_value = (
                                                sample_optimization_result
                                            )
                                            mock_optimizer_class.return_value = (
                                                mock_optimizer
                                            )

                                            await run_optimization()

                                            # Verify allocation_repo methods were called
                                            mock_allocation_repo.get_country_group_targets.assert_called_once()
                                            mock_allocation_repo.get_industry_group_targets.assert_called_once()

                                            # Verify settings_repo.get_json was NOT called for targets
                                            mock_settings_repo.get_json.assert_not_called()

                                            # Verify optimizer was called with targets as-is (already fractions)
                                            call_kwargs = (
                                                mock_optimizer.optimize.call_args.kwargs
                                            )
                                            # Targets are already 0.5, 0.3 (not divided by 100)
                                            assert call_kwargs["country_targets"] == {
                                                "United States": 0.5,
                                                "Germany": 0.3,
                                            }
                                            # Target is already 0.4 (not divided by 100)
                                            assert call_kwargs["ind_targets"] == {
                                                "Technology": 0.4
                                            }

    @pytest.mark.asyncio
    async def test_targets_not_divided_by_100_when_already_fractions(
        self, mock_settings, sample_optimization_result
    ):
        """Test that targets are NOT divided by 100 when they're already stored as fractions (0-1).

        This test prevents regression of the bug where targets stored as 0.5 (50%) were
        incorrectly divided by 100, becoming 0.005 (0.5%), causing constraint issues.
        """
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL"
        mock_stock.yahoo_symbol = "AAPL"

        mock_position = MagicMock()
        mock_position.symbol = "AAPL"

        with patch("app.api.optimizer.SettingsRepository") as mock_settings_repo_class:
            with patch("app.api.optimizer.SettingsService") as mock_service_class:
                with patch("app.api.optimizer.StockRepository") as mock_stock_class:
                    with patch(
                        "app.api.optimizer.PositionRepository"
                    ) as mock_position_class:
                        with patch(
                            "app.api.optimizer.AllocationRepository"
                        ) as mock_allocation_repo_class:
                            with patch(
                                "app.api.optimizer.DividendRepository"
                            ) as mock_dividend_class:
                                with patch("app.api.optimizer.yahoo") as mock_yahoo:
                                    with patch(
                                        "app.api.optimizer.TradernetClient"
                                    ) as mock_client_class:
                                        with patch(
                                            "app.api.optimizer.PortfolioOptimizer"
                                        ) as mock_optimizer_class:
                                            # Setup mocks
                                            mock_settings_repo = AsyncMock()
                                            mock_settings_repo_class.return_value = (
                                                mock_settings_repo
                                            )

                                            mock_service = AsyncMock()
                                            mock_service.get_settings.return_value = (
                                                mock_settings
                                            )
                                            mock_service_class.return_value = (
                                                mock_service
                                            )

                                            # Setup allocation_repo to return fractions (0-1), not percentages
                                            # These are the actual values stored in the database
                                            mock_allocation_repo = AsyncMock()
                                            mock_allocation_repo.get_country_group_targets.return_value = {
                                                "United States": 0.5,  # Already 0.5 (50%), should NOT be divided
                                                "Japan": 0.2,  # Already 0.2 (20%), should NOT be divided
                                            }
                                            mock_allocation_repo.get_industry_group_targets.return_value = {
                                                "Technology": 0.4,  # Already 0.4 (40%), should NOT be divided
                                                "Finance": 0.15,  # Already 0.15 (15%), should NOT be divided
                                            }
                                            mock_allocation_repo_class.return_value = (
                                                mock_allocation_repo
                                            )

                                            mock_stock_repo = AsyncMock()
                                            mock_stock_repo.get_all.return_value = [
                                                mock_stock
                                            ]
                                            mock_stock_class.return_value = (
                                                mock_stock_repo
                                            )

                                            mock_position_repo = AsyncMock()
                                            mock_position_repo.get_all.return_value = [
                                                mock_position
                                            ]
                                            mock_position_class.return_value = (
                                                mock_position_repo
                                            )

                                            mock_dividend_repo = AsyncMock()
                                            mock_dividend_repo.get_pending_bonuses.return_value = (
                                                {}
                                            )
                                            mock_dividend_class.return_value = (
                                                mock_dividend_repo
                                            )

                                            mock_yahoo.get_batch_quotes.return_value = {
                                                "AAPL": 150.0
                                            }

                                            mock_client = MagicMock()
                                            mock_client.get_total_cash_eur.return_value = (
                                                5000.0
                                            )
                                            mock_client_class.shared.return_value = (
                                                mock_client
                                            )

                                            mock_optimizer = AsyncMock()
                                            mock_optimizer.optimize.return_value = (
                                                sample_optimization_result
                                            )
                                            mock_optimizer_class.return_value = (
                                                mock_optimizer
                                            )

                                            await run_optimization()

                                            # Verify targets are NOT divided by 100 (they're already fractions)
                                            call_kwargs = (
                                                mock_optimizer.optimize.call_args.kwargs
                                            )
                                            country_targets = call_kwargs[
                                                "country_targets"
                                            ]
                                            ind_targets = call_kwargs["ind_targets"]

                                            # Verify country targets are passed as-is (not divided)
                                            assert (
                                                country_targets["United States"] == 0.5
                                            )  # 0.5, NOT 0.005
                                            assert (
                                                country_targets["Japan"] == 0.2
                                            )  # 0.2, NOT 0.002

                                            # Verify industry targets are passed as-is (not divided)
                                            assert (
                                                ind_targets["Technology"] == 0.4
                                            )  # 0.4, NOT 0.004
                                            assert (
                                                ind_targets["Finance"] == 0.15
                                            )  # 0.15, NOT 0.0015

    @pytest.mark.asyncio
    async def test_uses_allocation_repo_and_converts_percentages(
        self, mock_settings, sample_optimization_result
    ):
        """Test that allocation_repo is used and percentages are converted to fractions."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL"
        mock_stock.yahoo_symbol = "AAPL"

        mock_position = MagicMock()
        mock_position.symbol = "AAPL"

        with patch("app.api.optimizer.SettingsRepository") as mock_settings_repo_class:
            with patch("app.api.optimizer.SettingsService") as mock_service_class:
                with patch("app.api.optimizer.StockRepository") as mock_stock_class:
                    with patch(
                        "app.api.optimizer.PositionRepository"
                    ) as mock_position_class:
                        with patch(
                            "app.api.optimizer.AllocationRepository"
                        ) as mock_allocation_repo_class:
                            with patch(
                                "app.api.optimizer.DividendRepository"
                            ) as mock_dividend_class:
                                with patch("app.api.optimizer.yahoo") as mock_yahoo:
                                    with patch(
                                        "app.api.optimizer.TradernetClient"
                                    ) as mock_client_class:
                                        with patch(
                                            "app.api.optimizer.PortfolioOptimizer"
                                        ) as mock_optimizer_class:
                                            # Setup mocks
                                            mock_settings_repo = AsyncMock()
                                            mock_settings_repo_class.return_value = (
                                                mock_settings_repo
                                            )

                                            mock_service = AsyncMock()
                                            mock_service.get_settings.return_value = (
                                                mock_settings
                                            )
                                            mock_service_class.return_value = (
                                                mock_service
                                            )

                                            mock_allocation_repo = AsyncMock()
                                            mock_allocation_repo.get_country_group_targets.return_value = {
                                                "United States": 0.5,  # Already fraction
                                            }
                                            mock_allocation_repo.get_industry_group_targets.return_value = (
                                                {}
                                            )
                                            mock_allocation_repo_class.return_value = (
                                                mock_allocation_repo
                                            )

                                            mock_stock_repo = AsyncMock()
                                            mock_stock_repo.get_all.return_value = [
                                                mock_stock
                                            ]
                                            mock_stock_class.return_value = (
                                                mock_stock_repo
                                            )

                                            mock_position_repo = AsyncMock()
                                            mock_position_repo.get_all.return_value = [
                                                mock_position
                                            ]
                                            mock_position_class.return_value = (
                                                mock_position_repo
                                            )

                                            mock_dividend_repo = AsyncMock()
                                            mock_dividend_repo.get_pending_bonuses.return_value = (
                                                {}
                                            )
                                            mock_dividend_class.return_value = (
                                                mock_dividend_repo
                                            )

                                            mock_yahoo.get_batch_quotes.return_value = {
                                                "AAPL": 150.0
                                            }

                                            mock_client = MagicMock()
                                            mock_client.get_total_cash_eur.return_value = (
                                                5000.0
                                            )
                                            mock_client_class.shared.return_value = (
                                                mock_client
                                            )

                                            mock_optimizer = AsyncMock()
                                            mock_optimizer.optimize.return_value = (
                                                sample_optimization_result
                                            )
                                            mock_optimizer_class.return_value = (
                                                mock_optimizer
                                            )

                                            await run_optimization()

                                            # Verify country_targets is passed and the value comes from allocation_repo
                                            call_kwargs = (
                                                mock_optimizer.optimize.call_args.kwargs
                                            )
                                            # Verify parameter name is country_targets
                                            assert "country_targets" in call_kwargs
                                            assert "geo_targets" not in call_kwargs
                                            # Verify the value is passed as-is (already fraction, not divided)
                                            assert call_kwargs["country_targets"] == {
                                                "United States": 0.5
                                            }
