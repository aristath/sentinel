"""Tests for planner batch job.

These tests validate the planner batch processing in both API-driven
and scheduled fallback modes.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.shared.domain.value_objects.currency import Currency


@pytest.fixture
def mock_db_manager():
    """Mock database manager."""
    manager = MagicMock()
    return manager


@pytest.fixture
def mock_position_repo():
    """Mock position repository."""
    repo = AsyncMock()
    mock_position = MagicMock()
    mock_position.symbol = "AAPL"
    mock_position.quantity = 10
    repo.get_all.return_value = [mock_position]
    return repo


@pytest.fixture
def mock_stock_repo():
    """Mock stock repository."""
    repo = AsyncMock()
    from app.domain.models import Security

    mock_stock = Security(
        symbol="AAPL",
        name="Apple Inc.",
        country="United States",
        currency=Currency.USD,
    )
    repo.get_all_active.return_value = [mock_stock]
    return repo


@pytest.fixture
def mock_planner_repo():
    """Mock planner repository."""
    repo = AsyncMock()
    repo.has_sequences = AsyncMock(return_value=True)
    repo.are_all_sequences_evaluated = AsyncMock(return_value=False)
    repo.get_total_sequence_count = AsyncMock(return_value=100)
    repo.get_evaluation_count = AsyncMock(return_value=50)
    return repo


class TestTriggerNextBatchViaApi:
    """Test _trigger_next_batch_via_api function."""

    @pytest.mark.asyncio
    async def test_triggers_api_endpoint(self):
        """Test that API endpoint is triggered with correct parameters."""
        from app.jobs.planner_batch import _trigger_next_batch_via_api

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock()

            await _trigger_next_batch_via_api("abc12345", 2)

            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert "planner-batch" in call_args[0][0]
            assert call_args[1]["json"]["portfolio_hash"] == "abc12345"
            assert call_args[1]["json"]["depth"] == 2

    @pytest.mark.asyncio
    async def test_handles_api_failure_gracefully(self):
        """Test that API failures are handled gracefully."""
        from app.jobs.planner_batch import _trigger_next_batch_via_api

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=Exception("Connection error"))

            with patch("app.jobs.planner_batch.logger") as mock_logger:
                # Should not raise
                await _trigger_next_batch_via_api("abc12345", 2)

                mock_logger.warning.assert_called()


class TestProcessPlannerBatchJob:
    """Test process_planner_batch_job function."""

    @pytest.mark.asyncio
    async def test_generates_portfolio_hash_when_not_provided(self):
        """Test that portfolio hash is generated when not provided."""
        from app.jobs.planner_batch import process_planner_batch_job

        with patch("app.jobs.planner_batch.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            with patch(
                "app.jobs.planner_batch.PositionRepository"
            ) as mock_pos_repo_class:
                mock_pos_repo = AsyncMock()
                mock_position = MagicMock()
                mock_position.symbol = "AAPL"
                mock_position.quantity = 10
                mock_pos_repo.get_all.return_value = [mock_position]
                mock_pos_repo_class.return_value = mock_pos_repo

                with patch(
                    "app.jobs.planner_batch.SecurityRepository"
                ) as mock_stock_repo_class:
                    mock_stock_repo = AsyncMock()
                    from app.domain.models import Security

                    mock_stock = Security(
                        symbol="AAPL",
                        name="Apple Inc.",
                        country="United States",
                        currency=Currency.USD,
                    )
                    mock_stock_repo.get_all_active.return_value = [mock_stock]
                    mock_stock_repo_class.return_value = mock_stock_repo

                    with patch(
                        "app.jobs.planner_batch.TradernetClient"
                    ) as mock_client_class:
                        mock_client = MagicMock()
                        mock_client.is_connected = False
                        mock_client.get_cash_balances.return_value = []
                        mock_client.get_pending_orders.return_value = []
                        mock_client_class.return_value = mock_client

                        with patch(
                            "app.jobs.planner_batch.PlannerRepository"
                        ) as mock_planner_repo_class:
                            mock_planner_repo = AsyncMock()
                            mock_planner_repo.has_sequences = AsyncMock(
                                return_value=False
                            )
                            mock_planner_repo_class.return_value = mock_planner_repo

                            with patch(
                                "app.jobs.planner_batch.SettingsRepository"
                            ) as mock_settings_repo_class:
                                mock_settings_repo = AsyncMock()
                                mock_settings_repo.get_float = AsyncMock(
                                    return_value=5.0
                                )
                                mock_settings_repo_class.return_value = (
                                    mock_settings_repo
                                )

                                with patch(
                                    "app.jobs.planner_batch.AllocationRepository"
                                ):
                                    with patch(
                                        "app.jobs.planner_batch.ExchangeRateService"
                                    ):
                                        with patch(
                                            "app.jobs.planner_batch.build_portfolio_context"
                                        ):
                                            with patch(
                                                "app.jobs.planner_batch.PortfolioRepository"
                                            ) as mock_portfolio_repo_class:
                                                mock_portfolio_repo = AsyncMock()
                                                mock_portfolio_repo.get_latest = (
                                                    AsyncMock(return_value=None)
                                                )
                                                mock_portfolio_repo_class.return_value = (
                                                    mock_portfolio_repo
                                                )

                                                with patch(
                                                    "app.jobs.planner_batch.create_holistic_plan_incremental"
                                                ) as mock_create_plan:
                                                    mock_create_plan.return_value = None

                                                    # Should not raise, should generate hash
                                                    await process_planner_batch_job()

    @pytest.mark.asyncio
    async def test_skips_scheduled_job_when_api_batches_active(self):
        """Test that scheduled job (max_depth=0) skips when API-driven batches are active."""
        from app.jobs.planner_batch import process_planner_batch_job

        with patch("app.jobs.planner_batch.get_db_manager"):
            with patch(
                "app.jobs.planner_batch.PositionRepository"
            ) as mock_pos_repo_class:
                mock_pos_repo = AsyncMock()
                mock_pos_repo.get_all.return_value = []
                mock_pos_repo_class.return_value = mock_pos_repo

                with patch(
                    "app.jobs.planner_batch.SecurityRepository"
                ) as mock_stock_repo_class:
                    mock_stock_repo = AsyncMock()
                    mock_stock_repo.get_all_active.return_value = []
                    mock_stock_repo_class.return_value = mock_stock_repo

                    with patch(
                        "app.jobs.planner_batch.TradernetClient"
                    ) as mock_client_class:
                        mock_client = MagicMock()
                        mock_client.is_connected = False
                        mock_client.get_pending_orders.return_value = []
                        mock_client_class.return_value = mock_client

                        with patch(
                            "app.jobs.planner_batch.PlannerRepository"
                        ) as mock_planner_repo_class:
                            mock_planner_repo = AsyncMock()
                            mock_planner_repo.has_sequences = AsyncMock(
                                return_value=True
                            )
                            mock_planner_repo.are_all_sequences_evaluated = AsyncMock(
                                return_value=False
                            )  # Not all evaluated = API batches active
                            mock_planner_repo_class.return_value = mock_planner_repo

                            with patch(
                                "app.jobs.planner_batch.create_holistic_plan_incremental"
                            ) as mock_create_plan:
                                # Should skip, so create_holistic_plan_incremental should not be called
                                await process_planner_batch_job(
                                    max_depth=0, portfolio_hash="test123"
                                )

                                mock_create_plan.assert_not_called()

    @pytest.mark.asyncio
    async def test_uses_small_batch_size_in_api_driven_mode(self):
        """Test that API-driven mode uses small batch size (5)."""
        from app.jobs.planner_batch import process_planner_batch_job

        with patch("app.jobs.planner_batch.get_db_manager"):
            with patch(
                "app.jobs.planner_batch.PositionRepository"
            ) as mock_pos_repo_class:
                mock_pos_repo = AsyncMock()
                mock_pos_repo.get_all.return_value = []
                mock_pos_repo_class.return_value = mock_pos_repo

                with patch(
                    "app.jobs.planner_batch.SecurityRepository"
                ) as mock_stock_repo_class:
                    mock_stock_repo = AsyncMock()
                    mock_stock_repo.get_all_active.return_value = []
                    mock_stock_repo_class.return_value = mock_stock_repo

                    with patch(
                        "app.jobs.planner_batch.TradernetClient"
                    ) as mock_client_class:
                        mock_client = MagicMock()
                        mock_client.is_connected = False
                        mock_client.get_pending_orders.return_value = []
                        mock_client_class.return_value = mock_client

                        with patch(
                            "app.jobs.planner_batch.PlannerRepository"
                        ) as mock_planner_repo_class:
                            mock_planner_repo = AsyncMock()
                            mock_planner_repo.has_sequences = AsyncMock(
                                return_value=False
                            )
                            mock_planner_repo_class.return_value = mock_planner_repo

                            with patch(
                                "app.jobs.planner_batch.SettingsRepository"
                            ) as mock_settings_repo_class:
                                mock_settings_repo = AsyncMock()
                                mock_settings_repo.get_float = AsyncMock(
                                    return_value=5.0
                                )
                                mock_settings_repo_class.return_value = (
                                    mock_settings_repo
                                )

                                with patch(
                                    "app.jobs.planner_batch.AllocationRepository"
                                ):
                                    with patch(
                                        "app.jobs.planner_batch.ExchangeRateService"
                                    ):
                                        with patch(
                                            "app.jobs.planner_batch.build_portfolio_context"
                                        ):
                                            with patch(
                                                "app.jobs.planner_batch.PortfolioRepository"
                                            ) as mock_portfolio_repo_class:
                                                mock_portfolio_repo = AsyncMock()
                                                mock_portfolio_repo.get_latest = (
                                                    AsyncMock(return_value=None)
                                                )
                                                mock_portfolio_repo_class.return_value = (
                                                    mock_portfolio_repo
                                                )

                                                with patch(
                                                    "app.jobs.planner_batch.create_holistic_plan_incremental"
                                                ) as mock_create_plan:
                                                    mock_create_plan.return_value = None

                                                    await process_planner_batch_job(
                                                        max_depth=1,
                                                        portfolio_hash="test123",
                                                    )

                                                    # Should use batch_size=5 for API-driven mode
                                                    call_kwargs = (
                                                        mock_create_plan.call_args[1]
                                                    )
                                                    assert (
                                                        call_kwargs["batch_size"] == 5
                                                    )

    @pytest.mark.asyncio
    async def test_uses_large_batch_size_in_scheduled_mode(self):
        """Test that scheduled mode uses large batch size (50)."""
        from app.jobs.planner_batch import process_planner_batch_job

        with patch("app.jobs.planner_batch.get_db_manager"):
            with patch(
                "app.jobs.planner_batch.PositionRepository"
            ) as mock_pos_repo_class:
                mock_pos_repo = AsyncMock()
                mock_pos_repo.get_all.return_value = []
                mock_pos_repo_class.return_value = mock_pos_repo

                with patch(
                    "app.jobs.planner_batch.SecurityRepository"
                ) as mock_stock_repo_class:
                    mock_stock_repo = AsyncMock()
                    mock_stock_repo.get_all_active.return_value = []
                    mock_stock_repo_class.return_value = mock_stock_repo

                    with patch(
                        "app.jobs.planner_batch.TradernetClient"
                    ) as mock_client_class:
                        mock_client = MagicMock()
                        mock_client.is_connected = False
                        mock_client.get_pending_orders.return_value = []
                        mock_client_class.return_value = mock_client

                        with patch(
                            "app.jobs.planner_batch.PlannerRepository"
                        ) as mock_planner_repo_class:
                            mock_planner_repo = AsyncMock()
                            mock_planner_repo.has_sequences = AsyncMock(
                                return_value=False
                            )
                            mock_planner_repo_class.return_value = mock_planner_repo

                            with patch(
                                "app.jobs.planner_batch.SettingsRepository"
                            ) as mock_settings_repo_class:
                                mock_settings_repo = AsyncMock()
                                mock_settings_repo.get_float = AsyncMock(
                                    return_value=5.0
                                )
                                mock_settings_repo_class.return_value = (
                                    mock_settings_repo
                                )

                                with patch(
                                    "app.jobs.planner_batch.AllocationRepository"
                                ):
                                    with patch(
                                        "app.jobs.planner_batch.ExchangeRateService"
                                    ):
                                        with patch(
                                            "app.jobs.planner_batch.build_portfolio_context"
                                        ):
                                            with patch(
                                                "app.jobs.planner_batch.PortfolioRepository"
                                            ) as mock_portfolio_repo_class:
                                                mock_portfolio_repo = AsyncMock()
                                                mock_portfolio_repo.get_latest = (
                                                    AsyncMock(return_value=None)
                                                )
                                                mock_portfolio_repo_class.return_value = (
                                                    mock_portfolio_repo
                                                )

                                                with patch(
                                                    "app.jobs.planner_batch.create_holistic_plan_incremental"
                                                ) as mock_create_plan:
                                                    mock_create_plan.return_value = None

                                                    await process_planner_batch_job(
                                                        max_depth=0,
                                                        portfolio_hash="test123",
                                                    )

                                                    # Should use batch_size=50 for scheduled mode
                                                    call_kwargs = (
                                                        mock_create_plan.call_args[1]
                                                    )
                                                    assert (
                                                        call_kwargs["batch_size"] == 50
                                                    )

    @pytest.mark.asyncio
    async def test_self_triggers_next_batch_in_api_driven_mode(self):
        """Test that API-driven mode self-triggers next batch when work remains."""
        from app.jobs.planner_batch import process_planner_batch_job

        with patch("app.jobs.planner_batch.get_db_manager"):
            with patch(
                "app.jobs.planner_batch.PositionRepository"
            ) as mock_pos_repo_class:
                mock_pos_repo = AsyncMock()
                mock_pos_repo.get_all.return_value = []
                mock_pos_repo_class.return_value = mock_pos_repo

                with patch(
                    "app.jobs.planner_batch.SecurityRepository"
                ) as mock_stock_repo_class:
                    mock_stock_repo = AsyncMock()
                    mock_stock_repo.get_all_active.return_value = []
                    mock_stock_repo_class.return_value = mock_stock_repo

                    with patch(
                        "app.jobs.planner_batch.TradernetClient"
                    ) as mock_client_class:
                        mock_client = MagicMock()
                        mock_client.is_connected = False
                        mock_client.get_pending_orders.return_value = []
                        mock_client_class.return_value = mock_client

                        with patch(
                            "app.jobs.planner_batch.PlannerRepository"
                        ) as mock_planner_repo_class:
                            mock_planner_repo = AsyncMock()
                            mock_planner_repo.has_sequences = AsyncMock(
                                return_value=False
                            )
                            mock_planner_repo.are_all_sequences_evaluated = AsyncMock(
                                return_value=False
                            )  # More work remains
                            mock_planner_repo_class.return_value = mock_planner_repo

                            with patch(
                                "app.jobs.planner_batch.SettingsRepository"
                            ) as mock_settings_repo_class:
                                mock_settings_repo = AsyncMock()
                                mock_settings_repo.get_float = AsyncMock(
                                    return_value=5.0
                                )
                                mock_settings_repo_class.return_value = (
                                    mock_settings_repo
                                )

                                with patch(
                                    "app.jobs.planner_batch.AllocationRepository"
                                ):
                                    with patch(
                                        "app.jobs.planner_batch.ExchangeRateService"
                                    ):
                                        with patch(
                                            "app.jobs.planner_batch.build_portfolio_context"
                                        ):
                                            with patch(
                                                "app.jobs.planner_batch.PortfolioRepository"
                                            ) as mock_portfolio_repo_class:
                                                mock_portfolio_repo = AsyncMock()
                                                mock_portfolio_repo.get_latest = (
                                                    AsyncMock(return_value=None)
                                                )
                                                mock_portfolio_repo_class.return_value = (
                                                    mock_portfolio_repo
                                                )

                                                with patch(
                                                    "app.jobs.planner_batch.create_holistic_plan_incremental"
                                                ) as mock_create_plan:
                                                    mock_create_plan.return_value = None

                                                    with patch(
                                                        "app.jobs.planner_batch._trigger_next_batch_via_api"
                                                    ) as mock_trigger:
                                                        await process_planner_batch_job(
                                                            max_depth=1,
                                                            portfolio_hash="test123",
                                                        )

                                                        # Should trigger next batch with incremented depth
                                                        mock_trigger.assert_called_once_with(
                                                            "test123", 2
                                                        )

    @pytest.mark.asyncio
    async def test_stops_self_triggering_at_max_depth(self):
        """Test that self-triggering stops at max depth limit."""
        from app.jobs.planner_batch import process_planner_batch_job

        with patch("app.jobs.planner_batch.get_db_manager"):
            with patch(
                "app.jobs.planner_batch.PositionRepository"
            ) as mock_pos_repo_class:
                mock_pos_repo = AsyncMock()
                mock_pos_repo.get_all.return_value = []
                mock_pos_repo_class.return_value = mock_pos_repo

                with patch(
                    "app.jobs.planner_batch.SecurityRepository"
                ) as mock_stock_repo_class:
                    mock_stock_repo = AsyncMock()
                    mock_stock_repo.get_all_active.return_value = []
                    mock_stock_repo_class.return_value = mock_stock_repo

                    with patch(
                        "app.jobs.planner_batch.TradernetClient"
                    ) as mock_client_class:
                        mock_client = MagicMock()
                        mock_client.is_connected = False
                        mock_client.get_pending_orders.return_value = []
                        mock_client_class.return_value = mock_client

                        with patch(
                            "app.jobs.planner_batch.PlannerRepository"
                        ) as mock_planner_repo_class:
                            mock_planner_repo = AsyncMock()
                            mock_planner_repo.has_sequences = AsyncMock(
                                return_value=False
                            )
                            mock_planner_repo.are_all_sequences_evaluated = AsyncMock(
                                return_value=False
                            )
                            mock_planner_repo_class.return_value = mock_planner_repo

                            with patch(
                                "app.jobs.planner_batch.SettingsRepository"
                            ) as mock_settings_repo_class:
                                mock_settings_repo = AsyncMock()
                                mock_settings_repo.get_float = AsyncMock(
                                    return_value=5.0
                                )
                                mock_settings_repo_class.return_value = (
                                    mock_settings_repo
                                )

                                with patch(
                                    "app.jobs.planner_batch.AllocationRepository"
                                ):
                                    with patch(
                                        "app.jobs.planner_batch.ExchangeRateService"
                                    ):
                                        with patch(
                                            "app.jobs.planner_batch.build_portfolio_context"
                                        ):
                                            with patch(
                                                "app.jobs.planner_batch.PortfolioRepository"
                                            ) as mock_portfolio_repo_class:
                                                mock_portfolio_repo = AsyncMock()
                                                mock_portfolio_repo.get_latest = (
                                                    AsyncMock(return_value=None)
                                                )
                                                mock_portfolio_repo_class.return_value = (
                                                    mock_portfolio_repo
                                                )

                                                with patch(
                                                    "app.jobs.planner_batch.create_holistic_plan_incremental"
                                                ) as mock_create_plan:
                                                    mock_create_plan.return_value = None

                                                    with patch(
                                                        "app.jobs.planner_batch._trigger_next_batch_via_api"
                                                    ) as mock_trigger:
                                                        with patch(
                                                            "app.jobs.planner_batch.logger"
                                                        ) as mock_logger:
                                                            # Use max_depth > 100000 to trigger limit
                                                            await process_planner_batch_job(
                                                                max_depth=100001,
                                                                portfolio_hash="test123",
                                                            )

                                                            # Should not trigger next batch
                                                            mock_trigger.assert_not_called()
                                                            mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_emits_planner_batch_complete_event(self):
        """Test that planner batch complete event is emitted."""
        from app.jobs.planner_batch import process_planner_batch_job

        with patch("app.jobs.planner_batch.get_db_manager"):
            with patch(
                "app.jobs.planner_batch.PositionRepository"
            ) as mock_pos_repo_class:
                mock_pos_repo = AsyncMock()
                mock_pos_repo.get_all.return_value = []
                mock_pos_repo_class.return_value = mock_pos_repo

                with patch(
                    "app.jobs.planner_batch.SecurityRepository"
                ) as mock_stock_repo_class:
                    mock_stock_repo = AsyncMock()
                    mock_stock_repo.get_all_active.return_value = []
                    mock_stock_repo_class.return_value = mock_stock_repo

                    with patch(
                        "app.jobs.planner_batch.TradernetClient"
                    ) as mock_client_class:
                        mock_client = MagicMock()
                        mock_client.is_connected = False
                        mock_client.get_pending_orders.return_value = []
                        mock_client_class.return_value = mock_client

                        with patch(
                            "app.jobs.planner_batch.PlannerRepository"
                        ) as mock_planner_repo_class:
                            mock_planner_repo = AsyncMock()
                            mock_planner_repo.has_sequences = AsyncMock(
                                return_value=True
                            )
                            mock_planner_repo.get_total_sequence_count = AsyncMock(
                                return_value=100
                            )
                            mock_planner_repo.get_evaluation_count = AsyncMock(
                                return_value=50
                            )
                            mock_planner_repo.are_all_sequences_evaluated = AsyncMock(
                                return_value=False
                            )
                            mock_planner_repo_class.return_value = mock_planner_repo

                            with patch(
                                "app.jobs.planner_batch.SettingsRepository"
                            ) as mock_settings_repo_class:
                                mock_settings_repo = AsyncMock()
                                mock_settings_repo.get_float = AsyncMock(
                                    return_value=5.0
                                )
                                mock_settings_repo_class.return_value = (
                                    mock_settings_repo
                                )

                                with patch(
                                    "app.jobs.planner_batch.AllocationRepository"
                                ):
                                    with patch(
                                        "app.jobs.planner_batch.ExchangeRateService"
                                    ):
                                        with patch(
                                            "app.jobs.planner_batch.build_portfolio_context"
                                        ):
                                            with patch(
                                                "app.jobs.planner_batch.PortfolioRepository"
                                            ) as mock_portfolio_repo_class:
                                                mock_portfolio_repo = AsyncMock()
                                                mock_portfolio_repo.get_latest = (
                                                    AsyncMock(return_value=None)
                                                )
                                                mock_portfolio_repo_class.return_value = (
                                                    mock_portfolio_repo
                                                )

                                                with patch(
                                                    "app.jobs.planner_batch.create_holistic_plan_incremental"
                                                ) as mock_create_plan:
                                                    mock_create_plan.return_value = None

                                                    with patch(
                                                        "app.jobs.planner_batch.emit"
                                                    ) as mock_emit:
                                                        with patch(
                                                            "app.jobs.planner_batch.get_scheduler"
                                                        ) as mock_get_scheduler:
                                                            mock_scheduler = MagicMock()
                                                            mock_scheduler.running = (
                                                                True
                                                            )
                                                            mock_job = MagicMock()
                                                            mock_job.id = (
                                                                "planner_batch"
                                                            )
                                                            mock_scheduler.get_jobs.return_value = [
                                                                mock_job
                                                            ]
                                                            mock_get_scheduler.return_value = (
                                                                mock_scheduler
                                                            )

                                                            await process_planner_batch_job(
                                                                max_depth=0,
                                                                portfolio_hash="test123",
                                                            )

                                                            # Should emit event
                                                            mock_emit.assert_called()
                                                            call_args = (
                                                                mock_emit.call_args
                                                            )
                                                            from app.core.events import (
                                                                SystemEvent,
                                                            )

                                                            assert (
                                                                call_args[0][0]
                                                                == SystemEvent.PLANNER_BATCH_COMPLETE
                                                            )

    @pytest.mark.asyncio
    async def test_handles_errors_gracefully(self):
        """Test that errors are caught and logged."""
        from app.jobs.planner_batch import process_planner_batch_job

        with patch("app.jobs.planner_batch.get_db_manager") as mock_get_db:
            mock_get_db.side_effect = Exception("Database error")

            with patch("app.jobs.planner_batch.logger") as mock_logger:
                # Should not raise
                await process_planner_batch_job()

                mock_logger.error.assert_called()
