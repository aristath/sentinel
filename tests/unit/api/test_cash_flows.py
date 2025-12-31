"""Tests for cash flows API endpoints.

These tests validate cash flow retrieval, synchronization, and summary endpoints.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.domain.models import CashFlow
from app.shared.domain.value_objects.currency import Currency


class TestValidateDateFormat:
    """Test _validate_date_format helper function."""

    def test_accepts_valid_date_format(self):
        """Test that valid YYYY-MM-DD format is accepted."""
        from app.modules.cash_flows.api.cash_flows import _validate_date_format

        # Should not raise exception
        _validate_date_format("2024-01-15")
        _validate_date_format("2023-12-31")
        _validate_date_format("2024-02-29")  # Leap year

    def test_rejects_invalid_date_format(self):
        """Test that invalid date format raises HTTPException."""
        from app.modules.cash_flows.api.cash_flows import _validate_date_format

        with pytest.raises(HTTPException) as exc_info:
            _validate_date_format("15-01-2024")  # Wrong order

        assert exc_info.value.status_code == 400
        assert "YYYY-MM-DD" in exc_info.value.detail

    def test_rejects_invalid_date_values(self):
        """Test that invalid date values raise HTTPException."""
        from app.modules.cash_flows.api.cash_flows import _validate_date_format

        with pytest.raises(HTTPException) as exc_info:
            _validate_date_format("2024-13-01")  # Invalid month

        assert exc_info.value.status_code == 400

    def test_rejects_invalid_separator(self):
        """Test that invalid separator raises HTTPException."""
        from app.modules.cash_flows.api.cash_flows import _validate_date_format

        with pytest.raises(HTTPException) as exc_info:
            _validate_date_format("2024/01/15")  # Slash instead of dash

        assert exc_info.value.status_code == 400

    def test_rejects_partial_date(self):
        """Test that partial date raises HTTPException."""
        from app.modules.cash_flows.api.cash_flows import _validate_date_format

        with pytest.raises(HTTPException) as exc_info:
            _validate_date_format("2024-01")  # Missing day

        assert exc_info.value.status_code == 400


class TestValidateDateRange:
    """Test _validate_date_range helper function."""

    def test_accepts_valid_date_range(self):
        """Test that valid date range is accepted."""
        from app.modules.cash_flows.api.cash_flows import _validate_date_range

        # Should not raise exception
        _validate_date_range("2024-01-01", "2024-01-31")
        _validate_date_range("2024-01-15", "2024-01-15")  # Same date

    def test_accepts_none_values(self):
        """Test that None values are accepted."""
        from app.modules.cash_flows.api.cash_flows import _validate_date_range

        # Should not raise exception
        _validate_date_range(None, None)
        _validate_date_range("2024-01-01", None)
        _validate_date_range(None, "2024-01-31")

    def test_validates_start_date_format(self):
        """Test that start date format is validated."""
        from app.modules.cash_flows.api.cash_flows import _validate_date_range

        with pytest.raises(HTTPException) as exc_info:
            _validate_date_range("invalid-date", "2024-01-31")

        assert exc_info.value.status_code == 400

    def test_validates_end_date_format(self):
        """Test that end date format is validated."""
        from app.modules.cash_flows.api.cash_flows import _validate_date_range

        with pytest.raises(HTTPException) as exc_info:
            _validate_date_range("2024-01-01", "invalid-date")

        assert exc_info.value.status_code == 400

    def test_rejects_reversed_date_range(self):
        """Test that reversed date range raises HTTPException."""
        from app.modules.cash_flows.api.cash_flows import _validate_date_range

        with pytest.raises(HTTPException) as exc_info:
            _validate_date_range("2024-01-31", "2024-01-01")

        assert exc_info.value.status_code == 400
        assert "start_date must be before or equal to end_date" in exc_info.value.detail


class TestFormatCashFlowResponse:
    """Test _format_cash_flow_response helper function."""

    def test_formats_single_cash_flow(self):
        """Test formatting single cash flow to dict."""
        from app.modules.cash_flows.api.cash_flows import _format_cash_flow_response

        cash_flow = CashFlow(
            id=1,
            transaction_id="TX123",
            type_doc_id=5,
            transaction_type="deposit",
            date="2024-01-15",
            amount=1000.0,
            currency=Currency.EUR,
            amount_eur=1000.0,
            status="completed",
            status_c=1,
            description="Test deposit",
            created_at="2024-01-15T10:00:00",
            updated_at="2024-01-15T10:00:00",
        )

        result = _format_cash_flow_response([cash_flow])

        assert len(result) == 1
        assert result[0]["id"] == 1
        assert result[0]["transaction_id"] == "TX123"
        assert result[0]["type_doc_id"] == 5
        assert result[0]["transaction_type"] == "deposit"
        assert result[0]["date"] == "2024-01-15"
        assert result[0]["amount"] == 1000.0
        assert result[0]["currency"] == Currency.EUR
        assert result[0]["amount_eur"] == 1000.0
        assert result[0]["status"] == "completed"
        assert result[0]["status_c"] == 1
        assert result[0]["description"] == "Test deposit"
        assert result[0]["created_at"] == "2024-01-15T10:00:00"
        assert result[0]["updated_at"] == "2024-01-15T10:00:00"

    def test_formats_multiple_cash_flows(self):
        """Test formatting multiple cash flows."""
        from app.modules.cash_flows.api.cash_flows import _format_cash_flow_response

        cash_flows = [
            CashFlow(
                id=1,
                transaction_id="TX1",
                type_doc_id=5,
                date="2024-01-15",
                amount=1000.0,
                currency=Currency.EUR,
                amount_eur=1000.0,
            ),
            CashFlow(
                id=2,
                transaction_id="TX2",
                type_doc_id=6,
                date="2024-01-16",
                amount=500.0,
                currency=Currency.USD,
                amount_eur=475.0,
            ),
        ]

        result = _format_cash_flow_response(cash_flows)

        assert len(result) == 2
        assert result[0]["transaction_id"] == "TX1"
        assert result[1]["transaction_id"] == "TX2"

    def test_formats_empty_list(self):
        """Test formatting empty list."""
        from app.modules.cash_flows.api.cash_flows import _format_cash_flow_response

        result = _format_cash_flow_response([])

        assert result == []

    def test_handles_none_optional_fields(self):
        """Test handling of None optional fields."""
        from app.modules.cash_flows.api.cash_flows import _format_cash_flow_response

        cash_flow = CashFlow(
            id=1,
            transaction_id="TX123",
            type_doc_id=5,
            date="2024-01-15",
            amount=1000.0,
            currency=Currency.EUR,
            amount_eur=1000.0,
            transaction_type=None,
            status=None,
            status_c=None,
            description=None,
            created_at=None,
            updated_at=None,
        )

        result = _format_cash_flow_response([cash_flow])

        assert len(result) == 1
        assert result[0]["transaction_type"] is None
        assert result[0]["status"] is None
        assert result[0]["description"] is None


class TestFetchCashFlows:
    """Test _fetch_cash_flows helper function."""

    @pytest.mark.asyncio
    async def test_fetches_by_date_range(self):
        """Test fetching cash flows by date range."""
        from app.modules.cash_flows.api.cash_flows import _fetch_cash_flows

        mock_repo = AsyncMock()
        mock_repo.get_by_date_range = AsyncMock(return_value=[])

        await _fetch_cash_flows(
            mock_repo,
            start_date="2024-01-01",
            end_date="2024-01-31",
            transaction_type=None,
            limit=None,
        )

        mock_repo.get_by_date_range.assert_called_once_with("2024-01-01", "2024-01-31")

    @pytest.mark.asyncio
    async def test_fetches_by_transaction_type(self):
        """Test fetching cash flows by transaction type."""
        from app.modules.cash_flows.api.cash_flows import _fetch_cash_flows

        mock_repo = AsyncMock()
        mock_repo.get_by_type = AsyncMock(return_value=[])

        await _fetch_cash_flows(
            mock_repo,
            start_date=None,
            end_date=None,
            transaction_type="deposit",
            limit=None,
        )

        mock_repo.get_by_type.assert_called_once_with("deposit")

    @pytest.mark.asyncio
    async def test_fetches_all_with_limit(self):
        """Test fetching all cash flows with limit."""
        from app.modules.cash_flows.api.cash_flows import _fetch_cash_flows

        mock_repo = AsyncMock()
        mock_repo.get_all = AsyncMock(return_value=[])

        await _fetch_cash_flows(
            mock_repo,
            start_date=None,
            end_date=None,
            transaction_type=None,
            limit=100,
        )

        mock_repo.get_all.assert_called_once_with(limit=100)

    @pytest.mark.asyncio
    async def test_date_range_takes_precedence_over_type(self):
        """Test that date range takes precedence over transaction type."""
        from app.modules.cash_flows.api.cash_flows import _fetch_cash_flows

        mock_repo = AsyncMock()
        mock_repo.get_by_date_range = AsyncMock(return_value=[])
        mock_repo.get_by_type = AsyncMock(return_value=[])

        await _fetch_cash_flows(
            mock_repo,
            start_date="2024-01-01",
            end_date="2024-01-31",
            transaction_type="deposit",
            limit=None,
        )

        mock_repo.get_by_date_range.assert_called_once()
        mock_repo.get_by_type.assert_not_called()

    @pytest.mark.asyncio
    async def test_date_range_requires_both_dates(self):
        """Test that date range requires both start and end dates."""
        from app.modules.cash_flows.api.cash_flows import _fetch_cash_flows

        mock_repo = AsyncMock()
        mock_repo.get_by_date_range = AsyncMock(return_value=[])
        mock_repo.get_by_type = AsyncMock(return_value=[])
        mock_repo.get_all = AsyncMock(return_value=[])

        # Only start_date - should use get_by_type or get_all
        await _fetch_cash_flows(
            mock_repo,
            start_date="2024-01-01",
            end_date=None,
            transaction_type="deposit",
            limit=None,
        )

        mock_repo.get_by_date_range.assert_not_called()
        mock_repo.get_by_type.assert_called_once()


class TestGetCashFlows:
    """Test GET /cash-flows endpoint."""

    @pytest.mark.asyncio
    async def test_returns_all_cash_flows(self):
        """Test returning all cash flows."""
        from app.modules.cash_flows.api.cash_flows import get_cash_flows

        mock_cash_flows = [
            CashFlow(
                id=1,
                transaction_id="TX1",
                type_doc_id=5,
                date="2024-01-15",
                amount=1000.0,
                currency=Currency.EUR,
                amount_eur=1000.0,
                transaction_type="deposit",
            ),
        ]

        mock_repo = AsyncMock()
        mock_repo.get_all = AsyncMock(return_value=mock_cash_flows)

        result = await get_cash_flows(
            mock_repo, limit=None, transaction_type=None, start_date=None, end_date=None
        )

        assert len(result) == 1
        assert result[0]["transaction_id"] == "TX1"
        assert result[0]["amount"] == 1000.0
        mock_repo.get_all.assert_called_once_with(limit=None)

    @pytest.mark.asyncio
    async def test_applies_limit(self):
        """Test applying limit to results."""
        from app.modules.cash_flows.api.cash_flows import get_cash_flows

        mock_repo = AsyncMock()
        mock_repo.get_all = AsyncMock(return_value=[])

        await get_cash_flows(
            mock_repo, limit=50, transaction_type=None, start_date=None, end_date=None
        )

        mock_repo.get_all.assert_called_once_with(limit=50)

    @pytest.mark.asyncio
    async def test_filters_by_transaction_type(self):
        """Test filtering by transaction type."""
        from app.modules.cash_flows.api.cash_flows import get_cash_flows

        mock_cash_flows = [
            CashFlow(
                id=1,
                transaction_id="TX1",
                type_doc_id=5,
                date="2024-01-15",
                amount=1000.0,
                currency=Currency.EUR,
                amount_eur=1000.0,
                transaction_type="deposit",
            ),
        ]

        mock_repo = AsyncMock()
        mock_repo.get_by_type = AsyncMock(return_value=mock_cash_flows)

        result = await get_cash_flows(
            mock_repo,
            limit=None,
            transaction_type="deposit",
            start_date=None,
            end_date=None,
        )

        assert len(result) == 1
        assert result[0]["transaction_type"] == "deposit"
        mock_repo.get_by_type.assert_called_once_with("deposit")

    @pytest.mark.asyncio
    async def test_filters_by_date_range(self):
        """Test filtering by date range."""
        from app.modules.cash_flows.api.cash_flows import get_cash_flows

        mock_cash_flows = [
            CashFlow(
                id=1,
                transaction_id="TX1",
                type_doc_id=5,
                date="2024-01-15",
                amount=1000.0,
                currency=Currency.EUR,
                amount_eur=1000.0,
            ),
        ]

        mock_repo = AsyncMock()
        mock_repo.get_by_date_range = AsyncMock(return_value=mock_cash_flows)

        result = await get_cash_flows(
            mock_repo, start_date="2024-01-01", end_date="2024-01-31"
        )

        assert len(result) == 1
        mock_repo.get_by_date_range.assert_called_once_with("2024-01-01", "2024-01-31")

    @pytest.mark.asyncio
    async def test_validates_date_format(self):
        """Test that date format is validated."""
        from app.modules.cash_flows.api.cash_flows import get_cash_flows

        mock_repo = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_cash_flows(
                mock_repo, start_date="invalid-date", end_date="2024-01-31"
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_validates_date_range_order(self):
        """Test that date range order is validated."""
        from app.modules.cash_flows.api.cash_flows import get_cash_flows

        mock_repo = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_cash_flows(
                mock_repo, start_date="2024-01-31", end_date="2024-01-01"
            )

        assert exc_info.value.status_code == 400
        assert "start_date must be before or equal to end_date" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_handles_empty_results(self):
        """Test handling empty results."""
        from app.modules.cash_flows.api.cash_flows import get_cash_flows

        mock_repo = AsyncMock()
        mock_repo.get_all = AsyncMock(return_value=[])

        result = await get_cash_flows(
            mock_repo, limit=None, transaction_type=None, start_date=None, end_date=None
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_handles_repository_error(self):
        """Test handling repository errors."""
        from app.modules.cash_flows.api.cash_flows import get_cash_flows

        mock_repo = AsyncMock()
        mock_repo.get_all = AsyncMock(side_effect=Exception("Database error"))

        with pytest.raises(HTTPException) as exc_info:
            await get_cash_flows(
                mock_repo,
                limit=None,
                transaction_type=None,
                start_date=None,
                end_date=None,
            )

        assert exc_info.value.status_code == 500
        assert "Failed to retrieve cash flows" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_preserves_http_exceptions(self):
        """Test that HTTPExceptions are preserved."""
        from app.modules.cash_flows.api.cash_flows import get_cash_flows

        mock_repo = AsyncMock()
        mock_repo.get_all = AsyncMock(
            side_effect=HTTPException(status_code=403, detail="Forbidden")
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_cash_flows(
                mock_repo,
                limit=None,
                transaction_type=None,
                start_date=None,
                end_date=None,
            )

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Forbidden"


class TestSyncCashFlows:
    """Test GET /cash-flows/sync endpoint."""

    @pytest.mark.asyncio
    async def test_syncs_transactions_successfully(self):
        """Test successful transaction sync."""
        from app.modules.cash_flows.api.cash_flows import sync_cash_flows

        mock_transactions = [
            {
                "id": "TX1",
                "type_doc_id": 5,
                "type_doc": "deposit",
                "dt": "2024-01-15",
                "sm": 1000.0,
                "curr": "EUR",
                "sm_eur": 1000.0,
            },
            {
                "id": "TX2",
                "type_doc_id": 6,
                "type_doc": "withdrawal",
                "dt": "2024-01-16",
                "sm": -500.0,
                "curr": "EUR",
                "sm_eur": -500.0,
            },
        ]

        mock_client = MagicMock()
        mock_client.get_all_cash_flows.return_value = mock_transactions

        mock_repo = AsyncMock()
        mock_repo.sync_from_api = AsyncMock(return_value=2)

        with patch(
            "app.api.cash_flows.ensure_tradernet_connected",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await sync_cash_flows(mock_repo)

        assert result["synced"] == 2
        assert result["total_from_api"] == 2
        assert "Synced 2 transactions" in result["message"]
        mock_client.get_all_cash_flows.assert_called_once_with(limit=1000)
        mock_repo.sync_from_api.assert_called_once_with(mock_transactions)

    @pytest.mark.asyncio
    async def test_handles_no_transactions(self):
        """Test handling when no transactions are found."""
        from app.modules.cash_flows.api.cash_flows import sync_cash_flows

        mock_client = MagicMock()
        mock_client.get_all_cash_flows.return_value = []

        mock_repo = AsyncMock()

        with patch(
            "app.api.cash_flows.ensure_tradernet_connected",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await sync_cash_flows(mock_repo)

        assert result["synced"] == 0
        assert result["message"] == "No transactions found"

    @pytest.mark.asyncio
    async def test_handles_none_transactions(self):
        """Test handling when transactions are None."""
        from app.modules.cash_flows.api.cash_flows import sync_cash_flows

        mock_client = MagicMock()
        mock_client.get_all_cash_flows.return_value = None

        mock_repo = AsyncMock()

        with patch(
            "app.api.cash_flows.ensure_tradernet_connected",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await sync_cash_flows(mock_repo)

        assert result["synced"] == 0
        assert result["message"] == "No transactions found"

    @pytest.mark.asyncio
    async def test_handles_partial_sync(self):
        """Test handling when only some transactions are synced."""
        from app.modules.cash_flows.api.cash_flows import sync_cash_flows

        mock_transactions = [{"id": "TX1"}, {"id": "TX2"}, {"id": "TX3"}]

        mock_client = MagicMock()
        mock_client.get_all_cash_flows.return_value = mock_transactions

        mock_repo = AsyncMock()
        mock_repo.sync_from_api = AsyncMock(return_value=1)  # Only 1 new

        with patch(
            "app.api.cash_flows.ensure_tradernet_connected",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await sync_cash_flows(mock_repo)

        assert result["synced"] == 1
        assert result["total_from_api"] == 3

    @pytest.mark.asyncio
    async def test_handles_api_connection_error(self):
        """Test handling API connection errors.

        Note: ensure_tradernet_connected() is called outside the try block,
        so the exception is not caught and wrapped in HTTPException.
        """
        from app.modules.cash_flows.api.cash_flows import sync_cash_flows

        mock_repo = AsyncMock()

        with patch(
            "app.api.cash_flows.ensure_tradernet_connected",
            new_callable=AsyncMock,
            side_effect=Exception("Connection failed"),
        ):
            with pytest.raises(Exception) as exc_info:
                await sync_cash_flows(mock_repo)

            assert str(exc_info.value) == "Connection failed"

    @pytest.mark.asyncio
    async def test_handles_api_fetch_error(self):
        """Test handling API fetch errors."""
        from app.modules.cash_flows.api.cash_flows import sync_cash_flows

        mock_client = MagicMock()
        mock_client.get_all_cash_flows.side_effect = Exception("API error")

        mock_repo = AsyncMock()

        with patch(
            "app.api.cash_flows.ensure_tradernet_connected",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await sync_cash_flows(mock_repo)

        assert exc_info.value.status_code == 500
        assert "Failed to sync cash flows" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_handles_repository_sync_error(self):
        """Test handling repository sync errors."""
        from app.modules.cash_flows.api.cash_flows import sync_cash_flows

        mock_transactions = [{"id": "TX1"}]

        mock_client = MagicMock()
        mock_client.get_all_cash_flows.return_value = mock_transactions

        mock_repo = AsyncMock()
        mock_repo.sync_from_api = AsyncMock(side_effect=Exception("Database error"))

        with patch(
            "app.api.cash_flows.ensure_tradernet_connected",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await sync_cash_flows(mock_repo)

        assert exc_info.value.status_code == 500
        assert "Failed to sync cash flows" in exc_info.value.detail


class TestGetCashFlowsSummary:
    """Test GET /cash-flows/summary endpoint."""

    @pytest.mark.asyncio
    async def test_returns_summary_with_all_types(self):
        """Test returning summary with all transaction types."""
        from app.modules.cash_flows.api.cash_flows import get_cash_flows_summary

        mock_cash_flows = [
            CashFlow(
                id=1,
                transaction_id="TX1",
                type_doc_id=5,
                date="2024-01-15",
                amount=1000.0,
                currency=Currency.EUR,
                amount_eur=1000.0,
                transaction_type="deposit",
            ),
            CashFlow(
                id=2,
                transaction_id="TX2",
                type_doc_id=6,
                date="2024-01-16",
                amount=-500.0,
                currency=Currency.EUR,
                amount_eur=-500.0,
                transaction_type="withdrawal",
            ),
            CashFlow(
                id=3,
                transaction_id="TX3",
                type_doc_id=7,
                date="2024-01-17",
                amount=50.0,
                currency=Currency.EUR,
                amount_eur=50.0,
                transaction_type="dividend",
            ),
        ]

        mock_repo = AsyncMock()
        mock_repo.get_all = AsyncMock(return_value=mock_cash_flows)

        result = await get_cash_flows_summary(mock_repo)

        assert result["total_transactions"] == 3
        assert result["total_deposits_eur"] == 1000.0
        assert result["total_withdrawals_eur"] == -500.0
        # Net = deposits - withdrawals = 1000 - (-500) = 1500
        assert result["net_cash_flow_eur"] == 1500.0
        assert "deposit" in result["by_type"]
        assert "withdrawal" in result["by_type"]
        assert "dividend" in result["by_type"]
        assert result["by_type"]["deposit"]["total_eur"] == 1000.0
        assert result["by_type"]["deposit"]["count"] == 1
        assert result["by_type"]["withdrawal"]["total_eur"] == -500.0
        assert result["by_type"]["withdrawal"]["count"] == 1

    @pytest.mark.asyncio
    async def test_handles_multiple_same_type(self):
        """Test handling multiple transactions of the same type."""
        from app.modules.cash_flows.api.cash_flows import get_cash_flows_summary

        mock_cash_flows = [
            CashFlow(
                id=1,
                transaction_id="TX1",
                type_doc_id=5,
                date="2024-01-15",
                amount=1000.0,
                currency=Currency.EUR,
                amount_eur=1000.0,
                transaction_type="deposit",
            ),
            CashFlow(
                id=2,
                transaction_id="TX2",
                type_doc_id=5,
                date="2024-01-16",
                amount=2000.0,
                currency=Currency.EUR,
                amount_eur=2000.0,
                transaction_type="deposit",
            ),
        ]

        mock_repo = AsyncMock()
        mock_repo.get_all = AsyncMock(return_value=mock_cash_flows)

        result = await get_cash_flows_summary(mock_repo)

        assert result["total_transactions"] == 2
        assert result["total_deposits_eur"] == 3000.0
        assert result["by_type"]["deposit"]["total_eur"] == 3000.0
        assert result["by_type"]["deposit"]["count"] == 2

    @pytest.mark.asyncio
    async def test_handles_none_transaction_type(self):
        """Test handling transactions with None type."""
        from app.modules.cash_flows.api.cash_flows import get_cash_flows_summary

        mock_cash_flows = [
            CashFlow(
                id=1,
                transaction_id="TX1",
                type_doc_id=5,
                date="2024-01-15",
                amount=100.0,
                currency=Currency.EUR,
                amount_eur=100.0,
                transaction_type=None,
            ),
        ]

        mock_repo = AsyncMock()
        mock_repo.get_all = AsyncMock(return_value=mock_cash_flows)

        result = await get_cash_flows_summary(mock_repo)

        assert result["total_transactions"] == 1
        assert "unknown" in result["by_type"]
        assert result["by_type"]["unknown"]["total_eur"] == 100.0
        assert result["by_type"]["unknown"]["count"] == 1

    @pytest.mark.asyncio
    async def test_handles_empty_cash_flows(self):
        """Test handling empty cash flows."""
        from app.modules.cash_flows.api.cash_flows import get_cash_flows_summary

        mock_repo = AsyncMock()
        mock_repo.get_all = AsyncMock(return_value=[])

        result = await get_cash_flows_summary(mock_repo)

        assert result["total_transactions"] == 0
        assert result["total_deposits_eur"] == 0.0
        assert result["total_withdrawals_eur"] == 0.0
        assert result["net_cash_flow_eur"] == 0.0
        assert result["by_type"] == {}

    @pytest.mark.asyncio
    async def test_case_insensitive_deposit_matching(self):
        """Test case-insensitive matching for deposits."""
        from app.modules.cash_flows.api.cash_flows import get_cash_flows_summary

        mock_cash_flows = [
            CashFlow(
                id=1,
                transaction_id="TX1",
                type_doc_id=5,
                date="2024-01-15",
                amount=100.0,
                currency=Currency.EUR,
                amount_eur=100.0,
                transaction_type="DEPOSIT",
            ),
            CashFlow(
                id=2,
                transaction_id="TX2",
                type_doc_id=5,
                date="2024-01-16",
                amount=200.0,
                currency=Currency.EUR,
                amount_eur=200.0,
                transaction_type="Deposit",
            ),
            CashFlow(
                id=3,
                transaction_id="TX3",
                type_doc_id=5,
                date="2024-01-17",
                amount=300.0,
                currency=Currency.EUR,
                amount_eur=300.0,
                transaction_type="deposit",
            ),
        ]

        mock_repo = AsyncMock()
        mock_repo.get_all = AsyncMock(return_value=mock_cash_flows)

        result = await get_cash_flows_summary(mock_repo)

        assert result["total_deposits_eur"] == 600.0

    @pytest.mark.asyncio
    async def test_case_insensitive_withdrawal_matching(self):
        """Test case-insensitive matching for withdrawals."""
        from app.modules.cash_flows.api.cash_flows import get_cash_flows_summary

        mock_cash_flows = [
            CashFlow(
                id=1,
                transaction_id="TX1",
                type_doc_id=6,
                date="2024-01-15",
                amount=-100.0,
                currency=Currency.EUR,
                amount_eur=-100.0,
                transaction_type="WITHDRAWAL",
            ),
            CashFlow(
                id=2,
                transaction_id="TX2",
                type_doc_id=6,
                date="2024-01-16",
                amount=-200.0,
                currency=Currency.EUR,
                amount_eur=-200.0,
                transaction_type="Withdrawal",
            ),
            CashFlow(
                id=3,
                transaction_id="TX3",
                type_doc_id=6,
                date="2024-01-17",
                amount=-300.0,
                currency=Currency.EUR,
                amount_eur=-300.0,
                transaction_type="withdrawal",
            ),
        ]

        mock_repo = AsyncMock()
        mock_repo.get_all = AsyncMock(return_value=mock_cash_flows)

        result = await get_cash_flows_summary(mock_repo)

        assert result["total_withdrawals_eur"] == -600.0

    @pytest.mark.asyncio
    async def test_rounds_amounts_to_two_decimals(self):
        """Test that amounts are rounded to 2 decimal places."""
        from app.modules.cash_flows.api.cash_flows import get_cash_flows_summary

        mock_cash_flows = [
            CashFlow(
                id=1,
                transaction_id="TX1",
                type_doc_id=5,
                date="2024-01-15",
                amount=100.123456,
                currency=Currency.EUR,
                amount_eur=100.123456,
                transaction_type="deposit",
            ),
        ]

        mock_repo = AsyncMock()
        mock_repo.get_all = AsyncMock(return_value=mock_cash_flows)

        result = await get_cash_flows_summary(mock_repo)

        assert result["total_deposits_eur"] == 100.12
        assert result["by_type"]["deposit"]["total_eur"] == 100.12

    @pytest.mark.asyncio
    async def test_handles_repository_error(self):
        """Test handling repository errors."""
        from app.modules.cash_flows.api.cash_flows import get_cash_flows_summary

        mock_repo = AsyncMock()
        mock_repo.get_all = AsyncMock(side_effect=Exception("Database error"))

        with pytest.raises(HTTPException) as exc_info:
            await get_cash_flows_summary(mock_repo)

        assert exc_info.value.status_code == 500
        assert "Failed to get summary" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_net_cash_flow_calculation(self):
        """Test net cash flow calculation."""
        from app.modules.cash_flows.api.cash_flows import get_cash_flows_summary

        mock_cash_flows = [
            CashFlow(
                id=1,
                transaction_id="TX1",
                type_doc_id=5,
                date="2024-01-15",
                amount=1000.0,
                currency=Currency.EUR,
                amount_eur=1000.0,
                transaction_type="deposit",
            ),
            CashFlow(
                id=2,
                transaction_id="TX2",
                type_doc_id=6,
                date="2024-01-16",
                amount=-300.0,
                currency=Currency.EUR,
                amount_eur=-300.0,
                transaction_type="withdrawal",
            ),
        ]

        mock_repo = AsyncMock()
        mock_repo.get_all = AsyncMock(return_value=mock_cash_flows)

        result = await get_cash_flows_summary(mock_repo)

        # Net = deposits - withdrawals = 1000 - (-300) = 1300
        assert result["net_cash_flow_eur"] == 1300.0

    @pytest.mark.asyncio
    async def test_handles_mixed_transaction_types(self):
        """Test handling various transaction types."""
        from app.modules.cash_flows.api.cash_flows import get_cash_flows_summary

        mock_cash_flows = [
            CashFlow(
                id=1,
                transaction_id="TX1",
                type_doc_id=5,
                date="2024-01-15",
                amount=1000.0,
                currency=Currency.EUR,
                amount_eur=1000.0,
                transaction_type="deposit",
            ),
            CashFlow(
                id=2,
                transaction_id="TX2",
                type_doc_id=6,
                date="2024-01-16",
                amount=-500.0,
                currency=Currency.EUR,
                amount_eur=-500.0,
                transaction_type="withdrawal",
            ),
            CashFlow(
                id=3,
                transaction_id="TX3",
                type_doc_id=7,
                date="2024-01-17",
                amount=50.0,
                currency=Currency.EUR,
                amount_eur=50.0,
                transaction_type="dividend",
            ),
            CashFlow(
                id=4,
                transaction_id="TX4",
                type_doc_id=8,
                date="2024-01-18",
                amount=-10.0,
                currency=Currency.EUR,
                amount_eur=-10.0,
                transaction_type="fee",
            ),
        ]

        mock_repo = AsyncMock()
        mock_repo.get_all = AsyncMock(return_value=mock_cash_flows)

        result = await get_cash_flows_summary(mock_repo)

        assert result["total_transactions"] == 4
        assert len(result["by_type"]) == 4
        assert "dividend" in result["by_type"]
        assert "fee" in result["by_type"]
        assert result["by_type"]["dividend"]["total_eur"] == 50.0
        assert result["by_type"]["fee"]["total_eur"] == -10.0
