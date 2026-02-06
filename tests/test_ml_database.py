"""Tests for MLDatabase — separate ML database with per-model tables."""

import asyncio
import json
import time

import pytest

from sentinel_ml.database.ml import MLDatabase

MODEL_TYPES = ["xgboost", "ridge", "rf", "svr"]


@pytest.fixture
def ml_db_path(tmp_path):
    """Return a temporary path for an ML database."""
    return str(tmp_path / "test_ml.db")


@pytest.fixture
def ml_db(ml_db_path):
    """Create and connect a temporary MLDatabase."""
    db = MLDatabase(ml_db_path)
    asyncio.get_event_loop().run_until_complete(db.connect())
    yield db
    asyncio.get_event_loop().run_until_complete(db.close())
    db.remove_from_cache()


class TestMLDatabaseSchema:
    """Test database creation and schema."""

    def test_creates_all_ml_tables(self, ml_db):
        """MLDatabase creates all expected ML tables on connect."""

        async def check():
            cursor = await ml_db.conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            rows = await cursor.fetchall()
            tables = {row["name"] for row in rows}

            # 1 training + 4 models + 4 predictions + 4 performance + 2 regime tables = 15
            expected = {"ml_training_samples", "regime_states", "regime_models"}
            for mt in MODEL_TYPES:
                expected.add(f"ml_models_{mt}")
                expected.add(f"ml_predictions_{mt}")
                expected.add(f"ml_performance_{mt}")

            assert expected.issubset(tables), f"Missing tables: {expected - tables}"

        asyncio.get_event_loop().run_until_complete(check())

    def test_wal_mode_enabled(self, ml_db):
        """WAL journal mode is enabled."""

        async def check():
            cursor = await ml_db.conn.execute("PRAGMA journal_mode")
            row = await cursor.fetchone()
            assert row[0] == "wal"

        asyncio.get_event_loop().run_until_complete(check())

    def test_singleton_pattern(self, ml_db_path):
        """Same path returns same instance."""
        db1 = MLDatabase(ml_db_path)
        db2 = MLDatabase(ml_db_path)
        assert db1 is db2
        db1.remove_from_cache()


class TestTrainingSamples:
    """Test training sample storage and retrieval."""

    def test_store_and_load_training_data(self, ml_db):
        """Store and retrieve training samples."""

        async def check():
            import pandas as pd

            df = pd.DataFrame(
                [
                    {
                        "sample_id": "s1",
                        "symbol": "AAPL",
                        "sample_date": int(time.time()) - 86400,
                        "return_1d": 0.01,
                        "return_5d": 0.03,
                        "return_20d": 0.05,
                        "return_60d": 0.1,
                        "price_normalized": 0.02,
                        "volatility_10d": 0.015,
                        "volatility_30d": 0.02,
                        "atr_14d": 0.018,
                        "volume_normalized": 1.1,
                        "volume_trend": 0.05,
                        "rsi_14": 0.55,
                        "macd": 0.01,
                        "bollinger_position": 0.6,
                        "sentiment_score": 0.5,
                        "country_agg_momentum": 0.02,
                        "country_agg_rsi": 0.52,
                        "country_agg_volatility": 0.018,
                        "industry_agg_momentum": 0.03,
                        "industry_agg_rsi": 0.48,
                        "industry_agg_volatility": 0.02,
                        "future_return": 0.05,
                        "prediction_horizon_days": 14,
                        "created_at": int(time.time()),
                    }
                ]
            )

            await ml_db.store_training_samples(df)
            X, y = await ml_db.load_training_data("AAPL")
            assert len(X) == 1
            assert len(y) == 1
            assert abs(y[0] - 0.05) < 1e-6

        asyncio.get_event_loop().run_until_complete(check())

    def test_get_symbols_with_sufficient_data(self, ml_db):
        """Get symbols meeting minimum sample threshold."""

        async def check():
            import pandas as pd

            rows = []
            for i in range(5):
                rows.append(
                    {
                        "sample_id": f"s{i}",
                        "symbol": "AAPL",
                        "sample_date": int(time.time()) - (i * 86400),
                        "return_1d": 0.01,
                        "return_5d": 0.0,
                        "return_20d": 0.0,
                        "return_60d": 0.0,
                        "price_normalized": 0.0,
                        "volatility_10d": 0.02,
                        "volatility_30d": 0.02,
                        "atr_14d": 0.02,
                        "volume_normalized": 1.0,
                        "volume_trend": 0.0,
                        "rsi_14": 0.5,
                        "macd": 0.0,
                        "bollinger_position": 0.5,
                        "sentiment_score": 0.5,
                        "country_agg_momentum": 0.0,
                        "country_agg_rsi": 0.5,
                        "country_agg_volatility": 0.02,
                        "industry_agg_momentum": 0.0,
                        "industry_agg_rsi": 0.5,
                        "industry_agg_volatility": 0.02,
                        "future_return": 0.01 * i,
                        "prediction_horizon_days": 14,
                        "created_at": int(time.time()),
                    }
                )
            df = pd.DataFrame(rows)
            await ml_db.store_training_samples(df)

            result = await ml_db.get_symbols_with_sufficient_data(3)
            assert "AAPL" in result
            assert result["AAPL"] == 5

            result2 = await ml_db.get_symbols_with_sufficient_data(10)
            assert "AAPL" not in result2

        asyncio.get_event_loop().run_until_complete(check())

    def test_get_sample_count(self, ml_db):
        """Get sample count for a symbol."""

        async def check():
            count = await ml_db.get_sample_count("NONEXISTENT")
            assert count == 0

        asyncio.get_event_loop().run_until_complete(check())


class TestPredictions:
    """Test per-model prediction storage and retrieval."""

    def test_store_and_get_prediction(self, ml_db):
        """Store and retrieve a prediction for each model type."""

        async def check():
            ts = int(time.time())
            for mt in MODEL_TYPES:
                await ml_db.store_prediction(
                    model_type=mt,
                    prediction_id=f"pred_{mt}_1",
                    symbol="AAPL",
                    predicted_at=ts,
                    features=json.dumps({"return_1d": 0.01}),
                    predicted_return=0.05,
                    ml_score=0.6,
                    regime_score=0.5,
                    regime_dampening=0.9,
                    inference_time_ms=2.5,
                )

                result = await ml_db.get_prediction_as_of(mt, "AAPL", ts)
                assert result is not None
                assert abs(result["predicted_return"] - 0.05) < 1e-6
                assert abs(result["ml_score"] - 0.6) < 1e-6

        asyncio.get_event_loop().run_until_complete(check())

    def test_get_prediction_as_of_returns_most_recent(self, ml_db):
        """get_prediction_as_of returns the most recent prediction <= as_of_ts."""

        async def check():
            ts1 = 1000000
            ts2 = 2000000
            ts3 = 3000000

            await ml_db.store_prediction("xgboost", "p1", "AAPL", ts1, None, 0.01, 0.5, None, None, 1.0)
            await ml_db.store_prediction("xgboost", "p2", "AAPL", ts2, None, 0.02, 0.6, None, None, 1.0)

            # As of ts2 should return ts2
            result = await ml_db.get_prediction_as_of("xgboost", "AAPL", ts2)
            assert abs(result["predicted_return"] - 0.02) < 1e-6

            # As of ts3 should return ts2 (most recent)
            result = await ml_db.get_prediction_as_of("xgboost", "AAPL", ts3)
            assert abs(result["predicted_return"] - 0.02) < 1e-6

            # As of before ts1 should return None
            result = await ml_db.get_prediction_as_of("xgboost", "AAPL", 500000)
            assert result is None

        asyncio.get_event_loop().run_until_complete(check())

    def test_get_all_predictions_history(self, ml_db):
        """Get all predictions for a model type."""

        async def check():
            ts = int(time.time())
            await ml_db.store_prediction("ridge", "p1", "AAPL", ts, None, 0.01, 0.5, None, None, 1.0)
            await ml_db.store_prediction("ridge", "p2", "MSFT", ts, None, 0.02, 0.6, None, None, 1.0)

            history = await ml_db.get_all_predictions_history("ridge")
            assert len(history) == 2
            symbols = {h["symbol"] for h in history}
            assert symbols == {"AAPL", "MSFT"}

        asyncio.get_event_loop().run_until_complete(check())


class TestModelRecords:
    """Test per-model model record storage and retrieval."""

    def test_update_and_get_model_record(self, ml_db):
        """Store and retrieve model records."""

        async def check():
            metrics = {
                "validation_rmse": 0.05,
                "validation_mae": 0.04,
                "validation_r2": 0.3,
            }
            await ml_db.update_model_record("xgboost", "AAPL", 500, metrics)

            status = await ml_db.get_model_status("xgboost")
            assert len(status) == 1
            assert status[0]["symbol"] == "AAPL"
            assert status[0]["training_samples"] == 500
            assert abs(status[0]["validation_r2"] - 0.3) < 1e-6

        asyncio.get_event_loop().run_until_complete(check())

    def test_get_all_model_status(self, ml_db):
        """Get status across all model types."""

        async def check():
            metrics = {"validation_rmse": 0.05, "validation_mae": 0.04, "validation_r2": 0.3}
            await ml_db.update_model_record("xgboost", "AAPL", 500, metrics)
            await ml_db.update_model_record("ridge", "AAPL", 500, metrics)

            all_status = await ml_db.get_all_model_status()
            assert "xgboost" in all_status
            assert "ridge" in all_status
            assert len(all_status["xgboost"]) == 1
            assert len(all_status["ridge"]) == 1

        asyncio.get_event_loop().run_until_complete(check())


class TestPerformanceMetrics:
    """Test per-model performance tracking."""

    def test_store_and_query_performance(self, ml_db):
        """Store and query performance metrics."""

        async def check():
            ts = int(time.time())
            metrics = {
                "mean_absolute_error": 0.03,
                "root_mean_squared_error": 0.04,
                "prediction_bias": 0.005,
                "predictions_evaluated": 10,
            }
            await ml_db.store_performance_metrics("xgboost", "AAPL", ts, metrics)

            # Verify it was stored
            cursor = await ml_db.conn.execute("SELECT * FROM ml_performance_xgboost WHERE symbol = ?", ("AAPL",))
            row = await cursor.fetchone()
            assert row is not None
            assert abs(row["mean_absolute_error"] - 0.03) < 1e-6

        asyncio.get_event_loop().run_until_complete(check())


class TestDeleteOperations:
    """Test data deletion operations."""

    def test_delete_all_data(self, ml_db):
        """delete_all_data clears all 13 tables."""

        async def check():
            import pandas as pd

            # Insert data into various tables
            ts = int(time.time())
            df = pd.DataFrame(
                [
                    {
                        "sample_id": "s1",
                        "symbol": "AAPL",
                        "sample_date": ts,
                        "return_1d": 0.0,
                        "return_5d": 0.0,
                        "return_20d": 0.0,
                        "return_60d": 0.0,
                        "price_normalized": 0.0,
                        "volatility_10d": 0.0,
                        "volatility_30d": 0.0,
                        "atr_14d": 0.0,
                        "volume_normalized": 0.0,
                        "volume_trend": 0.0,
                        "rsi_14": 0.0,
                        "macd": 0.0,
                        "bollinger_position": 0.0,
                        "sentiment_score": 0.0,
                        "country_agg_momentum": 0.0,
                        "country_agg_rsi": 0.0,
                        "country_agg_volatility": 0.0,
                        "industry_agg_momentum": 0.0,
                        "industry_agg_rsi": 0.0,
                        "industry_agg_volatility": 0.0,
                        "future_return": 0.05,
                        "prediction_horizon_days": 14,
                        "created_at": ts,
                    }
                ]
            )
            await ml_db.store_training_samples(df)
            await ml_db.store_prediction("xgboost", "p1", "AAPL", ts, None, 0.05, 0.6, None, None, 1.0)

            await ml_db.delete_all_data()

            count = await ml_db.get_sample_count("AAPL")
            assert count == 0

            result = await ml_db.get_prediction_as_of("xgboost", "AAPL", ts)
            assert result is None

        asyncio.get_event_loop().run_until_complete(check())

    def test_delete_symbol_data(self, ml_db):
        """delete_symbol_data removes data for one symbol from all tables."""

        async def check():
            import pandas as pd

            ts = int(time.time())
            rows = []
            for sym in ["AAPL", "MSFT"]:
                rows.append(
                    {
                        "sample_id": f"s_{sym}",
                        "symbol": sym,
                        "sample_date": ts,
                        "return_1d": 0.0,
                        "return_5d": 0.0,
                        "return_20d": 0.0,
                        "return_60d": 0.0,
                        "price_normalized": 0.0,
                        "volatility_10d": 0.0,
                        "volatility_30d": 0.0,
                        "atr_14d": 0.0,
                        "volume_normalized": 0.0,
                        "volume_trend": 0.0,
                        "rsi_14": 0.0,
                        "macd": 0.0,
                        "bollinger_position": 0.0,
                        "sentiment_score": 0.0,
                        "country_agg_momentum": 0.0,
                        "country_agg_rsi": 0.0,
                        "country_agg_volatility": 0.0,
                        "industry_agg_momentum": 0.0,
                        "industry_agg_rsi": 0.0,
                        "industry_agg_volatility": 0.0,
                        "future_return": 0.05,
                        "prediction_horizon_days": 14,
                        "created_at": ts,
                    }
                )
            df = pd.DataFrame(rows)
            await ml_db.store_training_samples(df)

            await ml_db.delete_symbol_data("AAPL")

            assert await ml_db.get_sample_count("AAPL") == 0
            assert await ml_db.get_sample_count("MSFT") == 1

        asyncio.get_event_loop().run_until_complete(check())
