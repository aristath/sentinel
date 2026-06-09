"""Tests for rebalance_cash.py — edge cases for apply_cash_constraint and generate_deficit_sells."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel.planner import RebalanceEngine
from sentinel.planner.models import TradeRecommendation


class TestApplyCashConstraintEdgeCases:
    """Tests for apply_cash_constraint edge cases."""

    @pytest.mark.asyncio
    async def test_no_buys_returns_unchanged(self):
        engine = RebalanceEngine(db=MagicMock())
        engine._settings = MagicMock()
        engine._settings.get = AsyncMock(side_effect=lambda key, default=None: default)
        engine._portfolio = MagicMock()
        engine._currency = MagicMock()

        sell = TradeRecommendation(
            symbol="S",
            action="sell",
            current_allocation=0.1,
            target_allocation=0.0,
            allocation_delta=-0.1,
            current_value_eur=1000.0,
            target_value_eur=0.0,
            value_delta_eur=-1000.0,
            quantity=10,
            price=100.0,
            currency="EUR",
            lot_size=1,
            contrarian_score=0.1,
            priority=1.0,
            reason="sell",
        )
        result = await engine._apply_cash_constraint([sell], min_trade_value=100.0)
        assert len(result) == 1
        assert result[0].action == "sell"

    @pytest.mark.asyncio
    async def test_budget_sufficient_no_scaling(self):
        engine = RebalanceEngine(db=MagicMock())
        engine._settings = MagicMock()
        engine._settings.get = AsyncMock(
            side_effect=lambda key, default=None: {"transaction_fee_fixed": 2.0, "transaction_fee_percent": 0.2}.get(
                key, 0.0
            )
        )
        engine._portfolio = MagicMock()
        engine._portfolio.total_cash_eur = AsyncMock(return_value=5000.0)
        engine._currency = MagicMock()
        engine._currency.get_rate = AsyncMock(return_value=1.0)
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)

        buy = TradeRecommendation(
            symbol="B",
            action="buy",
            current_allocation=0.0,
            target_allocation=0.1,
            allocation_delta=0.1,
            current_value_eur=0.0,
            target_value_eur=1000.0,
            value_delta_eur=1000.0,
            quantity=10,
            price=100.0,
            currency="EUR",
            lot_size=1,
            contrarian_score=0.8,
            priority=2.0,
            reason="buy",
        )
        result = await engine._apply_cash_constraint([buy], min_trade_value=100.0)
        assert len(result) == 1
        assert result[0].quantity == 10  # unchanged

    @pytest.mark.asyncio
    async def test_budget_insufficient_scales_down(self):
        engine = RebalanceEngine(db=MagicMock())
        engine._settings = MagicMock()
        engine._settings.get = AsyncMock(
            side_effect=lambda key, default=None: {"transaction_fee_fixed": 0.0, "transaction_fee_percent": 0.0}.get(
                key, 0.0
            )
        )
        engine._portfolio = MagicMock()
        engine._portfolio.total_cash_eur = AsyncMock(return_value=200.0)
        engine._currency = MagicMock()
        engine._currency.get_rate = AsyncMock(return_value=1.0)
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        engine._generate_deficit_sells = AsyncMock(return_value=[])

        buy = TradeRecommendation(
            symbol="B",
            action="buy",
            current_allocation=0.0,
            target_allocation=0.1,
            allocation_delta=0.1,
            current_value_eur=0.0,
            target_value_eur=1000.0,
            value_delta_eur=1000.0,
            quantity=10,
            price=100.0,
            currency="EUR",
            lot_size=1,
            contrarian_score=0.8,
            priority=2.0,
            reason="buy",
        )
        result = await engine._apply_cash_constraint([buy], min_trade_value=100.0, symbol_convictions={"B": 0.8})
        assert len(result) == 1
        assert result[0].quantity == 2  # 200 / 100 = 2

    @pytest.mark.asyncio
    async def test_scaled_buy_preserves_metadata(self):
        engine = RebalanceEngine(db=MagicMock())
        engine._settings = MagicMock()
        engine._settings.get = AsyncMock(
            side_effect=lambda key, default=None: {"transaction_fee_fixed": 0.0, "transaction_fee_percent": 0.0}.get(
                key, 0.0
            )
        )
        engine._portfolio = MagicMock()
        engine._portfolio.total_cash_eur = AsyncMock(return_value=200.0)
        engine._currency = MagicMock()
        engine._currency.get_rate = AsyncMock(return_value=1.0)
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        engine._generate_deficit_sells = AsyncMock(return_value=[])

        buy = TradeRecommendation(
            symbol="B",
            action="buy",
            current_allocation=0.0,
            target_allocation=0.1,
            allocation_delta=0.1,
            current_value_eur=0.0,
            target_value_eur=1000.0,
            value_delta_eur=1000.0,
            quantity=10,
            price=100.0,
            currency="EUR",
            lot_size=1,
            contrarian_score=0.8,
            priority=2.0,
            reason="buy",
            reason_code="entry_t1",
            sleeve="opportunity",
            memory_entry=True,
        )
        result = await engine._apply_cash_constraint([buy], min_trade_value=100.0, symbol_convictions={"B": 0.8})
        assert result[0].reason_code == "entry_t1"
        assert result[0].sleeve == "opportunity"
        assert result[0].memory_entry is True

    @pytest.mark.asyncio
    async def test_multiple_buys_scaled_proportionally(self):
        engine = RebalanceEngine(db=MagicMock())
        engine._settings = MagicMock()
        engine._settings.get = AsyncMock(
            side_effect=lambda key, default=None: {"transaction_fee_fixed": 0.0, "transaction_fee_percent": 0.0}.get(
                key, 0.0
            )
        )
        engine._portfolio = MagicMock()
        engine._portfolio.total_cash_eur = AsyncMock(return_value=1000.0)
        engine._currency = MagicMock()
        engine._currency.get_rate = AsyncMock(return_value=1.0)
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        engine._generate_deficit_sells = AsyncMock(return_value=[])

        buy1 = TradeRecommendation(
            symbol="B1",
            action="buy",
            current_allocation=0.0,
            target_allocation=0.1,
            allocation_delta=0.1,
            current_value_eur=0.0,
            target_value_eur=500.0,
            value_delta_eur=500.0,
            quantity=5,
            price=100.0,
            currency="EUR",
            lot_size=1,
            contrarian_score=0.8,
            priority=2.0,
            reason="buy",
        )
        buy2 = TradeRecommendation(
            symbol="B2",
            action="buy",
            current_allocation=0.0,
            target_allocation=0.1,
            allocation_delta=0.1,
            current_value_eur=0.0,
            target_value_eur=500.0,
            value_delta_eur=500.0,
            quantity=5,
            price=100.0,
            currency="EUR",
            lot_size=1,
            contrarian_score=0.7,
            priority=1.0,
            reason="buy",
        )
        result = await engine._apply_cash_constraint(
            [buy1, buy2], min_trade_value=100.0, symbol_convictions={"B1": 0.8, "B2": 0.7}
        )
        # Budget 1000 = total cost 1000, no scaling needed
        assert len(result) == 2
        total_qty = sum(r.quantity for r in result)
        assert total_qty == 10

    @pytest.mark.asyncio
    async def test_buy_minimum_respected(self):
        engine = RebalanceEngine(db=MagicMock())
        engine._settings = MagicMock()
        engine._settings.get = AsyncMock(
            side_effect=lambda key, default=None: {"transaction_fee_fixed": 0.0, "transaction_fee_percent": 0.0}.get(
                key, 0.0
            )
        )
        engine._portfolio = MagicMock()
        engine._portfolio.total_cash_eur = AsyncMock(return_value=50.0)
        engine._currency = MagicMock()
        engine._currency.get_rate = AsyncMock(return_value=1.0)
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        engine._generate_deficit_sells = AsyncMock(return_value=[])

        buy = TradeRecommendation(
            symbol="B",
            action="buy",
            current_allocation=0.0,
            target_allocation=0.1,
            allocation_delta=0.1,
            current_value_eur=0.0,
            target_value_eur=1000.0,
            value_delta_eur=1000.0,
            quantity=10,
            price=100.0,
            currency="EUR",
            lot_size=1,
            contrarian_score=0.8,
            priority=2.0,
            reason="buy",
        )
        result = await engine._apply_cash_constraint([buy], min_trade_value=100.0, symbol_convictions={"B": 0.8})
        # Budget 50 < min_trade_value 100, so buy should be dropped
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_conviction_based_buy_trimming(self):
        """When budget is tight, lower-conviction buys are trimmed first."""
        engine = RebalanceEngine(db=MagicMock())
        engine._settings = MagicMock()
        engine._settings.get = AsyncMock(
            side_effect=lambda key, default=None: {"transaction_fee_fixed": 0.0, "transaction_fee_percent": 0.0}.get(
                key, 0.0
            )
        )
        engine._portfolio = MagicMock()
        engine._portfolio.total_cash_eur = AsyncMock(return_value=300.0)
        engine._currency = MagicMock()
        engine._currency.get_rate = AsyncMock(return_value=1.0)
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        engine._generate_deficit_sells = AsyncMock(return_value=[])

        buy_high = TradeRecommendation(
            symbol="HIGH",
            action="buy",
            current_allocation=0.0,
            target_allocation=0.1,
            allocation_delta=0.1,
            current_value_eur=0.0,
            target_value_eur=500.0,
            value_delta_eur=500.0,
            quantity=5,
            price=100.0,
            currency="EUR",
            lot_size=1,
            contrarian_score=0.9,
            priority=1.0,
            reason="buy",
        )
        buy_med = TradeRecommendation(
            symbol="MED",
            action="buy",
            current_allocation=0.0,
            target_allocation=0.1,
            allocation_delta=0.1,
            current_value_eur=0.0,
            target_value_eur=500.0,
            value_delta_eur=500.0,
            quantity=5,
            price=100.0,
            currency="EUR",
            lot_size=1,
            contrarian_score=0.7,
            priority=1.0,
            reason="buy",
        )
        buy_low = TradeRecommendation(
            symbol="LOW",
            action="buy",
            current_allocation=0.0,
            target_allocation=0.1,
            allocation_delta=0.1,
            current_value_eur=0.0,
            target_value_eur=500.0,
            value_delta_eur=500.0,
            quantity=5,
            price=100.0,
            currency="EUR",
            lot_size=1,
            contrarian_score=0.5,
            priority=1.0,
            reason="buy",
        )

        result = await engine._apply_cash_constraint(
            [buy_high, buy_med, buy_low],
            min_trade_value=100.0,
            symbol_convictions={"HIGH": 0.9, "MED": 0.7, "LOW": 0.5},
        )
        symbols = {r.symbol for r in result if r.action == "buy"}
        assert "HIGH" in symbols

    @pytest.mark.asyncio
    async def test_top_up_with_leftover_budget(self):
        """After initial allocation, leftover budget should top up buys."""
        engine = RebalanceEngine(db=MagicMock())
        engine._settings = MagicMock()
        engine._settings.get = AsyncMock(
            side_effect=lambda key, default=None: {"transaction_fee_fixed": 0.0, "transaction_fee_percent": 0.0}.get(
                key, 0.0
            )
        )
        engine._portfolio = MagicMock()
        engine._portfolio.total_cash_eur = AsyncMock(return_value=550.0)
        engine._currency = MagicMock()
        engine._currency.get_rate = AsyncMock(return_value=1.0)
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        engine._generate_deficit_sells = AsyncMock(return_value=[])

        buy = TradeRecommendation(
            symbol="B",
            action="buy",
            current_allocation=0.0,
            target_allocation=0.1,
            allocation_delta=0.1,
            current_value_eur=0.0,
            target_value_eur=1000.0,
            value_delta_eur=1000.0,
            quantity=10,
            price=100.0,
            currency="EUR",
            lot_size=1,
            contrarian_score=0.8,
            priority=2.0,
            reason="buy",
        )
        result = await engine._apply_cash_constraint([buy], min_trade_value=100.0, symbol_convictions={"B": 0.8})
        assert result[0].quantity >= 5


class TestGetDeficitSellsMultiCurrency:
    """Tests for get_deficit_sells with multi-currency balances."""

    @pytest.mark.asyncio
    async def test_multi_currency_deficit(self):
        """Negative balances in multiple currencies should be summed."""
        db = MagicMock()
        db.get_all_positions = AsyncMock(
            return_value=[
                {"symbol": "A", "quantity": 100, "current_price": 100.0, "currency": "EUR"},
            ]
        )
        db.get_all_securities = AsyncMock(
            return_value=[
                {"symbol": "A", "currency": "EUR", "min_lot": 1, "allow_sell": 1},
            ]
        )
        db.get_prices = AsyncMock(return_value=[{"close": 100.0}] * 250)
        portfolio = MagicMock()
        portfolio.get_cash_balances = AsyncMock(return_value={"EUR": -500.0, "USD": -200.0})
        portfolio.total_value = AsyncMock(return_value=10000.0)

        engine = RebalanceEngine(db=db, portfolio=portfolio)
        engine._currency = MagicMock()
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt * 0.9 if curr == "USD" else amt)
        engine._currency.get_rate = AsyncMock(return_value=1.0)

        sells = await engine._get_deficit_sells()
        assert len(sells) > 0


class TestGenerateDeficitSellsTotalValue:
    """Tests for generate_deficit_sells total_value edge cases."""

    @pytest.mark.asyncio
    async def test_total_value_from_portfolio_when_not_provided(self):
        db = MagicMock()
        db.get_all_positions = AsyncMock(return_value=[{"symbol": "A", "quantity": 10, "current_price": 100.0}])
        db.get_all_securities = AsyncMock(
            return_value=[{"symbol": "A", "currency": "EUR", "min_lot": 1, "allow_sell": 1}]
        )
        db.get_prices = AsyncMock(return_value=[{"close": 100.0}] * 300)

        portfolio = MagicMock()
        portfolio.total_value = AsyncMock(return_value=10000.0)
        portfolio.get_cash_balances = AsyncMock(return_value={"EUR": -500.0})

        engine = RebalanceEngine(db=db, portfolio=portfolio)
        engine._currency = MagicMock()
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        engine._currency.get_rate = AsyncMock(return_value=1.0)

        sells = await engine._generate_deficit_sells(
            deficit_eur=500.0,
            total_value=None,  # not provided
            preloaded_positions=[{"symbol": "A", "quantity": 10, "current_price": 100.0}],
            preloaded_securities_map={"A": {"symbol": "A", "currency": "EUR", "min_lot": 1, "allow_sell": 1}},
            preloaded_symbol_scores={"A": 0.5},
            preloaded_symbol_prices={"A": 100.0},
        )
        assert len(sells) > 0

    @pytest.mark.asyncio
    async def test_as_of_date_total_value_computation(self):
        db = MagicMock()
        portfolio = MagicMock()
        portfolio.get_cash_balances = AsyncMock(return_value={"EUR": -500.0})
        portfolio.total_value = AsyncMock(return_value=10000.0)

        engine = RebalanceEngine(db=db, portfolio=portfolio)
        engine._currency = MagicMock()
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        engine._currency.get_rate = AsyncMock(return_value=1.0)

        sells = await engine._generate_deficit_sells(
            deficit_eur=500.0,
            as_of_date="2025-01-15",
            total_value=None,
            preloaded_positions=[{"symbol": "A", "quantity": 10, "current_price": 100.0}],
            preloaded_securities_map={"A": {"symbol": "A", "currency": "EUR", "min_lot": 1, "allow_sell": 1}},
            preloaded_symbol_scores={"A": 0.5},
            preloaded_symbol_prices={"A": 100.0},
        )
        assert len(sells) > 0
