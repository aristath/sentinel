"""Tests for trades feature - syncing trade history from Tradernet.

This tests the new trades schema with broker_trade_id, raw_data storage,
and all associated functionality.
"""

import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from sentinel.database import Database


@pytest_asyncio.fixture
async def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    db = Database(db_path)
    await db.connect()

    yield db

    await db.close()
    db.remove_from_cache()
    if os.path.exists(db_path):
        os.unlink(db_path)
    for ext in ["-wal", "-shm"]:
        wal_path = db_path + ext
        if os.path.exists(wal_path):
            os.unlink(wal_path)


class TestTradesSchema:
    """Tests for the new trades table schema."""

    @pytest.mark.asyncio
    async def test_trades_table_exists(self, temp_db):
        """Trades table is created with correct schema."""
        cursor = await temp_db.conn.execute("PRAGMA table_info(trades)")
        columns = {row[1] for row in await cursor.fetchall()}

        required_columns = {"id", "broker_trade_id", "symbol", "side", "executed_at", "raw_data"}
        assert required_columns.issubset(columns)

    @pytest.mark.asyncio
    async def test_trades_indexes_exist(self, temp_db):
        """Required indexes are created on trades table."""
        cursor = await temp_db.conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='trades'")
        indexes = {row[0] for row in await cursor.fetchall()}

        # Check for expected indexes (excluding sqlite_autoindex)
        expected_prefixes = ["idx_trades_broker_id", "idx_trades_symbol", "idx_trades_executed_at", "idx_trades_side"]
        for prefix in expected_prefixes:
            assert any(idx.startswith(prefix) for idx in indexes), f"Missing index: {prefix}"


class TestUpsertTrade:
    """Tests for upsert_trade database method."""

    @pytest.mark.asyncio
    async def test_upsert_trade_creates_new_trade(self, temp_db):
        """upsert_trade creates a new trade when broker_trade_id doesn't exist."""
        raw_data = {"id": "123", "instr_nm": "AAPL.US", "price": 150.0, "qty": 10}

        trade_id = await temp_db.upsert_trade(
            broker_trade_id="123",
            symbol="AAPL.US",
            side="BUY",
            quantity=10.0,
            price=150.0,
            executed_at="2024-01-15T10:30:00",
            raw_data=raw_data,
        )

        assert trade_id is not None

        # Verify trade was created
        trades = await temp_db.get_trades(symbol="AAPL.US")
        assert len(trades) == 1
        assert trades[0]["broker_trade_id"] == "123"
        assert trades[0]["symbol"] == "AAPL.US"
        assert trades[0]["side"] == "BUY"

    @pytest.mark.asyncio
    async def test_upsert_trade_ignores_duplicate_broker_id(self, temp_db):
        """upsert_trade ignores trades with duplicate broker_trade_id."""
        raw_data1 = {"id": "123", "price": 150.0}
        raw_data2 = {"id": "123", "price": 160.0}  # Different data, same ID

        await temp_db.upsert_trade(
            broker_trade_id="123",
            symbol="AAPL.US",
            side="BUY",
            quantity=10.0,
            price=150.0,
            executed_at="2024-01-15T10:30:00",
            raw_data=raw_data1,
        )

        # Second upsert with same broker_trade_id should not create new record
        await temp_db.upsert_trade(
            broker_trade_id="123",
            symbol="AAPL.US",
            side="BUY",
            quantity=10.0,
            price=150.0,
            executed_at="2024-01-15T10:31:00",
            raw_data=raw_data2,
        )

        trades = await temp_db.get_trades(symbol="AAPL.US")
        assert len(trades) == 1
        # Should keep original data
        assert trades[0]["raw_data"]["price"] == 150.0

    @pytest.mark.asyncio
    async def test_upsert_trade_stores_raw_data_as_json(self, temp_db):
        """upsert_trade stores raw_data as JSON that can be parsed back."""
        raw_data = {
            "id": "456",
            "instr_nm": "MSFT.US",
            "price": 380.50,
            "qty": 5,
            "commission": 2.0,
            "currency": "USD",
        }

        await temp_db.upsert_trade(
            broker_trade_id="456",
            symbol="MSFT.US",
            side="SELL",
            quantity=10.0,
            price=150.0,
            executed_at="2024-01-16T14:00:00",
            raw_data=raw_data,
        )

        trades = await temp_db.get_trades(symbol="MSFT.US")
        assert len(trades) == 1
        # raw_data should be parsed back as dict
        assert trades[0]["raw_data"]["price"] == 380.50
        assert trades[0]["raw_data"]["commission"] == 2.0


class TestGetTrades:
    """Tests for get_trades database method."""

    @pytest.mark.asyncio
    async def test_get_trades_returns_all_trades(self, temp_db):
        """get_trades returns all trades when no filters applied."""
        for i in range(3):
            await temp_db.upsert_trade(
                broker_trade_id=f"trade_{i}",
                symbol=f"SYM{i}.US",
                side="BUY",
                quantity=10.0,
                price=150.0,
                executed_at=f"2024-01-{15 + i:02d}T10:00:00",
                raw_data={"id": f"trade_{i}"},
            )

        trades = await temp_db.get_trades()
        assert len(trades) == 3

    @pytest.mark.asyncio
    async def test_get_trades_filters_by_symbol(self, temp_db):
        """get_trades filters by symbol."""
        await temp_db.upsert_trade(
            broker_trade_id="1",
            symbol="AAPL.US",
            side="BUY",
            quantity=10.0,
            price=150.0,
            executed_at="2024-01-15T10:00:00",
            raw_data={"id": "1"},
        )
        await temp_db.upsert_trade(
            broker_trade_id="2",
            symbol="MSFT.US",
            side="BUY",
            quantity=10.0,
            price=150.0,
            executed_at="2024-01-16T10:00:00",
            raw_data={"id": "2"},
        )

        trades = await temp_db.get_trades(symbol="AAPL.US")
        assert len(trades) == 1
        assert trades[0]["symbol"] == "AAPL.US"

    @pytest.mark.asyncio
    async def test_get_trades_filters_by_side(self, temp_db):
        """get_trades filters by side (BUY/SELL)."""
        await temp_db.upsert_trade(
            broker_trade_id="1",
            symbol="AAPL.US",
            side="BUY",
            quantity=10.0,
            price=150.0,
            executed_at="2024-01-15T10:00:00",
            raw_data={"id": "1"},
        )
        await temp_db.upsert_trade(
            broker_trade_id="2",
            symbol="AAPL.US",
            side="SELL",
            quantity=10.0,
            price=150.0,
            executed_at="2024-01-16T10:00:00",
            raw_data={"id": "2"},
        )

        buy_trades = await temp_db.get_trades(side="BUY")
        assert len(buy_trades) == 1
        assert buy_trades[0]["side"] == "BUY"

        sell_trades = await temp_db.get_trades(side="SELL")
        assert len(sell_trades) == 1
        assert sell_trades[0]["side"] == "SELL"

    @pytest.mark.asyncio
    async def test_get_trades_filters_by_date_range(self, temp_db):
        """get_trades filters by start_date and end_date."""
        await temp_db.upsert_trade(
            broker_trade_id="1",
            symbol="AAPL.US",
            side="BUY",
            quantity=10.0,
            price=150.0,
            executed_at="2024-01-10T10:00:00",
            raw_data={"id": "1"},
        )
        await temp_db.upsert_trade(
            broker_trade_id="2",
            symbol="AAPL.US",
            side="BUY",
            quantity=10.0,
            price=150.0,
            executed_at="2024-01-15T10:00:00",
            raw_data={"id": "2"},
        )
        await temp_db.upsert_trade(
            broker_trade_id="3",
            symbol="AAPL.US",
            side="BUY",
            quantity=10.0,
            price=150.0,
            executed_at="2024-01-20T10:00:00",
            raw_data={"id": "3"},
        )

        # Filter by start_date only
        trades = await temp_db.get_trades(start_date="2024-01-14")
        assert len(trades) == 2

        # Filter by end_date only
        trades = await temp_db.get_trades(end_date="2024-01-16")
        assert len(trades) == 2

        # Filter by both
        trades = await temp_db.get_trades(start_date="2024-01-12", end_date="2024-01-18")
        assert len(trades) == 1
        assert trades[0]["broker_trade_id"] == "2"

    @pytest.mark.asyncio
    async def test_get_trades_pagination(self, temp_db):
        """get_trades supports limit and offset for pagination."""
        for i in range(10):
            await temp_db.upsert_trade(
                broker_trade_id=f"trade_{i:02d}",
                symbol="AAPL.US",
                side="BUY",
                quantity=10.0,
                price=150.0,
                executed_at=f"2024-01-{10 + i:02d}T10:00:00",
                raw_data={"id": f"trade_{i:02d}"},
            )

        # First page
        page1 = await temp_db.get_trades(limit=3, offset=0)
        assert len(page1) == 3

        # Second page
        page2 = await temp_db.get_trades(limit=3, offset=3)
        assert len(page2) == 3

        # Pages should have different trades
        page1_ids = {t["broker_trade_id"] for t in page1}
        page2_ids = {t["broker_trade_id"] for t in page2}
        assert page1_ids.isdisjoint(page2_ids)

    @pytest.mark.asyncio
    async def test_get_trades_parses_raw_data_json(self, temp_db):
        """get_trades parses raw_data JSON back to dict."""
        raw_data = {"id": "123", "complex": {"nested": True, "list": [1, 2, 3]}}
        await temp_db.upsert_trade(
            broker_trade_id="123",
            symbol="AAPL.US",
            side="BUY",
            quantity=10.0,
            price=150.0,
            executed_at="2024-01-15T10:00:00",
            raw_data=raw_data,
        )

        trades = await temp_db.get_trades()
        assert isinstance(trades[0]["raw_data"], dict)
        assert trades[0]["raw_data"]["complex"]["nested"] is True
        assert trades[0]["raw_data"]["complex"]["list"] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_get_trades_combined_filters(self, temp_db):
        """get_trades combines multiple filters correctly."""
        # Create diverse test data
        await temp_db.upsert_trade(
            broker_trade_id="1",
            symbol="AAPL.US",
            side="BUY",
            quantity=10.0,
            price=150.0,
            executed_at="2024-01-15T10:00:00",
            raw_data={"id": "1"},
        )
        await temp_db.upsert_trade(
            broker_trade_id="2",
            symbol="AAPL.US",
            side="SELL",
            quantity=10.0,
            price=150.0,
            executed_at="2024-01-16T10:00:00",
            raw_data={"id": "2"},
        )
        await temp_db.upsert_trade(
            broker_trade_id="3",
            symbol="MSFT.US",
            side="BUY",
            quantity=10.0,
            price=150.0,
            executed_at="2024-01-15T10:00:00",
            raw_data={"id": "3"},
        )

        # Filter by symbol and side
        trades = await temp_db.get_trades(symbol="AAPL.US", side="BUY")
        assert len(trades) == 1
        assert trades[0]["broker_trade_id"] == "1"


class TestGetTradesCount:
    """Tests for get_trades_count database method (for pagination)."""

    @pytest.mark.asyncio
    async def test_get_trades_count_all(self, temp_db):
        """get_trades_count returns total count of all trades."""
        for i in range(5):
            await temp_db.upsert_trade(
                broker_trade_id=f"trade_{i}",
                symbol="AAPL.US",
                side="BUY",
                quantity=10.0,
                price=150.0,
                executed_at=f"2024-01-{15 + i:02d}T10:00:00",
                raw_data={"id": f"trade_{i}"},
            )

        count = await temp_db.get_trades_count()
        assert count == 5

    @pytest.mark.asyncio
    async def test_get_trades_count_with_filters(self, temp_db):
        """get_trades_count respects filters."""
        await temp_db.upsert_trade(
            broker_trade_id="1",
            symbol="AAPL.US",
            side="BUY",
            quantity=10.0,
            price=150.0,
            executed_at="2024-01-15T10:00:00",
            raw_data={"id": "1"},
        )
        await temp_db.upsert_trade(
            broker_trade_id="2",
            symbol="AAPL.US",
            side="SELL",
            quantity=10.0,
            price=150.0,
            executed_at="2024-01-16T10:00:00",
            raw_data={"id": "2"},
        )
        await temp_db.upsert_trade(
            broker_trade_id="3",
            symbol="MSFT.US",
            side="BUY",
            quantity=10.0,
            price=150.0,
            executed_at="2024-01-15T10:00:00",
            raw_data={"id": "3"},
        )

        # Filter by symbol
        count = await temp_db.get_trades_count(symbol="AAPL.US")
        assert count == 2

        # Filter by side
        count = await temp_db.get_trades_count(side="BUY")
        assert count == 2

        # Combined filters
        count = await temp_db.get_trades_count(symbol="AAPL.US", side="BUY")
        assert count == 1

    @pytest.mark.asyncio
    async def test_get_trades_count_empty(self, temp_db):
        """get_trades_count returns 0 when no trades exist."""
        count = await temp_db.get_trades_count()
        assert count == 0


class TestBrokerGetTradesHistory:
    """Tests for broker.get_trades_history method."""

    @pytest.mark.asyncio
    async def test_get_trades_history_returns_list(self):
        """get_trades_history returns a list of trade dicts."""
        from sentinel.broker import Broker

        broker = Broker()

        # Mock the API call - actual API returns {"trades": {"trade": [...]}}
        mock_response = {
            "trades": {
                "trade": [
                    {"id": "1", "instr_nm": "AAPL.US", "type": 1, "date": "2024-01-15 10:30:00"},
                    {"id": "2", "instr_nm": "MSFT.US", "type": 2, "date": "2024-01-16 11:00:00"},
                ]
            }
        }

        with patch.object(broker, "_api") as mock_api:
            mock_api.get_trades_history = MagicMock(return_value=mock_response)
            broker._api = mock_api

            trades = await broker.get_trades_history()

            assert isinstance(trades, list)
            assert len(trades) == 2

    @pytest.mark.asyncio
    async def test_get_trades_history_maps_type_to_side(self):
        """get_trades_history maps Tradernet type (1/2) to side (BUY/SELL)."""
        from sentinel.broker import Broker

        broker = Broker()

        # Actual API returns {"trades": {"trade": [...]}}
        mock_response = {
            "trades": {
                "trade": [
                    {"id": "1", "instr_nm": "AAPL.US", "type": 1, "date": "2024-01-15"},  # type 1 = BUY
                    {"id": "2", "instr_nm": "MSFT.US", "type": 2, "date": "2024-01-16"},  # type 2 = SELL
                ]
            }
        }

        with patch.object(broker, "_api") as mock_api:
            mock_api.get_trades_history = MagicMock(return_value=mock_response)
            broker._api = mock_api

            trades = await broker.get_trades_history()

            buy_trade = next(t for t in trades if t["id"] == "1")
            sell_trade = next(t for t in trades if t["id"] == "2")

            assert buy_trade["side"] == "BUY"
            assert sell_trade["side"] == "SELL"

    @pytest.mark.asyncio
    async def test_get_trades_history_extracts_symbol(self):
        """get_trades_history extracts symbol from instr_nm."""
        from sentinel.broker import Broker

        broker = Broker()

        # Actual API returns {"trades": {"trade": [...]}}
        mock_response = {
            "trades": {
                "trade": [
                    {"id": "1", "instr_nm": "AAPL.US", "type": 1, "date": "2024-01-15"},
                ]
            }
        }

        with patch.object(broker, "_api") as mock_api:
            mock_api.get_trades_history = MagicMock(return_value=mock_response)
            broker._api = mock_api

            trades = await broker.get_trades_history()

            assert trades[0]["symbol"] == "AAPL.US"


class TestSyncTradesJob:
    """Tests for sync_trades job task."""

    @pytest.mark.asyncio
    async def test_sync_trades_imports_new_trades(self, temp_db):
        """sync_trades imports new trades from broker."""
        from sentinel.jobs.tasks import sync_trades

        mock_broker = AsyncMock()
        mock_broker.get_trades_history = AsyncMock(
            return_value=[
                {
                    "id": "123",
                    "symbol": "AAPL.US",
                    "side": "BUY",
                    "date": "2024-01-15 10:30:00",
                    "price": 150.0,
                    "qty": 10,
                },
                {
                    "id": "456",
                    "symbol": "MSFT.US",
                    "side": "SELL",
                    "date": "2024-01-16 11:00:00",
                    "price": 380.0,
                    "qty": 5,
                },
            ]
        )

        await sync_trades(temp_db, mock_broker)

        trades = await temp_db.get_trades()
        assert len(trades) == 2

    @pytest.mark.asyncio
    async def test_sync_trades_skips_existing_trades(self, temp_db):
        """sync_trades skips trades that already exist (by broker_trade_id)."""
        from sentinel.jobs.tasks import sync_trades

        # Pre-insert a trade
        await temp_db.upsert_trade(
            broker_trade_id="123",
            symbol="AAPL.US",
            side="BUY",
            quantity=10.0,
            price=150.0,
            executed_at="2024-01-15T10:30:00",
            raw_data={"id": "123", "original": True},
        )

        mock_broker = AsyncMock()
        mock_broker.get_trades_history = AsyncMock(
            return_value=[
                {
                    "id": "123",  # Same ID - should be skipped
                    "symbol": "AAPL.US",
                    "side": "BUY",
                    "date": "2024-01-15 10:30:00",
                    "new_field": True,  # Different data
                },
                {
                    "id": "456",  # New ID - should be inserted
                    "symbol": "MSFT.US",
                    "side": "SELL",
                    "date": "2024-01-16 11:00:00",
                },
            ]
        )

        await sync_trades(temp_db, mock_broker)

        trades = await temp_db.get_trades()
        assert len(trades) == 2

        # Original trade should keep original data
        original_trade = next(t for t in trades if t["broker_trade_id"] == "123")
        assert original_trade["raw_data"].get("original") is True


class TestCooloffIntegration:
    """Tests for cooloff period using broker trades."""

    @pytest.mark.asyncio
    async def test_cooloff_uses_broker_trades(self, temp_db):
        """_check_cooloff_violation uses trades from new schema."""
        from sentinel.planner import Planner

        # Setup: create a recent SELL trade
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
        await temp_db.upsert_trade(
            broker_trade_id="recent_sell",
            symbol="AAPL.US",
            side="SELL",
            quantity=10.0,
            price=150.0,
            executed_at=yesterday,
            raw_data={"id": "recent_sell"},
        )

        # Create planner with test db
        planner = Planner(db=temp_db)

        # Check cooloff for BUY (opposite of recent SELL) with 30 day cooloff
        is_blocked, reason = await planner._check_cooloff_violation("AAPL.US", "buy", cooloff_days=30)

        assert is_blocked is True
        assert "days remaining" in reason

    @pytest.mark.asyncio
    async def test_cooloff_allows_same_direction(self, temp_db):
        """Cooloff allows trades in same direction as last trade."""
        from sentinel.planner import Planner

        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
        await temp_db.upsert_trade(
            broker_trade_id="recent_buy",
            symbol="AAPL.US",
            side="BUY",
            quantity=10.0,
            price=150.0,
            executed_at=yesterday,
            raw_data={"id": "recent_buy"},
        )

        planner = Planner(db=temp_db)

        # BUY after BUY should be allowed
        is_blocked, reason = await planner._check_cooloff_violation("AAPL.US", "buy", cooloff_days=30)

        assert is_blocked is False

    @pytest.mark.asyncio
    async def test_cooloff_allows_after_period(self, temp_db):
        """Cooloff allows opposite trades after cooloff period expires."""
        from sentinel.planner import Planner

        # Trade from 60 days ago
        old_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%S")
        await temp_db.upsert_trade(
            broker_trade_id="old_sell",
            symbol="AAPL.US",
            side="SELL",
            quantity=10.0,
            price=150.0,
            executed_at=old_date,
            raw_data={"id": "old_sell"},
        )

        planner = Planner(db=temp_db)

        # BUY should be allowed after 30-day cooloff
        is_blocked, reason = await planner._check_cooloff_violation("AAPL.US", "buy", cooloff_days=30)

        assert is_blocked is False


class TestSecurityHasRecentTrade:
    """Tests for Security._has_recent_trade using new schema."""

    @pytest.mark.asyncio
    async def test_has_recent_trade_uses_new_schema(self, temp_db):
        """Security._has_recent_trade uses trades from new schema."""
        from sentinel.security import Security

        # Create a recent trade
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        await temp_db.upsert_trade(
            broker_trade_id="recent",
            symbol="AAPL.US",
            side="BUY",
            quantity=10.0,
            price=150.0,
            executed_at=now,
            raw_data={"id": "recent"},
        )

        security = Security("AAPL.US", db=temp_db)
        has_recent = await security._has_recent_trade()

        assert has_recent is True

    @pytest.mark.asyncio
    async def test_has_recent_trade_false_when_no_trades(self, temp_db):
        """Security._has_recent_trade returns False when no trades exist."""
        from sentinel.security import Security

        security = Security("AAPL.US", db=temp_db)
        has_recent = await security._has_recent_trade()

        assert has_recent is False

    @pytest.mark.asyncio
    async def test_has_recent_trade_false_for_old_trades(self, temp_db):
        """Security._has_recent_trade returns False for old trades."""
        from sentinel.security import Security

        # Trade from 2 hours ago (cooloff is 60 minutes)
        old_time = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")
        await temp_db.upsert_trade(
            broker_trade_id="old",
            symbol="AAPL.US",
            side="BUY",
            quantity=10.0,
            price=150.0,
            executed_at=old_time,
            raw_data={"id": "old"},
        )

        security = Security("AAPL.US", db=temp_db)
        has_recent = await security._has_recent_trade()

        assert has_recent is False
