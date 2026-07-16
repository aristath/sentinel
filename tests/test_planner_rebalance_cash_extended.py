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
    async def test_min_cash_buffer_is_not_spent_on_buys(self):
        engine = RebalanceEngine(db=MagicMock())
        engine._settings = MagicMock()
        engine._settings.get = AsyncMock(
            side_effect=lambda key, default=None: {
                "transaction_fee_fixed": 0.0,
                "transaction_fee_percent": 0.0,
                "min_cash_buffer": 0.05,
            }.get(key, default)
        )
        engine._portfolio = MagicMock()
        engine._portfolio.total_cash_eur = AsyncMock(return_value=1000.0)
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

        result = await engine._apply_cash_constraint(
            [buy],
            min_trade_value=100.0,
            total_value=10_000.0,
            symbol_convictions={"B": 0.8},
        )

        assert [(r.symbol, r.quantity) for r in result] == [("B", 5)]

    @pytest.mark.asyncio
    async def test_cash_reserve_shortfall_is_included_in_funding_request(self):
        engine = RebalanceEngine(db=MagicMock())
        engine._settings = MagicMock()
        engine._settings.get = AsyncMock(
            side_effect=lambda key, default=None: {
                "transaction_fee_fixed": 0.0,
                "transaction_fee_percent": 0.0,
                "min_cash_buffer": 0.05,
            }.get(key, default)
        )
        engine._portfolio = MagicMock()
        engine._portfolio.total_cash_eur = AsyncMock(return_value=100.0)
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

        await engine._apply_cash_constraint(
            [buy],
            min_trade_value=100.0,
            total_value=10_000.0,
            symbol_convictions={"B": 0.8},
        )

        assert engine._generate_deficit_sells.await_args.args[0] == 1410.0

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
    async def test_multiple_buys_use_priority_waterfall(self):
        engine = RebalanceEngine(db=MagicMock())
        engine._settings = MagicMock()
        engine._settings.get = AsyncMock(
            side_effect=lambda key, default=None: {"transaction_fee_fixed": 0.0, "transaction_fee_percent": 0.0}.get(
                key, 0.0
            )
        )
        engine._portfolio = MagicMock()
        engine._portfolio.total_cash_eur = AsyncMock(return_value=1500.0)
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
        buy2 = TradeRecommendation(
            symbol="B2",
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
            contrarian_score=0.7,
            priority=1.0,
            reason="buy",
        )
        result = await engine._apply_cash_constraint(
            [buy1, buy2], min_trade_value=100.0, symbol_convictions={"B1": 0.8, "B2": 0.7}
        )
        by_symbol = {r.symbol: r for r in result}
        assert by_symbol["B1"].quantity == 10
        assert by_symbol["B2"].quantity == 5

    @pytest.mark.asyncio
    async def test_funding_sells_cover_only_the_next_ranked_buy(self):
        engine = RebalanceEngine(db=MagicMock())
        engine._settings = MagicMock()
        engine._settings.get = AsyncMock(
            side_effect=lambda key, default=None: {
                "transaction_fee_fixed": 0.0,
                "transaction_fee_percent": 0.0,
            }.get(key, default)
        )
        engine._portfolio = MagicMock()
        engine._portfolio.total_cash_eur = AsyncMock(return_value=0.0)
        engine._currency = MagicMock()
        engine._currency.get_rate = AsyncMock(return_value=1.0)
        engine._generate_deficit_sells = AsyncMock(return_value=[])

        buys = [
            TradeRecommendation(
                symbol=symbol,
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
                contrarian_score=score,
                priority=1000.0,
                reason="buy",
                user_multiplier=0.8,
                target_gap_ratio=1.0,
            )
            for symbol, score in [("FIRST", 0.9), ("LATER", 0.8)]
        ]

        await engine._apply_cash_constraint(
            buys,
            min_trade_value=100.0,
            symbol_convictions={"FIRST": 0.8, "LATER": 0.8},
        )

        assert engine._generate_deficit_sells.await_args.args[0] == 1010.0

    @pytest.mark.asyncio
    async def test_partial_budget_stays_on_top_priority_buy(self):
        engine = RebalanceEngine(db=MagicMock())
        engine._settings = MagicMock()
        engine._settings.get = AsyncMock(
            side_effect=lambda key, default=None: {"transaction_fee_fixed": 0.0, "transaction_fee_percent": 0.0}.get(
                key, 0.0
            )
        )
        engine._portfolio = MagicMock()
        engine._portfolio.total_cash_eur = AsyncMock(return_value=700.0)
        engine._currency = MagicMock()
        engine._currency.get_rate = AsyncMock(return_value=1.0)
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        engine._generate_deficit_sells = AsyncMock(return_value=[])

        top = TradeRecommendation(
            symbol="TOP",
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
        second = TradeRecommendation(
            symbol="SECOND",
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
            contrarian_score=0.7,
            priority=1.0,
            reason="buy",
        )

        result = await engine._apply_cash_constraint(
            [top, second], min_trade_value=100.0, symbol_convictions={"TOP": 0.8, "SECOND": 0.7}
        )
        assert [(r.symbol, r.quantity) for r in result] == [("TOP", 7)]

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
    async def test_generated_funding_sell_is_dropped_when_no_buy_lot_is_executable(self):
        engine = RebalanceEngine(db=MagicMock())
        engine._settings = MagicMock()
        engine._settings.get = AsyncMock(return_value=0.0)
        engine._portfolio = MagicMock()
        engine._portfolio.total_cash_eur = AsyncMock(return_value=0.0)
        engine._currency = MagicMock()
        engine._currency.get_rate = AsyncMock(return_value=1.0)
        engine._currency.to_eur = AsyncMock(side_effect=lambda amount, _currency: amount)

        funding_sell = TradeRecommendation(
            symbol="SOURCE",
            action="sell",
            current_allocation=0.2,
            target_allocation=0.1,
            allocation_delta=-0.1,
            current_value_eur=2_000.0,
            target_value_eur=1_000.0,
            value_delta_eur=-500.0,
            quantity=5,
            price=100.0,
            currency="EUR",
            lot_size=1,
            contrarian_score=0.1,
            priority=10.0,
            reason="funding",
        )
        engine._generate_deficit_sells = AsyncMock(return_value=[funding_sell])
        coarse_buy = TradeRecommendation(
            symbol="COARSE",
            action="buy",
            current_allocation=0.0,
            target_allocation=0.2,
            allocation_delta=0.2,
            current_value_eur=0.0,
            target_value_eur=2_000.0,
            value_delta_eur=2_000.0,
            quantity=10,
            price=200.0,
            currency="EUR",
            lot_size=10,
            contrarian_score=0.9,
            priority=10.0,
            reason="buy",
        )

        result = await engine._apply_cash_constraint(
            [coarse_buy],
            min_trade_value=100.0,
            total_value=10_000.0,
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_equal_priority_waterfall_keeps_first_buy_first(self):
        """When priorities tie, the existing order remains the queue order."""
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
        assert [r.symbol for r in result if r.action == "buy"] == ["HIGH"]

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

    @pytest.mark.asyncio
    async def test_funding_rotation_uses_projected_target_value_for_overweight(self):
        engine = RebalanceEngine(db=MagicMock())
        engine._settings = MagicMock()
        engine._settings.get = AsyncMock(side_effect=lambda key, default=None: default)
        engine._currency = MagicMock()
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        engine._currency.get_rate = AsyncMock(return_value=1.0)

        sells = await engine._generate_deficit_sells(
            deficit_eur=500.0,
            ideal={"A": 0.25},
            current={"A": 10_000.0 / 24_000.0},
            total_value=24_000.0,
            planning_total_value=48_000.0,
            reason_kind="funding_rotation",
            preloaded_positions=[{"symbol": "A", "quantity": 100, "current_price": 100.0}],
            preloaded_securities_map={
                "A": {"symbol": "A", "currency": "EUR", "min_lot": 1, "allow_sell": 1, "user_multiplier": 0.5}
            },
            preloaded_symbol_scores={"A": 0.5},
            preloaded_symbol_prices={"A": 100.0},
        )

        assert sells == []


class TestDowngradedFundingPriority:
    """Explicitly-downgraded names are the preferred funding source (Fix 3)."""

    def _engine(self):
        engine = RebalanceEngine(db=MagicMock())
        engine._settings = MagicMock()
        engine._settings.get = AsyncMock(side_effect=lambda key, default=None: default)
        engine._currency = MagicMock()
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        engine._currency.get_rate = AsyncMock(return_value=1.0)
        return engine

    @pytest.mark.asyncio
    async def test_downgraded_name_sold_before_more_overweight_winner(self):
        """A downgraded loser funds buys before a more-overweight high-conviction name."""
        engine = self._engine()
        positions = [
            {"symbol": "WIN", "quantity": 30, "current_price": 100.0},
            {"symbol": "DOWN", "quantity": 5, "current_price": 100.0},
        ]
        secmap = {
            # WIN: far more overweight, but endorsed → touched last.
            "WIN": {
                "symbol": "WIN",
                "currency": "EUR",
                "min_lot": 1,
                "allow_sell": 1,
                "user_multiplier": 0.9,
                "user_multiplier_updated_at": "2026-06-01T00:00:00Z",
            },
            # DOWN: deliberately downgraded → drained first despite less overweight.
            "DOWN": {
                "symbol": "DOWN",
                "currency": "EUR",
                "min_lot": 1,
                "allow_sell": 1,
                "user_multiplier": 0.2,
                "user_multiplier_updated_at": "2026-06-01T00:00:00Z",
            },
        }
        sells = await engine._generate_deficit_sells(
            deficit_eur=200.0,
            ideal={"WIN": 0.05},  # DOWN absent → target 0
            current={"WIN": 0.30, "DOWN": 0.05},
            total_value=10000.0,
            reason_kind="funding_rotation",
            preloaded_positions=positions,
            preloaded_securities_map=secmap,
            preloaded_symbol_scores={"WIN": 0.5, "DOWN": 0.5},
            preloaded_symbol_prices={"WIN": 100.0, "DOWN": 100.0},
        )
        assert sells
        assert sells[0].symbol == "DOWN"

    @pytest.mark.asyncio
    async def test_downgraded_name_exempt_from_conviction_cap(self):
        """A downgraded name funds buys even when its conviction exceeds the cap."""
        engine = self._engine()
        positions = [{"symbol": "DOWN", "quantity": 5, "current_price": 100.0}]
        secmap = {
            "DOWN": {
                "symbol": "DOWN",
                "currency": "EUR",
                "min_lot": 1,
                "allow_sell": 1,
                "user_multiplier": 0.2,
                "user_multiplier_updated_at": "2026-06-01T00:00:00Z",
            }
        }
        # Cap below DOWN's 0.2 conviction — without the downgrade exemption it
        # would be filtered out and no sell produced.
        sells = await engine._generate_deficit_sells(
            deficit_eur=200.0,
            ideal={},
            current={"DOWN": 0.05},
            total_value=10000.0,
            reason_kind="funding_rotation",
            max_sell_conviction=0.1,
            preloaded_positions=positions,
            preloaded_securities_map=secmap,
            preloaded_symbol_scores={"DOWN": 0.5},
            preloaded_symbol_prices={"DOWN": 100.0},
        )
        assert sells
        assert sells[0].symbol == "DOWN"
