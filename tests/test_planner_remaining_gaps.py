"""Tests for remaining uncovered code paths in planner package."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel.planner import AllocationCalculator, RebalanceEngine
from sentinel.planner.rebalance_cash import _load_latest_trades


@pytest.fixture
def _make_allocator():
    """Factory to create an AllocationCalculator."""

    def _create():
        db = MagicMock()
        db.get_all_securities = AsyncMock(
            return_value=[
                {"symbol": "ASML.EU", "user_multiplier": 1.0, "allow_buy": 1},
                {"symbol": "TSM.US", "user_multiplier": 1.0, "allow_buy": 1},
            ]
        )
        db.get_uninvested_dividends = AsyncMock(return_value={})

        allocator = AllocationCalculator(db=db)
        allocator._settings = MagicMock()
        allocator._settings.get = AsyncMock(
            side_effect=lambda key, default: {
                "strategy_entry_t1_dd": -0.12,
                "strategy_entry_t3_dd": -0.28,
                "strategy_entry_memory_days": 90,
                "strategy_memory_max_boost": 0.20,
                "max_dividend_reinvestment_boost": 0.10,
                "strategy_core_target_pct": 80.0,
                "strategy_opportunity_target_pct": 20.0,
                "strategy_min_opp_score": 0.55,
                "max_position_pct": 25.0,
                "clara_preference_strength": 1.0,
                "user_multiplier_blend_pct": 80.0,
            }.get(key, default)
        )

        return allocator

    return _create


class TestAllocationRemainingCoverage:
    """Tests for remaining uncovered AllocationCalculator paths."""

    @pytest.mark.asyncio
    async def test_get_last_signal_bundle_mismatch(self, _make_allocator):
        """Test get_last_signal_bundle with date mismatch."""
        allocator = _make_allocator()

        # Mock cache with different date
        allocator._last_signal_bundle = {
            "as_of_date": "2023-01-01",
            "ideal_portfolio": {"ASML.EU": 0.5, "TSM.US": 0.5},
        }

        # Test with different date
        result = allocator.get_last_signal_bundle(as_of_date="2023-01-02")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_last_signal_bundle_invalid(self, _make_allocator):
        """Test get_last_signal_bundle with invalid bundle."""
        allocator = _make_allocator()

        # Mock cache with invalid bundle
        allocator._last_signal_bundle = "invalid"

        # Test with invalid bundle
        result = allocator.get_last_signal_bundle(as_of_date="2023-01-01")

        assert result is None

    @pytest.mark.asyncio
    async def test_calculate_ideal_portfolio_cache_miss(self, _make_allocator):
        """Test cache miss path in calculate_ideal_portfolio."""
        allocator = _make_allocator()

        # Mock cache miss
        allocator._last_signal_bundle = {
            "as_of_date": "2022-01-01",  # Different date
            "ideal_portfolio": {"ASML.EU": 0.5, "TSM.US": 0.5},
        }

        # Mock DB calls
        allocator._db.get_prices = AsyncMock(return_value=[{"close": 100.0}])  # Mock price data

        # Test cache miss
        result = await allocator.calculate_ideal_portfolio(as_of_date="2023-01-01")

        assert result is not None
        assert "ASML.EU" in result
        assert "TSM.US" in result

        # Verify DB calls were made
        allocator._db.get_all_securities.assert_called_once()
        allocator._db.get_prices.assert_called()

    @pytest.mark.asyncio
    async def test_calculate_ideal_portfolio_dividend_boost_edge_case(self, _make_allocator):
        """Test dividend boost with zero total pool."""
        allocator = _make_allocator()

        # Mock uninvested dividends with zero total
        allocator._db.get_uninvested_dividends = AsyncMock(
            return_value={
                "ASML.EU": 0.0,
                "TSM.US": 0.0,
            }
        )

        # Mock price data
        allocator._db.get_prices = AsyncMock(return_value=[{"close": 100.0}])

        # Test with zero dividend pool
        result = await allocator.calculate_ideal_portfolio()

        assert result is not None
        assert "ASML.EU" in result
        assert "TSM.US" in result

    @pytest.mark.asyncio
    async def test_calculate_ideal_portfolio_sleeve_normalization(self, _make_allocator):
        """Test sleeve target normalization."""
        allocator = _make_allocator()

        # Mock settings with valid sleeve targets
        allocator._settings.get = AsyncMock(
            side_effect=lambda key, default: {
                "strategy_core_target_pct": 70.0,
                "strategy_opportunity_target_pct": 30.0,
                "strategy_min_opp_score": 0.55,
                "max_position_pct": 25.0,
                "strategy_entry_t1_dd": -0.12,
                "strategy_entry_t3_dd": -0.28,
                "strategy_entry_memory_days": 90,
                "strategy_memory_max_boost": 0.20,
                "max_dividend_reinvestment_boost": 0.10,
                "clara_preference_strength": 1.0,
                "user_multiplier_blend_pct": 80.0,
            }.get(key, default)
        )

        # Mock price data
        allocator._db.get_prices = AsyncMock(return_value=[{"close": 100.0}])

        # Test with valid sleeve targets
        result = await allocator.calculate_ideal_portfolio()

        assert result is not None
        assert "ASML.EU" in result
        assert "TSM.US" in result


@pytest.fixture
def _make_engine():
    """Factory to create an engine with proper settings_ctx."""

    def _create():
        db = MagicMock()
        engine = RebalanceEngine(db=db)
        engine._broker = MagicMock()
        engine._settings = MagicMock()
        engine._settings.get = AsyncMock(side_effect=lambda key, default=None: default)
        engine._portfolio = MagicMock()
        engine._currency = MagicMock()
        engine._currency.get_rate = AsyncMock(return_value=1.0)
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        return engine

    return _create


class TestRebalanceRemainingCoverage:
    """Tests for remaining uncovered rebalance_cash paths."""

    @pytest.mark.asyncio
    async def test_load_latest_trades_empty(self, _make_engine):
        """Test _load_latest_trades with empty result."""
        engine = _make_engine()

        # Mock DB response with empty result
        engine._db.get_latest_trades_for_symbols = AsyncMock(return_value={})

        # Test loading trades with empty result
        trades = await _load_latest_trades(engine=engine, symbols=["ASML.EU", "TSM.US"])

        assert trades == {}

    @pytest.mark.asyncio
    async def test_load_latest_trades_none(self, _make_engine):
        """Test _load_latest_trades with None result."""
        engine = _make_engine()

        # Mock DB response with None result
        engine._db.get_latest_trades_for_symbols = AsyncMock(return_value=None)

        # Test loading trades with None result
        trades = await _load_latest_trades(engine=engine, symbols=["ASML.EU", "TSM.US"])

        assert trades == {}
