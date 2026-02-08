"""Tests for database operations.

These tests verify the intended behavior of the Database class:
1. Connection management and singleton pattern
2. Settings CRUD operations
3. Securities CRUD operations
4. Positions CRUD operations
5. Price history operations
6. Schema initialization
"""

import json
import os
import tempfile
from datetime import datetime

import pytest
import pytest_asyncio

from sentinel.database import Database


def _ts(iso: str) -> int:
    """Parse ISO datetime string to unix timestamp (for trades.executed_at)."""
    return int(datetime.fromisoformat(iso).timestamp())


@pytest_asyncio.fixture
async def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Create database instance
    db = Database(db_path)
    await db.connect()

    yield db

    # Cleanup
    await db.close()
    db.remove_from_cache()
    if os.path.exists(db_path):
        os.unlink(db_path)
    # Also clean up WAL files
    for ext in ["-wal", "-shm"]:
        wal_path = db_path + ext
        if os.path.exists(wal_path):
            os.unlink(wal_path)


class TestDatabaseConnection:
    """Tests for database connection management."""

    @pytest.mark.asyncio
    async def test_connect_creates_file(self):
        """Connecting creates the database file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = Database(db_path)
            await db.connect()

            assert os.path.exists(db_path)

            await db.close()
            db.remove_from_cache()

    @pytest.mark.asyncio
    async def test_connect_is_idempotent(self, temp_db):
        """Multiple connect calls are safe."""
        # Already connected in fixture
        await temp_db.connect()
        await temp_db.connect()
        # Should not raise

    @pytest.mark.asyncio
    async def test_conn_property_raises_before_connect(self):
        """Accessing conn before connect raises error."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        db = Database(db_path)
        db.remove_from_cache()  # Force new instance

        db = Database(db_path)

        with pytest.raises(RuntimeError, match="not connected"):
            _ = db.conn

        db.remove_from_cache()
        os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_close_clears_connection(self, temp_db):
        """Closing clears the connection."""
        await temp_db.close()

        with pytest.raises(RuntimeError):
            _ = temp_db.conn


class TestSettings:
    """Tests for settings operations."""

    @pytest.mark.asyncio
    async def test_get_setting_default(self, temp_db):
        """Getting non-existent setting returns default."""
        result = await temp_db.get_setting("nonexistent", "default_value")
        assert result == "default_value"

    @pytest.mark.asyncio
    async def test_set_and_get_string(self, temp_db):
        """Set and get string setting."""
        await temp_db.set_setting("test_key", "test_value")
        result = await temp_db.get_setting("test_key")
        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_set_and_get_number(self, temp_db):
        """Set and get numeric setting."""
        await temp_db.set_setting("number_key", 42)
        result = await temp_db.get_setting("number_key")
        assert result == 42

    @pytest.mark.asyncio
    async def test_set_and_get_float(self, temp_db):
        """Set and get float setting."""
        await temp_db.set_setting("float_key", 3.14159)
        result = await temp_db.get_setting("float_key")
        assert abs(result - 3.14159) < 0.00001

    @pytest.mark.asyncio
    async def test_set_and_get_bool(self, temp_db):
        """Set and get boolean setting."""
        await temp_db.set_setting("bool_key", True)
        result = await temp_db.get_setting("bool_key")
        assert result is True

    @pytest.mark.asyncio
    async def test_set_and_get_list(self, temp_db):
        """Set and get list setting."""
        await temp_db.set_setting("list_key", [1, 2, 3])
        result = await temp_db.get_setting("list_key")
        assert result == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_set_and_get_dict(self, temp_db):
        """Set and get dict setting."""
        await temp_db.set_setting("dict_key", {"a": 1, "b": 2})
        result = await temp_db.get_setting("dict_key")
        assert result == {"a": 1, "b": 2}

    @pytest.mark.asyncio
    async def test_update_setting(self, temp_db):
        """Updating a setting replaces the value."""
        await temp_db.set_setting("update_key", "old_value")
        await temp_db.set_setting("update_key", "new_value")
        result = await temp_db.get_setting("update_key")
        assert result == "new_value"

    @pytest.mark.asyncio
    async def test_get_all_settings(self, temp_db):
        """Get all settings as dict."""
        await temp_db.set_setting("key1", "value1")
        await temp_db.set_setting("key2", 42)

        all_settings = await temp_db.get_all_settings()

        assert "key1" in all_settings
        assert all_settings["key1"] == "value1"
        assert all_settings["key2"] == 42


class TestSecurities:
    """Tests for securities operations."""

    @pytest.mark.asyncio
    async def test_get_security_nonexistent(self, temp_db):
        """Getting non-existent security returns None."""
        result = await temp_db.get_security("NONEXISTENT")
        assert result is None

    @pytest.mark.asyncio
    async def test_upsert_and_get_security(self, temp_db):
        """Upsert creates new security."""
        await temp_db.upsert_security(
            "TEST.EU", name="Test Company", currency="EUR", geography="Europe", industry="Technology"
        )

        result = await temp_db.get_security("TEST.EU")

        assert result is not None
        assert result["symbol"] == "TEST.EU"
        assert result["name"] == "Test Company"
        assert result["currency"] == "EUR"
        assert result["geography"] == "Europe"
        assert result["industry"] == "Technology"

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self, temp_db):
        """Upsert updates existing security."""
        await temp_db.upsert_security("TEST.EU", name="Original Name")
        await temp_db.upsert_security("TEST.EU", name="Updated Name")

        result = await temp_db.get_security("TEST.EU")
        assert result["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_get_all_securities_active(self, temp_db):
        """Get all active securities."""
        await temp_db.upsert_security("ACTIVE1", active=1)
        await temp_db.upsert_security("ACTIVE2", active=1)
        await temp_db.upsert_security("INACTIVE", active=0)

        result = await temp_db.get_all_securities(active_only=True)

        symbols = [s["symbol"] for s in result]
        assert "ACTIVE1" in symbols
        assert "ACTIVE2" in symbols
        assert "INACTIVE" not in symbols

    @pytest.mark.asyncio
    async def test_get_all_securities_including_inactive(self, temp_db):
        """Get all securities including inactive."""
        await temp_db.upsert_security("ACTIVE", active=1)
        await temp_db.upsert_security("INACTIVE", active=0)

        result = await temp_db.get_all_securities(active_only=False)

        symbols = [s["symbol"] for s in result]
        assert "ACTIVE" in symbols
        assert "INACTIVE" in symbols

    @pytest.mark.asyncio
    async def test_update_quote_data(self, temp_db):
        """Update quote data for security."""
        await temp_db.upsert_security("TEST.EU")

        quote_data = {"ltp": 100.5, "chg5": 2.5, "chg22": 5.0}
        await temp_db.update_quote_data("TEST.EU", quote_data)

        result = await temp_db.get_security("TEST.EU")
        assert result["quote_data"] is not None

        stored_quote = json.loads(result["quote_data"])
        assert stored_quote["ltp"] == 100.5
        assert stored_quote["chg5"] == 2.5


class TestPositions:
    """Tests for position operations."""

    @pytest.mark.asyncio
    async def test_get_position_nonexistent(self, temp_db):
        """Getting non-existent position returns None."""
        result = await temp_db.get_position("NONEXISTENT")
        assert result is None

    @pytest.mark.asyncio
    async def test_upsert_and_get_position(self, temp_db):
        """Upsert creates new position."""
        await temp_db.upsert_position("TEST.EU", quantity=100, avg_cost=50.0, current_price=55.0, currency="EUR")

        result = await temp_db.get_position("TEST.EU")

        assert result is not None
        assert result["symbol"] == "TEST.EU"
        assert result["quantity"] == 100
        assert result["avg_cost"] == 50.0
        assert result["current_price"] == 55.0

    @pytest.mark.asyncio
    async def test_upsert_updates_existing_position(self, temp_db):
        """Upsert updates existing position."""
        await temp_db.upsert_position("TEST.EU", quantity=100)
        await temp_db.upsert_position("TEST.EU", quantity=150)

        result = await temp_db.get_position("TEST.EU")
        assert result["quantity"] == 150

    @pytest.mark.asyncio
    async def test_get_all_positions(self, temp_db):
        """Get all positions with quantity > 0."""
        await temp_db.upsert_position("POS1", quantity=100)
        await temp_db.upsert_position("POS2", quantity=50)
        await temp_db.upsert_position("EMPTY", quantity=0)

        result = await temp_db.get_all_positions()

        symbols = [p["symbol"] for p in result]
        assert "POS1" in symbols
        assert "POS2" in symbols
        assert "EMPTY" not in symbols


class TestPrices:
    """Tests for price history operations."""

    @pytest.mark.asyncio
    async def test_save_and_get_prices(self, temp_db):
        """Save and retrieve price history."""
        prices = [
            {"date": "2024-01-01", "open": 100, "high": 105, "low": 98, "close": 102, "volume": 1000},
            {"date": "2024-01-02", "open": 102, "high": 108, "low": 101, "close": 106, "volume": 1200},
        ]
        await temp_db.save_prices("TEST", prices)

        result = await temp_db.get_prices("TEST")

        assert len(result) == 2
        # Results are ordered by date DESC
        assert result[0]["date"] == "2024-01-02"
        assert result[0]["close"] == 106

    @pytest.mark.asyncio
    async def test_get_prices_with_limit(self, temp_db):
        """Get prices with limit."""
        prices = [{"date": f"2024-01-{i:02d}", "close": 100 + i} for i in range(1, 11)]
        await temp_db.save_prices("TEST", prices)

        result = await temp_db.get_prices("TEST", days=5)

        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_get_prices_end_date(self, temp_db):
        """get_prices with end_date returns only rows with date <= end_date."""
        prices = [
            {"date": f"2024-01-{i:02d}", "open": 100, "high": 101, "low": 99, "close": 100 + i, "volume": 1000}
            for i in range(1, 11)
        ]
        await temp_db.save_prices("TEST", prices)

        result = await temp_db.get_prices("TEST", end_date="2024-01-05")

        assert len(result) == 5
        assert result[0]["date"] == "2024-01-05"
        assert result[-1]["date"] == "2024-01-01"

    @pytest.mark.asyncio
    async def test_save_prices_upserts(self, temp_db):
        """Saving prices updates existing records."""
        await temp_db.save_prices("TEST", [{"date": "2024-01-01", "close": 100}])
        await temp_db.save_prices("TEST", [{"date": "2024-01-01", "close": 105}])

        result = await temp_db.get_prices("TEST")
        assert len(result) == 1
        assert result[0]["close"] == 105

    @pytest.mark.asyncio
    async def test_save_prices_merges(self, temp_db):
        """save_prices merges new data with existing (upsert)."""
        await temp_db.save_prices(
            "TEST",
            [
                {"date": "2024-01-01", "close": 100},
                {"date": "2024-01-02", "close": 101},
            ],
        )

        # Upsert: update existing date, add new date
        await temp_db.save_prices(
            "TEST",
            [
                {"date": "2024-01-02", "close": 105},  # Update existing
                {"date": "2024-01-03", "close": 102},  # Add new
            ],
        )

        result = await temp_db.get_prices("TEST")
        # Should have all 3 dates (01, 02 updated, 03 new)
        assert len(result) == 3
        prices_by_date = {r["date"]: r["close"] for r in result}
        assert prices_by_date["2024-01-01"] == 100  # Preserved
        assert prices_by_date["2024-01-02"] == 105  # Updated
        assert prices_by_date["2024-01-03"] == 102  # New

    @pytest.mark.asyncio
    async def test_get_prices_bulk_end_date(self, temp_db):
        """get_prices_bulk(symbols, days=N, end_date=date_str) returns only rows with date <= end_date."""
        for sym in ["A", "B"]:
            prices = [
                {"date": f"2024-01-{i:02d}", "open": 100, "high": 101, "low": 99, "close": 100 + i, "volume": 1000}
                for i in range(1, 11)
            ]
            await temp_db.save_prices(sym, prices)

        result = await temp_db.get_prices_bulk(["A", "B"], days=20, end_date="2024-01-05")

        assert "A" in result
        assert "B" in result
        for sym in ["A", "B"]:
            rows = result[sym]
            assert all(r["date"] <= "2024-01-05" for r in rows)
            assert len(rows) == 5
            assert rows[0]["date"] == "2024-01-05"
            assert rows[-1]["date"] == "2024-01-01"


class TestTrades:
    """Tests for trade operations (now using broker-synced trades)."""

    @pytest.mark.asyncio
    async def test_upsert_trade(self, temp_db):
        """Upsert a trade."""
        trade_id = await temp_db.upsert_trade(
            broker_trade_id="123",
            symbol="TEST",
            side="BUY",
            quantity=10.0,
            price=150.0,
            executed_at=_ts("2024-01-15T10:00:00"),
            raw_data={"id": "123", "qty": 100, "price": 50.0},
        )

        assert trade_id is not None

    @pytest.mark.asyncio
    async def test_get_trades(self, temp_db):
        """Get trade history."""
        await temp_db.upsert_trade(
            broker_trade_id="1",
            symbol="TEST",
            side="BUY",
            quantity=10.0,
            price=150.0,
            executed_at=_ts("2024-01-15T10:00:00"),
            raw_data={"id": "1"},
        )
        await temp_db.upsert_trade(
            broker_trade_id="2",
            symbol="TEST",
            side="SELL",
            quantity=10.0,
            price=150.0,
            executed_at=_ts("2024-01-16T10:00:00"),
            raw_data={"id": "2"},
        )

        result = await temp_db.get_trades(symbol="TEST")

        assert len(result) == 2
        # Verify both trades exist (order depends on implementation)
        sides = {r["side"] for r in result}
        assert "BUY" in sides
        assert "SELL" in sides

    @pytest.mark.asyncio
    async def test_get_trades_with_limit(self, temp_db):
        """Get trades with limit."""
        for i in range(10):
            await temp_db.upsert_trade(
                broker_trade_id=f"trade_{i}",
                symbol="TEST",
                side="BUY",
                quantity=10.0,
                price=150.0,
                executed_at=_ts(f"2024-01-{10 + i:02d}T10:00:00"),
                raw_data={"id": f"trade_{i}"},
            )

        result = await temp_db.get_trades(symbol="TEST", limit=5)

        assert len(result) == 5


class TestCashBalances:
    """Tests for cash balance operations."""

    @pytest.mark.asyncio
    async def test_get_cash_balances_empty(self, temp_db):
        """Empty database returns empty dict."""
        result = await temp_db.get_cash_balances()
        assert result == {}

    @pytest.mark.asyncio
    async def test_set_and_get_cash_balance(self, temp_db):
        """Set and get single cash balance."""
        await temp_db.set_cash_balance("EUR", 10000.0)

        result = await temp_db.get_cash_balances()
        assert "EUR" in result
        assert result["EUR"] == 10000.0

    @pytest.mark.asyncio
    async def test_set_cash_balances_bulk(self, temp_db):
        """Set multiple cash balances at once."""
        balances = {"EUR": 10000.0, "USD": 5000.0, "GBP": 2000.0}
        await temp_db.set_cash_balances(balances)

        result = await temp_db.get_cash_balances()
        assert result["EUR"] == 10000.0
        assert result["USD"] == 5000.0
        assert result["GBP"] == 2000.0

    @pytest.mark.asyncio
    async def test_set_cash_balances_clears_existing(self, temp_db):
        """set_cash_balances clears existing balances."""
        await temp_db.set_cash_balance("EUR", 10000.0)
        await temp_db.set_cash_balances({"USD": 5000.0})

        result = await temp_db.get_cash_balances()
        assert "EUR" not in result
        assert "USD" in result

    @pytest.mark.asyncio
    async def test_zero_balance_stored(self, temp_db):
        """Zero balances are stored."""
        await temp_db.set_cash_balances({"EUR": 0.0, "USD": 100.0})

        result = await temp_db.get_cash_balances()
        assert "EUR" in result
        assert result["EUR"] == 0.0
        assert "USD" in result

    @pytest.mark.asyncio
    async def test_negative_balance_stored(self, temp_db):
        """Negative balances (margin) are stored correctly."""
        await temp_db.set_cash_balances({"EUR": -2309.04, "USD": 7.5, "GBP": -2.11})

        result = await temp_db.get_cash_balances()
        assert result["EUR"] == -2309.04
        assert result["USD"] == 7.5
        assert result["GBP"] == -2.11


class TestAllocationTargets:
    """Tests for allocation target operations."""

    @pytest.mark.asyncio
    async def test_get_allocation_targets_empty(self, temp_db):
        """Empty database returns empty list."""
        result = await temp_db.get_allocation_targets()
        assert result == []

    @pytest.mark.asyncio
    async def test_set_and_get_allocation_target(self, temp_db):
        """Set and get allocation target."""
        await temp_db.set_allocation_target("geography", "Europe", 0.6)

        result = await temp_db.get_allocation_targets("geography")
        assert len(result) == 1
        assert result[0]["type"] == "geography"
        assert result[0]["name"] == "Europe"
        assert result[0]["weight"] == 0.6

    @pytest.mark.asyncio
    async def test_get_allocation_targets_by_type(self, temp_db):
        """Get allocation targets filtered by type."""
        await temp_db.set_allocation_target("geography", "Europe", 0.6)
        await temp_db.set_allocation_target("geography", "USA", 0.4)
        await temp_db.set_allocation_target("industry", "Technology", 0.5)

        geo_result = await temp_db.get_allocation_targets("geography")
        ind_result = await temp_db.get_allocation_targets("industry")

        assert len(geo_result) == 2
        assert len(ind_result) == 1

    @pytest.mark.asyncio
    async def test_delete_allocation_target(self, temp_db):
        """Delete an allocation target."""
        await temp_db.set_allocation_target("geography", "Europe", 0.6)
        await temp_db.delete_allocation_target("geography", "Europe")

        result = await temp_db.get_allocation_targets()
        assert len(result) == 0


class TestSchemaInitialization:
    """Tests for schema initialization."""

    @pytest.mark.asyncio
    async def test_schema_creates_required_tables(self, temp_db):
        """Schema creates all required tables."""
        cursor = await temp_db.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in await cursor.fetchall()]

        required_tables = [
            "settings",
            "securities",
            "positions",
            "prices",
            "trades",
            "allocation_targets",
            "cash_balances",
        ]

        for table in required_tables:
            assert table in tables, f"Missing table: {table}"


class TestCategories:
    """Tests for get_categories() which returns geography/industry values from securities."""

    @pytest.mark.asyncio
    async def test_get_categories_all(self, temp_db):
        """get_categories() with no filter returns both geographies and industries."""
        await temp_db.upsert_security("SYM1", geography="Europe", industry="Technology", active=1)
        await temp_db.upsert_security("SYM2", geography="US", industry="Finance", active=1)

        result = await temp_db.get_categories()

        assert "Europe" in result["geographies"]
        assert "US" in result["geographies"]
        assert "Technology" in result["industries"]
        assert "Finance" in result["industries"]

    @pytest.mark.asyncio
    async def test_get_categories_active_only(self, temp_db):
        """get_categories(active_only=True) returns only categories from active securities."""
        await temp_db.upsert_security("ACTIVE", geography="Europe", industry="Technology", active=1)
        await temp_db.upsert_security("INACTIVE", geography="Asia", industry="Energy", active=0)

        result = await temp_db.get_categories(active_only=True)

        assert "Europe" in result["geographies"]
        assert "Technology" in result["industries"]
        assert "Asia" not in result["geographies"]
        assert "Energy" not in result["industries"]

    @pytest.mark.asyncio
    async def test_get_categories_csv_splitting(self, temp_db):
        """get_categories() splits CSV geography/industry values into separate entries."""
        await temp_db.upsert_security("SYM1", geography="US, Europe", industry="Technology", active=1)

        result = await temp_db.get_categories()

        assert "US" in result["geographies"]
        assert "Europe" in result["geographies"]


class TestBuildTradesWhere:
    """Tests for _build_trades_where() helper method."""

    def test_build_trades_where_no_filters(self, temp_db):
        """No filters returns base WHERE clause."""
        where, params = temp_db._build_trades_where()
        assert where == "WHERE 1=1"
        assert params == []

    def test_build_trades_where_symbol(self, temp_db):
        """Symbol filter adds AND symbol = ? clause."""
        where, params = temp_db._build_trades_where(symbol="TEST")
        assert "AND symbol = ?" in where
        assert "TEST" in params

    def test_build_trades_where_all_filters(self, temp_db):
        """All filters produce all expected AND conditions (executed_at as unix timestamps)."""
        from datetime import datetime

        where, params = temp_db._build_trades_where(
            symbol="TEST",
            side="BUY",
            start_date="2024-01-01",
            end_date="2024-01-15",
        )
        assert "AND symbol = ?" in where
        assert "AND side = ?" in where
        assert "AND executed_at >= ?" in where
        assert "AND executed_at <= ?" in where
        assert "TEST" in params
        assert "BUY" in params
        start_ts = int(datetime.strptime("2024-01-01", "%Y-%m-%d").timestamp())
        assert start_ts in params

    def test_build_trades_where_end_date_appends_time(self, temp_db):
        """end_date parameter converts to end-of-day unix timestamp."""
        from datetime import datetime

        where, params = temp_db._build_trades_where(end_date="2024-01-15")
        end_ts = int(datetime.strptime("2024-01-15 23:59:59", "%Y-%m-%d %H:%M:%S").timestamp())
        assert end_ts in params


class TestPortfolioSnapshots:
    """Tests for JSON-based portfolio_snapshots table."""

    @pytest.mark.asyncio
    async def test_upsert_and_get_snapshot(self, temp_db):
        """Round-trip: upsert a snapshot with positions + cash, get it back."""
        data = {
            "positions": {
                "AAPL.US": {"quantity": 10, "value_eur": 2500.00},
                "VUAA.EU": {"quantity": 50, "value_eur": 3200.00},
            },
            "cash_eur": 1500.00,
        }
        ts = 1706745600  # 2024-02-01 midnight UTC
        await temp_db.upsert_portfolio_snapshot(ts, data)

        snapshots = await temp_db.get_portfolio_snapshots()
        assert len(snapshots) == 1
        snap = snapshots[0]
        assert snap["date"] == ts
        assert isinstance(snap["data"], dict)
        assert snap["data"]["cash_eur"] == 1500.00
        assert snap["data"]["positions"]["AAPL.US"]["quantity"] == 10
        assert snap["data"]["positions"]["VUAA.EU"]["value_eur"] == 3200.00

    @pytest.mark.asyncio
    async def test_get_snapshots_returns_date_and_data(self, temp_db):
        """Each returned dict has 'date' (int) and 'data' (dict)."""
        await temp_db.upsert_portfolio_snapshot(1706745600, {"positions": {}, "cash_eur": 100.0})
        snapshots = await temp_db.get_portfolio_snapshots()
        snap = snapshots[0]
        assert "date" in snap
        assert "data" in snap
        assert isinstance(snap["date"], int)
        assert isinstance(snap["data"], dict)

    @pytest.mark.asyncio
    async def test_get_snapshots_ordered_ascending(self, temp_db):
        """Multiple dates are returned oldest first."""
        ts1 = 1706745600  # Feb 1
        ts2 = 1706832000  # Feb 2
        ts3 = 1706918400  # Feb 3
        for ts in [ts3, ts1, ts2]:  # Insert out of order
            await temp_db.upsert_portfolio_snapshot(ts, {"positions": {}, "cash_eur": 0.0})
        snapshots = await temp_db.get_portfolio_snapshots()
        dates = [s["date"] for s in snapshots]
        assert dates == [ts1, ts2, ts3]

    @pytest.mark.asyncio
    async def test_get_snapshots_days_filter(self, temp_db):
        """Insert 30 days of snapshots, request last 7, verify only 7 returned."""
        import time

        now = int(time.time())
        base = now - 30 * 86400  # 30 days ago
        for i in range(30):
            ts = base + i * 86400
            await temp_db.upsert_portfolio_snapshot(ts, {"positions": {}, "cash_eur": float(i)})

        snapshots = await temp_db.get_portfolio_snapshots(days=7)
        assert len(snapshots) == 7
        # All returned dates should be within last 7 days
        cutoff = now - 7 * 86400
        for s in snapshots:
            assert s["date"] >= cutoff

    @pytest.mark.asyncio
    async def test_get_latest_snapshot_date(self, temp_db):
        """Returns int timestamp of most recent snapshot."""
        ts1 = 1706745600
        ts2 = 1706832000
        await temp_db.upsert_portfolio_snapshot(ts1, {"positions": {}, "cash_eur": 0.0})
        await temp_db.upsert_portfolio_snapshot(ts2, {"positions": {}, "cash_eur": 0.0})
        latest = await temp_db.get_latest_snapshot_date()
        assert latest == ts2
        assert isinstance(latest, int)

    @pytest.mark.asyncio
    async def test_get_latest_snapshot_date_empty(self, temp_db):
        """Returns None when no snapshots exist."""
        latest = await temp_db.get_latest_snapshot_date()
        assert latest is None

    @pytest.mark.asyncio
    async def test_get_portfolio_snapshot_dates_range(self, temp_db):
        """Returns only snapshot dates inside the optional range."""
        ts1 = 1706745600  # 2024-02-01
        ts2 = 1706832000  # 2024-02-02
        ts3 = 1706918400  # 2024-02-03
        for ts in [ts1, ts2, ts3]:
            await temp_db.upsert_portfolio_snapshot(ts, {"positions": {}, "cash_eur": 0.0})

        dates_all = await temp_db.get_portfolio_snapshot_dates()
        dates_ranged = await temp_db.get_portfolio_snapshot_dates(start_ts=ts2, end_ts=ts3)
        dates_start_only = await temp_db.get_portfolio_snapshot_dates(start_ts=ts2)

        assert dates_all == [ts1, ts2, ts3]
        assert dates_ranged == [ts2, ts3]
        assert dates_start_only == [ts2, ts3]

    @pytest.mark.asyncio
    async def test_upsert_replaces_existing(self, temp_db):
        """Upsert same date twice, second data wins."""
        ts = 1706745600
        await temp_db.upsert_portfolio_snapshot(
            ts, {"positions": {"A": {"quantity": 1, "value_eur": 100}}, "cash_eur": 50.0}
        )
        await temp_db.upsert_portfolio_snapshot(
            ts, {"positions": {"B": {"quantity": 2, "value_eur": 200}}, "cash_eur": 75.0}
        )

        snapshots = await temp_db.get_portfolio_snapshots()
        assert len(snapshots) == 1
        assert "B" in snapshots[0]["data"]["positions"]
        assert "A" not in snapshots[0]["data"]["positions"]
        assert snapshots[0]["data"]["cash_eur"] == 75.0


class TestStrategyState:
    """Tests for deterministic strategy state table helpers."""

    @pytest.mark.asyncio
    async def test_upsert_and_get_strategy_state(self, temp_db):
        await temp_db.upsert_strategy_state(
            "AAPL.US",
            sleeve="opportunity",
            tranche_stage=2,
            scaleout_stage=1,
            last_entry_price=150.0,
            last_entry_ts=1700000000,
            updated_at=1700000100,
        )

        state = await temp_db.get_strategy_state("AAPL.US")
        assert state is not None
        assert state["sleeve"] == "opportunity"
        assert state["tranche_stage"] == 2
        assert state["scaleout_stage"] == 1

    @pytest.mark.asyncio
    async def test_get_strategy_states_by_symbol_subset(self, temp_db):
        await temp_db.upsert_strategy_state("AAPL.US", sleeve="core", updated_at=1)
        await temp_db.upsert_strategy_state("MSFT.US", sleeve="opportunity", updated_at=2)

        states = await temp_db.get_strategy_states(["AAPL.US"])
        assert "AAPL.US" in states
        assert "MSFT.US" not in states

    @pytest.mark.asyncio
    async def test_get_portfolio_snapshot_as_of(self, temp_db):
        await temp_db.upsert_portfolio_snapshot(1700000000, {"positions": {}, "cash_eur": 100.0})
        await temp_db.upsert_portfolio_snapshot(1700100000, {"positions": {}, "cash_eur": 200.0})

        snap = await temp_db.get_portfolio_snapshot_as_of(1700050000)
        assert snap is not None
        assert snap["date"] == 1700000000
        assert snap["data"]["cash_eur"] == 100.0
