"""Administration and execution API for editable Sentinel folder tasks."""

from __future__ import annotations

from typing import Annotated, Any, NoReturn

from fastapi import APIRouter, Body, HTTPException, Response, status

from sentinel.database import Database
from sentinel.tasks import definitions
from sentinel.tasks.runtime import enqueue_task, get_run, list_runs, resync_task_schedules, stop_run

router = APIRouter(tags=["tasks"])


def _raise_http(exc: Exception) -> NoReturn:
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, FileExistsError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _ensure_not_active(task_id: str) -> None:
    if await Database().get_active_task_work(task_id):
        raise HTTPException(status_code=409, detail=f'Task "{task_id}" has queued or running work')


@router.get("/tasks")
async def tasks_list() -> list[dict[str, Any]]:
    return definitions.list_tasks()


@router.post("/tasks", status_code=status.HTTP_201_CREATED)
async def tasks_create(body: dict[str, Any]) -> dict[str, Any]:
    try:
        task = definitions.create_task(str(body.get("name") or "Untitled task"))
        await resync_task_schedules()
        return task
    except Exception as exc:  # noqa: BLE001
        _raise_http(exc)


@router.get("/tasks/{task_id}")
async def task_get(task_id: str) -> dict[str, Any]:
    try:
        return definitions.get_task(task_id)
    except Exception as exc:  # noqa: BLE001
        _raise_http(exc)


@router.put("/tasks/{task_id}")
async def task_save(task_id: str, body: dict[str, Any]) -> dict[str, Any]:
    try:
        await _ensure_not_active(task_id)
        definitions.write_file(task_id, "task.js", str(body.get("markdown") or ""))
        await resync_task_schedules()
        return definitions.get_task(task_id)
    except Exception as exc:  # noqa: BLE001
        _raise_http(exc)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def task_delete(task_id: str) -> Response:
    try:
        await _ensure_not_active(task_id)
        definitions.delete_task(task_id)
        await resync_task_schedules()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as exc:  # noqa: BLE001
        _raise_http(exc)


@router.get("/tasks/{task_id}/validate")
async def task_validate(task_id: str) -> dict[str, Any]:
    return definitions.validate_task(task_id)


@router.get("/tasks/{task_id}/files")
async def task_files(task_id: str) -> list[dict[str, Any]]:
    try:
        return definitions.list_files(task_id)
    except Exception as exc:  # noqa: BLE001
        _raise_http(exc)


@router.post("/tasks/{task_id}/files", status_code=status.HTTP_201_CREATED)
async def task_file_create(task_id: str, body: dict[str, Any]) -> dict[str, Any]:
    try:
        await _ensure_not_active(task_id)
        return definitions.write_file(task_id, str(body.get("name") or ""), str(body.get("content") or ""), create=True)
    except Exception as exc:  # noqa: BLE001
        _raise_http(exc)


@router.get("/tasks/{task_id}/files/{name}")
async def task_file_get(task_id: str, name: str) -> dict[str, Any]:
    try:
        return definitions.read_file(task_id, name)
    except Exception as exc:  # noqa: BLE001
        _raise_http(exc)


@router.put("/tasks/{task_id}/files/{name}")
async def task_file_save(task_id: str, name: str, body: dict[str, Any]) -> dict[str, Any]:
    try:
        await _ensure_not_active(task_id)
        result = definitions.write_file(task_id, name, str(body.get("content") or ""))
        if name.lower() == "task.json":
            await resync_task_schedules()
        return result
    except Exception as exc:  # noqa: BLE001
        _raise_http(exc)


@router.delete("/tasks/{task_id}/files/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def task_file_delete(task_id: str, name: str) -> Response:
    try:
        await _ensure_not_active(task_id)
        definitions.delete_file(task_id, name)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as exc:  # noqa: BLE001
        _raise_http(exc)


@router.put("/tasks/{task_id}/meta")
async def task_meta_save(task_id: str, body: dict[str, Any]) -> dict[str, Any]:
    try:
        await _ensure_not_active(task_id)
        task = definitions.update_meta(task_id, body)
        await resync_task_schedules()
        return task
    except Exception as exc:  # noqa: BLE001
        _raise_http(exc)


@router.post("/tasks/{task_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def task_run(task_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    body = body or {}
    try:
        return await enqueue_task(task_id, body.get("inputs") or {})
    except Exception as exc:  # noqa: BLE001
        _raise_http(exc)


@router.get("/tasks/{task_id}/runs")
async def task_runs(task_id: str, limit: int = 50) -> list[dict[str, Any]]:
    return await list_runs(task_id, max(1, min(200, limit)))


@router.get("/task-runs/{run_id}")
async def task_run_get(run_id: str) -> dict[str, Any]:
    run = await get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Task run not found")
    return run


@router.delete("/task-runs/{run_id}")
async def task_run_stop(run_id: str) -> dict[str, Any]:
    if not await stop_run(run_id):
        raise HTTPException(status_code=404, detail="Active task run not found")
    return {"status": "stopped"}


@router.post("/scheduler", status_code=status.HTTP_201_CREATED)
async def scheduler_enqueue(body: Annotated[Any, Body()]) -> dict[str, Any]:
    raw_items = (
        body
        if isinstance(body, list)
        else body.get("items")
        if isinstance(body, dict) and isinstance(body.get("items"), list)
        else [body]
    )
    if not raw_items:
        raise HTTPException(status_code=400, detail="At least one task enqueue request is required")
    if len(raw_items) > 500:
        raise HTTPException(status_code=400, detail="At most 500 task enqueue requests are allowed")
    items = []
    try:
        for raw in raw_items:
            if not isinstance(raw, dict):
                raise ValueError("Task enqueue request must be an object")
            task_id = str(raw.get("task") or "").strip()
            if not task_id:
                raise ValueError("task is required")
            schedule_id = await Database().ensure_task_queue_source(task_id, "queue")
            eligible_raw = raw.get("eligibleAt", raw.get("eligible_at"))
            eligible_at = None
            if eligible_raw is not None and eligible_raw != "":
                if isinstance(eligible_raw, bool) or not isinstance(eligible_raw, (str, int, float)):
                    raise ValueError("eligibleAt must be a Unix timestamp")
                eligible_at = int(float(eligible_raw))
            if eligible_at is not None and eligible_at < 10_000_000_000:
                eligible_at *= 1000
            items.append(
                await enqueue_task(
                    task_id,
                    raw.get("inputs") or {},
                    title=raw.get("title"),
                    dedupe_key=raw.get("dedupeKey") or raw.get("dedupe_key"),
                    priority=int(raw.get("priority") or 0),
                    eligible_at=eligible_at,
                    schedule_id=schedule_id,
                )
            )
        return {"item": items[0]} if len(items) == 1 else {"items": items}
    except Exception as exc:  # noqa: BLE001
        _raise_http(exc)
