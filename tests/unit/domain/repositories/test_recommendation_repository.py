"""Tests for RecommendationRepository.

These tests verify the recommendation tracking which is CRITICAL
for managing trade recommendations across rebalance cycles.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.repositories.recommendation import RecommendationRepository


class AsyncContextManagerMock:
    """Helper class to create async context manager mocks."""

    def __init__(self, return_value):
        self.return_value = return_value

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


def create_mock_row(data: dict) -> dict:
    """Create a mock database row with keys() method."""

    class MockRow(dict):
        def keys(self):
            return super().keys()

    return MockRow(data)


def create_mock_recommendation(
    uuid: str = "test-uuid-1",
    symbol: str = "AAPL",
    name: str = "Apple Inc.",
    side: str = "BUY",
    amount: float = 1000.0,
    quantity: int = 10,
    estimated_price: float = 100.0,
    estimated_value: float = 1000.0,
    reason: str = "Underweight in country",
    country: str = "United States",
    industry: str = "Consumer Electronics",
    currency: str = "EUR",
    priority: float = 1.5,
    current_portfolio_score: float = 0.5,
    new_portfolio_score: float = 0.6,
    score_change: float = 0.1,
    status: str = "pending",
    portfolio_hash: str = "hash123",
    created_at: str = "2024-01-15T10:00:00",
    updated_at: str = "2024-01-15T10:00:00",
    executed_at: str | None = None,
    dismissed_at: str | None = None,
) -> dict:
    """Create a mock recommendation database row."""
    return {
        "uuid": uuid,
        "symbol": symbol,
        "name": name,
        "side": side,
        "amount": amount,
        "quantity": quantity,
        "estimated_price": estimated_price,
        "estimated_value": estimated_value,
        "reason": reason,
        "country": country,
        "industry": industry,
        "currency": currency,
        "priority": priority,
        "current_portfolio_score": current_portfolio_score,
        "new_portfolio_score": new_portfolio_score,
        "score_change": score_change,
        "status": status,
        "portfolio_hash": portfolio_hash,
        "created_at": created_at,
        "updated_at": updated_at,
        "executed_at": executed_at,
        "dismissed_at": dismissed_at,
    }


class TestRecommendationRepositoryFindExisting:
    """Test finding existing recommendations."""

    @pytest.mark.asyncio
    async def test_find_existing_returns_recommendation(self):
        """Test finding an existing recommendation."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_row = create_mock_row(
                create_mock_recommendation(
                    symbol="AAPL",
                    side="BUY",
                    reason="Test reason",
                    portfolio_hash="hash123",
                )
            )
            mock_config.fetchone.return_value = mock_row

            repo = RecommendationRepository()
            result = await repo.find_existing("AAPL", "BUY", "Test reason", "hash123")

            assert result is not None
            assert result["symbol"] == "AAPL"
            assert result["side"] == "BUY"
            assert result["reason"] == "Test reason"
            mock_config.fetchone.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_existing_normalizes_symbol_case(self):
        """Test that find_existing normalizes symbol to uppercase."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_config.fetchone.return_value = None

            repo = RecommendationRepository()
            await repo.find_existing("aapl", "buy", "Test reason", "hash123")

            # Verify uppercase was used in query
            call_args = mock_config.fetchone.call_args
            params = call_args[0][1]
            assert params[0] == "AAPL"
            assert params[1] == "BUY"

    @pytest.mark.asyncio
    async def test_find_existing_returns_none_when_not_found(self):
        """Test finding non-existent recommendation returns None."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_config.fetchone.return_value = None

            repo = RecommendationRepository()
            result = await repo.find_existing(
                "NONEXISTENT", "BUY", "Test reason", "hash123"
            )

            assert result is None


class TestRecommendationRepositoryCreateOrUpdate:
    """Test creating or updating recommendations."""

    @pytest.mark.asyncio
    async def test_create_new_recommendation(self):
        """Test creating a new recommendation."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            # No existing recommendation
            mock_config.fetchone.return_value = None

            # Setup transaction mock
            mock_conn = AsyncMock()
            # transaction() is a regular method that returns an async context manager
            mock_config.transaction = MagicMock(
                return_value=AsyncContextManagerMock(mock_conn)
            )

            repo = RecommendationRepository()
            recommendation_data = {
                "symbol": "aapl",
                "name": "Apple Inc.",
                "side": "buy",
                "amount": 1000.0,
                "quantity": 10,
                "estimated_price": 100.0,
                "estimated_value": 1000.0,
                "reason": "Test reason",
                "country": "United States",
                "industry": "Consumer Electronics",
                "currency": "USD",
                "priority": 1.5,
                "current_portfolio_score": 0.5,
                "new_portfolio_score": 0.6,
                "score_change": 0.1,
            }

            result = await repo.create_or_update(recommendation_data, "hash123")

            assert result is not None
            assert isinstance(result, str)
            mock_conn.execute.assert_called_once()
            # Verify uppercase normalization in INSERT
            call_args = mock_conn.execute.call_args
            params = call_args[0][1]
            assert params[1] == "AAPL"  # symbol
            assert params[3] == "BUY"  # side

    @pytest.mark.asyncio
    async def test_create_recommendation_uses_default_currency(self):
        """Test that missing currency defaults to EUR."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_config.fetchone.return_value = None

            mock_conn = AsyncMock()
            mock_config.transaction = MagicMock(
                return_value=AsyncContextManagerMock(mock_conn)
            )

            repo = RecommendationRepository()
            recommendation_data = {
                "symbol": "AAPL",
                "side": "BUY",
                "reason": "Test reason",
                # No currency field
            }

            await repo.create_or_update(recommendation_data, "hash123")

            call_args = mock_conn.execute.call_args
            params = call_args[0][1]
            # Currency is at index 11 in INSERT statement
            assert params[11] == "EUR"

    @pytest.mark.asyncio
    async def test_update_existing_pending_recommendation(self):
        """Test updating an existing pending recommendation."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            # Existing pending recommendation
            existing_row = create_mock_row(
                create_mock_recommendation(
                    uuid="existing-uuid",
                    status="pending",
                    symbol="AAPL",
                    side="BUY",
                    reason="Test reason",
                    portfolio_hash="hash123",
                )
            )
            mock_config.fetchone.return_value = existing_row

            mock_conn = AsyncMock()
            mock_config.transaction = MagicMock(
                return_value=AsyncContextManagerMock(mock_conn)
            )

            repo = RecommendationRepository()
            recommendation_data = {
                "symbol": "AAPL",
                "side": "BUY",
                "reason": "Test reason",
                "name": "Apple Inc. Updated",
                "quantity": 15,
                "priority": 2.0,
            }

            result = await repo.create_or_update(recommendation_data, "hash123")

            assert result == "existing-uuid"
            mock_conn.execute.assert_called_once()
            # Verify UPDATE was called
            call_args = mock_conn.execute.call_args
            assert "UPDATE recommendations" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_dismissed_recommendation_returns_none(self):
        """Test that dismissed recommendations are skipped."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            # Existing dismissed recommendation
            existing_row = create_mock_row(
                create_mock_recommendation(
                    uuid="dismissed-uuid",
                    status="dismissed",
                    symbol="AAPL",
                    side="BUY",
                    reason="Test reason",
                    portfolio_hash="hash123",
                )
            )
            mock_config.fetchone.return_value = existing_row

            repo = RecommendationRepository()
            recommendation_data = {
                "symbol": "AAPL",
                "side": "BUY",
                "reason": "Test reason",
            }

            result = await repo.create_or_update(recommendation_data, "hash123")

            assert result is None

    @pytest.mark.asyncio
    async def test_executed_recommendation_updated_to_pending(self):
        """Test that executed recommendations are updated back to pending when regenerated."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            # Existing executed recommendation
            existing_row = create_mock_row(
                create_mock_recommendation(
                    uuid="executed-uuid",
                    status="executed",
                    symbol="AAPL",
                    side="BUY",
                    reason="Test reason",
                    portfolio_hash="hash123",
                    executed_at="2024-01-15T10:00:00",
                )
            )
            mock_config.fetchone.return_value = existing_row

            mock_conn = AsyncMock()
            mock_config.transaction = MagicMock(
                return_value=AsyncContextManagerMock(mock_conn)
            )

            repo = RecommendationRepository()
            recommendation_data = {
                "symbol": "AAPL",
                "side": "BUY",
                "reason": "Test reason",
                "name": "Apple Inc.",
            }

            result = await repo.create_or_update(recommendation_data, "hash123")

            assert result == "executed-uuid"
            mock_conn.execute.assert_called_once()
            # Verify executed_at is set to NULL
            call_args = mock_conn.execute.call_args
            assert "status = 'pending'" in call_args[0][0]
            assert "executed_at = NULL" in call_args[0][0]


class TestRecommendationRepositoryGetByUuid:
    """Test getting recommendations by UUID."""

    @pytest.mark.asyncio
    async def test_get_by_uuid_returns_recommendation(self):
        """Test retrieving recommendation by UUID."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_row = create_mock_row(
                create_mock_recommendation(uuid="test-uuid-1", symbol="AAPL")
            )
            mock_config.fetchone.return_value = mock_row

            repo = RecommendationRepository()
            result = await repo.get_by_uuid("test-uuid-1")

            assert result is not None
            assert result["uuid"] == "test-uuid-1"
            assert result["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_get_by_uuid_returns_none_when_not_found(self):
        """Test retrieving non-existent UUID returns None."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_config.fetchone.return_value = None

            repo = RecommendationRepository()
            result = await repo.get_by_uuid("nonexistent-uuid")

            assert result is None


class TestRecommendationRepositoryGetPending:
    """Test getting pending recommendations."""

    @pytest.mark.asyncio
    async def test_get_pending_returns_recommendations(self):
        """Test retrieving pending recommendations."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_rows = [
                create_mock_row(
                    create_mock_recommendation(
                        uuid="uuid1", symbol="AAPL", status="pending"
                    )
                ),
                create_mock_row(
                    create_mock_recommendation(
                        uuid="uuid2", symbol="GOOGL", status="pending"
                    )
                ),
            ]
            mock_config.fetchall.return_value = mock_rows

            repo = RecommendationRepository()
            result = await repo.get_pending(limit=10)

            assert len(result) == 2
            assert result[0]["symbol"] == "AAPL"
            assert result[1]["symbol"] == "GOOGL"
            assert all(r["status"] == "pending" for r in result)

    @pytest.mark.asyncio
    async def test_get_pending_respects_limit(self):
        """Test that get_pending respects the limit parameter."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_config.fetchall.return_value = []

            repo = RecommendationRepository()
            await repo.get_pending(limit=5)

            call_args = mock_config.fetchall.call_args
            assert call_args[0][1] == (5,)

    @pytest.mark.asyncio
    async def test_get_pending_empty_list(self):
        """Test get_pending returns empty list when no pending recommendations."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_config.fetchall.return_value = []

            repo = RecommendationRepository()
            result = await repo.get_pending()

            assert result == []


class TestRecommendationRepositoryGetPendingBySide:
    """Test getting pending recommendations by side."""

    @pytest.mark.asyncio
    async def test_get_pending_by_side_buy(self):
        """Test retrieving pending BUY recommendations."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_rows = [
                create_mock_row(
                    create_mock_recommendation(
                        uuid="uuid1", symbol="AAPL", side="BUY", status="pending"
                    )
                ),
                create_mock_row(
                    create_mock_recommendation(
                        uuid="uuid2", symbol="GOOGL", side="BUY", status="pending"
                    )
                ),
            ]
            mock_config.fetchall.return_value = mock_rows

            repo = RecommendationRepository()
            result = await repo.get_pending_by_side("BUY", limit=10)

            assert len(result) == 2
            assert all(r["side"] == "BUY" for r in result)

    @pytest.mark.asyncio
    async def test_get_pending_by_side_normalizes_case(self):
        """Test that get_pending_by_side normalizes side to uppercase."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_config.fetchall.return_value = []

            repo = RecommendationRepository()
            await repo.get_pending_by_side("sell", limit=10)

            call_args = mock_config.fetchall.call_args
            params = call_args[0][1]
            assert params[0] == "SELL"
            assert params[1] == "SELL"

    @pytest.mark.asyncio
    async def test_get_pending_by_side_respects_limit(self):
        """Test that get_pending_by_side respects limit parameter."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_config.fetchall.return_value = []

            repo = RecommendationRepository()
            await repo.get_pending_by_side("BUY", limit=3)

            call_args = mock_config.fetchall.call_args
            params = call_args[0][1]
            assert params[2] == 3


class TestRecommendationRepositoryMarkExecuted:
    """Test marking recommendations as executed."""

    @pytest.mark.asyncio
    async def test_mark_executed_with_provided_timestamp(self):
        """Test marking recommendation as executed with custom timestamp."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_conn = AsyncMock()
            mock_config.transaction = MagicMock(
                return_value=AsyncContextManagerMock(mock_conn)
            )

            repo = RecommendationRepository()
            custom_timestamp = "2024-01-15T15:30:00"
            await repo.mark_executed("test-uuid", executed_at=custom_timestamp)

            mock_conn.execute.assert_called_once()
            call_args = mock_conn.execute.call_args
            params = call_args[0][1]
            assert params[0] == custom_timestamp
            assert params[1] == "test-uuid"

    @pytest.mark.asyncio
    async def test_mark_executed_with_default_timestamp(self):
        """Test marking recommendation as executed with auto-generated timestamp."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_conn = AsyncMock()
            mock_config.transaction = MagicMock(
                return_value=AsyncContextManagerMock(mock_conn)
            )

            repo = RecommendationRepository()
            await repo.mark_executed("test-uuid")

            mock_conn.execute.assert_called_once()
            call_args = mock_conn.execute.call_args
            params = call_args[0][1]
            # Timestamp should be auto-generated (ISO format)
            assert "T" in params[0]
            assert params[1] == "test-uuid"


class TestRecommendationRepositoryMarkDismissed:
    """Test marking recommendations as dismissed."""

    @pytest.mark.asyncio
    async def test_mark_dismissed_with_provided_timestamp(self):
        """Test marking recommendation as dismissed with custom timestamp."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_conn = AsyncMock()
            mock_config.transaction = MagicMock(
                return_value=AsyncContextManagerMock(mock_conn)
            )

            repo = RecommendationRepository()
            custom_timestamp = "2024-01-15T15:30:00"
            await repo.mark_dismissed("test-uuid", dismissed_at=custom_timestamp)

            mock_conn.execute.assert_called_once()
            call_args = mock_conn.execute.call_args
            params = call_args[0][1]
            assert params[0] == custom_timestamp
            assert params[1] == "test-uuid"

    @pytest.mark.asyncio
    async def test_mark_dismissed_with_default_timestamp(self):
        """Test marking recommendation as dismissed with auto-generated timestamp."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_conn = AsyncMock()
            mock_config.transaction = MagicMock(
                return_value=AsyncContextManagerMock(mock_conn)
            )

            repo = RecommendationRepository()
            await repo.mark_dismissed("test-uuid")

            mock_conn.execute.assert_called_once()
            call_args = mock_conn.execute.call_args
            params = call_args[0][1]
            # Timestamp should be auto-generated (ISO format)
            assert "T" in params[0]
            assert params[1] == "test-uuid"


class TestRecommendationRepositoryIsDismissed:
    """Test checking if recommendation is dismissed."""

    @pytest.mark.asyncio
    async def test_is_dismissed_returns_true(self):
        """Test that is_dismissed returns True for dismissed recommendations."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_row = {"status": "dismissed"}
            mock_config.fetchone.return_value = mock_row

            repo = RecommendationRepository()
            result = await repo.is_dismissed("AAPL", "BUY", "Test reason", "hash123")

            assert result is True

    @pytest.mark.asyncio
    async def test_is_dismissed_returns_false_for_pending(self):
        """Test that is_dismissed returns False for pending recommendations."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_row = {"status": "pending"}
            mock_config.fetchone.return_value = mock_row

            repo = RecommendationRepository()
            result = await repo.is_dismissed("AAPL", "BUY", "Test reason", "hash123")

            assert result is False

    @pytest.mark.asyncio
    async def test_is_dismissed_returns_false_when_not_found(self):
        """Test that is_dismissed returns falsy value when recommendation doesn't exist."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_config.fetchone.return_value = None

            repo = RecommendationRepository()
            result = await repo.is_dismissed("AAPL", "BUY", "Test reason", "hash123")

            # When row is None, the expression evaluates to None (falsy)
            assert not result

    @pytest.mark.asyncio
    async def test_is_dismissed_normalizes_case(self):
        """Test that is_dismissed normalizes symbol and side to uppercase."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_config.fetchone.return_value = None

            repo = RecommendationRepository()
            await repo.is_dismissed("aapl", "buy", "Test reason", "hash123")

            call_args = mock_config.fetchone.call_args
            params = call_args[0][1]
            assert params[0] == "AAPL"
            assert params[1] == "BUY"


class TestRecommendationRepositoryFindMatchingForExecution:
    """Test finding matching recommendations for execution."""

    @pytest.mark.asyncio
    async def test_find_matching_for_execution_returns_matches(self):
        """Test finding matching pending recommendations for execution."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_rows = [
                create_mock_row(
                    create_mock_recommendation(
                        uuid="uuid1",
                        symbol="AAPL",
                        side="BUY",
                        status="pending",
                        portfolio_hash="hash123",
                    )
                ),
                create_mock_row(
                    create_mock_recommendation(
                        uuid="uuid2",
                        symbol="AAPL",
                        side="BUY",
                        status="pending",
                        portfolio_hash="hash123",
                        reason="Different reason",
                    )
                ),
            ]
            mock_config.fetchall.return_value = mock_rows

            repo = RecommendationRepository()
            result = await repo.find_matching_for_execution("AAPL", "BUY", "hash123")

            assert len(result) == 2
            assert all(r["symbol"] == "AAPL" for r in result)
            assert all(r["side"] == "BUY" for r in result)
            assert all(r["status"] == "pending" for r in result)

    @pytest.mark.asyncio
    async def test_find_matching_for_execution_normalizes_case(self):
        """Test that find_matching_for_execution normalizes symbol and side."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_config.fetchall.return_value = []

            repo = RecommendationRepository()
            await repo.find_matching_for_execution("aapl", "sell", "hash123")

            call_args = mock_config.fetchall.call_args
            params = call_args[0][1]
            assert params[0] == "AAPL"
            assert params[1] == "SELL"

    @pytest.mark.asyncio
    async def test_find_matching_for_execution_empty_list(self):
        """Test find_matching_for_execution returns empty list when no matches."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_config.fetchall.return_value = []

            repo = RecommendationRepository()
            result = await repo.find_matching_for_execution("AAPL", "BUY", "hash123")

            assert result == []

    @pytest.mark.asyncio
    async def test_find_matching_for_execution_filters_by_portfolio_hash(self):
        """Test that find_matching_for_execution filters by portfolio_hash."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_config.fetchall.return_value = []

            repo = RecommendationRepository()
            await repo.find_matching_for_execution("AAPL", "BUY", "specific-hash")

            call_args = mock_config.fetchall.call_args
            params = call_args[0][1]
            assert params[2] == "specific-hash"


class TestRecommendationRepositoryEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_create_recommendation_with_minimal_data(self):
        """Test creating recommendation with only required fields."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_config.fetchone.return_value = None

            mock_conn = AsyncMock()
            mock_config.transaction = MagicMock(
                return_value=AsyncContextManagerMock(mock_conn)
            )

            repo = RecommendationRepository()
            minimal_data = {
                "symbol": "AAPL",
                "side": "BUY",
                "reason": "Test reason",
            }

            result = await repo.create_or_update(minimal_data, "hash123")

            assert result is not None
            mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_recommendation_with_all_optional_fields(self):
        """Test creating recommendation with all optional fields populated."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_config.fetchone.return_value = None

            mock_conn = AsyncMock()
            mock_config.transaction = MagicMock(
                return_value=AsyncContextManagerMock(mock_conn)
            )

            repo = RecommendationRepository()
            full_data = {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "side": "BUY",
                "amount": 1000.0,
                "quantity": 10,
                "estimated_price": 100.0,
                "estimated_value": 1000.0,
                "reason": "Test reason",
                "country": "United States",
                "industry": "Consumer Electronics",
                "currency": "USD",
                "priority": 1.5,
                "current_portfolio_score": 0.5,
                "new_portfolio_score": 0.6,
                "score_change": 0.1,
            }

            result = await repo.create_or_update(full_data, "hash123")

            assert result is not None
            mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_recommendations_same_symbol_different_reasons(self):
        """Test that recommendations with same symbol but different reasons are distinct."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            # First call - no existing, second call - no existing
            mock_config.fetchone.side_effect = [None, None]

            mock_conn = AsyncMock()
            mock_config.transaction = MagicMock(
                return_value=AsyncContextManagerMock(mock_conn)
            )

            repo = RecommendationRepository()

            # Create first recommendation
            data1 = {"symbol": "AAPL", "side": "BUY", "reason": "Reason 1"}
            uuid1 = await repo.create_or_update(data1, "hash123")

            # Create second recommendation with different reason
            data2 = {"symbol": "AAPL", "side": "BUY", "reason": "Reason 2"}
            uuid2 = await repo.create_or_update(data2, "hash123")

            # Should create two different UUIDs
            assert uuid1 != uuid2
            assert mock_conn.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_get_pending_ordered_by_updated_at_desc(self):
        """Test that get_pending returns results ordered by updated_at DESC."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_rows = [
                create_mock_row(
                    create_mock_recommendation(
                        uuid="uuid1",
                        updated_at="2024-01-15T12:00:00",
                        status="pending",
                    )
                ),
                create_mock_row(
                    create_mock_recommendation(
                        uuid="uuid2",
                        updated_at="2024-01-15T11:00:00",
                        status="pending",
                    )
                ),
            ]
            mock_config.fetchall.return_value = mock_rows

            repo = RecommendationRepository()
            await repo.get_pending()

            # Verify query contains ORDER BY updated_at DESC
            call_args = mock_config.fetchall.call_args
            query = call_args[0][0]
            assert "ORDER BY updated_at DESC" in query

    @pytest.mark.asyncio
    async def test_get_pending_by_side_ordered_by_priority_and_updated_at(self):
        """Test that get_pending_by_side orders by priority DESC, updated_at DESC."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_config.fetchall.return_value = []

            repo = RecommendationRepository()
            await repo.get_pending_by_side("BUY")

            call_args = mock_config.fetchall.call_args
            query = call_args[0][0]
            assert "ORDER BY r.priority DESC, r.updated_at DESC" in query

    @pytest.mark.asyncio
    async def test_recommendation_with_zero_values(self):
        """Test creating recommendation with zero values (valid edge case)."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_config.fetchone.return_value = None

            mock_conn = AsyncMock()
            mock_config.transaction = MagicMock(
                return_value=AsyncContextManagerMock(mock_conn)
            )

            repo = RecommendationRepository()
            data = {
                "symbol": "AAPL",
                "side": "BUY",
                "reason": "Test",
                "amount": 0.0,
                "quantity": 0,
                "priority": 0.0,
                "score_change": 0.0,
            }

            result = await repo.create_or_update(data, "hash123")

            assert result is not None

    @pytest.mark.asyncio
    async def test_recommendation_with_negative_score_change(self):
        """Test creating recommendation with negative score change (valid for sells)."""
        with patch("app.repositories.recommendation.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_config = AsyncMock()
            mock_db.recommendations = mock_config
            mock_get_db.return_value = mock_db

            mock_config.fetchone.return_value = None

            mock_conn = AsyncMock()
            mock_config.transaction = MagicMock(
                return_value=AsyncContextManagerMock(mock_conn)
            )

            repo = RecommendationRepository()
            data = {
                "symbol": "AAPL",
                "side": "SELL",
                "reason": "Test",
                "score_change": -0.5,
            }

            result = await repo.create_or_update(data, "hash123")

            assert result is not None
