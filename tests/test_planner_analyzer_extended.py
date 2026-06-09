"""Tests for analyzer.py — non-as-of paths and missing functions."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel.planner.analyzer import PortfolioAnalyzer


class TestGetCurrentAllocations:
    """Tests for get_current_allocations (non-as-of path)."""

    @pytest.mark.asyncio
    async def test_basic_allocations(self):
        db = MagicMock()
        db.cache_get = AsyncMock(return_value=None)
        db.cache_set = AsyncMock()

        positions = [
            {"symbol": "A", "quantity": 10, "current_price": 100.0, "currency": "EUR"},
            {"symbol": "B", "quantity": 20, "current_price": 50.0, "currency": "EUR"},
        ]

        portfolio = MagicMock()
        portfolio.positions = AsyncMock(return_value=positions)
        portfolio.total_value = AsyncMock(return_value=2000.0)

        currency = MagicMock()
        currency.get_rate = AsyncMock(return_value=1.0)

        analyzer = PortfolioAnalyzer(db=db, portfolio=portfolio, currency=currency)
        allocations = await analyzer.get_current_allocations()

        # A = 1000 EUR, B = 1000 EUR, total = 2000 EUR
        assert allocations["A"] == pytest.approx(0.5)
        assert allocations["B"] == pytest.approx(0.5)
        assert abs(sum(allocations.values()) - 1.0) < 1e-9

    @pytest.mark.asyncio
    async def test_zero_quantity_skipped(self):
        positions = [
            {"symbol": "A", "quantity": 0, "current_price": 100.0, "currency": "EUR"},
            {"symbol": "B", "quantity": 10, "current_price": 100.0, "currency": "EUR"},
        ]

        portfolio = MagicMock()
        portfolio.positions = AsyncMock(return_value=positions)
        portfolio.total_value = AsyncMock(return_value=1000.0)

        currency = MagicMock()
        currency.get_rate = AsyncMock(return_value=1.0)

        analyzer = PortfolioAnalyzer(db=MagicMock(), portfolio=portfolio, currency=currency)
        allocations = await analyzer.get_current_allocations()

        assert "A" not in allocations
        assert allocations["B"] == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_zero_price_skipped(self):
        positions = [
            {"symbol": "A", "quantity": 10, "current_price": 0.0, "currency": "EUR"},
            {"symbol": "B", "quantity": 10, "current_price": 100.0, "currency": "EUR"},
        ]

        portfolio = MagicMock()
        portfolio.positions = AsyncMock(return_value=positions)
        portfolio.total_value = AsyncMock(return_value=1000.0)

        currency = MagicMock()
        currency.get_rate = AsyncMock(return_value=1.0)

        analyzer = PortfolioAnalyzer(db=MagicMock(), portfolio=portfolio, currency=currency)
        allocations = await analyzer.get_current_allocations()

        assert "A" not in allocations

    @pytest.mark.asyncio
    async def test_fx_conversion(self):
        positions = [
            {"symbol": "US.EQ", "quantity": 10, "current_price": 100.0, "currency": "USD"},
            {"symbol": "EU.EQ", "quantity": 10, "current_price": 100.0, "currency": "EUR"},
        ]

        portfolio = MagicMock()
        portfolio.positions = AsyncMock(return_value=positions)
        portfolio.total_value = AsyncMock(return_value=1900.0)

        currency = MagicMock()
        currency.get_rate = AsyncMock(side_effect=lambda curr: 0.9 if curr == "USD" else 1.0)

        analyzer = PortfolioAnalyzer(db=MagicMock(), portfolio=portfolio, currency=currency)
        allocations = await analyzer.get_current_allocations()

        # US.EQ = 1000 USD * 0.9 = 900 EUR
        # EU.EQ = 1000 EUR
        # total = 1900 EUR
        assert allocations["US.EQ"] == pytest.approx(900 / 1900)
        assert allocations["EU.EQ"] == pytest.approx(1000 / 1900)

    @pytest.mark.asyncio
    async def test_cached_result_returned(self):
        db = MagicMock()
        import json

        cached = json.dumps({"A": 0.6, "B": 0.4})
        db.cache_get = AsyncMock(return_value=cached)

        portfolio = MagicMock()
        currency = MagicMock()

        analyzer = PortfolioAnalyzer(db=db, portfolio=portfolio, currency=currency)
        allocations = await analyzer.get_current_allocations()

        assert allocations == {"A": 0.6, "B": 0.4}
        # Should not have called portfolio.positions since cache hit
        portfolio.positions.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_positions(self):
        portfolio = MagicMock()
        portfolio.positions = AsyncMock(return_value=[])
        portfolio.total_value = AsyncMock(return_value=0.0)

        currency = MagicMock()

        analyzer = PortfolioAnalyzer(db=MagicMock(), portfolio=portfolio, currency=currency)
        allocations = await analyzer.get_current_allocations()

        assert allocations == {}


class TestGetTotalValue:
    """Tests for get_total_value (non-as-of path)."""

    @pytest.mark.asyncio
    async def test_basic_total_value(self):
        portfolio = MagicMock()
        portfolio.total_value = AsyncMock(return_value=10000.0)

        analyzer = PortfolioAnalyzer(db=MagicMock(), portfolio=portfolio, currency=MagicMock())
        total = await analyzer.get_total_value()

        assert total == 10000.0


class TestGetRebalanceSummary:
    """Tests for get_rebalance_summary edge cases."""

    @pytest.mark.asyncio
    async def test_aligned_status(self):
        settings = MagicMock()
        settings.get = AsyncMock(return_value=5.0)

        analyzer = PortfolioAnalyzer(
            db=MagicMock(),
            portfolio=MagicMock(),
            currency=MagicMock(),
            settings=settings,
        )
        analyzer.get_current_allocations = AsyncMock(return_value={"A": 0.5, "B": 0.5})

        async def fake_ideal(calc):
            return {"A": 0.5, "B": 0.5}

        from sentinel.planner.allocation import AllocationCalculator

        original = AllocationCalculator.calculate_ideal_portfolio
        AllocationCalculator.calculate_ideal_portfolio = fake_ideal

        summary = await analyzer.get_rebalance_summary()

        AllocationCalculator.calculate_ideal_portfolio = original

        assert summary["status"] == "aligned"
        assert summary["needs_rebalance"] is False

    @pytest.mark.asyncio
    async def test_minor_drift_status(self):
        settings = MagicMock()
        settings.get = AsyncMock(return_value=5.0)

        analyzer = PortfolioAnalyzer(
            db=MagicMock(),
            portfolio=MagicMock(),
            currency=MagicMock(),
            settings=settings,
        )
        analyzer.get_current_allocations = AsyncMock(return_value={"A": 0.6, "B": 0.4})

        async def fake_ideal(calc):
            return {"A": 0.5, "B": 0.5}

        from sentinel.planner.allocation import AllocationCalculator

        original = AllocationCalculator.calculate_ideal_portfolio
        AllocationCalculator.calculate_ideal_portfolio = fake_ideal

        summary = await analyzer.get_rebalance_summary()

        AllocationCalculator.calculate_ideal_portfolio = original

        assert summary["status"] == "minor_drift"
        assert summary["needs_rebalance"] is True

    @pytest.mark.asyncio
    async def test_needs_rebalance_status(self):
        settings = MagicMock()
        settings.get = AsyncMock(return_value=5.0)

        analyzer = PortfolioAnalyzer(
            db=MagicMock(),
            portfolio=MagicMock(),
            currency=MagicMock(),
            settings=settings,
        )
        analyzer.get_current_allocations = AsyncMock(return_value={"A": 0.8, "B": 0.2})

        async def fake_ideal(calc):
            return {"A": 0.5, "B": 0.5}

        from sentinel.planner.allocation import AllocationCalculator

        original = AllocationCalculator.calculate_ideal_portfolio
        AllocationCalculator.calculate_ideal_portfolio = fake_ideal

        summary = await analyzer.get_rebalance_summary()

        AllocationCalculator.calculate_ideal_portfolio = original

        assert summary["status"] == "needs_rebalance"
        assert summary["needs_rebalance"] is True

    @pytest.mark.asyncio
    async def test_empty_current_allocations(self):
        settings = MagicMock()
        settings.get = AsyncMock(return_value=5.0)

        db = MagicMock()
        db.get_all_securities = AsyncMock(return_value=[])

        analyzer = PortfolioAnalyzer(
            db=db,
            portfolio=MagicMock(),
            currency=MagicMock(),
            settings=settings,
        )
        analyzer.get_current_allocations = AsyncMock(return_value={})

        summary = await analyzer.get_rebalance_summary()

        assert summary["status"] == "aligned"
        assert summary["needs_rebalance"] is False
        assert summary["total_securities"] == 0

    @pytest.mark.asyncio
    async def test_total_deviation_calculated(self):
        settings = MagicMock()
        settings.get = AsyncMock(return_value=5.0)

        analyzer = PortfolioAnalyzer(
            db=MagicMock(),
            portfolio=MagicMock(),
            currency=MagicMock(),
            settings=settings,
        )
        analyzer.get_current_allocations = AsyncMock(return_value={"A": 0.6, "B": 0.4})

        async def fake_ideal(calc):
            return {"A": 0.5, "B": 0.5}

        from sentinel.planner.allocation import AllocationCalculator

        original = AllocationCalculator.calculate_ideal_portfolio
        AllocationCalculator.calculate_ideal_portfolio = fake_ideal

        summary = await analyzer.get_rebalance_summary()

        AllocationCalculator.calculate_ideal_portfolio = original

        # |0.6-0.5| + |0.4-0.5| = 0.2
        assert summary["total_deviation"] == pytest.approx(0.2)
        assert summary["max_deviation"] == pytest.approx(0.1)
        assert summary["average_deviation"] == pytest.approx(0.1)


class TestGetPositionDetails:
    """Tests for get_position_details."""

    @pytest.mark.asyncio
    async def test_basic_position_details(self):
        positions = [
            {
                "symbol": "A",
                "quantity": 10,
                "current_price": 100.0,
                "currency": "EUR",
                "avg_cost": 80.0,
                "name": "Asset A",
            },
        ]

        portfolio = MagicMock()
        portfolio.positions = AsyncMock(return_value=positions)

        currency = MagicMock()
        currency.get_rate = AsyncMock(return_value=1.0)

        analyzer = PortfolioAnalyzer(db=MagicMock(), portfolio=portfolio, currency=currency)
        details = await analyzer.get_position_details()

        assert len(details) == 1
        assert details[0]["symbol"] == "A"
        assert details[0]["value_eur"] == 1000.0
        assert details[0]["value_local"] == 1000.0
        assert details[0]["profit_pct"] == pytest.approx(25.0)  # (100-80)/80 * 100

    @pytest.mark.asyncio
    async def test_fx_conversion_in_details(self):
        positions = [
            {
                "symbol": "US.EQ",
                "quantity": 10,
                "current_price": 100.0,
                "currency": "USD",
                "avg_cost": 90.0,
            },
        ]

        portfolio = MagicMock()
        portfolio.positions = AsyncMock(return_value=positions)

        currency = MagicMock()
        currency.get_rate = AsyncMock(return_value=0.9)
        currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt * 0.9 if curr == "USD" else amt)

        analyzer = PortfolioAnalyzer(db=MagicMock(), portfolio=portfolio, currency=currency)
        details = await analyzer.get_position_details()

        assert details[0]["value_eur"] == pytest.approx(900.0)  # 1000 USD * 0.9
        assert details[0]["value_local"] == 1000.0

    @pytest.mark.asyncio
    async def test_loss_position(self):
        positions = [
            {
                "symbol": "LOSS",
                "quantity": 10,
                "current_price": 50.0,
                "currency": "EUR",
                "avg_cost": 100.0,
            },
        ]

        portfolio = MagicMock()
        portfolio.positions = AsyncMock(return_value=positions)

        currency = MagicMock()
        currency.get_rate = AsyncMock(return_value=1.0)

        analyzer = PortfolioAnalyzer(db=MagicMock(), portfolio=portfolio, currency=currency)
        details = await analyzer.get_position_details()

        assert details[0]["profit_pct"] == pytest.approx(-50.0)

    @pytest.mark.asyncio
    async def test_zero_avg_cost(self):
        positions = [
            {
                "symbol": "NEW",
                "quantity": 10,
                "current_price": 100.0,
                "currency": "EUR",
                "avg_cost": 0.0,
            },
        ]

        portfolio = MagicMock()
        portfolio.positions = AsyncMock(return_value=positions)

        currency = MagicMock()
        currency.get_rate = AsyncMock(return_value=1.0)

        analyzer = PortfolioAnalyzer(db=MagicMock(), portfolio=portfolio, currency=currency)
        details = await analyzer.get_position_details()

        assert details[0]["profit_pct"] == 0.0

    @pytest.mark.asyncio
    async def test_zero_quantity_skipped(self):
        positions = [
            {
                "symbol": "ZERO",
                "quantity": 0,
                "current_price": 100.0,
                "currency": "EUR",
                "avg_cost": 80.0,
            },
        ]

        portfolio = MagicMock()
        portfolio.positions = AsyncMock(return_value=positions)

        currency = MagicMock()
        currency.get_rate = AsyncMock(return_value=1.0)

        analyzer = PortfolioAnalyzer(db=MagicMock(), portfolio=portfolio, currency=currency)
        details = await analyzer.get_position_details()

        assert len(details) == 0

    @pytest.mark.asyncio
    async def test_zero_price_skipped(self):
        positions = [
            {
                "symbol": "ZERO_PRICE",
                "quantity": 10,
                "current_price": 0.0,
                "currency": "EUR",
                "avg_cost": 80.0,
            },
        ]

        portfolio = MagicMock()
        portfolio.positions = AsyncMock(return_value=positions)

        currency = MagicMock()
        currency.get_rate = AsyncMock(return_value=1.0)

        analyzer = PortfolioAnalyzer(db=MagicMock(), portfolio=portfolio, currency=currency)
        details = await analyzer.get_position_details()

        assert len(details) == 0


class TestRebalanceThreshold:
    """Tests for _rebalance_threshold."""

    @pytest.mark.asyncio
    async def test_default_threshold(self):
        settings = MagicMock()
        settings.get = AsyncMock(return_value=None)

        analyzer = PortfolioAnalyzer(
            db=MagicMock(),
            portfolio=MagicMock(),
            currency=MagicMock(),
            settings=settings,
        )
        threshold = await analyzer._rebalance_threshold()
        assert threshold == pytest.approx(0.05)  # 5%

    @pytest.mark.asyncio
    async def test_custom_threshold(self):
        settings = MagicMock()
        settings.get = AsyncMock(return_value=10.0)

        analyzer = PortfolioAnalyzer(
            db=MagicMock(),
            portfolio=MagicMock(),
            currency=MagicMock(),
            settings=settings,
        )
        threshold = await analyzer._rebalance_threshold()
        assert threshold == pytest.approx(0.10)  # 10%

    @pytest.mark.asyncio
    async def test_zero_threshold(self):
        settings = MagicMock()
        settings.get = AsyncMock(return_value=0.0)

        analyzer = PortfolioAnalyzer(
            db=MagicMock(),
            portfolio=MagicMock(),
            currency=MagicMock(),
            settings=settings,
        )
        threshold = await analyzer._rebalance_threshold()
        assert threshold == 0.0
