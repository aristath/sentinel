"""Tests for calculations repository.

These tests validate pre-computed metrics storage and retrieval.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.repositories.calculations import CalculationsRepository


class TestCalculationsRepository:
    """Test CalculationsRepository class."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = AsyncMock()
        db.fetchone = AsyncMock(return_value=None)
        db.fetchall = AsyncMock(return_value=[])
        db.execute = AsyncMock()
        db.commit = AsyncMock()

        class MockTransaction:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return False

        db.transaction = MagicMock(return_value=MockTransaction())
        return db

    @pytest.fixture
    def mock_db_manager(self, mock_db):
        """Create mock database manager."""
        manager = MagicMock()
        manager.calculations = mock_db
        return manager

    @pytest.fixture
    def repo(self, mock_db_manager):
        """Create repository with mocked database."""
        with patch(
            "app.repositories.calculations.get_db_manager",
            return_value=mock_db_manager,
        ):
            return CalculationsRepository()

    @pytest.mark.asyncio
    async def test_get_metric_returns_value_when_found(self, repo, mock_db):
        """Test getting metric that exists."""
        mock_db.fetchone.return_value = {"value": 0.75}

        result = await repo.get_metric("AAPL.US", "RSI_14")

        assert result == 0.75
        mock_db.fetchone.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_metric_returns_none_when_not_found(self, repo, mock_db):
        """Test getting metric that doesn't exist."""
        mock_db.fetchone.return_value = None

        result = await repo.get_metric("AAPL.US", "RSI_14")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_metric_uppercases_symbol(self, repo, mock_db):
        """Test that symbol is uppercased."""
        mock_db.fetchone.return_value = None

        await repo.get_metric("aapl.us", "RSI_14")

        call_args = mock_db.fetchone.call_args
        assert "AAPL.US" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_set_metric_stores_value(self, repo, mock_db):
        """Test setting a metric value."""
        await repo.set_metric("AAPL.US", "RSI_14", 0.65)

        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_metric_with_ttl_override(self, repo, mock_db):
        """Test setting metric with custom TTL."""
        await repo.set_metric("AAPL.US", "RSI_14", 0.65, ttl_override=3600)

        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_metric_with_source(self, repo, mock_db):
        """Test setting metric with custom source."""
        await repo.set_metric("AAPL.US", "PE_RATIO", 25.5, source="yahoo")

        mock_db.execute.assert_called_once()
        # Check that source was passed
        call_args = mock_db.execute.call_args
        assert "yahoo" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_get_metrics_batch(self, repo, mock_db):
        """Test batch getting multiple metrics."""
        mock_db.fetchall.return_value = [
            {"metric": "RSI_14", "value": 0.65},
            {"metric": "MACD", "value": 0.8},
        ]

        result = await repo.get_metrics("AAPL.US", ["RSI_14", "MACD", "SMA_50"])

        assert result["RSI_14"] == 0.65
        assert result["MACD"] == 0.8
        assert result["SMA_50"] is None

    @pytest.mark.asyncio
    async def test_get_metrics_returns_none_for_missing(self, repo, mock_db):
        """Test that missing metrics return None."""
        mock_db.fetchall.return_value = []

        result = await repo.get_metrics("AAPL.US", ["RSI_14"])

        assert result == {"RSI_14": None}

    @pytest.mark.asyncio
    async def test_set_metrics_batch(self, repo, mock_db):
        """Test batch setting multiple metrics."""
        metrics = {"RSI_14": 0.65, "MACD": 0.8, "SMA_50": 150.0}

        await repo.set_metrics("AAPL.US", metrics)

        assert mock_db.execute.call_count == 3
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_metrics_with_ttl_override(self, repo, mock_db):
        """Test batch setting with TTL override."""
        metrics = {"RSI_14": 0.65, "MACD": 0.8}

        await repo.set_metrics("AAPL.US", metrics, ttl_override=7200)

        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_get_all_metrics(self, repo, mock_db):
        """Test getting all metrics for a symbol."""
        mock_db.fetchall.return_value = [
            {"metric": "RSI_14", "value": 0.65},
            {"metric": "PE_RATIO", "value": 25.5},
        ]

        result = await repo.get_all_metrics("AAPL.US")

        assert result == {"RSI_14": 0.65, "PE_RATIO": 25.5}

    @pytest.mark.asyncio
    async def test_get_all_metrics_empty(self, repo, mock_db):
        """Test getting all metrics when none exist."""
        mock_db.fetchall.return_value = []

        result = await repo.get_all_metrics("AAPL.US")

        assert result == {}

    @pytest.mark.asyncio
    async def test_delete_expired(self, repo, mock_db):
        """Test deleting expired metrics."""
        mock_cursor = AsyncMock()
        mock_cursor.rowcount = 5
        mock_db.execute.return_value = mock_cursor

        result = await repo.delete_expired()

        assert result == 5
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_expired_zero(self, repo, mock_db):
        """Test deleting when no expired metrics."""
        mock_cursor = AsyncMock()
        mock_cursor.rowcount = 0
        mock_db.execute.return_value = mock_cursor

        result = await repo.delete_expired()

        assert result == 0

    def test_get_ttl_for_metric_known(self, repo):
        """Test getting TTL for known metric."""
        # RSI_14 should have a specific TTL
        ttl = repo.get_ttl_for_metric("RSI_14")
        assert ttl > 0

    def test_get_ttl_for_metric_default(self, repo):
        """Test getting default TTL for unknown metric."""
        ttl = repo.get_ttl_for_metric("UNKNOWN_METRIC_XYZ")
        assert ttl > 0  # Should return default

    def test_private_get_ttl_for_metric(self, repo):
        """Test private _get_ttl_for_metric method."""
        # This tests the internal method used by set operations
        ttl = repo._get_ttl_for_metric("SHARPE")
        assert ttl > 0
