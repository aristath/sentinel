"""Tests for Planner components - negative balance deficit sells and feature caching."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel.planner import RebalanceEngine


class TestDeficitSells:
    """Tests for sell recommendations when positive balances can't cover deficit."""

    @pytest.mark.asyncio
    async def test_no_sells_when_positive_balances_cover_deficit(self):
        """No sells when positive currency balances can cover the deficit."""
        db = MagicMock()

        portfolio = MagicMock()
        # Negative EUR but plenty of USD to cover it
        portfolio.get_cash_balances = AsyncMock(return_value={"EUR": -500.0, "USD": 1000.0})

        engine = RebalanceEngine(db=db, portfolio=portfolio)
        engine._currency = MagicMock()
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt * 0.85 if curr == "USD" else amt)
        engine._db = db
        engine._portfolio = portfolio

        sells = await engine._get_deficit_sells()

        # USD (850 EUR) can cover EUR deficit (600 EUR with buffer), so no sells needed
        assert sells == []

    @pytest.mark.asyncio
    async def test_sells_generated_when_positive_balances_insufficient(self):
        """Sell recommendations generated when positive balances can't cover deficit."""
        db = MagicMock()
        # Large deficit, small positive balance
        db.get_all_positions = AsyncMock(
            return_value=[
                {"symbol": "AAPL.US", "quantity": 10, "current_price": 200.0},
            ]
        )
        db.get_all_securities = AsyncMock(
            return_value=[
                {
                    "symbol": "AAPL.US",
                    "currency": "USD",
                    "min_lot": 1,
                    "allow_sell": 1,
                },
            ]
        )
        db.get_scores = AsyncMock(return_value={"AAPL.US": 0.5})

        engine = RebalanceEngine(db=db)
        engine._currency = MagicMock()
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt * 0.85 if curr == "USD" else amt)
        engine._currency.get_rate = AsyncMock(return_value=0.85)
        engine._portfolio = MagicMock()
        engine._portfolio.total_value = AsyncMock(return_value=10000.0)
        engine._portfolio.get_cash_balances = AsyncMock(return_value={"EUR": -5000.0, "USD": 100.0})
        engine._db = db

        sells = await engine._get_deficit_sells()

        # USD (85 EUR) can't cover EUR deficit (5100 EUR with buffer), so sells needed
        assert len(sells) > 0
        assert sells[0].action == "sell"

    @pytest.mark.asyncio
    async def test_no_sells_when_all_balances_positive(self):
        """No sells when all balances are positive."""
        db = MagicMock()

        portfolio = MagicMock()
        portfolio.get_cash_balances = AsyncMock(return_value={"EUR": 1000.0, "USD": 500.0})

        engine = RebalanceEngine(db=db, portfolio=portfolio)
        engine._currency = MagicMock()
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt * 0.85 if curr == "USD" else amt)
        engine._db = db
        engine._portfolio = portfolio

        sells = await engine._get_deficit_sells()

        assert sells == []

    @pytest.mark.asyncio
    async def test_sells_prioritize_lowest_score(self):
        """Sells prioritize positions with lowest score."""
        db = MagicMock()
        db.get_all_positions = AsyncMock(
            return_value=[
                {"symbol": "HIGH.EU", "quantity": 10, "current_price": 100.0},
                {"symbol": "LOW.EU", "quantity": 10, "current_price": 100.0},
            ]
        )
        db.get_all_securities = AsyncMock(
            return_value=[
                {"symbol": "HIGH.EU", "currency": "EUR", "min_lot": 1, "allow_sell": 1},
                {"symbol": "LOW.EU", "currency": "EUR", "min_lot": 1, "allow_sell": 1},
            ]
        )

        # LOW.EU has lower score
        db.get_scores = AsyncMock(return_value={"HIGH.EU": 0.8, "LOW.EU": 0.2})

        engine = RebalanceEngine(db=db)
        engine._currency = MagicMock()
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        engine._currency.get_rate = AsyncMock(return_value=1.0)
        engine._portfolio = MagicMock()
        engine._portfolio.total_value = AsyncMock(return_value=10000.0)
        engine._portfolio.get_cash_balances = AsyncMock(return_value={"EUR": -1000.0})
        engine._db = db

        sells = await engine._get_deficit_sells()

        # Should sell LOW.EU first (lower score)
        assert len(sells) > 0
        assert sells[0].symbol == "LOW.EU"

    @pytest.mark.asyncio
    async def test_sells_have_high_priority(self):
        """Deficit-fix sells have high priority (1000)."""
        db = MagicMock()
        db.get_all_positions = AsyncMock(
            return_value=[
                {"symbol": "TEST.EU", "quantity": 10, "current_price": 100.0},
            ]
        )
        db.get_all_securities = AsyncMock(
            return_value=[
                {
                    "symbol": "TEST.EU",
                    "currency": "EUR",
                    "min_lot": 1,
                    "allow_sell": 1,
                },
            ]
        )
        db.get_scores = AsyncMock(return_value={"TEST.EU": 0.5})

        engine = RebalanceEngine(db=db)
        engine._currency = MagicMock()
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        engine._currency.get_rate = AsyncMock(return_value=1.0)
        engine._portfolio = MagicMock()
        engine._portfolio.total_value = AsyncMock(return_value=10000.0)
        engine._portfolio.get_cash_balances = AsyncMock(return_value={"EUR": -500.0})
        engine._db = db

        sells = await engine._get_deficit_sells()

        assert len(sells) > 0
        assert sells[0].priority == 1000

    @pytest.mark.asyncio
    async def test_respects_allow_sell_flag(self):
        """Doesn't recommend selling positions with allow_sell=0."""
        db = MagicMock()
        db.get_all_positions = AsyncMock(
            return_value=[
                {"symbol": "NOSELL.EU", "quantity": 10, "current_price": 100.0},
                {"symbol": "CANSELL.EU", "quantity": 10, "current_price": 100.0},
            ]
        )
        db.get_all_securities = AsyncMock(
            return_value=[
                {"symbol": "NOSELL.EU", "currency": "EUR", "min_lot": 1, "allow_sell": 0},
                {"symbol": "CANSELL.EU", "currency": "EUR", "min_lot": 1, "allow_sell": 1},
            ]
        )
        db.get_scores = AsyncMock(return_value={"NOSELL.EU": 0.5, "CANSELL.EU": 0.5})

        engine = RebalanceEngine(db=db)
        engine._currency = MagicMock()
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        engine._currency.get_rate = AsyncMock(return_value=1.0)
        engine._portfolio = MagicMock()
        engine._portfolio.total_value = AsyncMock(return_value=10000.0)
        engine._portfolio.get_cash_balances = AsyncMock(return_value={"EUR": -500.0})
        engine._db = db

        sells = await engine._get_deficit_sells()

        # Should only sell CANSELL.EU
        sell_symbols = [s.symbol for s in sells]
        assert "NOSELL.EU" not in sell_symbols
        if sells:
            assert "CANSELL.EU" in sell_symbols


class TestDeficitSellsSimulatedCash:
    """Tests that deficit sells respect simulated cash from Portfolio."""

    @pytest.mark.asyncio
    async def test_deficit_sells_uses_simulated_cash(self):
        """When portfolio returns simulated positive cash, no deficit sells generated."""
        db = MagicMock()
        # DB has negative cash, but portfolio (with simulated cash) will return positive
        db.get_cash_balances = AsyncMock(return_value={"EUR": -5000.0})

        portfolio = MagicMock()
        # Simulated cash overrides the negative balance
        portfolio.get_cash_balances = AsyncMock(return_value={"EUR": 10000.0})
        portfolio.total_value = AsyncMock(return_value=50000.0)

        engine = RebalanceEngine(db=db, portfolio=portfolio)
        engine._currency = MagicMock()
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        engine._portfolio = portfolio

        sells = await engine._get_deficit_sells()

        # Portfolio returns positive cash, so no deficit sells needed
        assert sells == []
