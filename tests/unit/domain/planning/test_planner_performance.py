"""Performance benchmarks for holistic planner.

These tests measure the performance improvements from batching DB queries
and parallel evaluation.

NOTE: These tests are skipped because create_holistic_plan() has deep internal
dependencies that create their own repository instances (SettingsRepository,
DividendRepository, TradeRepository). These require database access and cannot
be easily mocked at the unit test level.
"""

import time
from unittest.mock import AsyncMock, patch

import pytest

from app.domain.models import Position, Security
from app.modules.planning.domain.holistic_planner import create_holistic_plan
from app.modules.scoring.domain.models import PortfolioContext


@pytest.mark.skip(
    reason="Test requires database due to deep internal dependencies in create_holistic_plan()"
)
@pytest.mark.asyncio
async def test_metrics_prefetching_reduces_db_queries():
    """Test that metrics pre-fetching reduces DB query count."""
    from app.repositories.calculations import CalculationsRepository

    # Create mock portfolio
    portfolio_context = PortfolioContext(
        country_weights={"United States": 0.6, "Germany": 0.4},
        industry_weights={"Technology": 0.5, "Finance": 0.5},
        positions={"AAPL.US": 5000, "MSFT.US": 3000, "SAP.DE": 2000},
        total_value=10000,
        security_countries={
            "AAPL.US": "United States",
            "MSFT.US": "United States",
            "SAP.DE": "Germany",
        },
        security_industries={
            "AAPL.US": "Technology",
            "MSFT.US": "Technology",
            "SAP.DE": "Technology",
        },
        security_scores={"AAPL.US": 0.8, "MSFT.US": 0.7, "SAP.DE": 0.6},
        security_dividends={"AAPL.US": 0.015, "MSFT.US": 0.01, "SAP.DE": 0.02},
    )

    positions = [
        Position(
            symbol="AAPL.US",
            quantity=100,
            avg_price=50.0,
            current_price=50.0,
            market_value_eur=5000,
            currency="EUR",
        ),
        Position(
            symbol="MSFT.US",
            quantity=50,
            avg_price=60.0,
            current_price=60.0,
            market_value_eur=3000,
            currency="EUR",
        ),
        Position(
            symbol="SAP.DE",
            quantity=30,
            avg_price=66.67,
            current_price=66.67,
            market_value_eur=2000,
            currency="EUR",
        ),
    ]

    stocks = [
        Security(
            symbol="AAPL.US",
            name="Apple Inc",
            country="United States",
            industry="Technology",
            allow_buy=True,
            allow_sell=True,
            min_lot=1,
        ),
        Security(
            symbol="MSFT.US",
            name="Microsoft Corp",
            country="United States",
            industry="Technology",
            allow_buy=True,
            allow_sell=True,
            min_lot=1,
        ),
        Security(
            symbol="SAP.DE",
            name="SAP SE",
            country="Germany",
            industry="Technology",
            allow_buy=True,
            allow_sell=True,
            min_lot=1,
        ),
    ]

    # Mock CalculationsRepository to count get_metrics calls
    mock_calc_repo = AsyncMock(spec=CalculationsRepository)
    get_metrics_call_count = 0

    async def mock_get_metrics(symbol: str, metrics: list):
        nonlocal get_metrics_call_count
        get_metrics_call_count += 1
        # Return mock metrics
        return {
            "CAGR_5Y": 0.12,
            "DIVIDEND_YIELD": 0.015,
            "CONSISTENCY_SCORE": 0.8,
            "FINANCIAL_STRENGTH": 0.7,
            "DIVIDEND_CONSISTENCY": 0.6,
            "PAYOUT_RATIO": 0.5,
            "SORTINO": 1.5,
            "VOLATILITY_ANNUAL": 0.20,
            "MAX_DRAWDOWN": -0.15,
            "SHARPE": 1.5,
        }

    mock_calc_repo.get_metrics = mock_get_metrics

    with patch(
        "app.repositories.calculations.CalculationsRepository",
        return_value=mock_calc_repo,
    ):
        # Create a plan (this will generate sequences and evaluate them)
        await create_holistic_plan(
            portfolio_context=portfolio_context,
            available_cash=1000.0,
            stocks=stocks,
            positions=positions,
            max_plan_depth=3,  # Smaller depth for faster test
        )

    # With metrics pre-fetching, we should only call get_metrics once per unique symbol
    # (not once per sequence per position)
    # For 3 symbols, we should have at most 3 calls (one per symbol)
    assert get_metrics_call_count <= 3, (
        f"Expected at most 3 get_metrics calls (one per symbol), "
        f"got {get_metrics_call_count}. This indicates metrics are not being pre-fetched."
    )


@pytest.mark.skip(
    reason="Test requires database due to deep internal dependencies in create_holistic_plan()"
)
@pytest.mark.asyncio
async def test_parallel_evaluation_improves_performance():
    """Test that parallel evaluation is faster than sequential."""
    # This is a basic smoke test - full performance testing would require
    # more complex setup and timing measurements
    portfolio_context = PortfolioContext(
        country_weights={"United States": 0.6},
        industry_weights={"Technology": 1.0},
        positions={"AAPL.US": 10000},
        total_value=10000,
        security_countries={"AAPL.US": "United States"},
        security_industries={"AAPL.US": "Technology"},
        security_scores={"AAPL.US": 0.8},
        security_dividends={"AAPL.US": 0.015},
    )

    positions = [
        Position(
            symbol="AAPL.US",
            quantity=100,
            avg_price=100.0,
            current_price=100.0,
            market_value_eur=10000,
            currency="EUR",
        )
    ]

    stocks = [
        Security(
            symbol="AAPL.US",
            name="Apple Inc",
            country="United States",
            industry="Technology",
            allow_buy=True,
            allow_sell=True,
            min_lot=1,
        )
    ]

    # Mock CalculationsRepository
    mock_calc_repo = AsyncMock()

    async def mock_get_metrics(symbol: str, metrics: list):
        return {
            "CAGR_5Y": 0.12,
            "DIVIDEND_YIELD": 0.015,
            "CONSISTENCY_SCORE": 0.8,
            "FINANCIAL_STRENGTH": 0.7,
            "DIVIDEND_CONSISTENCY": 0.6,
            "PAYOUT_RATIO": 0.5,
            "SORTINO": 1.5,
            "VOLATILITY_ANNUAL": 0.20,
            "MAX_DRAWDOWN": -0.15,
            "SHARPE": 1.5,
        }

    mock_calc_repo.get_metrics = mock_get_metrics

    with patch(
        "app.repositories.calculations.CalculationsRepository",
        return_value=mock_calc_repo,
    ):
        start_time = time.time()
        plan = await create_holistic_plan(
            portfolio_context=portfolio_context,
            available_cash=1000.0,
            stocks=stocks,
            positions=positions,
            max_plan_depth=2,  # Small depth for faster test
        )
        elapsed_time = time.time() - start_time

    # Basic sanity check: should complete in reasonable time
    # With optimizations, this should be much faster than before
    assert elapsed_time < 5.0, f"Planning took {elapsed_time:.2f}s, expected < 5s"
    assert plan is not None
