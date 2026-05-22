"""Tests for the benchmark-indices storage layer.

Benchmarks live in their own tables (`benchmarks`, `benchmark_prices`) —
completely separate from `securities`/`prices` — so that index symbols and
their daily closes never get confused with tradable rows.
"""

from __future__ import annotations

import os
import tempfile

import pytest
import pytest_asyncio

from sentinel.database import Database


@pytest_asyncio.fixture
async def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    db = Database(path)
    await db.connect()
    yield db
    await db.close()
    db.remove_from_cache()
    for ext in ["", "-wal", "-shm"]:
        p = path + ext
        if os.path.exists(p):
            os.unlink(p)


class TestBenchmarksSchema:
    @pytest.mark.asyncio
    async def test_benchmarks_table_created(self, temp_db):
        cursor = await temp_db.conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='benchmarks'")
        assert (await cursor.fetchone()) is not None

    @pytest.mark.asyncio
    async def test_benchmark_prices_table_created(self, temp_db):
        cursor = await temp_db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='benchmark_prices'"
        )
        assert (await cursor.fetchone()) is not None

    @pytest.mark.asyncio
    async def test_benchmarks_and_securities_are_independent_tables(self, temp_db):
        """Sanity: a row in `securities` does not appear in `benchmarks`."""
        await temp_db.upsert_security("AAPL.US", name="Apple Inc.")
        all_b = await temp_db.get_benchmarks()
        assert all_b == []


class TestUpsertBenchmark:
    @pytest.mark.asyncio
    async def test_insert_new(self, temp_db):
        await temp_db.upsert_benchmark(
            "SP500.IDX",
            name="Index S&P 500",
            mkt_short_code="FIX",
            instr_kind_c=1,
            currency="USD",
        )
        rows = await temp_db.get_benchmarks()
        assert len(rows) == 1
        row = rows[0]
        assert row["symbol"] == "SP500.IDX"
        assert row["name"] == "Index S&P 500"
        assert row["mkt_short_code"] == "FIX"
        assert row["instr_kind_c"] == 1
        assert row["currency"] == "USD"
        assert row["created_at"] > 0

    @pytest.mark.asyncio
    async def test_upsert_updates_metadata_preserves_created_at(self, temp_db):
        await temp_db.upsert_benchmark("SP500.IDX", name="Old name", mkt_short_code="FIX")
        first = (await temp_db.get_benchmarks())[0]

        await temp_db.upsert_benchmark("SP500.IDX", name="Index S&P 500", mkt_short_code="FIX")
        second = (await temp_db.get_benchmarks())[0]

        assert second["name"] == "Index S&P 500"
        assert second["created_at"] == first["created_at"]

    @pytest.mark.asyncio
    async def test_last_synced_records_unix_ts(self, temp_db):
        import time

        before = int(time.time())
        await temp_db.upsert_benchmark("SP500.IDX", name="S&P", mkt_short_code="FIX")
        after = int(time.time())

        row = (await temp_db.get_benchmarks())[0]
        assert before <= row["last_synced"] <= after


class TestBenchmarkPrices:
    @pytest.mark.asyncio
    async def test_save_and_read_round_trip(self, temp_db):
        await temp_db.upsert_benchmark("SP500.IDX", name="S&P", mkt_short_code="FIX")
        await temp_db.save_benchmark_prices(
            "SP500.IDX",
            [
                {"date": "2025-01-02", "close": 4720.0},
                {"date": "2025-01-03", "close": 4735.5},
            ],
        )

        prices = await temp_db.get_benchmark_prices("SP500.IDX")
        # Newest-first per the convention `get_prices` already uses.
        assert prices[0]["date"] == "2025-01-03"
        assert prices[0]["close"] == 4735.5
        assert prices[1]["date"] == "2025-01-02"

    @pytest.mark.asyncio
    async def test_save_is_idempotent(self, temp_db):
        await temp_db.upsert_benchmark("SP500.IDX", name="S&P", mkt_short_code="FIX")
        rows = [{"date": "2025-01-02", "close": 4720.0}]
        await temp_db.save_benchmark_prices("SP500.IDX", rows)
        await temp_db.save_benchmark_prices("SP500.IDX", rows)

        prices = await temp_db.get_benchmark_prices("SP500.IDX")
        assert len(prices) == 1

    @pytest.mark.asyncio
    async def test_unknown_symbol_returns_empty(self, temp_db):
        prices = await temp_db.get_benchmark_prices("NOPE.IDX")
        assert prices == []

    @pytest.mark.asyncio
    async def test_days_filter_limits_window(self, temp_db):
        await temp_db.upsert_benchmark("SP500.IDX", name="S&P", mkt_short_code="FIX")
        # Two years of monthly closes — plenty for a 1y window to drop oldest rows.
        prices = []
        for year in (2023, 2024, 2025):
            for month in range(1, 13):
                prices.append({"date": f"{year}-{month:02d}-15", "close": 4000.0 + month + year})
        await temp_db.save_benchmark_prices("SP500.IDX", prices)

        last_year = await temp_db.get_benchmark_prices("SP500.IDX", days=365)
        # All returned dates should be within the last 365 days from today
        from datetime import date, timedelta

        cutoff = (date.today() - timedelta(days=365)).isoformat()
        for p in last_year:
            assert p["date"] >= cutoff

    @pytest.mark.asyncio
    async def test_orphan_prices_rejected(self, temp_db):
        """Trying to save prices for a benchmark that doesn't exist should fail
        rather than silently creating orphan rows."""
        with pytest.raises(ValueError, match="unregistered benchmark"):
            await temp_db.save_benchmark_prices(
                "NOTREGISTERED.IDX",
                [{"date": "2025-01-02", "close": 100.0}],
            )


class TestBenchmarksListing:
    @pytest.mark.asyncio
    async def test_get_benchmarks_sorted_by_symbol(self, temp_db):
        await temp_db.upsert_benchmark("VIX.IDX", name="VIX", mkt_short_code="FIX")
        await temp_db.upsert_benchmark("SP500.IDX", name="S&P", mkt_short_code="FIX")
        await temp_db.upsert_benchmark("DAX.IDX", name="DAX", mkt_short_code="EU")

        rows = await temp_db.get_benchmarks()
        assert [r["symbol"] for r in rows] == ["DAX.IDX", "SP500.IDX", "VIX.IDX"]
