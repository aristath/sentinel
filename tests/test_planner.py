"""Tests for Planner components - deterministic contrarian execution behavior."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel.planner import Planner, RebalanceEngine
from sentinel.planner.models import TradeRecommendation
from sentinel.planner.rebalance_rules import desired_tranche_stage, get_forced_opportunity_exit
from sentinel.strategy import recent_dd252_min


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
        db.get_prices = AsyncMock(return_value=[{"close": 180.0}, {"close": 190.0}, {"close": 200.0}] * 100)

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
        db.get_prices = AsyncMock(
            side_effect=lambda symbol, **_: (
                [{"close": 100 + i * 0.2} for i in range(300)]
                if symbol == "HIGH.EU"
                else [{"close": 100 - i * 0.2} for i in range(300)]
            )
        )

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
        db.get_prices = AsyncMock(return_value=[{"close": 100.0}] * 300)

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
        db.get_prices = AsyncMock(return_value=[{"close": 100.0}] * 300)

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


class TestContrarianSizing:
    @pytest.mark.asyncio
    async def test_coarse_lot_buy_is_capped_to_one_lot(self):
        db = MagicMock()
        db.get_all_positions = AsyncMock(return_value=[])
        db.get_all_securities = AsyncMock(
            return_value=[
                {
                    "symbol": "CATL",
                    "currency": "EUR",
                    "min_lot": 100,
                    "allow_buy": 1,
                    "allow_sell": 1,
                    "user_multiplier": 1.0,
                }
            ]
        )
        db.get_prices = AsyncMock(return_value=[{"date": i, "close": 40.0} for i in range(300)])
        db.cache_get = AsyncMock(return_value=None)
        db.cache_set = AsyncMock()

        engine = RebalanceEngine(db=db)
        engine._broker = MagicMock()
        engine._broker.get_quotes = AsyncMock(return_value={"CATL": {"price": 50.0}})
        engine._settings = MagicMock()
        settings_values = {
            "min_trade_value": 100.0,
            "transaction_fee_fixed": 2.0,
            "transaction_fee_percent": 0.2,
            "strategy_lot_standard_max_pct": 0.08,
            "strategy_lot_coarse_max_pct": 0.30,
            "strategy_coarse_max_new_lots_per_cycle": 1,
            "trade_cooloff_days": 0,
            "strategy_core_floor_pct": 0.05,
        }
        engine._settings.get = AsyncMock(side_effect=lambda key, default=None: settings_values.get(key, default))
        engine._portfolio = MagicMock()
        engine._portfolio.total_cash_eur = AsyncMock(return_value=50_000.0)
        engine._currency = MagicMock()
        engine._currency.get_rate = AsyncMock(return_value=1.0)
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        engine._get_deficit_sells = AsyncMock(return_value=[])

        recs = await engine.get_recommendations(
            ideal={"CATL": 0.7},
            current={"CATL": 0.0},
            total_value=20_000.0,
            as_of_date="2025-01-15",
        )

        assert len(recs) == 1
        assert recs[0].action == "buy"
        assert recs[0].quantity == 100

    @pytest.mark.asyncio
    async def test_buy_is_capped_by_hard_max_position_pct(self):
        db = MagicMock()
        db.get_all_positions = AsyncMock(return_value=[{"symbol": "AAPL", "quantity": 48, "current_price": 100.0}])
        db.get_all_securities = AsyncMock(
            return_value=[
                {
                    "symbol": "AAPL",
                    "currency": "EUR",
                    "min_lot": 1,
                    "allow_buy": 1,
                    "allow_sell": 1,
                    "user_multiplier": 1.0,
                }
            ]
        )
        db.get_prices = AsyncMock(return_value=[{"date": i, "close": 100.0} for i in range(300)])
        db.cache_get = AsyncMock(return_value=None)
        db.cache_set = AsyncMock()

        engine = RebalanceEngine(db=db)
        engine._broker = MagicMock()
        engine._broker.get_quotes = AsyncMock(return_value={"AAPL": {"price": 100.0}})
        engine._settings = MagicMock()
        settings_values = {
            "min_trade_value": 100.0,
            "transaction_fee_fixed": 2.0,
            "transaction_fee_percent": 0.2,
            "strategy_lot_standard_max_pct": 0.08,
            "strategy_lot_coarse_max_pct": 0.30,
            "strategy_coarse_max_new_lots_per_cycle": 1,
            "strategy_core_floor_pct": 0.05,
            "strategy_min_opp_score": 0.55,
            "max_position_pct": 25,
            "strategy_opportunity_addon_threshold": 0.75,
            "strategy_entry_t1_dd": -0.10,
            "strategy_entry_t2_dd": -0.16,
            "strategy_entry_t3_dd": -0.22,
            "strategy_entry_memory_days": 42,
            "strategy_memory_max_boost": 0.18,
            "strategy_opportunity_cooloff_days": 0,
            "strategy_core_cooloff_days": 0,
        }
        engine._settings.get = AsyncMock(side_effect=lambda key, default=None: settings_values.get(key, default))
        engine._portfolio = MagicMock()
        engine._portfolio.total_cash_eur = AsyncMock(return_value=50_000.0)
        engine._currency = MagicMock()
        engine._currency.get_rate = AsyncMock(return_value=1.0)
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        engine._get_deficit_sells = AsyncMock(return_value=[])

        recs = await engine.get_recommendations(
            ideal={"AAPL": 0.70},
            current={"AAPL": 0.24},
            total_value=20_000.0,
            as_of_date="2025-01-15",
        )

        assert len(recs) == 1
        assert recs[0].action == "buy"
        # 25% cap on 20k means max position value = 5k. Current=4.8k, so max add = 200 => 2 shares.
        assert recs[0].quantity == 2


class TestCashFundingRotation:
    @pytest.mark.asyncio
    async def test_apply_cash_constraint_requests_funding_sells_when_budget_short(self):
        engine = RebalanceEngine(db=MagicMock())
        engine._settings = MagicMock()
        engine._settings.get = AsyncMock(side_effect=lambda key, default=None: default)
        engine._portfolio = MagicMock()
        engine._portfolio.total_cash_eur = AsyncMock(return_value=0.0)
        engine._currency = MagicMock()
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        engine._currency.get_rate = AsyncMock(return_value=1.0)

        buy = TradeRecommendation(
            symbol="AAPL",
            action="buy",
            current_allocation=0.0,
            target_allocation=0.2,
            allocation_delta=0.2,
            current_value_eur=0.0,
            target_value_eur=2000.0,
            value_delta_eur=2000.0,
            quantity=20,
            price=100.0,
            currency="EUR",
            lot_size=1,
            contrarian_score=0.8,
            priority=10.0,
            reason="buy",
        )
        funding_sell = TradeRecommendation(
            symbol="OLD",
            action="sell",
            current_allocation=0.2,
            target_allocation=0.0,
            allocation_delta=-0.2,
            current_value_eur=2000.0,
            target_value_eur=0.0,
            value_delta_eur=-2000.0,
            quantity=20,
            price=100.0,
            currency="EUR",
            lot_size=1,
            contrarian_score=0.1,
            priority=1000.0,
            reason="funding",
        )

        engine._generate_deficit_sells = AsyncMock(return_value=[funding_sell])
        recs = await engine._apply_cash_constraint([buy], min_trade_value=100.0, as_of_date="2025-01-15")

        engine._generate_deficit_sells.assert_awaited()
        assert any(r.action == "sell" and r.symbol == "OLD" for r in recs)


class TestOpportunityThrottle:
    @pytest.mark.asyncio
    async def test_throttle_keeps_top_ranked_opportunity_buys(self):
        engine = RebalanceEngine(db=MagicMock())
        engine._settings = MagicMock()
        settings_values = {
            "strategy_max_opportunity_buys_per_cycle": 2,
            "strategy_max_new_opportunity_buys_per_cycle": 1,
        }
        engine._settings.get = AsyncMock(side_effect=lambda key, default=None: settings_values.get(key, default))

        sell = TradeRecommendation(
            symbol="SELL1",
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
            priority=50.0,
            reason="sell",
        )
        # opportunity new
        o1 = TradeRecommendation(
            symbol="O1",
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
            priority=20.0,
            reason="buy",
            sleeve="opportunity",
        )
        o2 = TradeRecommendation(
            symbol="O2",
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
            priority=10.0,
            reason="buy",
            sleeve="opportunity",
        )
        # opportunity add-ons
        a1 = TradeRecommendation(
            symbol="A1",
            action="buy",
            current_allocation=0.05,
            target_allocation=0.1,
            allocation_delta=0.05,
            current_value_eur=500.0,
            target_value_eur=1000.0,
            value_delta_eur=500.0,
            quantity=5,
            price=100.0,
            currency="EUR",
            lot_size=1,
            contrarian_score=0.9,
            priority=30.0,
            reason="buy",
            sleeve="opportunity",
        )
        non_opp = TradeRecommendation(
            symbol="CORE1",
            action="buy",
            current_allocation=0.02,
            target_allocation=0.05,
            allocation_delta=0.03,
            current_value_eur=200.0,
            target_value_eur=500.0,
            value_delta_eur=300.0,
            quantity=3,
            price=100.0,
            currency="EUR",
            lot_size=1,
            contrarian_score=0.4,
            priority=5.0,
            reason="buy",
            sleeve="core",
        )

        out = await engine._apply_opportunity_buy_throttle([sell, o1, o2, a1, non_opp])
        buy_syms = [r.symbol for r in out if r.action == "buy"]
        # one new (O1 top), one add-on (A1 top), plus non-opportunity buy preserved
        assert "O1" in buy_syms
        assert "A1" in buy_syms
        assert "O2" not in buy_syms
        assert "CORE1" in buy_syms


class TestPlannerAsOfPropagation:
    @pytest.mark.asyncio
    async def test_get_recommendations_propagates_as_of_to_components(self):
        planner = Planner(db=MagicMock(), broker=MagicMock(), portfolio=MagicMock())

        planner._allocation_calculator.calculate_ideal_portfolio = AsyncMock(return_value={"AAA": 1.0})
        planner._portfolio_analyzer.get_current_allocations = AsyncMock(return_value={"AAA": 1.0})
        planner._portfolio_analyzer.get_total_value = AsyncMock(return_value=1000.0)
        planner._rebalance_engine.get_recommendations = AsyncMock(return_value=[])

        await planner.get_recommendations(as_of_date="2025-01-01")

        planner._allocation_calculator.calculate_ideal_portfolio.assert_awaited_once_with(as_of_date="2025-01-01")
        planner._portfolio_analyzer.get_current_allocations.assert_awaited_once_with(as_of_date="2025-01-01")
        planner._portfolio_analyzer.get_total_value.assert_awaited_once_with(as_of_date="2025-01-01")
        planner._rebalance_engine.get_recommendations.assert_awaited_once_with(
            ideal={"AAA": 1.0},
            current={"AAA": 1.0},
            total_value=1000.0,
            min_trade_value=None,
            as_of_date="2025-01-01",
        )


class TestTrancheAndRotationRules:
    def test_desired_tranche_stage_mapping(self):
        assert desired_tranche_stage(-0.10) == 0
        assert desired_tranche_stage(-0.12) == 1
        assert desired_tranche_stage(-0.20) == 2
        assert desired_tranche_stage(-0.28) == 3

    def test_forced_exit_on_momentum_rollover_after_recovery(self):
        signal = {"mom20": -0.02, "mom60": 0.01, "lot_size": 1}
        state = {"scaleout_stage": 1, "last_entry_price": 100.0}
        forced = get_forced_opportunity_exit(
            signal=signal,
            state=state,
            current_qty=10,
            price=112.0,
            avg_cost=100.0,
            as_of_date=None,
            time_stop_days=90,
        )
        assert forced is not None
        assert forced["reason_code"] == "exit_momentum"

    def test_recent_dd252_min_captures_prior_dip_event(self):
        closes = [100.0] * 260 + [95.0, 90.0, 88.0, 92.0, 95.0, 97.0, 99.0]
        recent_min = recent_dd252_min(closes_oldest_first=closes, window_days=42)
        assert recent_min <= -0.10
