"""Tests for holistic planner - validates sequence generation and planning logic.

These tests ensure the holistic planner correctly:
- Generates action sequences with proper priorities
- Respects cash constraints
- Prioritizes profit-taking and averaging down
- Builds balanced rebalancing sequences
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.planning.holistic_planner import (
    ActionCandidate,
    HolisticPlan,
    HolisticStep,
    generate_action_sequences,
)
from app.domain.value_objects.trade_side import TradeSide


class TestActionCandidate:
    """Tests for ActionCandidate data structure."""

    def test_creates_buy_candidate(self):
        """Buy candidates should have correct structure."""
        candidate = ActionCandidate(
            side=TradeSide.BUY,
            symbol="AAPL",
            name="Apple Inc",
            quantity=10,
            price=150.0,
            value_eur=1500.0,
            currency="USD",
            priority=0.85,
            reason="High quality stock",
            tags=["quality", "opportunity"],
        )

        assert candidate.side == TradeSide.BUY
        assert candidate.symbol == "AAPL"
        assert candidate.value_eur == 1500.0
        assert "quality" in candidate.tags

    def test_creates_sell_candidate(self):
        """Sell candidates should have correct structure."""
        candidate = ActionCandidate(
            side=TradeSide.SELL,
            symbol="MSFT",
            name="Microsoft Corp",
            quantity=5,
            price=300.0,
            value_eur=1300.0,
            currency="USD",
            priority=1.2,
            reason="Windfall gain of 65%",
            tags=["windfall", "profit_taking"],
        )

        assert candidate.side == TradeSide.SELL
        assert candidate.symbol == "MSFT"
        assert "windfall" in candidate.tags


class TestHolisticStep:
    """Tests for HolisticStep data structure."""

    def test_creates_step_with_defaults(self):
        """Steps should have sensible defaults."""
        step = HolisticStep(
            step_number=1,
            side=TradeSide.BUY,
            symbol="AAPL",
            name="Apple Inc",
            quantity=10,
            estimated_price=150.0,
            estimated_value=1500.0,
            currency="USD",
            reason="Quality opportunity",
            narrative="Buy Apple due to strong fundamentals",
        )

        assert step.is_windfall is False
        assert step.is_averaging_down is False
        assert step.contributes_to == []

    def test_creates_windfall_step(self):
        """Windfall steps should be marked correctly."""
        step = HolisticStep(
            step_number=1,
            side=TradeSide.SELL,
            symbol="NVDA",
            name="NVIDIA Corp",
            quantity=20,
            estimated_price=500.0,
            estimated_value=8700.0,
            currency="USD",
            reason="Windfall gain of 80%",
            narrative="Taking windfall profits from NVIDIA",
            is_windfall=True,
            contributes_to=["profit_taking", "risk_reduction"],
        )

        assert step.is_windfall is True
        assert "profit_taking" in step.contributes_to


class TestHolisticPlan:
    """Tests for HolisticPlan data structure."""

    def test_empty_plan_is_feasible(self):
        """Empty plan with no actions should be feasible."""
        plan = HolisticPlan(
            steps=[],
            current_score=75.0,
            end_state_score=75.0,
            improvement=0.0,
            narrative_summary="No actions recommended",
            score_breakdown={},
            cash_required=0.0,
            cash_generated=0.0,
            feasible=True,
        )

        assert plan.feasible is True
        assert plan.improvement == 0.0

    def test_plan_with_improvement(self):
        """Plan with positive improvement should be tracked."""
        step = HolisticStep(
            step_number=1,
            side=TradeSide.BUY,
            symbol="BABA",
            name="Alibaba",
            quantity=50,
            estimated_price=80.0,
            estimated_value=3500.0,
            currency="USD",
            reason="Underweight Asia",
            narrative="Buying BABA to increase Asia exposure",
        )

        plan = HolisticPlan(
            steps=[step],
            current_score=72.0,
            end_state_score=76.5,
            improvement=4.5,
            narrative_summary="Plan improves diversification",
            score_breakdown={"diversification": 0.30, "total_return": 0.35},
            cash_required=3500.0,
            cash_generated=0.0,
            feasible=True,
        )

        assert plan.improvement == 4.5
        assert len(plan.steps) == 1


class TestGenerateActionSequences:
    """Tests for action sequence generation logic."""

    @pytest.mark.asyncio
    async def test_direct_buys_with_available_cash(self):
        """Should generate direct buy sequence when cash is available.

        Bug caught: If cash is available, system should prioritize
        buying quality stocks without requiring sells first.
        """
        opportunities = {
            "profit_taking": [],
            "averaging_down": [
                ActionCandidate(
                    side=TradeSide.BUY,
                    symbol="AAPL",
                    name="Apple",
                    quantity=5,
                    price=150.0,
                    value_eur=700.0,
                    currency="USD",
                    priority=0.8,
                    reason="Down 25%, quality stock",
                    tags=["averaging_down"],
                ),
            ],
            "rebalance_sells": [],
            "rebalance_buys": [],
            "opportunity_buys": [],
        }

        sequences = await generate_action_sequences(
            opportunities=opportunities,
            available_cash=1000.0,
        )

        assert len(sequences) >= 1
        # First sequence should contain the averaging down buy
        first_seq = sequences[0]
        assert any(c.symbol == "AAPL" for c in first_seq)

    @pytest.mark.asyncio
    async def test_profit_taking_first(self):
        """Should generate profit-taking sequence when windfall exists.

        Bug caught: Windfall positions should be trimmed to lock in gains.
        """
        opportunities = {
            "profit_taking": [
                ActionCandidate(
                    side=TradeSide.SELL,
                    symbol="NVDA",
                    name="NVIDIA",
                    quantity=10,
                    price=500.0,
                    value_eur=4500.0,
                    currency="USD",
                    priority=1.5,
                    reason="Windfall 70%",
                    tags=["windfall", "profit_taking"],
                ),
            ],
            "averaging_down": [
                ActionCandidate(
                    side=TradeSide.BUY,
                    symbol="BABA",
                    name="Alibaba",
                    quantity=30,
                    price=80.0,
                    value_eur=2100.0,
                    currency="USD",
                    priority=0.75,
                    reason="Quality dip",
                    tags=["averaging_down"],
                ),
            ],
            "rebalance_sells": [],
            "rebalance_buys": [],
            "opportunity_buys": [],
        }

        sequences = await generate_action_sequences(
            opportunities=opportunities,
            available_cash=0.0,
        )

        # Should have a sequence that starts with profit-taking sell
        profit_seq = None
        for seq in sequences:
            if seq and seq[0].side == TradeSide.SELL and "windfall" in seq[0].tags:
                profit_seq = seq
                break

        assert profit_seq is not None
        # Profit-taking sequence may contain just the sell
        # (reinvestment is handled separately by the planner)

    @pytest.mark.asyncio
    async def test_respects_cash_constraints(self):
        """Should not include buys that exceed available cash.

        Bug caught: System should not recommend buys it can't afford.
        """
        opportunities = {
            "profit_taking": [],
            "averaging_down": [],
            "rebalance_sells": [],
            "rebalance_buys": [
                ActionCandidate(
                    side=TradeSide.BUY,
                    symbol="EXPENSIVE",
                    name="Expensive Stock",
                    quantity=100,
                    price=100.0,
                    value_eur=10000.0,  # More than available cash
                    currency="EUR",
                    priority=0.9,
                    reason="Underweight region",
                    tags=["rebalance"],
                ),
            ],
            "opportunity_buys": [],
        }

        sequences = await generate_action_sequences(
            opportunities=opportunities,
            available_cash=500.0,  # Not enough for the buy
        )

        # Should not include the expensive buy in any sequence
        for seq in sequences:
            assert not any(c.symbol == "EXPENSIVE" for c in seq)

    @pytest.mark.asyncio
    async def test_empty_opportunities_returns_empty(self):
        """Empty opportunities should return no sequences.

        Bug caught: Edge case handling for portfolios with no actions.
        """
        opportunities = {
            "profit_taking": [],
            "averaging_down": [],
            "rebalance_sells": [],
            "rebalance_buys": [],
            "opportunity_buys": [],
        }

        sequences = await generate_action_sequences(
            opportunities=opportunities,
            available_cash=1000.0,
        )

        assert sequences == []

    @pytest.mark.asyncio
    async def test_rebalance_sequence_includes_sells_and_buys(self):
        """Rebalance sequence should include both sells and buys.

        Bug caught: Rebalancing requires selling overweight and buying underweight.
        """
        opportunities = {
            "profit_taking": [],
            "averaging_down": [],
            "rebalance_sells": [
                ActionCandidate(
                    side=TradeSide.SELL,
                    symbol="OVERWEIGHT",
                    name="Overweight Stock",
                    quantity=20,
                    price=50.0,
                    value_eur=900.0,
                    currency="EUR",
                    priority=0.6,
                    reason="Overweight US by 8%",
                    tags=["rebalance", "overweight_us"],
                ),
            ],
            "rebalance_buys": [
                ActionCandidate(
                    side=TradeSide.BUY,
                    symbol="UNDERWEIGHT",
                    name="Underweight Stock",
                    quantity=15,
                    price=60.0,
                    value_eur=800.0,
                    currency="EUR",
                    priority=0.55,
                    reason="Underweight Asia by 10%",
                    tags=["rebalance", "underweight_asia"],
                ),
            ],
            "opportunity_buys": [],
        }

        sequences = await generate_action_sequences(
            opportunities=opportunities,
            available_cash=0.0,
        )

        # Should have a rebalance sequence
        rebalance_seq = None
        for seq in sequences:
            has_sell = any(
                c.side == TradeSide.SELL and "rebalance" in c.tags for c in seq
            )
            has_buy = any(
                c.side == TradeSide.BUY and "rebalance" in c.tags for c in seq
            )
            if has_sell and has_buy:
                rebalance_seq = seq
                break

        assert rebalance_seq is not None
        # Sell should come before buy
        sell_idx = next(
            i for i, c in enumerate(rebalance_seq) if c.side == TradeSide.SELL
        )
        buy_idx = next(
            i for i, c in enumerate(rebalance_seq) if c.side == TradeSide.BUY
        )
        assert sell_idx < buy_idx

    @pytest.mark.asyncio
    async def test_averaging_down_funded_by_profit_taking(self):
        """Should fund averaging down with profit-taking if no cash.

        Bug caught: When cash is low but we have windfall, we should
        take profits to fund averaging down on quality dips.
        """
        opportunities = {
            "profit_taking": [
                ActionCandidate(
                    side=TradeSide.SELL,
                    symbol="WINNER",
                    name="Winner Stock",
                    quantity=10,
                    price=200.0,
                    value_eur=1800.0,
                    currency="USD",
                    priority=1.2,
                    reason="Windfall 80%",
                    tags=["windfall", "profit_taking"],
                ),
            ],
            "averaging_down": [
                ActionCandidate(
                    side=TradeSide.BUY,
                    symbol="QUALITY_DIP",
                    name="Quality Dip",
                    quantity=25,
                    price=40.0,
                    value_eur=900.0,
                    currency="USD",
                    priority=0.85,
                    reason="Down 30%, strong fundamentals",
                    tags=["averaging_down"],
                ),
            ],
            "rebalance_sells": [],
            "rebalance_buys": [],
            "opportunity_buys": [],
        }

        sequences = await generate_action_sequences(
            opportunities=opportunities,
            available_cash=100.0,  # Not enough for the buy alone
        )

        # Should have a sequence that sells first then buys
        found_sequence = False
        for seq in sequences:
            sells = [c for c in seq if c.side == TradeSide.SELL]
            buys = [c for c in seq if c.side == TradeSide.BUY]
            if sells and buys:
                found_sequence = True
                # The averaging down buy should be funded by the sell
                assert any(c.symbol == "QUALITY_DIP" for c in buys)
                break

        assert found_sequence
