"""Tests for narrative generation.

These tests validate the human-readable explanation generation
for trading actions and plans.
"""

from unittest.mock import MagicMock


class TestAddStrategySummary:
    """Test strategy summary generation."""

    def test_windfall_and_averaging(self):
        """Test narrative for windfall sells with averaging buys."""
        from app.modules.planning.domain.narrative import _add_strategy_summary

        parts = []
        _add_strategy_summary(
            parts,
            windfall_sells=["sell1"],
            averaging_buys=["buy1"],
            sells=[],
            buys=[],
        )

        assert len(parts) == 1
        assert "profits" in parts[0].lower()
        assert "reinvest" in parts[0].lower()

    def test_windfall_only(self):
        """Test narrative for windfall sells only."""
        from app.modules.planning.domain.narrative import _add_strategy_summary

        parts = []
        _add_strategy_summary(
            parts,
            windfall_sells=["sell1"],
            averaging_buys=[],
            sells=[],
            buys=[],
        )

        assert len(parts) == 1
        assert "windfall" in parts[0].lower()

    def test_averaging_only(self):
        """Test narrative for averaging buys only."""
        from app.modules.planning.domain.narrative import _add_strategy_summary

        parts = []
        _add_strategy_summary(
            parts,
            windfall_sells=[],
            averaging_buys=["buy1"],
            sells=[],
            buys=[],
        )

        assert len(parts) == 1
        assert "averaging down" in parts[0].lower()

    def test_rebalance(self):
        """Test narrative for rebalancing."""
        from app.modules.planning.domain.narrative import _add_strategy_summary

        parts = []
        _add_strategy_summary(
            parts,
            windfall_sells=[],
            averaging_buys=[],
            sells=["sell1"],
            buys=["buy1"],
        )

        assert len(parts) == 1
        assert "rebalance" in parts[0].lower()

    def test_buys_only(self):
        """Test narrative for buys only."""
        from app.modules.planning.domain.narrative import _add_strategy_summary

        parts = []
        _add_strategy_summary(
            parts,
            windfall_sells=[],
            averaging_buys=[],
            sells=[],
            buys=["buy1"],
        )

        assert len(parts) == 1
        assert "cash" in parts[0].lower()

    def test_sells_only(self):
        """Test narrative for sells only."""
        from app.modules.planning.domain.narrative import _add_strategy_summary

        parts = []
        _add_strategy_summary(
            parts,
            windfall_sells=[],
            averaging_buys=[],
            sells=["sell1"],
            buys=[],
        )

        assert len(parts) == 1
        assert "reduces risk" in parts[0].lower() or "profit" in parts[0].lower()


class TestAddStepSummary:
    """Test step summary generation."""

    def test_includes_action_count(self):
        """Test that action count is included."""
        from app.modules.planning.domain.narrative import _add_step_summary

        parts = []
        mock_step1 = MagicMock()
        mock_step1.estimated_value = 1000
        mock_step1.symbol = "AAPL.US"
        mock_step2 = MagicMock()
        mock_step2.estimated_value = 500
        mock_step2.symbol = "MSFT.US"

        _add_step_summary(
            parts,
            steps=[mock_step1, mock_step2],
            sells=[mock_step1],
            buys=[mock_step2],
        )

        assert any("2 action" in part for part in parts)

    def test_includes_sell_summary(self):
        """Test that sell summary is included."""
        from app.modules.planning.domain.narrative import _add_step_summary

        parts = []
        mock_sell = MagicMock()
        mock_sell.estimated_value = 1000
        mock_sell.symbol = "AAPL.US"

        _add_step_summary(
            parts,
            steps=[mock_sell],
            sells=[mock_sell],
            buys=[],
        )

        assert any(
            "Sell" in part and "€1000" in part or "1,000" in part for part in parts
        )

    def test_includes_buy_summary(self):
        """Test that buy summary is included."""
        from app.modules.planning.domain.narrative import _add_step_summary

        parts = []
        mock_buy = MagicMock()
        mock_buy.estimated_value = 500
        mock_buy.symbol = "MSFT.US"

        _add_step_summary(
            parts,
            steps=[mock_buy],
            sells=[],
            buys=[mock_buy],
        )

        assert any("Buy" in part for part in parts)


class TestAddExpectedOutcome:
    """Test expected outcome generation."""

    def test_positive_improvement(self):
        """Test narrative for positive improvement."""
        from app.modules.planning.domain.narrative import _add_expected_outcome

        parts = []
        _add_expected_outcome(
            parts, improvement=5.0, current_score=60.0, end_score=65.0
        )

        assert len(parts) == 1
        assert "+5.0" in parts[0]
        assert "60.0" in parts[0]
        assert "65.0" in parts[0]

    def test_negative_improvement(self):
        """Test narrative for negative improvement."""
        from app.modules.planning.domain.narrative import _add_expected_outcome

        parts = []
        _add_expected_outcome(
            parts, improvement=-2.0, current_score=60.0, end_score=58.0
        )

        assert len(parts) == 1
        assert "decrease" in parts[0].lower() or "long-term" in parts[0].lower()

    def test_zero_improvement(self):
        """Test narrative for no change."""
        from app.modules.planning.domain.narrative import _add_expected_outcome

        parts = []
        _add_expected_outcome(
            parts, improvement=0.0, current_score=60.0, end_score=60.0
        )

        assert len(parts) == 1
        assert "maintain" in parts[0].lower()


class TestGenerateSellNarrative:
    """Test sell narrative generation."""

    def test_windfall_narrative(self):
        """Test windfall sell narrative."""
        from app.modules.planning.domain.narrative import _generate_sell_narrative

        context = MagicMock()

        narrative = _generate_sell_narrative(
            symbol="AAPL.US",
            name="Apple Inc",
            value=1000,
            tags=["windfall"],
            reason="Stock gained 50% above normal growth",
            portfolio_context=context,
            all_opportunities={},
        )

        assert "Sell" in narrative
        assert "Apple" in narrative
        assert "1000" in narrative or "1,000" in narrative
        assert "windfall" in narrative.lower()

    def test_profit_taking_narrative(self):
        """Test profit taking narrative."""
        from app.modules.planning.domain.narrative import _generate_sell_narrative

        context = MagicMock()

        narrative = _generate_sell_narrative(
            symbol="AAPL.US",
            name="Apple Inc",
            value=500,
            tags=["profit_taking"],
            reason="Taking profits after rally",
            portfolio_context=context,
            all_opportunities={},
        )

        assert "Sell" in narrative
        assert "profit" in narrative.lower()

    def test_rebalance_overweight_narrative(self):
        """Test rebalance with overweight country."""
        from app.modules.planning.domain.narrative import _generate_sell_narrative

        context = MagicMock()

        narrative = _generate_sell_narrative(
            symbol="AAPL.US",
            name="Apple Inc",
            value=500,
            tags=["rebalance", "overweight_us"],
            reason="Portfolio overweight in US",
            portfolio_context=context,
            all_opportunities={},
        )

        assert "Sell" in narrative
        assert "US" in narrative
        assert "diversification" in narrative.lower()

    def test_includes_buy_opportunity_context(self):
        """Test that buy opportunities are mentioned."""
        from app.modules.planning.domain.narrative import _generate_sell_narrative

        context = MagicMock()
        mock_buy = MagicMock()
        mock_buy.name = "SAP SE"

        narrative = _generate_sell_narrative(
            symbol="AAPL.US",
            name="Apple Inc",
            value=500,
            tags=["profit_taking"],
            reason="Taking profits",
            portfolio_context=context,
            all_opportunities={"averaging_down": [mock_buy]},
        )

        assert "SAP" in narrative


class TestGenerateBuyNarrative:
    """Test buy narrative generation."""

    def test_averaging_down_narrative(self):
        """Test averaging down buy narrative."""
        from app.modules.planning.domain.narrative import _generate_buy_narrative

        context = MagicMock()
        context.stock_dividends = {}

        narrative = _generate_buy_narrative(
            symbol="BABA.US",
            name="Alibaba Group",
            value=1000,
            tags=["averaging_down"],
            reason="Quality stock down 20%",
            portfolio_context=context,
            all_opportunities={},
        )

        assert "Buy" in narrative
        assert "Alibaba" in narrative
        assert "averaging down" in narrative.lower()

    def test_rebalance_underweight_narrative(self):
        """Test rebalance with underweight country."""
        from app.modules.planning.domain.narrative import _generate_buy_narrative

        context = MagicMock()
        context.stock_dividends = {}

        narrative = _generate_buy_narrative(
            symbol="SAP.EU",
            name="SAP SE",
            value=500,
            tags=["rebalance", "underweight_eu"],
            reason="Portfolio underweight in EU",
            portfolio_context=context,
            all_opportunities={},
        )

        assert "Buy" in narrative
        assert "EU" in narrative
        assert "diversification" in narrative.lower()

    def test_quality_narrative(self):
        """Test quality/opportunity buy narrative."""
        from app.modules.planning.domain.narrative import _generate_buy_narrative

        context = MagicMock()
        context.stock_dividends = {}

        narrative = _generate_buy_narrative(
            symbol="MSFT.US",
            name="Microsoft",
            value=500,
            tags=["quality", "opportunity"],
            reason="High quality with good fundamentals",
            portfolio_context=context,
            all_opportunities={},
        )

        assert "Buy" in narrative
        assert "quality" in narrative.lower()

    def test_includes_dividend_yield(self):
        """Test that high dividend yield is mentioned."""
        from app.modules.planning.domain.narrative import _generate_buy_narrative

        context = MagicMock()
        context.stock_dividends = {"T.US": 0.07}  # 7% yield

        narrative = _generate_buy_narrative(
            symbol="T.US",
            name="AT&T",
            value=500,
            tags=["quality"],
            reason="Solid dividend stock",
            portfolio_context=context,
            all_opportunities={},
        )

        assert "dividend" in narrative.lower()
        assert "7.0%" in narrative


class TestGenerateStepNarrative:
    """Test step narrative generation."""

    def test_generates_sell_narrative(self):
        """Test that sell actions get sell narrative."""
        from app.domain.value_objects.trade_side import TradeSide
        from app.modules.planning.domain.narrative import generate_step_narrative

        action = MagicMock()
        action.symbol = "AAPL.US"
        action.name = "Apple Inc"
        action.side = TradeSide.SELL
        action.tags = ["profit_taking"]
        action.reason = "Taking profits"
        action.value_eur = 1000

        context = MagicMock()
        context.stock_dividends = {}
        context.positions = {"AAPL.US": 5000.0}  # Current position value

        narrative = generate_step_narrative(action, context, {})

        assert "Sell" in narrative

    def test_generates_buy_narrative(self):
        """Test that buy actions get buy narrative."""
        from app.domain.value_objects.trade_side import TradeSide
        from app.modules.planning.domain.narrative import generate_step_narrative

        action = MagicMock()
        action.symbol = "AAPL.US"
        action.name = "Apple Inc"
        action.side = TradeSide.BUY
        action.tags = ["quality"]
        action.reason = "Good quality stock"
        action.value_eur = 1000

        context = MagicMock()
        context.stock_dividends = {}

        narrative = generate_step_narrative(action, context, {})

        assert "Buy" in narrative


class TestGeneratePlanNarrative:
    """Test plan narrative generation."""

    def test_empty_plan(self):
        """Test narrative for empty plan."""
        from app.modules.planning.domain.narrative import generate_plan_narrative

        narrative = generate_plan_narrative(
            steps=[],
            current_score=60.0,
            end_score=60.0,
            all_opportunities={},
        )

        assert "no action" in narrative.lower()

    def test_includes_all_components(self):
        """Test that all narrative components are included."""
        from app.domain.value_objects.trade_side import TradeSide
        from app.modules.planning.domain.narrative import generate_plan_narrative

        mock_sell = MagicMock()
        mock_sell.side = TradeSide.SELL
        mock_sell.is_windfall = True
        mock_sell.is_averaging_down = False
        mock_sell.estimated_value = 1000
        mock_sell.symbol = "AAPL.US"

        mock_buy = MagicMock()
        mock_buy.side = TradeSide.BUY
        mock_buy.is_windfall = False
        mock_buy.is_averaging_down = True
        mock_buy.estimated_value = 800
        mock_buy.symbol = "BABA.US"

        narrative = generate_plan_narrative(
            steps=[mock_sell, mock_buy],
            current_score=60.0,
            end_score=65.0,
            all_opportunities={},
        )

        # Should mention strategy, steps, and outcome
        assert len(narrative) > 50  # Non-trivial narrative


class TestGenerateTradeoffExplanation:
    """Test trade-off explanation generation."""

    def test_no_explanation_for_positive_individual(self):
        """Test no explanation when individual impact is positive."""
        from app.domain.value_objects.trade_side import TradeSide
        from app.modules.planning.domain.narrative import generate_tradeoff_explanation

        action = MagicMock()
        action.side = TradeSide.SELL
        action.name = "Apple Inc"

        explanation = generate_tradeoff_explanation(
            action=action,
            individual_impact=2.0,  # Positive individual
            sequence_impact=5.0,
        )

        assert explanation == ""

    def test_no_explanation_when_sequence_worse(self):
        """Test no explanation when sequence doesn't improve."""
        from app.domain.value_objects.trade_side import TradeSide
        from app.modules.planning.domain.narrative import generate_tradeoff_explanation

        action = MagicMock()
        action.side = TradeSide.SELL
        action.name = "Apple Inc"

        explanation = generate_tradeoff_explanation(
            action=action,
            individual_impact=-2.0,
            sequence_impact=-3.0,  # Worse than individual
        )

        assert explanation == ""

    def test_explains_tradeoff(self):
        """Test trade-off explanation when sequence improves."""
        from app.domain.value_objects.trade_side import TradeSide
        from app.modules.planning.domain.narrative import generate_tradeoff_explanation

        action = MagicMock()
        action.side = TradeSide.SELL
        action.name = "Apple Inc"

        explanation = generate_tradeoff_explanation(
            action=action,
            individual_impact=-2.0,
            sequence_impact=3.0,
        )

        assert "Selling" in explanation
        assert "Apple" in explanation
        assert "2.0" in explanation
        assert "3.0" in explanation


class TestFormatActionSummary:
    """Test action summary formatting."""

    def test_formats_sell(self):
        """Test sell action formatting."""
        from app.domain.value_objects.trade_side import TradeSide
        from app.modules.planning.domain.narrative import format_action_summary

        action = MagicMock()
        action.side = TradeSide.SELL
        action.symbol = "AAPL.US"
        action.quantity = 10
        action.price = 150.50
        action.value_eur = 1505.0

        summary = format_action_summary(action)

        assert "SELL" in summary
        assert "AAPL.US" in summary
        assert "10" in summary
        assert "150.50" in summary

    def test_formats_buy(self):
        """Test buy action formatting."""
        from app.domain.value_objects.trade_side import TradeSide
        from app.modules.planning.domain.narrative import format_action_summary

        action = MagicMock()
        action.side = TradeSide.BUY
        action.symbol = "MSFT.US"
        action.quantity = 5
        action.price = 350.00
        action.value_eur = 1750.0

        summary = format_action_summary(action)

        assert "BUY" in summary
        assert "MSFT.US" in summary
        assert "5" in summary
        assert "350.00" in summary
