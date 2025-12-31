"""Tests for holistic planner - validates sequence generation and planning logic.

These tests ensure the holistic planner correctly:
- Generates action sequences with proper priorities
- Respects cash constraints
- Prioritizes profit-taking and averaging down
- Builds balanced rebalancing sequences
"""

from unittest.mock import MagicMock

import pytest

from app.domain.value_objects.trade_side import TradeSide
from app.modules.planning.domain.holistic_planner import (
    ActionCandidate,
    HolisticPlan,
    HolisticStep,
    _calculate_weight_gaps,
    _is_trade_worthwhile,
    _process_buy_opportunity,
    generate_action_sequences,
)


class TestCalculateWeightGaps:
    """Test weight gap calculation."""

    def test_calculates_underweight_gap(self):
        """Test detecting underweight positions."""
        target = {"AAPL": 0.30, "MSFT": 0.20}
        current = {"AAPL": 0.20, "MSFT": 0.20}
        total = 100000

        gaps = _calculate_weight_gaps(target, current, total)

        # AAPL is underweight by 10%
        aapl_gap = next(g for g in gaps if g["symbol"] == "AAPL")
        assert aapl_gap["gap"] == pytest.approx(0.10)
        assert aapl_gap["gap_value"] == pytest.approx(10000.0)

    def test_calculates_overweight_gap(self):
        """Test detecting overweight positions."""
        target = {"AAPL": 0.20}
        current = {"AAPL": 0.35}
        total = 100000

        gaps = _calculate_weight_gaps(target, current, total)

        aapl_gap = next(g for g in gaps if g["symbol"] == "AAPL")
        assert aapl_gap["gap"] == pytest.approx(-0.15)
        assert aapl_gap["gap_value"] == pytest.approx(-15000.0)

    def test_includes_positions_not_in_target(self):
        """Test detecting positions that should be sold (not in target)."""
        target = {"AAPL": 0.50}
        current = {"AAPL": 0.40, "MSFT": 0.10}
        total = 100000

        gaps = _calculate_weight_gaps(target, current, total)

        # MSFT is not in target, should show negative gap
        msft_gap = next((g for g in gaps if g["symbol"] == "MSFT"), None)
        assert msft_gap is not None
        assert msft_gap["target"] == 0.0
        assert msft_gap["gap"] == pytest.approx(-0.10)

    def test_ignores_tiny_gaps(self):
        """Test that tiny gaps (<0.5%) are ignored."""
        target = {"AAPL": 0.30}
        current = {"AAPL": 0.302}  # 0.2% difference
        total = 100000

        gaps = _calculate_weight_gaps(target, current, total)

        assert len(gaps) == 0

    def test_sorts_by_absolute_gap_size(self):
        """Test that gaps are sorted by absolute size, largest first."""
        target = {"AAPL": 0.30, "MSFT": 0.20, "GOOG": 0.15}
        current = {"AAPL": 0.20, "MSFT": 0.35, "GOOG": 0.10}
        total = 100000

        gaps = _calculate_weight_gaps(target, current, total)

        # MSFT gap is -15%, AAPL is +10%, GOOG is +5%
        # Sorted by absolute value: MSFT, AAPL, GOOG
        assert gaps[0]["symbol"] == "MSFT"
        assert gaps[1]["symbol"] == "AAPL"
        assert gaps[2]["symbol"] == "GOOG"


class TestIsTradeWorthwhile:
    """Test trade worthiness check based on transaction costs."""

    def test_worthwhile_large_trade(self):
        """Test that large trades are worthwhile."""
        # Gap of 5000, cost is 2 + 0.002*5000 = 12
        # Trade is worthwhile if gap >= 2 * cost = 24
        assert _is_trade_worthwhile(5000.0, 2.0, 0.002) is True

    def test_not_worthwhile_small_trade(self):
        """Test that small trades are not worthwhile."""
        # Gap of 10, cost is 2 + 0.002*10 = 2.02
        # Trade is worthwhile if gap >= 2 * cost = 4.04
        # But gap is 10, so this should be True
        # Actually, 10 >= 4.04, so True
        # Let's use a smaller gap
        # Gap of 3, cost is 2 + 0.002*3 = 2.006
        # Worthwhile if 3 >= 4.01 -> False
        assert _is_trade_worthwhile(3.0, 2.0, 0.002) is False

    def test_borderline_trade(self):
        """Test borderline case."""
        # Find exact threshold: gap = 2 * (fixed + gap * percent)
        # gap = 2 * fixed + 2 * gap * percent
        # gap - 2 * gap * percent = 2 * fixed
        # gap * (1 - 2 * percent) = 2 * fixed
        # gap = 2 * fixed / (1 - 2 * percent)
        # gap = 2 * 2 / (1 - 0.004) = 4 / 0.996 = 4.016
        # So gap of 5 should be worthwhile, gap of 4 should not
        assert _is_trade_worthwhile(5.0, 2.0, 0.002) is True
        assert _is_trade_worthwhile(3.0, 2.0, 0.002) is False


class TestProcessBuyOpportunity:
    """Test buy opportunity processing."""

    def test_adds_buy_opportunity(self):
        """Test that valid buy opportunity is added."""
        gap_info = {
            "symbol": "AAPL",
            "gap_value": 1500.0,
            "gap": 0.10,
            "target": 0.30,
            "current": 0.20,
        }
        stock = MagicMock()
        stock.allow_buy = True
        stock.name = "Apple Inc"
        stock.min_lot = 1

        position = None
        price = 150.0
        opportunities = {
            "rebalance_buys": [],
            "averaging_down": [],
        }

        _process_buy_opportunity(gap_info, stock, position, price, opportunities)

        assert len(opportunities["rebalance_buys"]) == 1
        candidate = opportunities["rebalance_buys"][0]
        assert candidate.symbol == "AAPL"
        assert candidate.quantity == 10  # 1500 / 150

    def test_skips_if_allow_buy_false(self):
        """Test that stock with allow_buy=False is skipped."""
        gap_info = {
            "symbol": "AAPL",
            "gap_value": 1500.0,
            "gap": 0.10,
            "target": 0.30,
            "current": 0.20,
        }
        stock = MagicMock()
        stock.allow_buy = False

        opportunities = {"rebalance_buys": [], "averaging_down": []}

        _process_buy_opportunity(gap_info, stock, None, 150.0, opportunities)

        assert len(opportunities["rebalance_buys"]) == 0
        assert len(opportunities["averaging_down"]) == 0

    def test_skips_if_stock_is_none(self):
        """Test that None stock is skipped."""
        gap_info = {
            "symbol": "AAPL",
            "gap_value": 1500.0,
            "gap": 0.10,
            "target": 0.30,
            "current": 0.20,
        }
        opportunities = {"rebalance_buys": [], "averaging_down": []}

        _process_buy_opportunity(gap_info, None, None, 150.0, opportunities)

        assert len(opportunities["rebalance_buys"]) == 0

    def test_respects_min_lot(self):
        """Test that min_lot is respected."""
        gap_info = {
            "symbol": "AAPL",
            "gap_value": 50.0,
            "gap": 0.05,
            "target": 0.25,
            "current": 0.20,
        }
        stock = MagicMock()
        stock.allow_buy = True
        stock.name = "Apple"
        stock.min_lot = 5

        opportunities = {"rebalance_buys": [], "averaging_down": []}

        _process_buy_opportunity(gap_info, stock, None, 150.0, opportunities)

        # Should use min_lot of 5
        assert len(opportunities["rebalance_buys"]) == 1
        assert opportunities["rebalance_buys"][0].quantity == 5

    def test_categorizes_as_averaging_down(self):
        """Test that buying below avg_price is categorized as averaging_down."""
        gap_info = {
            "symbol": "AAPL",
            "gap_value": 1500.0,
            "gap": 0.10,
            "target": 0.30,
            "current": 0.20,
        }
        stock = MagicMock()
        stock.allow_buy = True
        stock.name = "Apple"
        stock.min_lot = 1

        position = MagicMock()
        position.avg_price = 200.0  # Current price below avg
        position.currency = "USD"

        opportunities = {"rebalance_buys": [], "averaging_down": []}

        _process_buy_opportunity(gap_info, stock, position, 150.0, opportunities)

        # Should be in averaging_down, not rebalance_buys
        assert len(opportunities["averaging_down"]) == 1
        assert len(opportunities["rebalance_buys"]) == 0
        assert "averaging_down" in opportunities["averaging_down"][0].tags

    def test_skips_zero_quantity(self):
        """Test that zero quantity is skipped."""
        gap_info = {
            "symbol": "AAPL",
            "gap_value": 1.0,
            "gap": 0.001,
            "target": 0.201,
            "current": 0.20,
        }
        stock = MagicMock()
        stock.allow_buy = True
        stock.name = "Apple"
        stock.min_lot = None

        opportunities = {"rebalance_buys": [], "averaging_down": []}

        _process_buy_opportunity(gap_info, stock, None, 150.0, opportunities)

        assert len(opportunities["rebalance_buys"]) == 0


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
            enable_combinatorial=False,  # Test pattern generators only
        )

        # Pattern generators should respect cash constraints
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
