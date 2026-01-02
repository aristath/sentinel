"""Integration tests for Go evaluation client.

These tests verify the Python → Go → Python roundtrip works correctly.
They require the Go service to be running on localhost:9000.
"""

import pytest

from app.domain.models import Security
from app.domain.value_objects.product_type import ProductType
from app.domain.value_objects.trade_side import TradeSide
from app.modules.planning.domain.models import ActionCandidate
from app.modules.planning.infrastructure.go_evaluation_client import (
    GoEvaluationClient,
    GoEvaluationError,
)
from app.modules.scoring.domain.models import PortfolioContext
from app.shared.domain.value_objects.currency import Currency


@pytest.fixture
def sample_portfolio_context():
    """Create sample portfolio context for testing."""
    return PortfolioContext(
        country_weights={"NORTH_AMERICA": 0.6, "EUROPE": 0.4},
        industry_weights={"TECHNOLOGY": 0.5, "FINANCE": 0.3, "HEALTHCARE": 0.2},
        positions={"AAPL": 5000.0, "MSFT": 3000.0},
        total_value=10000.0,
        security_countries={"AAPL": "United States", "MSFT": "United States"},
        security_industries={"AAPL": "Technology", "MSFT": "Technology"},
        security_scores={"AAPL": 0.85, "MSFT": 0.82},
        security_dividends={"AAPL": 0.005, "MSFT": 0.008},
        country_to_group={"United States": "NORTH_AMERICA", "Germany": "EUROPE"},
        industry_to_group={"Technology": "TECHNOLOGY"},
    )


@pytest.fixture
def sample_securities():
    """Create sample securities for testing."""
    return [
        Security(
            symbol="AAPL",
            name="Apple Inc.",
            product_type=ProductType.EQUITY,
            country="United States",
            industry="Technology",
            currency=Currency.USD,
        ),
        Security(
            symbol="MSFT",
            name="Microsoft Corporation",
            product_type=ProductType.EQUITY,
            country="United States",
            industry="Technology",
            currency=Currency.USD,
        ),
        Security(
            symbol="GOOGL",
            name="Alphabet Inc.",
            product_type=ProductType.EQUITY,
            country="United States",
            industry="Technology",
            currency=Currency.USD,
        ),
    ]


@pytest.fixture
def sample_sequences():
    """Create sample action sequences for testing."""
    return [
        # Sequence 1: Buy GOOGL
        [
            ActionCandidate(
                side=TradeSide.BUY,
                symbol="GOOGL",
                name="Alphabet Inc.",
                quantity=10,
                price=150.0,
                value_eur=1500.0,
                currency="USD",
                priority=0.8,
                reason="Underweight technology",
                tags=["rebalance", "optimizer_target"],
            )
        ],
        # Sequence 2: Sell AAPL, then buy GOOGL
        [
            ActionCandidate(
                side=TradeSide.SELL,
                symbol="AAPL",
                name="Apple Inc.",
                quantity=5,
                price=180.0,
                value_eur=900.0,
                currency="USD",
                priority=0.5,
                reason="Overweight position",
                tags=["rebalance"],
            ),
            ActionCandidate(
                side=TradeSide.BUY,
                symbol="GOOGL",
                name="Alphabet Inc.",
                quantity=10,
                price=150.0,
                value_eur=1500.0,
                currency="USD",
                priority=0.8,
                reason="Underweight technology",
                tags=["rebalance"],
            ),
        ],
    ]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_health_check():
    """Test Go service health check endpoint."""
    async with GoEvaluationClient() as client:
        health = await client.health_check()

        assert health["status"] == "healthy"
        assert "version" in health


@pytest.mark.asyncio
@pytest.mark.integration
async def test_evaluate_batch_basic(
    sample_sequences, sample_portfolio_context, sample_securities
):
    """Test basic batch evaluation with Go service."""
    async with GoEvaluationClient() as client:
        results = await client.evaluate_batch(
            sequences=sample_sequences,
            portfolio_context=sample_portfolio_context,
            available_cash_eur=2000.0,
            securities=sample_securities,
            transaction_cost_fixed=2.0,
            transaction_cost_percent=0.002,
        )

        # Should return results for all sequences
        assert len(results) == len(sample_sequences)

        # Check first result structure
        result = results[0]
        assert "sequence" in result
        assert "score" in result
        assert "end_cash_eur" in result
        assert "end_portfolio" in result
        assert "transaction_costs" in result
        assert "feasible" in result

        # First sequence should be feasible (has enough cash)
        assert result["feasible"] is True
        assert result["score"] > 0.0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_evaluate_batch_infeasible_sequence(
    sample_portfolio_context, sample_securities
):
    """Test evaluation of infeasible sequence (insufficient cash)."""
    # Create sequence that requires more cash than available
    sequences = [
        [
            ActionCandidate(
                side=TradeSide.BUY,
                symbol="GOOGL",
                name="Alphabet Inc.",
                quantity=100,
                price=150.0,
                value_eur=15000.0,  # More than available cash
                currency="USD",
                priority=0.8,
                reason="Test",
                tags=["test"],
            )
        ]
    ]

    async with GoEvaluationClient() as client:
        results = await client.evaluate_batch(
            sequences=sequences,
            portfolio_context=sample_portfolio_context,
            available_cash_eur=1000.0,  # Not enough
            securities=sample_securities,
        )

        assert len(results) == 1
        result = results[0]

        # Should mark as infeasible
        assert result["feasible"] is False
        assert result["score"] == 0.0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_evaluate_batch_empty_sequences(
    sample_portfolio_context, sample_securities
):
    """Test evaluation with empty sequence list."""
    async with GoEvaluationClient() as client:
        results = await client.evaluate_batch(
            sequences=[],
            portfolio_context=sample_portfolio_context,
            available_cash_eur=2000.0,
            securities=sample_securities,
        )

        assert results == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_evaluate_batch_price_adjustments(
    sample_sequences, sample_portfolio_context, sample_securities
):
    """Test evaluation with price adjustments (stochastic scenario)."""
    price_adjustments = {
        "GOOGL": 1.05,  # +5% price increase
        "AAPL": 0.95,  # -5% price decrease
    }

    async with GoEvaluationClient() as client:
        results = await client.evaluate_batch(
            sequences=sample_sequences,
            portfolio_context=sample_portfolio_context,
            available_cash_eur=2000.0,
            securities=sample_securities,
            price_adjustments=price_adjustments,
        )

        assert len(results) == len(sample_sequences)
        # Results should reflect price adjustments in end_cash calculation


@pytest.mark.asyncio
@pytest.mark.integration
async def test_connection_error():
    """Test error handling when Go service is not running."""
    # Use non-existent port
    client = GoEvaluationClient(base_url="http://localhost:9999")

    with pytest.raises(GoEvaluationError, match="Cannot connect to Go service"):
        async with client:
            await client.health_check()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_timeout_error(sample_portfolio_context, sample_securities):
    """Test timeout handling."""
    # Set very short timeout
    async with GoEvaluationClient(timeout=0.001) as client:
        sequences = [[]]  # Empty sequence

        with pytest.raises(GoEvaluationError, match="timed out"):
            await client.evaluate_batch(
                sequences=sequences,
                portfolio_context=sample_portfolio_context,
                available_cash_eur=1000.0,
                securities=sample_securities,
            )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_client_without_context_manager():
    """Test that client raises error when used without context manager."""
    client = GoEvaluationClient()

    with pytest.raises(GoEvaluationError, match="not initialized"):
        await client.health_check()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_serialization_roundtrip(
    sample_sequences, sample_portfolio_context, sample_securities
):
    """Test that serialization/deserialization preserves data correctly."""
    async with GoEvaluationClient() as client:
        results = await client.evaluate_batch(
            sequences=sample_sequences,
            portfolio_context=sample_portfolio_context,
            available_cash_eur=2000.0,
            securities=sample_securities,
        )

        # Check that returned sequences match input
        for i, result in enumerate(results):
            returned_sequence = result["sequence"]
            original_sequence = sample_sequences[i]

            assert len(returned_sequence) == len(original_sequence)

            for j, action in enumerate(returned_sequence):
                original = original_sequence[j]
                assert action["symbol"] == original.symbol
                assert action["side"] == original.side
                assert action["quantity"] == original.quantity
                # Prices may differ due to float serialization, allow small tolerance
                assert abs(action["price"] - original.price) < 0.01


@pytest.mark.asyncio
@pytest.mark.integration
async def test_multiple_evaluations_same_client(
    sample_sequences, sample_portfolio_context, sample_securities
):
    """Test that same client can be reused for multiple evaluations."""
    async with GoEvaluationClient() as client:
        # First evaluation
        results1 = await client.evaluate_batch(
            sequences=sample_sequences,
            portfolio_context=sample_portfolio_context,
            available_cash_eur=2000.0,
            securities=sample_securities,
        )

        # Second evaluation with different cash
        results2 = await client.evaluate_batch(
            sequences=sample_sequences,
            portfolio_context=sample_portfolio_context,
            available_cash_eur=5000.0,
            securities=sample_securities,
        )

        assert len(results1) == len(sample_sequences)
        assert len(results2) == len(sample_sequences)

        # Results should differ due to different available cash
        # (more cash = potentially better scores)
