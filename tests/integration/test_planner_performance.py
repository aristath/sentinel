"""Integration tests for holistic planner performance.

These tests measure the performance improvements from batching DB queries
and parallel evaluation, using a real test database.
"""

import time
from datetime import datetime

import pytest

from app.domain.models import Position, Security
from app.modules.planning.domain.holistic_planner import create_holistic_plan
from app.modules.scoring.domain.models import PortfolioContext
from app.repositories import SettingsRepository


async def setup_test_stocks(db_manager):
    """Set up test stocks in the database."""
    config_db = db_manager.config

    stocks = [
        ("AAPL.US", "AAPL", "Apple Inc", "Technology", "United States"),
        ("MSFT.US", "MSFT", "Microsoft Corp", "Technology", "United States"),
        ("SAP.DE", "SAP.DE", "SAP SE", "Technology", "Germany"),
    ]

    for symbol, yahoo, name, industry, country in stocks:
        await config_db.execute(
            """
            INSERT INTO stocks (symbol, yahoo_symbol, name, industry, country,
                              priority_multiplier, min_lot, active, allow_buy, allow_sell,
                              created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol,
                yahoo,
                name,
                industry,
                country,
                1.0,
                1,
                1,
                1,
                1,
                datetime.now().isoformat(),
                datetime.now().isoformat(),
            ),
        )

    # Create allocation targets (use INSERT OR REPLACE since schema may have defaults)
    await config_db.execute(
        """
        INSERT OR REPLACE INTO allocation_targets (type, name, target_pct, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "country",
            "United States",
            0.6,
            datetime.now().isoformat(),
            datetime.now().isoformat(),
        ),
    )
    await config_db.execute(
        """
        INSERT OR REPLACE INTO allocation_targets (type, name, target_pct, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "country",
            "Germany",
            0.4,
            datetime.now().isoformat(),
            datetime.now().isoformat(),
        ),
    )

    await config_db.commit()

    # Add default settings
    settings_repo = SettingsRepository()
    await settings_repo.set("min_cash_reserve", 500.0)
    await settings_repo.set("transaction_cost_fixed", 2.0)
    await settings_repo.set("transaction_cost_percent", 0.002)


async def setup_test_metrics(db_manager, symbols: list):
    """Set up test metrics/calculations for stocks."""
    calc_db = db_manager.calculations

    for symbol in symbols:
        # Insert test metrics
        metrics = [
            ("CAGR_5Y", 0.12),
            ("DIVIDEND_YIELD", 0.015),
            ("CONSISTENCY_SCORE", 0.8),
            ("FINANCIAL_STRENGTH", 0.7),
            ("DIVIDEND_CONSISTENCY", 0.6),
            ("PAYOUT_RATIO", 0.5),
            ("SORTINO", 1.5),
            ("VOLATILITY_ANNUAL", 0.20),
            ("MAX_DRAWDOWN", -0.15),
            ("SHARPE", 1.5),
        ]

        for metric_name, value in metrics:
            await calc_db.execute(
                """
                INSERT OR REPLACE INTO calculated_metrics (symbol, metric, value, calculated_at)
                VALUES (?, ?, ?, ?)
                """,
                (symbol, metric_name, value, datetime.now().isoformat()),
            )

    await calc_db.commit()


@pytest.mark.asyncio
async def test_planner_completes_in_reasonable_time(db_manager):
    """Test that holistic planner completes within acceptable time bounds."""
    await setup_test_stocks(db_manager)
    symbols = ["AAPL.US", "MSFT.US", "SAP.DE"]
    await setup_test_metrics(db_manager, symbols)

    portfolio_context = PortfolioContext(
        country_weights={"United States": 0.6, "Germany": 0.4},
        industry_weights={"Technology": 1.0},
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

    start_time = time.time()
    plan = await create_holistic_plan(
        portfolio_context=portfolio_context,
        available_cash=1000.0,
        stocks=stocks,
        positions=positions,
        max_plan_depth=2,  # Keep small for test speed
    )
    elapsed_time = time.time() - start_time

    # Should complete in reasonable time
    assert elapsed_time < 10.0, f"Planning took {elapsed_time:.2f}s, expected < 10s"
    assert plan is not None


@pytest.mark.asyncio
async def test_planner_handles_empty_portfolio(db_manager):
    """Test that planner handles empty portfolio gracefully."""
    await setup_test_stocks(db_manager)
    symbols = ["AAPL.US", "MSFT.US", "SAP.DE"]
    await setup_test_metrics(db_manager, symbols)

    portfolio_context = PortfolioContext(
        country_weights={},
        industry_weights={},
        positions={},
        total_value=0,
        security_countries={},
        security_industries={},
        security_scores={},
        security_dividends={},
    )

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
    ]

    plan = await create_holistic_plan(
        portfolio_context=portfolio_context,
        available_cash=1000.0,
        stocks=stocks,
        positions=[],
        max_plan_depth=2,
    )

    assert plan is not None
    assert plan.feasible
