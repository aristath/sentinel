"""Planner API endpoints for sequence regeneration."""

import json
import logging
from typing import Any, AsyncIterator, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.domain.portfolio_hash import generate_portfolio_hash
from app.infrastructure.dependencies import (
    PositionRepositoryDep,
    StockRepositoryDep,
    TradernetClientDep,
)
from app.modules.planning.database.planner_repository import PlannerRepository

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/regenerate-sequences")
async def regenerate_sequences(
    position_repo: PositionRepositoryDep,
    stock_repo: StockRepositoryDep,
    tradernet_client: TradernetClientDep,
):
    """
    Regenerate sequences for current portfolio with current settings.

    This:
    1. Deletes existing sequences (keeps evaluations)
    2. Clears best_result (since best sequence may no longer exist)
    3. Returns success status

    Next batch run will detect no sequences and regenerate them.
    """
    try:
        # Get current portfolio state
        positions = await position_repo.get_all()
        stocks = await stock_repo.get_all_active()

        # Fetch pending orders for hash generation
        pending_orders = []
        cash_balances = {}
        if tradernet_client.is_connected:
            try:
                pending_orders = tradernet_client.get_pending_orders()
                cash_balances_raw = tradernet_client.get_cash_balances()
                cash_balances = (
                    {b.currency: b.amount for b in cash_balances_raw}
                    if cash_balances_raw
                    else {}
                )
            except Exception as e:
                logger.warning(f"Failed to fetch pending orders: {e}")

        # Generate portfolio hash
        position_dicts = [
            {"symbol": p.symbol, "quantity": p.quantity} for p in positions
        ]
        portfolio_hash = generate_portfolio_hash(
            position_dicts, stocks, cash_balances, pending_orders
        )

        # Delete sequences only (keep evaluations)
        planner_repo = PlannerRepository()
        await planner_repo.delete_sequences_only(portfolio_hash)

        # Clear best_result (since best sequence may no longer exist)
        db = await planner_repo._get_db()
        await db.execute(
            "DELETE FROM best_result WHERE portfolio_hash = ?", (portfolio_hash,)
        )
        await db.commit()

        logger.info(
            f"Regenerated sequences for portfolio {portfolio_hash[:8]} - sequences deleted, evaluations preserved"
        )

        return {
            "status": "success",
            "message": "Sequences regenerated. New sequences will be generated on next batch run.",
            "portfolio_hash": portfolio_hash[:8],
        }

    except Exception as e:
        logger.error(f"Error regenerating sequences: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _get_planner_status_internal(
    position_repo: PositionRepositoryDep,
    stock_repo: StockRepositoryDep,
    tradernet_client: TradernetClientDep,
) -> Dict[str, Any]:
    """
    Internal function to get planner status.

    Returns:
        Planner status dictionary
    """
    # Get current portfolio state
    positions = await position_repo.get_all()
    stocks = await stock_repo.get_all_active()

    # Fetch pending orders for hash generation
    pending_orders = []
    cash_balances = {}
    if tradernet_client.is_connected:
        try:
            pending_orders = tradernet_client.get_pending_orders()
            cash_balances_raw = tradernet_client.get_cash_balances()
            cash_balances = (
                {b.currency: b.amount for b in cash_balances_raw}
                if cash_balances_raw
                else {}
            )
        except Exception as e:
            logger.warning(f"Failed to fetch pending orders: {e}")

    # Generate portfolio hash
    position_dicts = [{"symbol": p.symbol, "quantity": p.quantity} for p in positions]
    portfolio_hash = generate_portfolio_hash(
        position_dicts, stocks, cash_balances, pending_orders
    )

    planner_repo = PlannerRepository()

    # Get sequence statistics
    has_sequences = await planner_repo.has_sequences(portfolio_hash)
    total_sequences = await planner_repo.get_total_sequence_count(portfolio_hash)
    evaluated_count = await planner_repo.get_evaluation_count(portfolio_hash)
    is_finished = await planner_repo.are_all_sequences_evaluated(portfolio_hash)

    # Calculate progress percentage
    if total_sequences > 0:
        progress_percentage = (evaluated_count / total_sequences) * 100.0
    else:
        progress_percentage = 0.0

    # Check if planning is currently running
    # Planning is considered active if:
    # 1. Sequences exist
    # 2. Not all sequences are evaluated
    # 3. Scheduler is running and has planner_batch job scheduled
    is_planning = False
    if has_sequences and not is_finished:
        try:
            from app.jobs.scheduler import get_scheduler

            scheduler = get_scheduler()
            if scheduler and scheduler.running:
                # Check if planner_batch job exists in scheduler
                jobs = scheduler.get_jobs()
                planner_job = next(
                    (job for job in jobs if job.id == "planner_batch"), None
                )
                if planner_job:
                    is_planning = True
        except Exception as e:
            logger.debug(f"Could not check scheduler status: {e}")
            # If we can't check scheduler, assume planning is active if there's work to do
            is_planning = True

    return {
        "has_sequences": has_sequences,
        "total_sequences": total_sequences,
        "evaluated_count": evaluated_count,
        "is_planning": is_planning,
        "is_finished": is_finished,
        "portfolio_hash": portfolio_hash[:8],
        "progress_percentage": round(progress_percentage, 1),
    }


@router.get("/status")
async def get_planner_status(
    position_repo: PositionRepositoryDep,
    stock_repo: StockRepositoryDep,
    tradernet_client: TradernetClientDep,
):
    """
    Get planner status including sequence generation and evaluation progress.

    Returns:
        Planner status with:
        - has_sequences: Whether sequences have been generated
        - total_sequences: Total sequences generated
        - evaluated_count: Number of evaluated sequences
        - is_planning: Whether planning is currently running
        - is_finished: Whether all sequences have been evaluated
        - portfolio_hash: Portfolio hash being processed
        - progress_percentage: Percentage of sequences evaluated (0-100)
    """
    try:
        return await _get_planner_status_internal(
            position_repo, stock_repo, tradernet_client
        )
    except Exception as e:
        logger.error(f"Error getting planner status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/stream")
async def stream_planner_status(
    position_repo: PositionRepositoryDep,
    stock_repo: StockRepositoryDep,
    tradernet_client: TradernetClientDep,
):
    """Stream planner status updates via Server-Sent Events (SSE).

    Real-time streaming of planner status updates. Initial status is sent
    immediately on connection, then updates are streamed as batches complete.
    """
    from app.modules.planning import events as planner_events

    async def event_generator() -> AsyncIterator[str]:
        """Generate SSE events from planner status changes."""
        try:
            # Get initial status and cache it (subscribe_planner_events will send it)
            initial_status = await _get_planner_status_internal(
                position_repo, stock_repo, tradernet_client
            )
            await planner_events.set_current_status(initial_status)

            # Subscribe to planner events (sends initial status from cache, then streams updates)
            async for status_data in planner_events.subscribe_planner_events():
                # Format as SSE event: data: {json}\n\n
                event_data = json.dumps(status_data)
                yield f"data: {event_data}\n\n"

        except Exception as e:
            logger.error(f"SSE stream error: {e}", exc_info=True)
            # Send error event and close
            error_data = json.dumps({"error": "Stream closed"})
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
