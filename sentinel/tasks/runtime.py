"""Durable Clara-style folder-task scheduler and orchestrator runtime."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from sentinel.ai import tools as ai_tools
from sentinel.ai.llm import LLMClient, expand_paths, run_prompt, tool_result_to_text
from sentinel.database import Database
from sentinel.paths import SENTINEL_HOME
from sentinel.settings import Settings
from sentinel.tasks.definitions import get_task, list_tasks, resolve_cwd, task_directory

logger = logging.getLogger(__name__)

BRIDGE = Path(__file__).with_name("orchestrator.mjs")
APP_ROOT = Path(__file__).resolve().parents[2]
STALE_EVALUATOR_JOB = "task-scheduler:stale-evaluator"
STALE_EVALUATOR_OFFSET_SECONDS = 30
ACTIVE_STATUSES = {"queued", "claimed", "running"}
API_READINESS_POLL_SECONDS = 0.25
API_READINESS_TIMEOUT_SECONDS = 1.0
# Clara permits task subprocess output up to 8 MiB. A JSON-line bridge frame can
# expand that text through escaping, so leave enough room for the worst case.
ORCHESTRATOR_FRAME_LIMIT_BYTES = 64 * 1024 * 1024

_worker: asyncio.Task | None = None
_wake_event: asyncio.Event | None = None
_scheduler: Any = None
_bridges: dict[str, asyncio.subprocess.Process] = {}
_children: dict[str, set[asyncio.subprocess.Process]] = {}
_active_runs: dict[str, asyncio.Task[None]] = {}
_shutdown = False


def _iso(milliseconds: int | None) -> str | None:
    if milliseconds is None:
        return None
    return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc).isoformat()


def _normalize_inputs(inputs: dict[str, Any] | None) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in (inputs or {}).items():
        if value is None:
            normalized[str(key)] = ""
        elif isinstance(value, bool):
            normalized[str(key)] = "true" if value else "false"
        elif isinstance(value, (str, int, float)):
            normalized[str(key)] = str(value)
        else:
            raise ValueError(f'Task input "{key}" must be a string, number, boolean, or null')
    return normalized


async def _serialize_run(row: dict[str, Any], *, include_events: bool = False) -> dict[str, Any]:
    events = await Database().list_task_run_events(str(row["id"])) if include_events else []
    logs: list[str] = []
    live_output = ""
    for event in events:
        try:
            payload = json.loads(event["payload_json"])
        except (json.JSONDecodeError, TypeError):
            continue
        if event["event_type"] == "log":
            logs.append(str(payload.get("text", "")))
        elif event["event_type"] == "live":
            live_output = str(payload.get("text", ""))
    try:
        inputs = json.loads(row.get("inputs_json") or "{}")
    except json.JSONDecodeError:
        inputs = {}
    try:
        task_name = get_task(str(row["task_id"]))["name"]
    except Exception:
        task_name = str(row["task_id"])
    status = {"claimed": "queued", "done": "done", "error": "error", "cancelled": "stopped"}.get(
        str(row["status"]), str(row["status"])
    )
    started = row.get("started_at")
    finished = row.get("finished_at")
    duration = finished - started if isinstance(started, int) and isinstance(finished, int) else None
    return {
        "id": row["id"],
        "taskId": row["task_id"],
        "taskName": task_name,
        "title": row.get("title"),
        "inputs": inputs,
        "dedupeKey": row.get("dedupe_key"),
        "status": status,
        "createdAt": _iso(row.get("created_at")),
        "startedAt": _iso(started),
        "finishedAt": _iso(finished),
        "durationMs": duration,
        "log": logs,
        "liveOutput": live_output,
        "error": row.get("error"),
    }


async def enqueue_task(
    task_id: str,
    inputs: dict[str, Any] | None = None,
    *,
    title: str | None = None,
    dedupe_key: str | None = None,
    priority: int = 0,
    eligible_at: int | None = None,
    schedule_id: str | None = None,
) -> dict[str, Any]:
    get_task(task_id)
    db = Database()
    if schedule_id is None:
        schedule_id = await db.ensure_task_queue_source(task_id, "manual")
    row = await db.enqueue_task_work(
        schedule_id,
        task_id,
        _normalize_inputs(inputs),
        title=title,
        dedupe_key=dedupe_key,
        priority=priority,
        eligible_at=eligible_at,
    )
    await _ensure_worker()
    _wake_worker()
    return await _serialize_run(row)


async def list_runs(task_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    rows = await Database().list_task_work(task_id, limit)
    return [await _serialize_run(row) for row in rows]


async def list_runs_for_tasks(task_ids: list[str], limit: int = 200) -> list[dict[str, Any]]:
    rows = await Database().list_task_work_for_tasks(task_ids, limit)
    return [await _serialize_run(row) for row in rows]


async def get_run(run_id: str) -> dict[str, Any] | None:
    row = await Database().get_task_work(run_id)
    return await _serialize_run(row, include_events=True) if row else None


async def stop_run(run_id: str) -> bool:
    stopped = await Database().cancel_task_work(run_id)
    if not stopped:
        return False
    await Database().append_task_run_event(run_id, "log", {"text": "Stopped"})
    execution = _active_runs.get(run_id)
    if execution is not None and execution is not asyncio.current_task():
        execution.cancel()
        await asyncio.gather(execution, return_exceptions=True)
    else:
        await _terminate_run_processes(run_id)
    _wake_worker()
    return True


async def start_task_runtime(scheduler: Any) -> None:
    global _shutdown
    _shutdown = False
    recovered = await Database().recover_interrupted_task_work()
    if recovered:
        logger.info("Recovered %d interrupted folder-task runs", recovered)
    removed = await Database().cleanup_terminal_task_checkpoints()
    if removed:
        logger.info("Removed %d checkpoints belonging to terminal folder-task runs", removed)
    await sync_task_schedules(scheduler)
    await _ensure_worker()
    await evaluate_stale_schedules()
    _wake_worker()


async def stop_task_runtime() -> None:
    global _worker, _shutdown
    _shutdown = True
    active = list(_active_runs.values())
    for execution in active:
        execution.cancel()
    if active:
        await asyncio.gather(*active, return_exceptions=True)
    for run_id in set(_bridges) | set(_children):
        await _terminate_run_processes(run_id)
    if _worker:
        _worker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _worker
    _worker = None


async def _ensure_worker() -> None:
    global _worker, _wake_event
    if _wake_event is None:
        _wake_event = asyncio.Event()
    if _worker is None or _worker.done():
        _worker = asyncio.create_task(_worker_loop(), name="sentinel-task-worker")


def _wake_worker() -> None:
    if _wake_event is not None:
        _wake_event.set()


async def _worker_loop() -> None:
    await _wait_for_api_ready()
    while not _shutdown:
        if _wake_event is None:
            return
        # Clear before checking the queue so an enqueue racing with the check
        # leaves the event set and cannot strand new work.
        _wake_event.clear()
        item = await Database().claim_next_task_work()
        if item is None:
            if _shutdown:
                return
            next_eligible_at = await Database().get_next_task_work_eligible_at()
            wait_seconds = (
                None if next_eligible_at is None else max(0.05, (next_eligible_at - int(time.time() * 1000)) / 1000)
            )
            try:
                if wait_seconds is None:
                    await _wake_event.wait()
                else:
                    await asyncio.wait_for(_wake_event.wait(), timeout=wait_seconds)
            except asyncio.TimeoutError:
                pass
            continue
        try:
            run_id = str(item["id"])
            execution = asyncio.create_task(_execute(item), name=f"sentinel-task-run:{run_id}")
            _active_runs[run_id] = execution
            try:
                await execution
            finally:
                _active_runs.pop(run_id, None)
        except asyncio.CancelledError:
            if _shutdown:
                raise
        except Exception as exc:  # noqa: BLE001 - keep the durable queue pump alive
            logger.exception("Task worker crashed while executing %s", item["id"])
            current = await Database().get_task_work(str(item["id"]))
            if current and current["status"] in ACTIVE_STATUSES:
                await Database().finish_task_work(str(item["id"]), "error", str(exc)[:4000])


async def _wait_for_api_ready() -> None:
    base_url = os.environ.get("SENTINEL_BASE_URL", "http://localhost:8000").rstrip("/")
    health_url = f"{base_url}/api/health"
    waiting_logged = False
    async with httpx.AsyncClient(timeout=API_READINESS_TIMEOUT_SECONDS, trust_env=False) as client:
        while not _shutdown:
            try:
                response = await client.get(health_url)
                if 200 <= response.status_code < 300:
                    if waiting_logged:
                        logger.info("Sentinel API is ready; folder-task execution can begin")
                    return
            except httpx.HTTPError:
                pass
            if not waiting_logged:
                logger.info("Folder-task execution is waiting for Sentinel API readiness at %s", health_url)
                waiting_logged = True
            await asyncio.sleep(API_READINESS_POLL_SECONDS)


def _task_hash(task_id: str) -> str:
    digest = hashlib.sha256()
    path = task_directory(task_id)
    for file in sorted(item for item in path.iterdir() if item.is_file()):
        digest.update(file.name.encode())
        digest.update(b"\0")
        digest.update(file.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


async def _log(run_id: str, text: str) -> None:
    await Database().append_task_run_event(run_id, "log", {"text": text})


async def _live(run_id: str, text: str) -> None:
    await Database().replace_task_run_live_event(run_id, {"text": text})


async def _scheduled_item_is_current(item: dict[str, Any], task: dict[str, Any]) -> bool:
    schedule_id = str(item.get("schedule_id") or "")
    if schedule_id.endswith(":manual") or schedule_id.endswith(":queue"):
        return True
    if not task.get("enabled") or task.get("invalid"):
        return False
    schedule = await Database().get_task_schedule(schedule_id)
    if not schedule or not bool(schedule.get("enabled")):
        return False
    if schedule_id.endswith(":cron"):
        return bool(task.get("schedule"))
    if schedule_id.endswith(":stale"):
        policy = task.get("schedulePolicy") or {}
        return int(policy.get("staleAfterSeconds") or 0) > 0
    return False


async def _execute(item: dict[str, Any]) -> None:
    run_id = str(item["id"])
    db = Database()
    client: LLMClient | None = None
    executors: Any = None
    process: asyncio.subprocess.Process | None = None
    stderr_task: asyncio.Task[bytes] | None = None
    try:
        task = get_task(str(item["task_id"]))
        if not await _scheduled_item_is_current(item, task):
            error = "Task is no longer enabled or scheduled"
            await _log(run_id, error)
            await db.finish_task_work(run_id, "cancelled", error)
            return
        task_dir = task_directory(task["id"])
        work_root = resolve_cwd(task)
        work_root.mkdir(parents=True, exist_ok=True)
        current_hash = _task_hash(task["id"])
        run_row = await db.get_task_run_row(run_id)
        if run_row and run_row.get("task_hash") and run_row["task_hash"] != current_hash:
            raise RuntimeError("Task definition changed since this run started; cannot resume automatically")
        if not run_row or not run_row.get("task_hash"):
            await db.set_task_run_hash(run_id, current_hash)
        if not await db.mark_task_work_running(run_id):
            return
        await _log(run_id, f"Running {task['name']}")

        settings = Settings()
        client = await LLMClient.from_settings(settings)
        executors = ai_tools.make_tool_executors(
            client.searxng_base_url,
            client.url_summarizer_base_url,
            work_root,
            client.browser_search_base_url,
        )
        inputs = json.loads(item.get("inputs_json") or "{}")
        env = os.environ.copy()
        env.update(
            {
                "SENTINEL_TASKS_HOME": str(SENTINEL_HOME),
                "SENTINEL_BASE_URL": os.environ.get("SENTINEL_BASE_URL", "http://localhost:8000"),
                "SENTINEL_APP_ROOT": str(APP_ROOT),
                "SENTINEL_PYTHON": sys.executable,
                "SENTINEL_URL_SUMMARIZER_BASE_URL": str(client.url_summarizer_base_url or "http://127.0.0.1:8890"),
                "TASK_CWD": str(work_root),
                **{str(key): str(value) for key, value in inputs.items()},
            }
        )
        process = await asyncio.create_subprocess_exec(
            "node",
            str(BRIDGE),
            str(task_dir / "task.js"),
            task["id"],
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(work_root),
            env=env,
            start_new_session=True,
            limit=ORCHESTRATOR_FRAME_LIMIT_BYTES,
        )
        _bridges[run_id] = process
        if process.stderr:
            stderr_task = asyncio.create_task(process.stderr.read())
        timeout = task.get("timeout") or 0
        serve = _serve_bridge(
            process,
            run_id,
            task,
            task_dir,
            work_root,
            env,
            client,
            executors,
        )
        if timeout > 0:
            await asyncio.wait_for(serve, timeout=float(timeout))
        else:
            await serve
        code = await process.wait()
        stderr = (await stderr_task).decode("utf-8", "replace") if stderr_task else ""
        current = await db.get_task_work(run_id)
        if current and current["status"] == "cancelled":
            return
        if code != 0:
            raise RuntimeError(stderr.strip() or f"orchestrator exited with code {code}")
        await db.finish_task_work(run_id, "done")
    except asyncio.TimeoutError:
        await _terminate_run_processes(run_id)
        task_timeout = task.get("timeout") if "task" in locals() else None
        error = f"Task timed out after {task_timeout}s"
        await _log(run_id, f"Error: {error}")
        current = await db.get_task_work(run_id)
        if current and current["status"] in ACTIVE_STATUSES:
            await db.finish_task_work(run_id, "error", error)
    except asyncio.CancelledError:
        await _terminate_run_processes(run_id)
        raise
    except Exception as exc:  # noqa: BLE001 - persist every task failure
        await _terminate_run_processes(run_id)
        error = str(exc)[:4000]
        await _log(run_id, f"Error: {error}")
        current = await db.get_task_work(run_id)
        if current and current["status"] in ACTIVE_STATUSES:
            await db.finish_task_work(run_id, "error", error)
    finally:
        _bridges.pop(run_id, None)
        _children.pop(run_id, None)
        if stderr_task and not stderr_task.done():
            stderr_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await stderr_task
        if executors is not None:
            await executors.aclose()
        if client is not None:
            await client.close()
        _wake_worker()


async def _serve_bridge(
    process: asyncio.subprocess.Process,
    run_id: str,
    task: dict[str, Any],
    task_dir: Path,
    work_root: Path,
    env: dict[str, str],
    client: LLMClient,
    executors: Any,
) -> None:
    if process.stdout is None or process.stdin is None:
        raise RuntimeError("Task orchestrator pipes are unavailable")
    call_index = 0
    while line := await process.stdout.readline():
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            await _log(run_id, line.decode("utf-8", "replace").rstrip())
            continue
        kind = message.get("type")
        if kind == "log":
            text = str(message.get("text", ""))
            await _log(run_id, text)
            await _live(run_id, text)
            continue
        if kind == "done":
            return
        if kind == "error":
            raise RuntimeError(str(message.get("error") or "Task failed"))
        if kind != "call":
            continue
        method = str(message.get("method") or "")
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        label = str(params.get("file") or params.get("name") or method)
        call_key = f"call:{call_index}"
        call_index += 1
        response: dict[str, Any] = {"id": message.get("id")}
        try:
            cached = await Database().get_task_checkpoint(run_id, call_key)
            if cached is not None:
                await _log(run_id, f"Replaying cached {method} {label} ({call_key})")
                response["result"] = cached
            else:
                result = await _handle_call(run_id, method, params, task, task_dir, work_root, env, client, executors)
                if not await Database().save_task_checkpoint(run_id, call_key, method, label, result):
                    return
                response["result"] = result
            await _live(run_id, str(response["result"]))
        except Exception as exc:  # noqa: BLE001 - task.js receives call errors normally
            response["error"] = str(exc)
        process.stdin.write((json.dumps(response, ensure_ascii=False) + "\n").encode())
        await process.stdin.drain()


async def _handle_call(
    run_id: str,
    method: str,
    params: dict[str, Any],
    task: dict[str, Any],
    task_dir: Path,
    work_root: Path,
    env: dict[str, str],
    client: LLMClient,
    executors: Any,
) -> str:
    raw_options = params.get("options")
    options: dict[str, Any] = raw_options if isinstance(raw_options, dict) else {}
    timeout = options.get("timeoutSeconds")

    async def invoke() -> str:
        if method == "prompt":
            raw_file = Path(str(params.get("file") or ""))
            file = raw_file.resolve() if raw_file.is_absolute() else (task_dir / raw_file).resolve()
            value = await run_prompt(
                client,
                str(file),
                task_id=task["id"],
                task_cwd=work_root,
                context=options.get("context") if isinstance(options.get("context"), dict) else None,
                system=str(options["systemPrompt"]) if options.get("systemPrompt") else None,
                as_json=options.get("outputType") == "json",
                temperature=options.get("temperature"),
            )
            return json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
        if method == "tool":
            name = str(params.get("name", ""))
            executor = executors.get(name)
            if executor is None:
                raise ValueError(f'Tool "{name}" not found')
            args = expand_paths(params.get("args") or {}, ai_data_dir=SENTINEL_HOME, work_root=work_root)
            return tool_result_to_text(await executor(args))
        if method == "run":
            raw_file = Path(str(params.get("file") or ""))
            file = raw_file.resolve() if raw_file.is_absolute() else (task_dir / raw_file).resolve()
            suffix = file.suffix.lower()
            if suffix not in {".js", ".mjs", ".py", ".sh"}:
                raise ValueError(f'Unsupported script type "{suffix}"')
            command = ["node" if suffix in {".js", ".mjs"} else sys.executable if suffix == ".py" else "sh", str(file)]
            raw_sandbox_env = params.get("env")
            sandbox_env: dict[str, Any] = raw_sandbox_env if isinstance(raw_sandbox_env, dict) else {}
            raw_call_env = options.get("env")
            call_env: dict[str, Any] = raw_call_env if isinstance(raw_call_env, dict) else {}
            child_env = (
                env
                | {str(key): str(value) for key, value in sandbox_env.items()}
                | {str(key): str(value) for key, value in call_env.items()}
            )
            cwd = work_root
            if options.get("cwd"):
                raw_cwd = Path(str(options["cwd"]))
                cwd = raw_cwd if raw_cwd.is_absolute() else task_dir / raw_cwd
            child = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(cwd),
                env=child_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
            _children.setdefault(run_id, set()).add(child)
            try:
                stdout, stderr = await child.communicate()
            except BaseException:
                await _terminate_process(child)
                raise
            finally:
                _children.get(run_id, set()).discard(child)
            if child.returncode != 0:
                raise RuntimeError(
                    f'Script "{file.name}" exited with code {child.returncode}: {stderr.decode("utf-8", "replace")}'
                )
            return stdout.decode("utf-8", "replace")
        raise ValueError(f"Unknown orchestrator call: {method}")

    if isinstance(timeout, (int, float)) and not isinstance(timeout, bool) and timeout > 0:
        try:
            return await asyncio.wait_for(invoke(), timeout=float(timeout))
        except asyncio.TimeoutError as exc:
            raise RuntimeError(
                f'{method.title()} "{params.get("file") or params.get("name") or "call"}" timed out after {timeout}s'
            ) from exc
    return await invoke()


async def _terminate_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        await asyncio.wait_for(process.wait(), timeout=3)
    except asyncio.TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        await process.wait()


async def _terminate_run_processes(run_id: str) -> None:
    children = list(_children.get(run_id, set()))
    bridge = _bridges.get(run_id)
    await asyncio.gather(*(_terminate_process(child) for child in children), return_exceptions=True)
    if bridge:
        await _terminate_process(bridge)


async def sync_task_schedules(scheduler: Any) -> None:
    global _scheduler
    _scheduler = scheduler
    if scheduler is None:
        return
    db = Database()
    active_schedule_ids: set[str] = set()
    active_cron_jobs: set[str] = set()
    for task in list_tasks():
        if task.get("invalid") or not task.get("enabled"):
            continue
        if task.get("schedule"):
            schedule_id = f"task:{task['id']}:cron"
            active_schedule_ids.add(schedule_id)
            active_cron_jobs.add(schedule_id)
            await db.upsert_task_schedule(
                schedule_id,
                task["id"],
                {"type": "cron", "schedule": task["schedule"]},
                {"runWhen": "immediate", "priority": 0},
            )
            scheduler.add_job(
                _cron_enqueue,
                CronTrigger.from_crontab(task["schedule"]),
                id=schedule_id,
                name=task["name"],
                args=[task["id"], schedule_id],
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
        policy = task.get("schedulePolicy") or {}
        stale_seconds = int(policy.get("staleAfterSeconds") or 0)
        if stale_seconds > 0:
            schedule_id = f"task:{task['id']}:stale"
            active_schedule_ids.add(schedule_id)
            await db.upsert_task_schedule(
                schedule_id,
                task["id"],
                {"type": "stale_after", "seconds": stale_seconds},
                {"runWhen": policy.get("runWhen") or "idle", "priority": int(policy.get("priority") or 0)},
            )
    await db.disable_missing_task_schedules(active_schedule_ids)
    for job in scheduler.get_jobs():
        if job.id.startswith("task:") and job.id.endswith(":cron") and job.id not in active_cron_jobs:
            scheduler.remove_job(job.id)
        if job.id.startswith("task:") and not job.id.endswith(":cron"):
            # Remove jobs created by the earlier interval-based WIP.
            scheduler.remove_job(job.id)
    scheduler.add_job(
        evaluate_stale_schedules,
        IntervalTrigger(
            minutes=1,
            start_date=datetime.now(timezone.utc) + timedelta(seconds=STALE_EVALUATOR_OFFSET_SECONDS),
        ),
        id=STALE_EVALUATOR_JOB,
        name="Folder task stale-policy evaluator",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )


async def resync_task_schedules() -> None:
    await sync_task_schedules(_scheduler)
    await evaluate_stale_schedules()


async def _cron_enqueue(task_id: str, schedule_id: str) -> None:
    await enqueue_task(task_id, dedupe_key=f"scheduled:{task_id}", schedule_id=schedule_id)


async def evaluate_stale_schedules() -> None:
    db = Database()
    for row in await db.list_due_stale_task_schedules():
        try:
            policy = json.loads(row.get("policy_json") or "{}")
        except json.JSONDecodeError:
            policy = {}
        run_when = policy.get("runWhen") or "idle"
        if run_when == "idle" and await db.task_runtime_busy():
            continue
        await enqueue_task(
            str(row["task_id"]),
            dedupe_key=f"scheduled:{row['task_id']}",
            priority=int(policy.get("priority") or 0),
            schedule_id=str(row["id"]),
        )
        if run_when == "idle":
            break
