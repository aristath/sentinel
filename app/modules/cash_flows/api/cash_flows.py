"""Cash flows API endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.infrastructure.dependencies import CashFlowRepositoryDep
from app.infrastructure.external.tradernet_connection import ensure_tradernet_connected

router = APIRouter()


def _validate_date_format(date_str: str) -> None:
    """Validate date string is in YYYY-MM-DD format."""
    from datetime import datetime

    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Date must be in YYYY-MM-DD format")


def _validate_date_range(start_date: Optional[str], end_date: Optional[str]) -> None:
    """Validate date parameters."""
    if start_date or end_date:
        if start_date:
            _validate_date_format(start_date)
        if end_date:
            _validate_date_format(end_date)
        if start_date and end_date and start_date > end_date:
            raise HTTPException(
                status_code=400,
                detail="start_date must be before or equal to end_date",
            )


def _format_cash_flow_response(cash_flows) -> list[dict]:
    """Convert cash flow objects to dict format for JSON response."""
    return [
        {
            "id": cf.id,
            "transaction_id": cf.transaction_id,
            "type_doc_id": cf.type_doc_id,
            "transaction_type": cf.transaction_type,
            "date": cf.date,
            "amount": cf.amount,
            "currency": cf.currency,
            "amount_eur": cf.amount_eur,
            "status": cf.status,
            "status_c": cf.status_c,
            "description": cf.description,
            "created_at": cf.created_at,
            "updated_at": cf.updated_at,
        }
        for cf in cash_flows
    ]


async def _fetch_cash_flows(
    cash_flow_repo: CashFlowRepositoryDep,
    start_date: Optional[str],
    end_date: Optional[str],
    transaction_type: Optional[str],
    limit: Optional[int],
) -> list:
    """Fetch cash flows based on query parameters."""
    if start_date and end_date:
        return await cash_flow_repo.get_by_date_range(start_date, end_date)
    elif transaction_type:
        return await cash_flow_repo.get_by_type(transaction_type)
    else:
        return await cash_flow_repo.get_all(limit=limit)


@router.get("")
async def get_cash_flows(
    cash_flow_repo: CashFlowRepositoryDep,
    limit: Optional[int] = Query(
        None, ge=1, le=10000, description="Limit number of results (1-10000)"
    ),
    transaction_type: Optional[str] = Query(
        None, description="Filter by transaction type"
    ),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
):
    """
    Get cash flow transactions.

    Supports filtering by type, date range, and limiting results.
    """
    _validate_date_range(start_date, end_date)

    try:
        cash_flows = await _fetch_cash_flows(
            cash_flow_repo, start_date, end_date, transaction_type, limit
        )
        return _format_cash_flow_response(cash_flows)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve cash flows: {str(e)}"
        )


@router.get("/sync")
async def sync_cash_flows(cash_flow_repo: CashFlowRepositoryDep):
    """
    Sync cash flows from tradernet API.

    Fetches all cash flow transactions from the API and upserts them into the database.
    """
    client = await ensure_tradernet_connected()

    try:
        # Fetch all cash flows from API
        transactions = client.get_all_cash_flows(limit=1000)

        if not transactions:
            return {"message": "No transactions found", "synced": 0}

        # Sync to database
        synced_count = await cash_flow_repo.sync_from_api(transactions)

        return {
            "message": f"Synced {synced_count} transactions",
            "synced": synced_count,
            "total_from_api": len(transactions),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to sync cash flows: {str(e)}"
        )


@router.get("/summary")
async def get_cash_flows_summary(cash_flow_repo: CashFlowRepositoryDep):
    """
    Get summary statistics for cash flows.

    Returns totals by transaction type (deposits, withdrawals, etc.)
    """

    try:
        all_flows = await cash_flow_repo.get_all()

        # Group by transaction type
        type_totals = {}
        type_counts = {}

        for cf in all_flows:
            tx_type = cf.transaction_type or "unknown"

            if tx_type not in type_totals:
                type_totals[tx_type] = 0.0
                type_counts[tx_type] = 0

            type_totals[tx_type] += cf.amount_eur
            type_counts[tx_type] += 1

        # Calculate overall totals
        # Note: These are heuristics based on transaction_type name
        # Adjust as needed based on actual transaction types discovered
        total_deposits = sum(
            cf.amount_eur
            for cf in all_flows
            if cf.transaction_type and "deposit" in cf.transaction_type.lower()
        )
        total_withdrawals = sum(
            cf.amount_eur
            for cf in all_flows
            if cf.transaction_type and "withdrawal" in cf.transaction_type.lower()
        )

        return {
            "total_transactions": len(all_flows),
            "total_deposits_eur": round(total_deposits, 2),
            "total_withdrawals_eur": round(total_withdrawals, 2),
            "net_cash_flow_eur": round(total_deposits - total_withdrawals, 2),
            "by_type": {
                tx_type: {"total_eur": round(total, 2), "count": type_counts[tx_type]}
                for tx_type, total in type_totals.items()
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get summary: {str(e)}")
