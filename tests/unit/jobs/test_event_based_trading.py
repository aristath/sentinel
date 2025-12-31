"""Tests for the event-based trading loop.

The event-based trading system:
1. Waits for planning completion (all sequences evaluated)
2. Gets optimal recommendation from best result
3. Checks trading conditions (P&L guardrails)
4. Checks market hours (with flexible behavior)
5. Executes trade if allowed
6. Monitors portfolio for changes (two-phase approach)
7. Restarts loop when portfolio hash changes
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.models import Recommendation
from app.domain.value_objects.recommendation_status import RecommendationStatus
from app.domain.value_objects.trade_side import TradeSide
from app.shared.domain.value_objects.currency import Currency


class TestWaitForPlanningCompletion:
    """Tests for _wait_for_planning_completion function."""

    @pytest.mark.asyncio
    async def test_waits_until_all_sequences_evaluated(self):
        """Test that function waits until all sequences are evaluated."""
        from app.jobs.event_based_trading import _wait_for_planning_completion

        mock_repo = MagicMock()
        mock_repo.has_sequences = AsyncMock(return_value=True)
        mock_repo.are_all_sequences_evaluated = AsyncMock(
            side_effect=[False, False, True]
        )

        with (
            patch(
                "app.jobs.event_based_trading.PlannerRepository", return_value=mock_repo
            ),
            patch("app.jobs.event_based_trading.PositionRepository"),
            patch("app.jobs.event_based_trading.StockRepository"),
            patch(
                "app.jobs.planner_batch.process_planner_batch_job",
                new_callable=AsyncMock,
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await _wait_for_planning_completion()

        # Should have checked completion 3 times (False, False, True)
        assert mock_repo.are_all_sequences_evaluated.call_count == 3

    @pytest.mark.asyncio
    async def test_generates_sequences_if_not_exist(self):
        """Test that sequences are generated if they don't exist."""
        from app.jobs.event_based_trading import _wait_for_planning_completion

        mock_repo = MagicMock()
        mock_repo.has_sequences = AsyncMock(return_value=False)
        mock_repo.are_all_sequences_evaluated = AsyncMock(return_value=True)

        with (
            patch(
                "app.jobs.event_based_trading.PlannerRepository", return_value=mock_repo
            ),
            patch("app.jobs.event_based_trading.PositionRepository"),
            patch("app.jobs.event_based_trading.StockRepository"),
            patch(
                "app.modules.planning.services.portfolio_context_builder.build_portfolio_context",
                new_callable=AsyncMock,
            ),
            patch("app.infrastructure.external.tradernet.get_tradernet_client"),
            patch(
                "app.domain.planning.holistic_planner.create_holistic_plan_incremental",
                new_callable=AsyncMock,
            ),
            patch("app.jobs.event_based_trading.SettingsRepository"),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await _wait_for_planning_completion()

        # Should have checked if sequences exist
        mock_repo.has_sequences.assert_called_once()

    @pytest.mark.asyncio
    async def test_timeout_after_max_iterations(self):
        """Test that function times out after max iterations."""
        from app.jobs.event_based_trading import _wait_for_planning_completion

        mock_repo = MagicMock()
        mock_repo.has_sequences = AsyncMock(return_value=True)
        mock_repo.are_all_sequences_evaluated = AsyncMock(return_value=False)

        with (
            patch(
                "app.jobs.event_based_trading.PlannerRepository", return_value=mock_repo
            ),
            patch("app.jobs.event_based_trading.PositionRepository"),
            patch("app.jobs.event_based_trading.StockRepository"),
            patch(
                "app.jobs.planner_batch.process_planner_batch_job",
                new_callable=AsyncMock,
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await _wait_for_planning_completion()

        # Should have checked completion max_iterations times (360)
        assert mock_repo.are_all_sequences_evaluated.call_count == 360


class TestGetOptimalRecommendation:
    """Tests for _get_optimal_recommendation function."""

    @pytest.mark.asyncio
    async def test_returns_recommendation_from_best_result(self):
        """Test that function returns recommendation from best result."""
        from app.jobs.event_based_trading import _get_optimal_recommendation

        mock_repo = MagicMock()
        mock_repo.get_best_result = AsyncMock(
            return_value={
                "best_sequence_hash": "abc123",
                "end_score": 100.0,
            }
        )
        mock_repo.get_best_sequence_from_hash = AsyncMock(
            return_value=[
                {
                    "side": "BUY",
                    "symbol": "AAPL",
                    "name": "Apple Inc.",
                    "quantity": 10,
                    "price": 150.0,
                    "value_eur": 1500.0,
                    "reason": "Test reason",
                }
            ]
        )

        mock_db = MagicMock()
        mock_db.fetchone = AsyncMock(
            return_value={
                "end_score": 100.0,
                "breakdown_json": '{"total": 100.0}',
                "end_cash": 1000.0,
                "end_context_positions_json": "{}",
                "div_score": 0.8,
                "total_value": 10000.0,
            }
        )

        with (
            patch(
                "app.jobs.event_based_trading.PlannerRepository", return_value=mock_repo
            ),
            patch("app.jobs.event_based_trading.PositionRepository"),
            patch("app.jobs.event_based_trading.StockRepository"),
            patch.object(mock_repo, "_get_db", return_value=mock_db),
            patch(
                "app.domain.scoring.portfolio_scorer.calculate_portfolio_score",
                new_callable=AsyncMock,
                return_value=90.0,
            ),
        ):
            recommendation = await _get_optimal_recommendation()

        assert recommendation is not None
        assert recommendation.symbol == "AAPL"
        assert recommendation.side == TradeSide.BUY
        assert recommendation.quantity == 10

    @pytest.mark.asyncio
    async def test_returns_none_if_no_best_result(self):
        """Test that function returns None if no best result exists."""
        from app.jobs.event_based_trading import _get_optimal_recommendation

        mock_repo = MagicMock()
        mock_repo.get_best_result = AsyncMock(return_value=None)

        with (
            patch(
                "app.jobs.event_based_trading.PlannerRepository", return_value=mock_repo
            ),
            patch("app.jobs.event_based_trading.PositionRepository"),
            patch("app.jobs.event_based_trading.StockRepository"),
        ):
            recommendation = await _get_optimal_recommendation()

        assert recommendation is None


class TestCanExecuteTrade:
    """Tests for _can_execute_trade function."""

    @pytest.mark.asyncio
    async def test_allows_trade_when_market_hours_not_required(self):
        """Test that trade is allowed when market hours check not required."""
        from app.jobs.event_based_trading import _can_execute_trade

        recommendation = Recommendation(
            symbol="AAPL",
            name="Apple Inc.",
            side=TradeSide.BUY,
            quantity=10,
            estimated_price=150.0,
            estimated_value=1500.0,
            reason="Test",
            currency=Currency.USD,
            status=RecommendationStatus.PENDING,
        )

        mock_stock = MagicMock()
        mock_stock.fullExchangeName = "NASDAQ"

        mock_repo = MagicMock()
        mock_repo.get_by_symbol = AsyncMock(return_value=mock_stock)

        with (
            patch(
                "app.jobs.event_based_trading.StockRepository", return_value=mock_repo
            ),
            patch(
                "app.jobs.event_based_trading.should_check_market_hours",
                return_value=False,
            ),
        ):
            can_execute, reason = await _can_execute_trade(recommendation)

        assert can_execute is True
        assert reason is None

    @pytest.mark.asyncio
    async def test_allows_trade_when_market_open(self):
        """Test that trade is allowed when market is open."""
        from app.jobs.event_based_trading import _can_execute_trade

        recommendation = Recommendation(
            symbol="AAPL",
            name="Apple Inc.",
            side=TradeSide.SELL,
            quantity=10,
            estimated_price=150.0,
            estimated_value=1500.0,
            reason="Test",
            currency=Currency.USD,
            status=RecommendationStatus.PENDING,
        )

        mock_stock = MagicMock()
        mock_stock.fullExchangeName = "NASDAQ"

        mock_repo = MagicMock()
        mock_repo.get_by_symbol = AsyncMock(return_value=mock_stock)

        with (
            patch(
                "app.jobs.event_based_trading.StockRepository", return_value=mock_repo
            ),
            patch(
                "app.jobs.event_based_trading.should_check_market_hours",
                return_value=True,
            ),
            patch("app.jobs.event_based_trading.is_market_open", return_value=True),
        ):
            can_execute, reason = await _can_execute_trade(recommendation)

        assert can_execute is True
        assert reason is None

    @pytest.mark.asyncio
    async def test_blocks_trade_when_market_closed(self):
        """Test that trade is blocked when market is closed."""
        from app.jobs.event_based_trading import _can_execute_trade

        recommendation = Recommendation(
            symbol="AAPL",
            name="Apple Inc.",
            side=TradeSide.SELL,
            quantity=10,
            estimated_price=150.0,
            estimated_value=1500.0,
            reason="Test",
            currency=Currency.USD,
            status=RecommendationStatus.PENDING,
        )

        mock_stock = MagicMock()
        mock_stock.fullExchangeName = "NASDAQ"

        mock_repo = MagicMock()
        mock_repo.get_by_symbol = AsyncMock(return_value=mock_stock)

        with (
            patch(
                "app.jobs.event_based_trading.StockRepository", return_value=mock_repo
            ),
            patch(
                "app.jobs.event_based_trading.should_check_market_hours",
                return_value=True,
            ),
            patch("app.jobs.event_based_trading.is_market_open", return_value=False),
        ):
            can_execute, reason = await _can_execute_trade(recommendation)

        assert can_execute is False
        assert "Market closed" in reason

    @pytest.mark.asyncio
    async def test_allows_trade_when_stock_not_found(self):
        """Test that trade is allowed when stock not found (fail open)."""
        from app.jobs.event_based_trading import _can_execute_trade

        recommendation = Recommendation(
            symbol="UNKNOWN",
            name="Unknown Stock",
            side=TradeSide.BUY,
            quantity=10,
            estimated_price=150.0,
            estimated_value=1500.0,
            reason="Test",
            currency=Currency.USD,
            status=RecommendationStatus.PENDING,
        )

        mock_repo = MagicMock()
        mock_repo.get_by_symbol = AsyncMock(return_value=None)

        with patch(
            "app.jobs.event_based_trading.StockRepository", return_value=mock_repo
        ):
            can_execute, reason = await _can_execute_trade(recommendation)

        assert can_execute is True
        assert reason is None


class TestMonitorPortfolioForChanges:
    """Tests for _monitor_portfolio_for_changes function."""

    @pytest.mark.asyncio
    async def test_detects_hash_change_in_phase_1(self):
        """Test that function detects hash change in phase 1 (30s intervals)."""
        from app.jobs.event_based_trading import _monitor_portfolio_for_changes

        initial_hash = "hash1"
        changed_hash = "hash2"

        with (
            patch("app.jobs.event_based_trading.PositionRepository"),
            patch("app.jobs.event_based_trading.StockRepository"),
            patch("app.infrastructure.external.tradernet.get_tradernet_client"),
            patch(
                "app.domain.portfolio_hash.generate_portfolio_hash",
                side_effect=[initial_hash, changed_hash],
            ),
            patch(
                "app.jobs.event_based_trading._step_sync_portfolio",
                new_callable=AsyncMock,
            ),
            patch("app.jobs.event_based_trading.get_cache_invalidation_service"),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await _monitor_portfolio_for_changes()

        assert result is True

    @pytest.mark.asyncio
    async def test_detects_hash_change_in_phase_2(self):
        """Test that function detects hash change in phase 2 (1min intervals)."""
        from app.jobs.event_based_trading import _monitor_portfolio_for_changes

        initial_hash = "hash1"
        unchanged_hash = "hash1"
        changed_hash = "hash2"

        # First 10 iterations (phase 1) - no change
        # Then phase 2 - change detected
        hash_sequence = [unchanged_hash] * 10 + [changed_hash]

        with (
            patch("app.jobs.event_based_trading.PositionRepository"),
            patch("app.jobs.event_based_trading.StockRepository"),
            patch("app.jobs.event_based_trading.get_tradernet_client"),
            patch(
                "app.jobs.event_based_trading.generate_portfolio_hash",
                side_effect=[initial_hash] + hash_sequence,
            ),
            patch(
                "app.jobs.event_based_trading._step_sync_portfolio",
                new_callable=AsyncMock,
            ),
            patch("app.jobs.event_based_trading.get_cache_invalidation_service"),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await _monitor_portfolio_for_changes()

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_no_hash_change(self):
        """Test that function returns False when no hash change detected."""
        from app.jobs.event_based_trading import _monitor_portfolio_for_changes

        initial_hash = "hash1"
        unchanged_hash = "hash1"

        # All iterations return same hash
        hash_sequence = [unchanged_hash] * 25  # 10 phase 1 + 15 phase 2

        with (
            patch("app.jobs.event_based_trading.PositionRepository"),
            patch("app.jobs.event_based_trading.StockRepository"),
            patch("app.jobs.event_based_trading.get_tradernet_client"),
            patch(
                "app.jobs.event_based_trading.generate_portfolio_hash",
                side_effect=[initial_hash] + hash_sequence,
            ),
            patch(
                "app.jobs.event_based_trading._step_sync_portfolio",
                new_callable=AsyncMock,
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await _monitor_portfolio_for_changes()

        assert result is False


class TestEventBasedTradingLoop:
    """Tests for the main event-based trading loop."""

    @pytest.mark.asyncio
    async def test_loop_continues_when_no_recommendation(self):
        """Test that loop continues when no recommendation available."""
        from app.jobs.event_based_trading import _run_event_based_trading_loop_internal

        call_count = 0

        async def mock_wait_for_planning():
            nonlocal call_count
            call_count += 1
            if call_count > 2:  # Stop after 2 iterations
                raise KeyboardInterrupt("Stop test")

        async def mock_get_recommendation():
            return None  # No recommendation

        with (
            patch(
                "app.jobs.event_based_trading._wait_for_planning_completion",
                side_effect=mock_wait_for_planning,
            ),
            patch(
                "app.jobs.event_based_trading._get_optimal_recommendation",
                side_effect=mock_get_recommendation,
            ),
            patch("app.jobs.event_based_trading.set_text"),
            patch("pass  # LED cleared"),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            try:
                await _run_event_based_trading_loop_internal()
            except KeyboardInterrupt:
                pass  # Expected

        assert call_count == 3  # 2 iterations + 1 that raises

    @pytest.mark.asyncio
    async def test_loop_skips_trade_when_conditions_not_met(self):
        """Test that loop skips trade when trading conditions not met."""
        from app.jobs.event_based_trading import _run_event_based_trading_loop_internal

        recommendation = Recommendation(
            symbol="AAPL",
            name="Apple Inc.",
            side=TradeSide.BUY,
            quantity=10,
            estimated_price=150.0,
            estimated_value=1500.0,
            reason="Test",
            currency=Currency.USD,
            status=RecommendationStatus.PENDING,
        )

        call_count = 0

        async def mock_wait_for_planning():
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise KeyboardInterrupt("Stop test")

        async def mock_get_recommendation():
            return recommendation

        async def mock_check_conditions():
            return False, {"reason": "P&L guardrails not met"}

        with (
            patch(
                "app.jobs.event_based_trading._wait_for_planning_completion",
                side_effect=mock_wait_for_planning,
            ),
            patch(
                "app.jobs.event_based_trading._get_optimal_recommendation",
                side_effect=mock_get_recommendation,
            ),
            patch(
                "app.jobs.event_based_trading._step_check_trading_conditions",
                side_effect=mock_check_conditions,
            ),
            patch("app.jobs.event_based_trading.set_text"),
            patch("pass  # LED cleared"),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            try:
                await _run_event_based_trading_loop_internal()
            except KeyboardInterrupt:
                pass  # Expected

        assert call_count == 2  # 1 iteration + 1 that raises

    @pytest.mark.asyncio
    async def test_loop_executes_trade_when_all_conditions_met(self):
        """Test that loop executes trade when all conditions are met."""
        from app.jobs.event_based_trading import _run_event_based_trading_loop_internal

        recommendation = Recommendation(
            symbol="AAPL",
            name="Apple Inc.",
            side=TradeSide.BUY,
            quantity=10,
            estimated_price=150.0,
            estimated_value=1500.0,
            reason="Test",
            currency=Currency.USD,
            status=RecommendationStatus.PENDING,
        )

        call_count = 0

        async def mock_wait_for_planning():
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise KeyboardInterrupt("Stop test")

        async def mock_get_recommendation():
            return recommendation

        async def mock_check_conditions():
            return True, {}

        async def mock_can_execute():
            return True, None

        async def mock_execute_trade():
            return {"status": "success"}

        async def mock_sync_portfolio():
            pass

        async def mock_monitor():
            return False  # No portfolio change

        with (
            patch(
                "app.jobs.event_based_trading._wait_for_planning_completion",
                side_effect=mock_wait_for_planning,
            ),
            patch(
                "app.jobs.event_based_trading._get_optimal_recommendation",
                side_effect=mock_get_recommendation,
            ),
            patch(
                "app.jobs.event_based_trading._step_check_trading_conditions",
                side_effect=mock_check_conditions,
            ),
            patch(
                "app.jobs.event_based_trading._can_execute_trade",
                side_effect=mock_can_execute,
            ),
            patch(
                "app.jobs.event_based_trading._execute_trade_order",
                side_effect=mock_execute_trade,
            ),
            patch(
                "app.jobs.event_based_trading._step_sync_portfolio",
                side_effect=mock_sync_portfolio,
            ),
            patch(
                "app.jobs.event_based_trading._monitor_portfolio_for_changes",
                side_effect=mock_monitor,
            ),
            patch("app.jobs.event_based_trading.set_text"),
            patch("pass  # LED cleared"),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            try:
                await _run_event_based_trading_loop_internal()
            except KeyboardInterrupt:
                pass  # Expected

        assert call_count == 2  # 1 iteration + 1 that raises
