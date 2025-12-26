"""Cash flows API endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.infrastructure.dependencies import CashFlowRepositoryDep
from app.infrastructure.external.tradernet_connection import ensure_tradernet_connected

router = APIRouter()


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

    # Validate date format if provided
    if start_date or end_date:
        from datetime import datetime

        try:
            if start_date:
                datetime.strptime(start_date, "%Y-%m-%d")
            if end_date:
                datetime.strptime(end_date, "%Y-%m-%d")
            if start_date and end_date and start_date > end_date:
                raise HTTPException(
                    status_code=400,
                    detail="start_date must be before or equal to end_date",
                )
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Date must be in YYYY-MM-DD format"
            )

    try:
        if start_date and end_date:
            cash_flows = await cash_flow_repo.get_by_date_range(start_date, end_date)
        elif transaction_type:
            cash_flows = await cash_flow_repo.get_by_type(transaction_type)
        else:
            cash_flows = await cash_flow_repo.get_all(limit=limit)

        # Convert to dict for JSON response
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
