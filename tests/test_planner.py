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


class TestFeatureCaching:
    """Tests for caching feature extraction results with 24h TTL."""

    def _make_engine_with_mocks(self):
        """Create a RebalanceEngine with mocked dependencies for feature caching tests."""
        db = MagicMock()
        db.conn = MagicMock()
        db.cache_get = AsyncMock(return_value=None)
        db.cache_set = AsyncMock()
        db.get_all_securities = AsyncMock(
            return_value=[
                {
                    "symbol": "TEST.EU",
                    "currency": "EUR",
                    "min_lot": 1,
                    "allow_buy": 1,
                    "allow_sell": 1,
                    "ml_enabled": 1,
                    "ml_blend_ratio": 0.5,
                    "user_multiplier": 1.0,
                },
            ]
        )
        db.get_all_positions = AsyncMock(
            return_value=[
                {"symbol": "TEST.EU", "quantity": 10, "current_price": 100.0},
            ]
        )
        db.get_scores = AsyncMock(return_value={"TEST.EU": 0.5})
        db.get_ml_enabled_securities = AsyncMock(
            return_value=[
                {"symbol": "TEST.EU"},
            ]
        )
        db.get_trades = AsyncMock(return_value=[])
        db.get_recent_trades_for_symbol = AsyncMock(return_value=[])

        engine = RebalanceEngine(db=db)
        engine._db = db

        # Mock portfolio
        engine._portfolio = MagicMock()
        engine._portfolio.total_value = AsyncMock(return_value=50000.0)
        engine._portfolio.total_cash_eur = AsyncMock(return_value=5000.0)
        engine._portfolio.get_cash_balances = AsyncMock(return_value={"EUR": 5000.0})

        # Mock broker
        engine._broker = MagicMock()
        engine._broker.get_quotes = AsyncMock(
            return_value={
                "TEST.EU": {"price": 100.0},
            }
        )

        # Mock currency
        engine._currency = MagicMock()
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        engine._currency.get_rate = AsyncMock(return_value=1.0)

        # Mock settings
        engine._settings = MagicMock()
        engine._settings.get = AsyncMock(return_value=100.0)

        # Mock feature extractor
        engine._feature_extractor = MagicMock()
        engine._feature_extractor.extract_features = AsyncMock(
            return_value={
                "rsi_14": 55.0,
                "macd_signal": 0.5,
                "sma_50": 98.0,
            }
        )

        # Mock ML predictor
        engine._ml_predictor = MagicMock()
        engine._ml_predictor.predict_and_blend = AsyncMock(
            return_value={
                "final_score": 0.6,
                "ml_prediction": None,
                "blend_ratio": 0.5,
            }
        )

        # RebalanceEngine now uses db.get_prices(symbol, days=250, end_date=as_of_date) for hist data
        db.get_prices = AsyncMock(return_value=self._make_hist_dicts(250))

        return engine, db

    def _make_hist_dicts(self, count=250):
        """Generate mock historical price dicts (newest first, for get_prices)."""
        from datetime import datetime, timedelta

        base = datetime(2025, 1, 31).date()
        return [
            {
                "date": (base - timedelta(days=i)).isoformat(),
                "open": 100.0,
                "high": 105.0,
                "low": 95.0,
                "close": 102.0,
                "volume": 10000.0,
            }
            for i in range(count)
        ]

    def _make_hist_rows(self, count=250):
        """Generate mock historical price rows (desc order)."""
        rows = []
        for i in range(count):
            row = MagicMock()
            row.__getitem__ = lambda self, k, _i=i: {
                "date": f"2025-01-{250 - _i:03d}",
                "open": 100.0,
                "high": 105.0,
                "low": 95.0,
                "close": 102.0,
                "volume": 10000.0,
            }.get(k, 0)
            row.keys = lambda self=row: ["date", "open", "high", "low", "close", "volume"]
            rows.append(row)
        return rows

    @pytest.mark.asyncio
    async def test_features_cached_after_first_computation(self):
        """On first call, extract_features is called and result is stored in cache."""
        engine, db = self._make_engine_with_mocks()

        hist_rows = self._make_hist_rows(250)

        # Mock DB cursor for historical prices
        cursor_mock = MagicMock()
        cursor_mock.fetchall = AsyncMock(return_value=hist_rows)
        db.conn.execute = AsyncMock(return_value=cursor_mock)

        # cache_get returns None (cache miss)
        db.cache_get = AsyncMock(return_value=None)

        await engine.get_recommendations(
            ideal={"TEST.EU": 0.5},
            current={"TEST.EU": 0.4},
            total_value=50000.0,
        )

        # extract_features should have been called
        engine._feature_extractor.extract_features.assert_called_once()

        # cache_set should have been called with features key and 24h TTL
        feature_cache_calls = [c for c in db.cache_set.call_args_list if c.args[0].startswith("features:")]
        assert len(feature_cache_calls) == 1
        assert feature_cache_calls[0].args[0].startswith("features:TEST.EU:")
        assert feature_cache_calls[0].kwargs.get("ttl_seconds") == 86400

    @pytest.mark.asyncio
    async def test_cached_features_returned_on_subsequent_call(self):
        """When cache_get returns features, extract_features is NOT called."""
        import json

        engine, db = self._make_engine_with_mocks()

        hist_rows = self._make_hist_rows(250)
        cursor_mock = MagicMock()
        cursor_mock.fetchall = AsyncMock(return_value=hist_rows)
        db.conn.execute = AsyncMock(return_value=cursor_mock)

        cached_features = {"rsi_14": 55.0, "macd_signal": 0.5, "sma_50": 98.0}

        # cache_get returns None for planner:recommendations (cache miss),
        # but returns cached features for features:* key
        async def mock_cache_get(key):
            if key.startswith("features:"):
                return json.dumps(cached_features)
            return None

        db.cache_get = AsyncMock(side_effect=mock_cache_get)

        await engine.get_recommendations(
            ideal={"TEST.EU": 0.5},
            current={"TEST.EU": 0.4},
            total_value=50000.0,
        )

        # extract_features should NOT have been called (cache hit)
        engine._feature_extractor.extract_features.assert_not_called()

        # predict_and_blend should have been called with the cached features
        engine._ml_predictor.predict_and_blend.assert_called_once()
        call_kwargs = engine._ml_predictor.predict_and_blend.call_args.kwargs
        assert call_kwargs["features"] == cached_features

    @pytest.mark.asyncio
    async def test_feature_cache_key_includes_date(self):
        """Cache key uses current date so next trading day gets fresh features."""
        from datetime import datetime

        engine, db = self._make_engine_with_mocks()

        hist_rows = self._make_hist_rows(250)
        cursor_mock = MagicMock()
        cursor_mock.fetchall = AsyncMock(return_value=hist_rows)
        db.conn.execute = AsyncMock(return_value=cursor_mock)
        db.cache_get = AsyncMock(return_value=None)

        await engine.get_recommendations(
            ideal={"TEST.EU": 0.5},
            current={"TEST.EU": 0.4},
            total_value=50000.0,
        )

        today = datetime.now().strftime("%Y-%m-%d")
        expected_key = f"features:TEST.EU:{today}"

        # Verify cache_get was called with date-based key
        feature_get_calls = [c for c in db.cache_get.call_args_list if c.args[0].startswith("features:")]
        assert len(feature_get_calls) == 1
        assert feature_get_calls[0].args[0] == expected_key

    @pytest.mark.asyncio
    async def test_features_not_cached_when_insufficient_history(self):
        """When hist_rows < 200, extract_features and cache_set are not called."""
        engine, db = self._make_engine_with_mocks()

        # Only 50 rows — insufficient (code uses get_prices, not raw SQL)
        db.get_prices = AsyncMock(return_value=self._make_hist_dicts(50))
        db.cache_get = AsyncMock(return_value=None)

        await engine.get_recommendations(
            ideal={"TEST.EU": 0.5},
            current={"TEST.EU": 0.4},
            total_value=50000.0,
        )

        # extract_features should NOT have been called
        engine._feature_extractor.extract_features.assert_not_called()

        # No features:* cache_set calls
        feature_set_calls = [c for c in db.cache_set.call_args_list if c.args[0].startswith("features:")]
        assert len(feature_set_calls) == 0

    @pytest.mark.asyncio
    async def test_corrupted_cache_falls_through_to_extraction(self):
        """When cached value is corrupted JSON, extraction runs as fallback."""
        engine, db = self._make_engine_with_mocks()

        hist_rows = self._make_hist_rows(250)
        cursor_mock = MagicMock()
        cursor_mock.fetchall = AsyncMock(return_value=hist_rows)
        db.conn.execute = AsyncMock(return_value=cursor_mock)

        # cache_get returns corrupted data for features key
        async def mock_cache_get(key):
            if key.startswith("features:"):
                return "NOT_VALID_JSON{{"
            return None

        db.cache_get = AsyncMock(side_effect=mock_cache_get)

        await engine.get_recommendations(
            ideal={"TEST.EU": 0.5},
            current={"TEST.EU": 0.4},
            total_value=50000.0,
        )

        # Despite cache hit with corrupted data, extraction should have run
        engine._feature_extractor.extract_features.assert_called_once()

        # And valid features should have been cached (overwriting the corrupt entry)
        feature_set_calls = [c for c in db.cache_set.call_args_list if c.args[0].startswith("features:")]
        assert len(feature_set_calls) == 1
