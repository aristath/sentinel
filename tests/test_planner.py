"""Tests for Planner class - negative balance deficit sells.

These tests verify the intended behavior of the Planner's deficit sells:
1. Sell recommendations when negative balances can't be covered by positive balances
2. Priority ordering (lowest score, smallest first)
3. No sells when positive balances can cover the deficit
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel.planner import Planner


class TestDeficitSells:
    """Tests for sell recommendations when positive balances can't cover deficit."""

    @pytest.mark.asyncio
    async def test_no_sells_when_positive_balances_cover_deficit(self):
        """No sells when positive currency balances can cover the deficit."""
        db = MagicMock()
        # Negative EUR but plenty of USD to cover it
        db.get_cash_balances = AsyncMock(return_value={"EUR": -500.0, "USD": 1000.0})

        planner = Planner(db=db)
        planner._currency = MagicMock()
        planner._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt * 0.85 if curr == "USD" else amt)
        planner._db = db

        sells = await planner._get_deficit_sells()

        # USD (850 EUR) can cover EUR deficit (600 EUR with buffer), so no sells needed
        assert sells == []

    @pytest.mark.asyncio
    async def test_sells_generated_when_positive_balances_insufficient(self):
        """Sell recommendations generated when positive balances can't cover deficit."""
        db = MagicMock()
        # Large deficit, small positive balance
        db.get_cash_balances = AsyncMock(return_value={"EUR": -5000.0, "USD": 100.0})
        db.get_all_positions = AsyncMock(
            return_value=[
                {"symbol": "AAPL.US", "quantity": 10, "current_price": 200.0},
            ]
        )
        db.get_security = AsyncMock(
            return_value={
                "symbol": "AAPL.US",
                "currency": "USD",
                "min_lot": 1,
                "allow_sell": 1,
            }
        )

        # Mock score lookup
        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value={"score": 0.5})
        db.conn = MagicMock()
        db.conn.execute = AsyncMock(return_value=mock_cursor)

        planner = Planner(db=db)
        planner._currency = MagicMock()
        planner._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt * 0.85 if curr == "USD" else amt)
        planner._currency.get_rate = AsyncMock(return_value=0.85)
        planner._portfolio = MagicMock()
        planner._portfolio.total_value = AsyncMock(return_value=10000.0)
        planner._db = db

        sells = await planner._get_deficit_sells()

        # USD (85 EUR) can't cover EUR deficit (5100 EUR with buffer), so sells needed
        assert len(sells) > 0
        assert sells[0].action == "sell"

    @pytest.mark.asyncio
    async def test_no_sells_when_all_balances_positive(self):
        """No sells when all balances are positive."""
        db = MagicMock()
        db.get_cash_balances = AsyncMock(return_value={"EUR": 1000.0, "USD": 500.0})

        planner = Planner(db=db)
        planner._currency = MagicMock()
        planner._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt * 0.85 if curr == "USD" else amt)
        planner._db = db

        sells = await planner._get_deficit_sells()

        assert sells == []

    @pytest.mark.asyncio
    async def test_sells_prioritize_lowest_score(self):
        """Sells prioritize positions with lowest score."""
        db = MagicMock()
        db.get_cash_balances = AsyncMock(return_value={"EUR": -1000.0})  # No positive balances
        db.get_all_positions = AsyncMock(
            return_value=[
                {"symbol": "HIGH.EU", "quantity": 10, "current_price": 100.0},
                {"symbol": "LOW.EU", "quantity": 10, "current_price": 100.0},
            ]
        )

        securities = {
            "HIGH.EU": {"symbol": "HIGH.EU", "currency": "EUR", "min_lot": 1, "allow_sell": 1},
            "LOW.EU": {"symbol": "LOW.EU", "currency": "EUR", "min_lot": 1, "allow_sell": 1},
        }
        db.get_security = AsyncMock(side_effect=lambda s: securities.get(s))

        # LOW.EU has lower score
        scores = {"HIGH.EU": 0.8, "LOW.EU": 0.2}

        async def mock_execute(query, params=None):
            mock_cursor = MagicMock()
            if "SELECT score" in query and params:
                symbol = params[0]
                mock_cursor.fetchone = AsyncMock(return_value={"score": scores.get(symbol, 0)})
            else:
                mock_cursor.fetchone = AsyncMock(return_value=None)
            return mock_cursor

        db.conn = MagicMock()
        db.conn.execute = AsyncMock(side_effect=mock_execute)

        planner = Planner(db=db)
        planner._currency = MagicMock()
        planner._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        planner._currency.get_rate = AsyncMock(return_value=1.0)
        planner._portfolio = MagicMock()
        planner._portfolio.total_value = AsyncMock(return_value=10000.0)
        planner._db = db

        sells = await planner._get_deficit_sells()

        # Should sell LOW.EU first (lower score)
        assert len(sells) > 0
        assert sells[0].symbol == "LOW.EU"

    @pytest.mark.asyncio
    async def test_sells_have_high_priority(self):
        """Deficit-fix sells have high priority (1000)."""
        db = MagicMock()
        db.get_cash_balances = AsyncMock(return_value={"EUR": -500.0})  # No positive balances
        db.get_all_positions = AsyncMock(
            return_value=[
                {"symbol": "TEST.EU", "quantity": 10, "current_price": 100.0},
            ]
        )
        db.get_security = AsyncMock(
            return_value={
                "symbol": "TEST.EU",
                "currency": "EUR",
                "min_lot": 1,
                "allow_sell": 1,
            }
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value={"score": 0.5})
        db.conn = MagicMock()
        db.conn.execute = AsyncMock(return_value=mock_cursor)

        planner = Planner(db=db)
        planner._currency = MagicMock()
        planner._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        planner._currency.get_rate = AsyncMock(return_value=1.0)
        planner._portfolio = MagicMock()
        planner._portfolio.total_value = AsyncMock(return_value=10000.0)
        planner._db = db

        sells = await planner._get_deficit_sells()

        assert len(sells) > 0
        assert sells[0].priority == 1000

    @pytest.mark.asyncio
    async def test_respects_allow_sell_flag(self):
        """Doesn't recommend selling positions with allow_sell=0."""
        db = MagicMock()
        db.get_cash_balances = AsyncMock(return_value={"EUR": -500.0})  # No positive balances
        db.get_all_positions = AsyncMock(
            return_value=[
                {"symbol": "NOSELL.EU", "quantity": 10, "current_price": 100.0},
                {"symbol": "CANSELL.EU", "quantity": 10, "current_price": 100.0},
            ]
        )

        securities = {
            "NOSELL.EU": {"symbol": "NOSELL.EU", "currency": "EUR", "min_lot": 1, "allow_sell": 0},
            "CANSELL.EU": {"symbol": "CANSELL.EU", "currency": "EUR", "min_lot": 1, "allow_sell": 1},
        }
        db.get_security = AsyncMock(side_effect=lambda s: securities.get(s))

        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value={"score": 0.5})
        db.conn = MagicMock()
        db.conn.execute = AsyncMock(return_value=mock_cursor)

        planner = Planner(db=db)
        planner._currency = MagicMock()
        planner._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        planner._currency.get_rate = AsyncMock(return_value=1.0)
        planner._portfolio = MagicMock()
        planner._portfolio.total_value = AsyncMock(return_value=10000.0)
        planner._db = db

        sells = await planner._get_deficit_sells()

        # Should only sell CANSELL.EU
        sell_symbols = [s.symbol for s in sells]
        assert "NOSELL.EU" not in sell_symbols
        if sells:
            assert "CANSELL.EU" in sell_symbols
