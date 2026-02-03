"""Jobs API routes for job management and scheduling."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from typing_extensions import Annotated

from sentinel.api.dependencies import CommonDependencies, get_common_deps
from sentinel.jobs import get_status, reschedule, run_now

router = APIRouter(prefix="/jobs", tags=["jobs"])

MARKET_TIMING_LABELS = {
    0: "Any time",
    1: "After market close",
    2: "During market open",
    3: "All markets closed",
}

# Global scheduler reference - set from app.py
_scheduler = None


def set_scheduler(scheduler):
    """Set the scheduler instance from app.py."""
    global _scheduler
    _scheduler = scheduler


@router.get("")
async def get_jobs() -> dict:
    """Get current job, upcoming jobs and recent job history."""
    status = await get_status()
    return status


@router.post("/{job_type:path}/run")
async def run_job_endpoint(job_type: str) -> dict:
    """Manually trigger a job by type. Executes immediately."""
    result = await run_now(job_type)
    if result.get("status") == "failed" and "Unknown job type" in result.get("error", ""):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/refresh-all")
async def refresh_all(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict:
    """Reset last_run timestamp to 0 for all jobs and reschedule."""
    await deps.db.conn.execute("UPDATE job_schedules SET last_run = 0")
    await deps.db.conn.commit()
    schedules = await deps.db.get_job_schedules()
    for s in schedules:
        await reschedule(s["job_type"], deps.db)
    return {"status": "ok", "message": "All jobs rescheduled"}


@router.get("/schedules")
async def get_job_schedules(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict:
    """Get all job schedule configurations with status info."""
    schedules = await deps.db.get_job_schedules()

    # Get next run times from APScheduler
    next_run_times = {}
    if _scheduler:
        for job in _scheduler.get_jobs():
            if job.next_run_time:
                next_run_times[job.id] = job.next_run_time.isoformat()

    # Enrich with runtime info
    result = []
    for s in schedules:
        job_type = s["job_type"]

        # Get most recent execution (not just successful ones)
        history = await deps.db.get_job_history_for_type(job_type, limit=1)
        if history:
            last_run = datetime.fromtimestamp(history[0]["executed_at"]).isoformat()
            last_status = history[0]["status"]
        else:
            last_run = None
            last_status = None

        result.append(
            {
                "job_type": s["job_type"],
                "interval_minutes": s["interval_minutes"],
                "interval_market_open_minutes": s.get("interval_market_open_minutes"),
                "market_timing": s["market_timing"],
                "market_timing_label": MARKET_TIMING_LABELS.get(s["market_timing"], "Unknown"),
                "description": s.get("description"),
                "category": s.get("category"),
                "last_run": last_run,
                "last_status": last_status,
                "next_run": next_run_times.get(job_type),
            }
        )

    return {"schedules": result}


@router.put("/schedules/{job_type:path}")
async def update_job_schedule(
    job_type: str,
    data: dict,
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict:
    """Update a job's schedule configuration."""
    # Check if job_type exists
    existing = await deps.db.get_job_schedule(job_type)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Unknown job type: {job_type}")

    # Validate interval_minutes
    if "interval_minutes" in data:
        val = data["interval_minutes"]
        if not isinstance(val, int) or val < 1 or val > 10080:
            raise HTTPException(status_code=400, detail="interval_minutes must be between 1 and 10080")

    # Validate interval_market_open_minutes
    if "interval_market_open_minutes" in data:
        val = data["interval_market_open_minutes"]
        if val is not None and (not isinstance(val, int) or val < 1 or val > 10080):
            raise HTTPException(status_code=400, detail="interval_market_open_minutes must be between 1 and 10080")

    # Validate market_timing
    if "market_timing" in data:
        val = data["market_timing"]
        if not isinstance(val, int) or val < 0 or val > 3:
            raise HTTPException(status_code=400, detail="market_timing must be 0, 1, 2, or 3")

    await deps.db.upsert_job_schedule(
        job_type,
        interval_minutes=data.get("interval_minutes"),
        interval_market_open_minutes=data.get("interval_market_open_minutes"),
        market_timing=data.get("market_timing"),
    )

    # Reschedule the job in APScheduler
    await reschedule(job_type, deps.db)

    return {"status": "ok"}


@router.get("/history")
async def get_job_history(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
    job_type: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Get job execution history."""
    if job_type:
        history = await deps.db.get_job_history_for_type(job_type, limit=limit)
    else:
        history = await deps.db.get_job_history(limit=limit)

    return {"history": history}
