"""Performance benchmarks for Go evaluation service vs Python.

These benchmarks measure the performance difference between Go and Python
evaluation to verify we're achieving the expected 10-100x speedup.
"""

import time

import pytest

from app.domain.models import Security
from app.domain.value_objects.product_type import ProductType
from app.domain.value_objects.trade_side import TradeSide
from app.modules.planning.domain.calculations.simulation import simulate_sequence
from app.modules.planning.domain.models import ActionCandidate
from app.modules.planning.infrastructure.go_evaluation_client import (
    GoEvaluationClient,
    GoEvaluationError,
)
from app.modules.scoring.domain.diversification import calculate_portfolio_score
from app.modules.scoring.domain.end_state import calculate_portfolio_end_state_score
from app.modules.scoring.domain.models import PortfolioContext


@pytest.fixture
def portfolio_context():
    """Create a realistic portfolio context."""
    return PortfolioContext(
        positions={
            "AAPL": 10000.0,
            "GOOGL": 8000.0,
            "MSFT": 12000.0,
            "AMZN": 9000.0,
            "NVDA": 7000.0,
        },
        total_value=100000.0,
        position_count=5,
        security_countries={"United States": 5},
        security_industries={"Technology": 5},
        security_sectors={"Technology": 5},
    )


@pytest.fixture
def securities():
    """Create sample securities."""
    symbols = [
        ("AAPL", "Apple Inc."),
        ("GOOGL", "Alphabet Inc."),
        ("MSFT", "Microsoft Corporation"),
        ("AMZN", "Amazon.com Inc."),
        ("NVDA", "NVIDIA Corporation"),
        ("TSLA", "Tesla Inc."),
        ("META", "Meta Platforms Inc."),
        ("NFLX", "Netflix Inc."),
        ("AMD", "Advanced Micro Devices Inc."),
        ("INTC", "Intel Corporation"),
    ]

    return [
        Security(
            symbol=symbol,
            name=name,
            product_type=ProductType.EQUITY,
            country="United States",
            industry="Technology",
            sector="Technology",
            allow_buy=True,
            allow_sell=True,
            is_active=True,
        )
        for symbol, name in symbols
    ]


def generate_test_sequences(num_sequences: int, complexity: int = 3):
    """Generate test sequences for benchmarking.

    Args:
        num_sequences: Number of sequences to generate
        complexity: Number of actions per sequence (1-5)

    Returns:
        List of action sequences
    """
    symbols = ["AMZN", "NVDA", "TSLA", "META", "NFLX"]
    sequences = []

    for i in range(num_sequences):
        sequence = []
        for j in range(complexity):
            symbol = symbols[j % len(symbols)]
            sequence.append(
                ActionCandidate(
                    side=TradeSide.BUY,
                    symbol=symbol,
                    name=f"{symbol} Inc.",
                    quantity=10 + (i % 5),
                    price=150.0 + (i % 50),
                    value_eur=1500.0 + (i % 500),
                    currency="USD",
                    priority=0.7 + (i % 3) * 0.1,
                    reason=f"Test sequence {i}",
                    tags=["benchmark"],
                )
            )
        sequences.append(sequence)

    return sequences


@pytest.mark.asyncio
async def test_benchmark_python_evaluation_10_sequences(portfolio_context, securities):
    """Benchmark Python evaluation for 10 sequences."""
    sequences = generate_test_sequences(num_sequences=10, complexity=3)
    available_cash = 50000.0

    start_time = time.time()

    for sequence in sequences:
        end_context, end_cash = await simulate_sequence(
            sequence, portfolio_context, available_cash, securities
        )
        div_score = await calculate_portfolio_score(end_context)
        await calculate_portfolio_end_state_score(
            positions=end_context.positions,
            total_value=end_context.total_value,
            diversification_score=div_score.total / 100,
            metrics_cache={},
        )

    elapsed = time.time() - start_time

    print(
        f"\nPython evaluation (10 sequences): {elapsed:.3f}s ({elapsed/10:.3f}s per sequence)"
    )
    assert elapsed < 60.0, "Python evaluation took too long"


@pytest.mark.asyncio
async def test_benchmark_go_evaluation_10_sequences(portfolio_context, securities):
    """Benchmark Go evaluation for 10 sequences."""
    sequences = generate_test_sequences(num_sequences=10, complexity=3)
    available_cash = 50000.0

    try:
        async with GoEvaluationClient() as client:
            start_time = time.time()

            await client.evaluate_batch(
                sequences=sequences,
                portfolio_context=portfolio_context,
                available_cash_eur=available_cash,
                securities=securities,
                transaction_cost_fixed=2.0,
                transaction_cost_percent=0.002,
            )

            elapsed = time.time() - start_time

            print(
                f"\nGo evaluation (10 sequences): {elapsed:.3f}s ({elapsed/10:.3f}s per sequence)"
            )
            print("Expected speedup: 10-100x")

            # Go should be significantly faster
            assert elapsed < 10.0, "Go evaluation should be faster"

    except GoEvaluationError:
        pytest.skip("Go service not available")


@pytest.mark.asyncio
async def test_benchmark_python_evaluation_100_sequences(portfolio_context, securities):
    """Benchmark Python evaluation for 100 sequences (slow test)."""
    sequences = generate_test_sequences(num_sequences=100, complexity=3)
    available_cash = 50000.0

    start_time = time.time()

    for sequence in sequences:
        end_context, end_cash = await simulate_sequence(
            sequence, portfolio_context, available_cash, securities
        )
        div_score = await calculate_portfolio_score(end_context)
        await calculate_portfolio_end_state_score(
            positions=end_context.positions,
            total_value=end_context.total_value,
            diversification_score=div_score.total / 100,
            metrics_cache={},
        )

    elapsed = time.time() - start_time

    print(
        f"\nPython evaluation (100 sequences): {elapsed:.3f}s ({elapsed/100:.3f}s per sequence)"
    )
    assert elapsed < 600.0, "Python evaluation took too long"


@pytest.mark.asyncio
async def test_benchmark_go_evaluation_100_sequences(portfolio_context, securities):
    """Benchmark Go evaluation for 100 sequences (should be fast)."""
    sequences = generate_test_sequences(num_sequences=100, complexity=3)
    available_cash = 50000.0

    try:
        async with GoEvaluationClient() as client:
            start_time = time.time()

            await client.evaluate_batch(
                sequences=sequences,
                portfolio_context=portfolio_context,
                available_cash_eur=available_cash,
                securities=securities,
                transaction_cost_fixed=2.0,
                transaction_cost_percent=0.002,
            )

            elapsed = time.time() - start_time

            print(
                f"\nGo evaluation (100 sequences): {elapsed:.3f}s ({elapsed/100:.3f}s per sequence)"
            )
            print("Expected speedup: 10-100x vs Python")

            # Go should handle 100 sequences quickly
            assert elapsed < 20.0, "Go evaluation should be very fast for 100 sequences"

    except GoEvaluationError:
        pytest.skip("Go service not available")


@pytest.mark.asyncio
@pytest.mark.slow
async def test_benchmark_comparison_speedup(portfolio_context, securities):
    """Compare Go vs Python performance and measure speedup."""
    sequences = generate_test_sequences(num_sequences=50, complexity=3)
    available_cash = 50000.0

    # Python benchmark
    python_start = time.time()
    for sequence in sequences:
        end_context, end_cash = await simulate_sequence(
            sequence, portfolio_context, available_cash, securities
        )
        div_score = await calculate_portfolio_score(end_context)
        await calculate_portfolio_end_state_score(
            positions=end_context.positions,
            total_value=end_context.total_value,
            diversification_score=div_score.total / 100,
            metrics_cache={},
        )
    python_elapsed = time.time() - python_start

    # Go benchmark
    try:
        async with GoEvaluationClient() as client:
            go_start = time.time()
            await client.evaluate_batch(
                sequences=sequences,
                portfolio_context=portfolio_context,
                available_cash_eur=available_cash,
                securities=securities,
                transaction_cost_fixed=2.0,
                transaction_cost_percent=0.002,
            )
            go_elapsed = time.time() - go_start

        speedup = python_elapsed / go_elapsed

        print("\n=== Performance Comparison (50 sequences) ===")
        print(f"Python: {python_elapsed:.3f}s ({python_elapsed/50:.3f}s per sequence)")
        print(f"Go:     {go_elapsed:.3f}s ({go_elapsed/50:.3f}s per sequence)")
        print(f"Speedup: {speedup:.1f}x")
        print("Target:  10-100x")

        # Go should be at least 5x faster (conservative target)
        assert speedup >= 5.0, f"Go speedup ({speedup:.1f}x) should be at least 5x"

    except GoEvaluationError:
        pytest.skip("Go service not available")
