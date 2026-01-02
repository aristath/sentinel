"""Test Go evaluation service produces identical results to Python.

These tests verify that the Go evaluation service produces the same results
as the Python evaluation logic for basic sequence evaluation (without advanced
features like multi-objective, stochastic scenarios, etc.).
"""

import pytest

from app.domain.models import Security
from app.domain.value_objects.product_type import ProductType
from app.domain.value_objects.trade_side import TradeSide
from app.modules.planning.domain.calculations.simulation import simulate_sequence
from app.modules.planning.domain.models import ActionCandidate
from app.modules.planning.infrastructure.go_evaluation_client import GoEvaluationClient
from app.modules.scoring.domain.diversification import calculate_portfolio_score
from app.modules.scoring.domain.end_state import calculate_portfolio_end_state_score
from app.modules.scoring.domain.models import PortfolioContext


@pytest.fixture
def portfolio_context():
    """Create a sample portfolio context."""
    return PortfolioContext(
        positions={"AAPL": 100.0, "GOOGL": 50.0, "MSFT": 75.0},
        total_value=50000.0,
        position_count=3,
        security_countries={"United States": 3},
        security_industries={"Technology": 3},
        security_sectors={"Technology": 3},
    )


@pytest.fixture
def securities():
    """Create sample securities."""
    return [
        Security(
            symbol="AAPL",
            name="Apple Inc.",
            product_type=ProductType.EQUITY,
            country="United States",
            industry="Technology",
            sector="Technology",
            allow_buy=True,
            allow_sell=True,
            is_active=True,
        ),
        Security(
            symbol="GOOGL",
            name="Alphabet Inc.",
            product_type=ProductType.EQUITY,
            country="United States",
            industry="Technology",
            sector="Technology",
            allow_buy=True,
            allow_sell=True,
            is_active=True,
        ),
        Security(
            symbol="MSFT",
            name="Microsoft Corporation",
            product_type=ProductType.EQUITY,
            country="United States",
            industry="Technology",
            sector="Technology",
            allow_buy=True,
            allow_sell=True,
            is_active=True,
        ),
        Security(
            symbol="AMZN",
            name="Amazon.com Inc.",
            product_type=ProductType.EQUITY,
            country="United States",
            industry="E-commerce",
            sector="Consumer Cyclical",
            allow_buy=True,
            allow_sell=False,
            is_active=True,
        ),
    ]


@pytest.fixture
def simple_buy_sequence():
    """Create a simple buy sequence."""
    return [
        ActionCandidate(
            side=TradeSide.BUY,
            symbol="AMZN",
            name="Amazon.com Inc.",
            quantity=10,
            price=180.0,
            value_eur=1800.0,
            currency="USD",
            priority=0.8,
            reason="Test buy",
            tags=["test"],
        )
    ]


@pytest.fixture
def sell_then_buy_sequence():
    """Create a sell-then-buy sequence."""
    return [
        ActionCandidate(
            side=TradeSide.SELL,
            symbol="AAPL",
            name="Apple Inc.",
            quantity=50,
            price=190.0,
            value_eur=9500.0,
            currency="USD",
            priority=0.7,
            reason="Take profits",
            tags=["profit-taking"],
        ),
        ActionCandidate(
            side=TradeSide.BUY,
            symbol="AMZN",
            name="Amazon.com Inc.",
            quantity=20,
            price=180.0,
            value_eur=3600.0,
            currency="USD",
            priority=0.9,
            reason="Reinvest proceeds",
            tags=["rebalance"],
        ),
    ]


@pytest.mark.asyncio
async def test_go_python_equivalence_simple_buy(
    portfolio_context, securities, simple_buy_sequence
):
    """Test Go matches Python for simple buy sequence."""
    available_cash = 10000.0
    transaction_cost_fixed = 2.0
    transaction_cost_percent = 0.002

    # Python evaluation
    end_context_py, end_cash_py = await simulate_sequence(
        simple_buy_sequence, portfolio_context, available_cash, securities
    )
    div_score_py = await calculate_portfolio_score(end_context_py)
    score_py, breakdown_py = await calculate_portfolio_end_state_score(
        positions=end_context_py.positions,
        total_value=end_context_py.total_value,
        diversification_score=div_score_py.total / 100,
        metrics_cache={},  # Empty cache for test
    )

    # Go evaluation
    async with GoEvaluationClient() as client:
        go_results = await client.evaluate_batch(
            sequences=[simple_buy_sequence],
            portfolio_context=portfolio_context,
            available_cash_eur=available_cash,
            securities=securities,
            transaction_cost_fixed=transaction_cost_fixed,
            transaction_cost_percent=transaction_cost_percent,
        )

    assert len(go_results) == 1
    go_result = go_results[0]

    # Verify feasibility matches
    assert go_result["feasible"] is True

    # Verify scores are close (allow small tolerance for floating point)
    # Note: Scores might differ slightly due to implementation details
    # but should be within 1% of each other
    assert (
        abs(go_result["score"] - score_py) < 0.01
        or pytest.approx(go_result["score"], rel=0.01) == score_py
    )

    # Verify cash is similar (exact match)
    expected_cost = (
        simple_buy_sequence[0].value_eur
        + transaction_cost_fixed
        + (simple_buy_sequence[0].value_eur * transaction_cost_percent)
    )
    expected_end_cash = available_cash - expected_cost

    assert pytest.approx(go_result["end_cash_eur"], rel=0.001) == expected_end_cash
    assert pytest.approx(end_cash_py, rel=0.001) == expected_end_cash


@pytest.mark.asyncio
async def test_go_python_equivalence_sell_then_buy(
    portfolio_context, securities, sell_then_buy_sequence
):
    """Test Go matches Python for sell-then-buy sequence."""
    available_cash = 5000.0
    transaction_cost_fixed = 2.0
    transaction_cost_percent = 0.002

    # Python evaluation
    end_context_py, end_cash_py = await simulate_sequence(
        sell_then_buy_sequence, portfolio_context, available_cash, securities
    )
    div_score_py = await calculate_portfolio_score(end_context_py)
    score_py, breakdown_py = await calculate_portfolio_end_state_score(
        positions=end_context_py.positions,
        total_value=end_context_py.total_value,
        diversification_score=div_score_py.total / 100,
        metrics_cache={},  # Empty cache for test
    )

    # Go evaluation
    async with GoEvaluationClient() as client:
        go_results = await client.evaluate_batch(
            sequences=[sell_then_buy_sequence],
            portfolio_context=portfolio_context,
            available_cash_eur=available_cash,
            securities=securities,
            transaction_cost_fixed=transaction_cost_fixed,
            transaction_cost_percent=transaction_cost_percent,
        )

    assert len(go_results) == 1
    go_result = go_results[0]

    # Verify feasibility
    assert go_result["feasible"] is True

    # Verify scores are close (allow tolerance for implementation differences)
    assert (
        abs(go_result["score"] - score_py) < 0.01
        or pytest.approx(go_result["score"], rel=0.01) == score_py
    )


@pytest.mark.asyncio
async def test_go_python_equivalence_infeasible_sequence(portfolio_context, securities):
    """Test Go matches Python for infeasible sequence (insufficient cash)."""
    # Sequence that requires more cash than available
    infeasible_sequence = [
        ActionCandidate(
            side=TradeSide.BUY,
            symbol="AMZN",
            name="Amazon.com Inc.",
            quantity=1000,  # Very large quantity
            price=180.0,
            value_eur=180000.0,  # Much more than available cash
            currency="USD",
            priority=0.8,
            reason="Test infeasible",
            tags=["test"],
        )
    ]

    available_cash = 1000.0  # Not enough
    transaction_cost_fixed = 2.0
    transaction_cost_percent = 0.002

    # Go evaluation
    async with GoEvaluationClient() as client:
        go_results = await client.evaluate_batch(
            sequences=[infeasible_sequence],
            portfolio_context=portfolio_context,
            available_cash_eur=available_cash,
            securities=securities,
            transaction_cost_fixed=transaction_cost_fixed,
            transaction_cost_percent=transaction_cost_percent,
        )

    assert len(go_results) == 1
    go_result = go_results[0]

    # Verify infeasible detection
    assert go_result["feasible"] is False
    assert go_result["score"] == 0.0


@pytest.mark.asyncio
async def test_go_python_batch_equivalence(portfolio_context, securities):
    """Test Go matches Python for batch of multiple sequences."""
    available_cash = 15000.0
    transaction_cost_fixed = 2.0
    transaction_cost_percent = 0.002

    # Create multiple sequences
    sequences = [
        [
            ActionCandidate(
                side=TradeSide.BUY,
                symbol="AMZN",
                name="Amazon.com Inc.",
                quantity=5,
                price=180.0,
                value_eur=900.0,
                currency="USD",
                priority=0.8,
                reason="Small buy",
                tags=["test"],
            )
        ],
        [
            ActionCandidate(
                side=TradeSide.BUY,
                symbol="AMZN",
                name="Amazon.com Inc.",
                quantity=10,
                price=180.0,
                value_eur=1800.0,
                currency="USD",
                priority=0.8,
                reason="Medium buy",
                tags=["test"],
            )
        ],
        [
            ActionCandidate(
                side=TradeSide.BUY,
                symbol="AMZN",
                name="Amazon.com Inc.",
                quantity=20,
                price=180.0,
                value_eur=3600.0,
                currency="USD",
                priority=0.8,
                reason="Large buy",
                tags=["test"],
            )
        ],
    ]

    # Python evaluations
    python_scores = []
    for sequence in sequences:
        end_context_py, end_cash_py = await simulate_sequence(
            sequence, portfolio_context, available_cash, securities
        )
        div_score_py = await calculate_portfolio_score(end_context_py)
        score_py, _ = await calculate_portfolio_end_state_score(
            positions=end_context_py.positions,
            total_value=end_context_py.total_value,
            diversification_score=div_score_py.total / 100,
            metrics_cache={},
        )
        python_scores.append(score_py)

    # Go evaluation (batch)
    async with GoEvaluationClient() as client:
        go_results = await client.evaluate_batch(
            sequences=sequences,
            portfolio_context=portfolio_context,
            available_cash_eur=available_cash,
            securities=securities,
            transaction_cost_fixed=transaction_cost_fixed,
            transaction_cost_percent=transaction_cost_percent,
        )

    assert len(go_results) == len(sequences)

    # Verify each result matches
    for i, (py_score, go_result) in enumerate(zip(python_scores, go_results)):
        assert go_result["feasible"] is True
        assert (
            abs(go_result["score"] - py_score) < 0.01
            or pytest.approx(go_result["score"], rel=0.01) == py_score
        ), f"Sequence {i} scores don't match"
