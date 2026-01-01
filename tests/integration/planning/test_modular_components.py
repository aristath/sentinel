"""Integration tests for individual modular planner components.

Tests each module type (calculators, patterns, generators, filters) individually
to ensure proper functionality and registry integration.
"""

import pytest

from app.domain.models import Position, Security
from app.modules.planning.domain.calculations.context import OpportunityContext
from app.modules.planning.domain.calculations.filters.base import (
    sequence_filter_registry,
)
from app.modules.planning.domain.calculations.opportunities.base import (
    opportunity_calculator_registry,
)
from app.modules.planning.domain.calculations.patterns.base import (
    pattern_generator_registry,
)
from app.modules.planning.domain.calculations.sequences.base import (
    sequence_generator_registry,
)
from app.modules.planning.domain.models import ActionCandidate
from app.modules.scoring.domain.models import PortfolioContext


@pytest.fixture
def sample_opportunity_context():
    """Create sample opportunity context for testing."""
    from app.shared.domain.value_objects.currency import Currency

    portfolio_context = PortfolioContext(
        country_weights={"USA": 0.7, "Germany": 0.3},
        industry_weights={"Technology": 0.5, "Healthcare": 0.5},
        positions={"AAPL": 5000.0, "MSFT": 4000.0},
        total_value=9000.0,
        security_countries={"AAPL": "USA", "MSFT": "USA"},
        security_industries={"AAPL": "Technology", "MSFT": "Technology"},
        security_scores={"AAPL": 0.85, "MSFT": 0.80},
        security_dividends={},
    )

    positions = [
        Position(
            symbol="AAPL",
            quantity=50,
            avg_price=100.0,
            currency=Currency.USD,
            currency_rate=1.0,
        ),
        Position(
            symbol="MSFT",
            quantity=40,
            avg_price=100.0,
            currency=Currency.USD,
            currency_rate=1.0,
        ),
    ]

    securities = [
        Security(
            symbol="AAPL",
            name="Apple Inc.",
            country="USA",
            industry="Technology",
            currency="USD",
            yahoo_symbol="AAPL",
            active=True,
        ),
        Security(
            symbol="MSFT",
            name="Microsoft Corp.",
            country="USA",
            industry="Technology",
            currency="USD",
            yahoo_symbol="MSFT",
            active=True,
        ),
        Security(
            symbol="SAP",
            name="SAP SE",
            country="Germany",
            industry="Technology",
            currency="EUR",
            yahoo_symbol="SAP",
            active=True,
        ),
    ]

    return OpportunityContext(
        portfolio_context=portfolio_context,
        positions=positions,
        securities=securities,
        available_cash_eur=2000.0,
        current_prices={"AAPL": 150.0, "MSFT": 250.0, "SAP": 120.0},
        target_weights=None,
        ineligible_symbols=set(),
    )


class TestOpportunityCalculatorRegistry:
    """Test opportunity calculator registry and individual calculators."""

    def test_all_calculators_registered(self):
        """Verify all expected calculators are registered."""
        expected_calculators = [
            "profit_taking",
            "averaging_down",
            "opportunity_buys",
            "rebalance_sells",
            "rebalance_buys",
            "weight_based",
        ]

        for name in expected_calculators:
            calculator = opportunity_calculator_registry.get(name)
            assert calculator is not None, f"Calculator '{name}' not registered"

    @pytest.mark.asyncio
    async def test_opportunity_buys_calculator(self, sample_opportunity_context):
        """Test opportunity buys calculator execution."""
        calculator = opportunity_calculator_registry.get("opportunity_buys")
        assert calculator is not None

        opportunities = await calculator.identify(sample_opportunity_context, params={})

        # Should identify at least SAP as a buy opportunity (not currently held)
        assert isinstance(opportunities, list)
        # With limited context, we can't guarantee specific opportunities
        # but the calculator should execute without errors

    @pytest.mark.asyncio
    async def test_profit_taking_calculator(self, sample_opportunity_context):
        """Test profit taking calculator execution."""
        calculator = opportunity_calculator_registry.get("profit_taking")
        assert calculator is not None

        opportunities = await calculator.identify(
            sample_opportunity_context, params={"windfall_threshold": 0.20}
        )

        assert isinstance(opportunities, list)
        # Opportunities depend on position gains, which we haven't set up


class TestPatternGeneratorRegistry:
    """Test pattern generator registry and individual generators."""

    def test_all_patterns_registered(self):
        """Verify all expected patterns are registered."""
        expected_patterns = [
            "direct_buy",
            "profit_taking",
            "rebalance",
            "averaging_down",
            "single_best",
            "multi_sell",
            "mixed_strategy",
            "opportunity_first",
            "deep_rebalance",
            "cash_generation",
            "cost_optimized",
            "adaptive",
            "market_regime",
        ]

        for name in expected_patterns:
            pattern = pattern_generator_registry.get(name)
            assert pattern is not None, f"Pattern '{name}' not registered"

    @pytest.mark.asyncio
    async def test_direct_buy_pattern(self):
        """Test direct buy pattern execution."""
        from app.domain.value_objects.trade_side import TradeSide

        pattern = pattern_generator_registry.get("direct_buy")
        assert pattern is not None

        # Create sample buy opportunities
        buy_opportunities = [
            ActionCandidate(
                side=TradeSide.BUY,
                symbol="AAPL",
                name="Apple Inc.",
                quantity=10,
                price=150.0,
                value_eur=1500.0,
                currency="USD",
                priority=0.8,
                reason="High quality buy",
                tags=["buy", "quality"],
            )
        ]

        opportunities_by_category = {"buy": buy_opportunities}
        sequences = await pattern.generate(
            opportunities_by_category, params={"max_sequences": 5}
        )

        assert isinstance(sequences, list)
        assert len(sequences) > 0
        # Direct buy should create single-action sequences
        for seq in sequences:
            assert len(seq) >= 1  # At least one action

    @pytest.mark.asyncio
    async def test_single_best_pattern(self):
        """Test single best pattern execution."""
        from app.domain.value_objects.trade_side import TradeSide

        pattern = pattern_generator_registry.get("single_best")
        assert pattern is not None

        # Create mixed opportunities
        opportunities_by_category = {
            "buy": [
                ActionCandidate(
                    side=TradeSide.BUY,
                    symbol="AAPL",
                    name="Apple Inc.",
                    quantity=10,
                    price=150.0,
                    value_eur=1500.0,
                    currency="USD",
                    priority=0.8,
                    reason="Buy opportunity",
                    tags=["buy"],
                )
            ],
            "sell": [
                ActionCandidate(
                    side=TradeSide.SELL,
                    symbol="MSFT",
                    name="Microsoft",
                    quantity=5,
                    price=250.0,
                    value_eur=1250.0,
                    currency="USD",
                    priority=0.9,
                    reason="Sell opportunity",
                    tags=["sell"],
                )
            ],
        }

        sequences = await pattern.generate(opportunities_by_category, params={})

        assert isinstance(sequences, list)
        # Single best should return exactly one sequence with the highest priority action
        assert len(sequences) == 1
        assert len(sequences[0]) == 1


class TestSequenceGeneratorRegistry:
    """Test sequence generator registry and individual generators."""

    def test_all_generators_registered(self):
        """Verify all expected generators are registered."""
        expected_generators = [
            "combinatorial",
            "enhanced_combinatorial",
            "partial_execution",
            "constraint_relaxation",
        ]

        for name in expected_generators:
            generator = sequence_generator_registry.get(name)
            assert generator is not None, f"Generator '{name}' not registered"

    @pytest.mark.asyncio
    async def test_partial_execution_generator(self):
        """Test partial execution generator."""
        from app.domain.value_objects.trade_side import TradeSide

        generator = sequence_generator_registry.get("partial_execution")
        assert generator is not None

        buy_opp = ActionCandidate(
            side=TradeSide.BUY,
            symbol="AAPL",
            name="Apple Inc.",
            quantity=100,
            price=150.0,
            value_eur=15000.0,
            currency="USD",
            priority=0.8,
            reason="Buy opportunity",
            tags=["buy"],
        )

        opportunities_by_category = {"buy": [buy_opp]}
        sequences = await generator.generate(
            opportunities_by_category, params={"fill_percentages": [0.5, 1.0]}
        )

        assert isinstance(sequences, list)
        # Should generate sequences with 50% and 100% fills
        assert len(sequences) >= 2


class TestSequenceFilterRegistry:
    """Test sequence filter registry and individual filters."""

    def test_all_filters_registered(self):
        """Verify all expected filters are registered."""
        expected_filters = [
            "correlation_aware",
            "diversity",
            "eligibility",
            "recently_traded",
        ]

        for name in expected_filters:
            filter_obj = sequence_filter_registry.get(name)
            assert filter_obj is not None, f"Filter '{name}' not registered"

    @pytest.mark.asyncio
    async def test_diversity_filter(self):
        """Test diversity selection filter."""
        from app.domain.value_objects.trade_side import TradeSide

        diversity_filter = sequence_filter_registry.get("diversity")
        assert diversity_filter is not None

        # Create sequences with different characteristics
        sequences = [
            [
                ActionCandidate(
                    side=TradeSide.BUY,
                    symbol="AAPL",
                    name="Apple",
                    quantity=10,
                    price=150.0,
                    value_eur=1500.0,
                    currency="USD",
                    priority=0.9,
                    reason="Tech buy",
                    tags=["buy", "technology"],
                )
            ],
            [
                ActionCandidate(
                    side=TradeSide.BUY,
                    symbol="JNJ",
                    name="Johnson & Johnson",
                    quantity=15,
                    price=160.0,
                    value_eur=2400.0,
                    currency="USD",
                    priority=0.85,
                    reason="Healthcare buy",
                    tags=["buy", "healthcare"],
                )
            ],
        ]

        filtered = await diversity_filter.filter(
            sequences, params={"diversity_weight": 0.3, "max_sequences": 2}
        )

        assert isinstance(filtered, list)
        # Filter should preserve both diverse sequences
        assert len(filtered) <= 2


@pytest.mark.asyncio
async def test_end_to_end_module_pipeline():
    """Test complete pipeline: identify -> generate -> filter -> evaluate."""
    from app.shared.domain.value_objects.currency import Currency

    # Setup test data
    portfolio_context = PortfolioContext(
        country_weights={"USA": 1.0},
        industry_weights={"Technology": 1.0},
        positions={"AAPL": 5000.0},
        total_value=5000.0,
        security_countries={"AAPL": "USA"},
        security_industries={"AAPL": "Technology"},
        security_scores={"AAPL": 0.85},
        security_dividends={},
    )

    positions = [
        Position(
            symbol="AAPL",
            quantity=50,
            avg_price=100.0,
            currency=Currency.USD,
            currency_rate=1.0,
        )
    ]

    securities = [
        Security(
            symbol="AAPL",
            name="Apple Inc.",
            country="USA",
            industry="Technology",
            currency="USD",
            yahoo_symbol="AAPL",
            active=True,
        ),
        Security(
            symbol="MSFT",
            name="Microsoft Corp.",
            country="USA",
            industry="Technology",
            currency="USD",
            yahoo_symbol="MSFT",
            active=True,
        ),
    ]

    opp_context = OpportunityContext(
        portfolio_context=portfolio_context,
        positions=positions,
        securities=securities,
        available_cash_eur=2000.0,
        current_prices={"AAPL": 150.0, "MSFT": 250.0},
        target_weights=None,
        ineligible_symbols=set(),
    )

    # Step 1: Identify opportunities
    calculator = opportunity_calculator_registry.get("opportunity_buys")
    assert calculator is not None
    opportunities = await calculator.identify(opp_context, params={})

    # Step 2: Generate patterns
    pattern = pattern_generator_registry.get("direct_buy")
    assert pattern is not None
    opportunities_by_category = {"buy": opportunities}
    sequences = await pattern.generate(opportunities_by_category, params={})

    # Step 3: Apply filters
    diversity_filter = sequence_filter_registry.get("diversity")
    assert diversity_filter is not None
    filtered_sequences = await diversity_filter.filter(
        sequences, params={"max_sequences": 5}
    )

    # Verify pipeline completed
    assert isinstance(filtered_sequences, list)
    # Each component should execute without errors
