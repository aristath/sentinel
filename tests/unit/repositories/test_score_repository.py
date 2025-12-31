"""Tests for score repository.

These tests validate stock score storage and retrieval.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.models import SecurityScore
from app.repositories.score import ScoreRepository


class TestScoreRepository:
    """Test ScoreRepository class."""

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
        return ScoreRepository(db=mock_db)

    @pytest.fixture
    def sample_row(self):
        """Create sample database row."""
        return {
            "symbol": "AAPL.US",
            "quality_score": 0.8,
            "opportunity_score": 0.7,
            "analyst_score": 0.75,
            "allocation_fit_score": 0.9,
            "cagr_score": 0.65,
            "consistency_score": 0.85,
            "financial_strength_score": 0.7,
            "sharpe_score": 0.6,
            "drawdown_score": 0.55,
            "dividend_bonus": 0.05,
            "rsi": 45.0,
            "ema_200": 155.0,
            "below_52w_high_pct": -15.0,
            "total_score": 0.72,
            "sell_score": 0.3,
            "history_years": 5,
            "volatility": 0.25,
            "calculated_at": "2024-01-15T10:30:00",
        }

    @pytest.mark.asyncio
    async def test_get_by_symbol_returns_score(self, repo, mock_db, sample_row):
        """Test getting score by symbol."""
        mock_db.fetchone.return_value = sample_row

        result = await repo.get_by_symbol("AAPL.US")

        assert result is not None
        assert isinstance(result, SecurityScore)
        assert result.symbol == "AAPL.US"
        assert result.total_score == 0.72

    @pytest.mark.asyncio
    async def test_get_by_symbol_returns_none_when_not_found(self, repo, mock_db):
        """Test getting score for non-existent symbol."""
        mock_db.fetchone.return_value = None

        result = await repo.get_by_symbol("UNKNOWN.US")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_symbol_uppercases(self, repo, mock_db):
        """Test that symbol is uppercased."""
        mock_db.fetchone.return_value = None

        await repo.get_by_symbol("aapl.us")

        call_args = mock_db.fetchone.call_args
        assert "AAPL.US" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_get_all(self, repo, mock_db, sample_row):
        """Test getting all scores."""
        mock_db.fetchall.return_value = [sample_row, sample_row]

        result = await repo.get_all()

        assert len(result) == 2
        assert all(isinstance(s, SecurityScore) for s in result)

    @pytest.mark.asyncio
    async def test_get_all_empty(self, repo, mock_db):
        """Test getting all when no scores exist."""
        mock_db.fetchall.return_value = []

        result = await repo.get_all()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_top(self, repo, mock_db, sample_row):
        """Test getting top scored stocks."""
        mock_db.fetchall.return_value = [sample_row]

        result = await repo.get_top(limit=5)

        assert len(result) == 1
        mock_db.fetchall.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_score(self, repo):
        """Test upserting a score."""
        score = SecurityScore(
            symbol="AAPL.US",
            total_score=0.75,
            quality_score=0.8,
            calculated_at=datetime.now(),
        )

        with patch("app.repositories.score.transaction_context") as mock_txn:
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()

            class MockContext:
                async def __aenter__(self):
                    return mock_conn

                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    return False

            mock_txn.return_value = MockContext()

            await repo.upsert(score)

            mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_score_with_string_calculated_at(self, repo):
        """Test upserting a score with string calculated_at."""
        score = SecurityScore(
            symbol="AAPL.US",
            total_score=0.75,
            calculated_at="2024-01-15T10:30:00",
        )

        with patch("app.repositories.score.transaction_context") as mock_txn:
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()

            class MockContext:
                async def __aenter__(self):
                    return mock_conn

                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    return False

            mock_txn.return_value = MockContext()

            await repo.upsert(score)

            mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_score_none_calculated_at(self, repo):
        """Test upserting a score with no calculated_at."""
        score = SecurityScore(
            symbol="AAPL.US",
            total_score=0.75,
            calculated_at=None,
        )

        with patch("app.repositories.score.transaction_context") as mock_txn:
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()

            class MockContext:
                async def __aenter__(self):
                    return mock_conn

                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    return False

            mock_txn.return_value = MockContext()

            await repo.upsert(score)

            mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete(self, repo):
        """Test deleting a score."""
        with patch("app.repositories.score.transaction_context") as mock_txn:
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()

            class MockContext:
                async def __aenter__(self):
                    return mock_conn

                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    return False

            mock_txn.return_value = MockContext()

            await repo.delete("AAPL.US")

            mock_conn.execute.assert_called_once()
            call_args = mock_conn.execute.call_args
            assert "DELETE" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_delete_all(self, repo):
        """Test deleting all scores."""
        with patch("app.repositories.score.transaction_context") as mock_txn:
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()

            class MockContext:
                async def __aenter__(self):
                    return mock_conn

                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    return False

            mock_txn.return_value = MockContext()

            await repo.delete_all()

            mock_conn.execute.assert_called_once()
            call_args = mock_conn.execute.call_args
            assert "DELETE FROM scores" in call_args[0][0]

    def test_row_to_score_with_valid_data(self, repo, sample_row):
        """Test converting row to StockScore."""
        result = repo._row_to_score(sample_row)

        assert isinstance(result, SecurityScore)
        assert result.symbol == "AAPL.US"
        assert result.quality_score == 0.8
        assert result.total_score == 0.72
        assert result.calculated_at is not None

    def test_row_to_score_with_invalid_date(self, repo):
        """Test converting row with invalid calculated_at."""
        row = {
            "symbol": "AAPL.US",
            "quality_score": None,
            "opportunity_score": None,
            "analyst_score": None,
            "allocation_fit_score": None,
            "cagr_score": None,
            "consistency_score": None,
            "financial_strength_score": None,
            "sharpe_score": None,
            "drawdown_score": None,
            "dividend_bonus": None,
            "rsi": None,
            "ema_200": None,
            "below_52w_high_pct": None,
            "total_score": None,
            "sell_score": None,
            "history_years": None,
            "volatility": None,
            "calculated_at": "invalid-date",
        }

        result = repo._row_to_score(row)

        assert result.calculated_at is None

    def test_row_to_score_with_missing_fields(self, repo):
        """Test converting row with missing optional fields."""
        row = {
            "symbol": "AAPL.US",
            "calculated_at": None,
        }

        # Create a dict-like that returns None for missing keys
        class RowProxy:
            def __init__(self, data):
                self._data = data

            def __getitem__(self, key):
                return self._data.get(key)

        result = repo._row_to_score(RowProxy(row))

        assert result.symbol == "AAPL.US"
        assert result.quality_score is None

    def test_init_with_raw_connection(self):
        """Test initializing with raw aiosqlite connection."""
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock()
        del mock_conn.fetchone

        repo = ScoreRepository(db=mock_conn)

        assert hasattr(repo._db, "fetchone")

    def test_init_with_database_instance(self):
        """Test initializing with Database instance."""
        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock()
        mock_db.fetchall = AsyncMock()

        repo = ScoreRepository(db=mock_db)

        assert repo._db == mock_db

    def test_init_without_db(self):
        """Test initializing without db uses get_db_manager."""
        with patch("app.repositories.score.get_db_manager") as mock_manager:
            mock_state = MagicMock()
            mock_manager.return_value.state = mock_state

            repo = ScoreRepository()

            mock_manager.assert_called_once()
            assert repo._db == mock_state
