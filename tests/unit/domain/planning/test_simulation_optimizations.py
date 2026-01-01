"""Tests for copy-on-write optimization in sequence simulation.

Tests verify that the memory-efficient dict copying works correctly
while maintaining correctness of simulation results.
"""

import pytest

from app.domain.models import Security
from app.domain.value_objects.trade_side import TradeSide
from app.modules.planning.domain.calculations.simulation import simulate_sequence
from app.modules.planning.domain.models import ActionCandidate
from app.modules.scoring.domain.models import PortfolioContext


class TestSimulationCopyOnWrite:
    """Test copy-on-write optimization in sequence simulation."""

    @pytest.mark.asyncio
    async def test_sell_does_not_modify_original_context(self):
        """SELL actions should create new context without modifying original."""
        # Create portfolio with existing positions
        original_positions = {"AAPL": 1000.0, "GOOGL": 2000.0}
        portfolio_context = PortfolioContext(
            positions=original_positions.copy(),
            total_value=3000.0,
            country_weights={},
            industry_weights={},
            security_countries={"AAPL": "US", "GOOGL": "US"},
            security_industries={"AAPL": "Technology", "GOOGL": "Technology"},
            security_scores={},
            security_dividends={},
        )

        # SELL action
        sequence = [
            ActionCandidate(
                side=TradeSide.SELL,
                symbol="AAPL",
                name="Apple Inc.",
                quantity=-10,
                price=100.0,
                value_eur=1000.0,
                currency="USD",
                priority=0.8,
                reason="Test sell",
                tags=[],
            )
        ]

        securities = [
            Security(
                symbol="AAPL",
                name="Apple Inc.",
                country="US",
                industry="Technology",
                active=True,
                product_type="stock",
            )
        ]

        end_context, end_cash = await simulate_sequence(
            sequence, portfolio_context, 500.0, securities
        )

        # Verify original context unchanged
        assert portfolio_context.positions == original_positions
        # Verify end context correct
        assert "AAPL" not in end_context.positions  # Sold out
        assert "GOOGL" in end_context.positions
        assert end_cash == 1500.0  # 500 + 1000 from sale

    @pytest.mark.asyncio
    async def test_buy_adds_geography_industry_metadata(self):
        """BUY actions with country/industry should add metadata to new context."""
        portfolio_context = PortfolioContext(
            positions={"AAPL": 1000.0},
            total_value=1000.0,
            country_weights={},
            industry_weights={},
            security_countries={"AAPL": "US"},
            security_industries={"AAPL": "Technology"},
            security_scores={},
            security_dividends={},
        )

        # BUY action with metadata
        sequence = [
            ActionCandidate(
                side=TradeSide.BUY,
                symbol="MSFT",
                name="Microsoft",
                quantity=10,
                price=100.0,
                value_eur=1000.0,
                currency="USD",
                priority=0.8,
                reason="Test buy",
                tags=[],
            )
        ]

        securities = [
            Security(
                symbol="MSFT",
                name="Microsoft",
                country="US",
                industry="Technology",
                active=True,
                product_type="stock",
            )
        ]

        end_context, end_cash = await simulate_sequence(
            sequence, portfolio_context, 1500.0, securities
        )

        # After BUY, new symbol should be in geography/industry
        assert "MSFT" in end_context.positions
        assert end_context.positions["MSFT"] == 1000.0
        assert "MSFT" in end_context.security_countries
        assert end_context.security_countries["MSFT"] == "US"
        assert "MSFT" in end_context.security_industries
        assert end_context.security_industries["MSFT"] == "Technology"
        assert end_cash == 500.0  # 1500 - 1000 spent

    @pytest.mark.asyncio
    async def test_buy_without_metadata_still_works(self):
        """BUY actions without country/industry should still create positions."""
        portfolio_context = PortfolioContext(
            positions={"AAPL": 1000.0},
            total_value=1000.0,
            country_weights={},
            industry_weights={},
            security_countries={"AAPL": "US"},
            security_industries={"AAPL": "Technology"},
            security_scores={},
            security_dividends={},
        )

        # BUY action without metadata (security has no country/industry)
        sequence = [
            ActionCandidate(
                side=TradeSide.BUY,
                symbol="UNKNOWN",
                name="Unknown Stock",
                quantity=10,
                price=50.0,
                value_eur=500.0,
                currency="USD",
                priority=0.5,
                reason="Test buy",
                tags=[],
            )
        ]

        securities = []  # No security metadata available

        end_context, end_cash = await simulate_sequence(
            sequence, portfolio_context, 1000.0, securities
        )

        # Position created but no geography/industry added (graceful handling)
        assert "UNKNOWN" in end_context.positions
        assert end_context.positions["UNKNOWN"] == 500.0
        assert "UNKNOWN" not in end_context.security_countries
        assert "UNKNOWN" not in end_context.security_industries
        assert end_cash == 500.0

    @pytest.mark.asyncio
    async def test_multiple_actions_accumulate_correctly(self):
        """Multiple actions in sequence should work with updated context from previous."""
        portfolio_context = PortfolioContext(
            positions={"AAPL": 1000.0},
            total_value=1000.0,
            country_weights={},
            industry_weights={},
            security_countries={"AAPL": "US"},
            security_industries={"AAPL": "Technology"},
            security_scores={},
            security_dividends={},
        )

        sequence = [
            # First: Sell AAPL
            ActionCandidate(
                side=TradeSide.SELL,
                symbol="AAPL",
                name="Apple Inc.",
                quantity=-10,
                price=100.0,
                value_eur=1000.0,
                currency="USD",
                priority=0.8,
                reason="Sell",
                tags=[],
            ),
            # Then: Buy MSFT with proceeds
            ActionCandidate(
                side=TradeSide.BUY,
                symbol="MSFT",
                name="Microsoft",
                quantity=10,
                price=100.0,
                value_eur=1000.0,
                currency="USD",
                priority=0.8,
                reason="Buy",
                tags=[],
            ),
        ]

        securities = [
            Security(
                symbol="MSFT",
                name="Microsoft",
                country="US",
                industry="Technology",
                active=True,
                product_type="stock",
            )
        ]

        end_context, end_cash = await simulate_sequence(
            sequence, portfolio_context, 0.0, securities
        )

        # After sequence: AAPL sold, MSFT bought
        assert "AAPL" not in end_context.positions
        assert "MSFT" in end_context.positions
        assert end_context.positions["MSFT"] == 1000.0
        assert end_cash == 0.0  # 0 + 1000 (from sell) - 1000 (buy) = 0

    @pytest.mark.asyncio
    async def test_insufficient_cash_skips_buy(self):
        """BUY action with insufficient cash should be skipped."""
        portfolio_context = PortfolioContext(
            positions={"AAPL": 1000.0},
            total_value=1000.0,
            country_weights={},
            industry_weights={},
            security_countries={},
            security_industries={},
            security_scores={},
            security_dividends={},
        )

        sequence = [
            ActionCandidate(
                side=TradeSide.BUY,
                symbol="MSFT",
                name="Microsoft",
                quantity=10,
                price=100.0,
                value_eur=1000.0,
                currency="USD",
                priority=0.8,
                reason="Test",
                tags=[],
            )
        ]

        securities = []

        # Only 500 available, but action needs 1000
        end_context, end_cash = await simulate_sequence(
            sequence, portfolio_context, 500.0, securities
        )

        # Action skipped - no MSFT purchased
        assert "MSFT" not in end_context.positions
        assert end_cash == 500.0  # Unchanged
