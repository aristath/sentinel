"""Tests for allocation repository.

These tests validate allocation target storage and retrieval.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.models import AllocationTarget
from app.modules.allocation.database.allocation_repository import AllocationRepository


class TestAllocationRepository:
    """Test AllocationRepository class."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = AsyncMock()
        db.fetchone = AsyncMock(return_value=None)
        db.fetchall = AsyncMock(return_value=[])
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        return db

    @pytest.fixture
    def repo(self, mock_db):
        """Create repository with mocked database."""
        return AllocationRepository(db=mock_db)

    @pytest.mark.asyncio
    async def test_get_all_returns_dict(self, repo, mock_db):
        """Test getting all allocation targets as dict."""
        mock_db.fetchall.return_value = [
            {"type": "country_group", "name": "US", "target_pct": 0.4},
            {"type": "country_group", "name": "EU", "target_pct": 0.3},
            {"type": "industry_group", "name": "Technology", "target_pct": 0.25},
        ]

        result = await repo.get_all()

        assert result == {
            "country_group:US": 0.4,
            "country_group:EU": 0.3,
            "industry_group:Technology": 0.25,
        }

    @pytest.mark.asyncio
    async def test_get_all_empty(self, repo, mock_db):
        """Test getting all when no targets exist."""
        mock_db.fetchall.return_value = []

        result = await repo.get_all()

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_by_type_country_group(self, repo, mock_db):
        """Test getting country group targets."""
        mock_db.fetchall.return_value = [
            {"type": "country_group", "name": "US", "target_pct": 0.4},
            {"type": "country_group", "name": "EU", "target_pct": 0.3},
        ]

        result = await repo.get_by_type("country_group")

        assert len(result) == 2
        assert all(isinstance(t, AllocationTarget) for t in result)
        assert result[0].name == "US"
        assert result[0].target_pct == 0.4

    @pytest.mark.asyncio
    async def test_get_by_type_industry_group(self, repo, mock_db):
        """Test getting industry group targets."""
        mock_db.fetchall.return_value = [
            {"type": "industry_group", "name": "Technology", "target_pct": 0.25},
        ]

        result = await repo.get_by_type("industry_group")

        assert len(result) == 1
        assert result[0].name == "Technology"

    @pytest.mark.asyncio
    async def test_get_country_group_targets(self, repo, mock_db):
        """Test getting country group targets as dict."""
        mock_db.fetchall.return_value = [
            {"type": "country_group", "name": "US", "target_pct": 0.4},
            {"type": "country_group", "name": "EU", "target_pct": 0.3},
        ]

        result = await repo.get_country_group_targets()

        assert result == {"US": 0.4, "EU": 0.3}

    @pytest.mark.asyncio
    async def test_get_industry_group_targets(self, repo, mock_db):
        """Test getting industry group targets as dict."""
        mock_db.fetchall.return_value = [
            {"type": "industry_group", "name": "Technology", "target_pct": 0.25},
            {"type": "industry_group", "name": "Finance", "target_pct": 0.15},
        ]

        result = await repo.get_industry_group_targets()

        assert result == {"Technology": 0.25, "Finance": 0.15}

    @pytest.mark.asyncio
    async def test_upsert_target(self, repo, mock_db):
        """Test upserting an allocation target."""
        target = AllocationTarget(
            type="country_group",
            name="US",
            target_pct=0.45,
        )

        with patch(
            "app.modules.allocation.database.allocation_repository.transaction_context"
        ) as mock_txn:
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()

            class MockContext:
                async def __aenter__(self):
                    return mock_conn

                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    return False

            mock_txn.return_value = MockContext()

            await repo.upsert(target)

            mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_target(self, repo, mock_db):
        """Test deleting an allocation target."""
        with patch(
            "app.modules.allocation.database.allocation_repository.transaction_context"
        ) as mock_txn:
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()

            class MockContext:
                async def __aenter__(self):
                    return mock_conn

                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    return False

            mock_txn.return_value = MockContext()

            await repo.delete("country_group", "US")

            mock_conn.execute.assert_called_once()
            call_args = mock_conn.execute.call_args
            assert "DELETE" in call_args[0][0]
            assert ("country_group", "US") == call_args[0][1]

    def test_init_with_raw_connection(self):
        """Test initializing with raw aiosqlite connection."""
        # Create a mock that has execute but not fetchone
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock()
        # Ensure fetchone doesn't exist
        del mock_conn.fetchone

        repo = AllocationRepository(db=mock_conn)

        # Should have wrapped with DatabaseAdapter
        assert hasattr(repo._db, "fetchone")

    def test_init_with_database_instance(self):
        """Test initializing with Database instance."""
        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock()
        mock_db.fetchall = AsyncMock()

        repo = AllocationRepository(db=mock_db)

        # Should use directly without wrapping
        assert repo._db == mock_db

    def test_init_without_db(self):
        """Test initializing without db uses get_db_manager."""
        with patch(
            "app.modules.allocation.database.allocation_repository.get_db_manager"
        ) as mock_manager:
            mock_config = MagicMock()
            mock_manager.return_value.config = mock_config

            repo = AllocationRepository()

            mock_manager.assert_called_once()
            assert repo._db == mock_config
