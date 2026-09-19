"""AI research pipeline API routes."""

from __future__ import annotations

import asyncio
import json
import math
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from sentinel.ai import tools as ai_tools
from sentinel.ai.chat_tools import ResearchChatTools
from sentinel.ai.errors import LLMError
from sentinel.ai.llm import LLMClient, build_system_prompt, discover_models
from sentinel.ai.memory import make_memory_store
from sentinel.ai.universe import get_research_unit, load_research_units
from sentinel.api.dependencies import CommonDependencies, get_common_deps
from sentinel.paths import SENTINEL_HOME, TASK_ARTIFACTS_DIR
from sentinel.tasks.definitions import list_tasks
from sentinel.tasks.runtime import enqueue_task, list_runs_for_tasks

router = APIRouter(prefix="/ai", tags=["ai"])
AI_TASK_IDS = {
    "analyze-security",
    "rate-portfolio",
    "rate-security",
    "refresh-securities-universe",
    "schedule-next-security-analysis",
    "schedule-rate-portfolio",
}
MEMORY_STATS_TTL_SECONDS = 30.0
CHAT_CONTEXT_TOKEN_LIMIT = 128 * 1024
_memory_stats_cache: dict[str, Any] | None = None
_memory_stats_cached_at = 0.0
_memory_stats_lock = asyncio.Lock()


def _estimate_chat_tokens(value: Any) -> int:
    """Conservatively estimate model tokens without coupling to one tokenizer."""
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return max(1, math.ceil(len(value.encode("utf-8")) / 3))


def _window_chat_history(
    history: list[dict[str, str]],
    *,
    system: str,
    tools: list[dict[str, Any]],
    message: str,
) -> tuple[list[dict[str, str]], int]:
    """Keep the newest complete messages inside a 128k-token request window."""
    fixed_tokens = _estimate_chat_tokens(system) + _estimate_chat_tokens(tools) + _estimate_chat_tokens(message) + 32
    remaining = max(0, CHAT_CONTEXT_TOKEN_LIMIT - fixed_tokens)
    retained_reversed: list[dict[str, str]] = []
    for entry in reversed(history):
        cost = _estimate_chat_tokens(entry) + 4
        if cost > remaining:
            break
        retained_reversed.append(entry)
        remaining -= cost
    retained = list(reversed(retained_reversed))
    return retained, len(history) - len(retained)


def _age_seconds(value: Any, now: datetime) -> float:
    if not isinstance(value, str) or not value.strip():
        return float("inf")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return float("inf")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0.0, (now - parsed.astimezone(timezone.utc)).total_seconds())


ARTIFACT_ALLOWLIST = {
    "analysis.md",
    "context.md",
    "evidence-pack.md",
    "latest.json",
    "profile.json",
    "rating.json",
    "ratings.json",
    "report.md",
    "summary.md",
}


def _artifact_path(relative_path: str, *, require_file: bool = True) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or not relative.parts:
        raise HTTPException(status_code=404, detail="artifact not found")
    root = TASK_ARTIFACTS_DIR.resolve()
    target = (root / relative).resolve()
    if target != root and root not in target.parents:
        raise HTTPException(status_code=404, detail="artifact not found")
    if require_file and not target.is_file():
        raise HTTPException(status_code=404, detail="artifact not found")
    return target


def _stale(unit: dict[str, Any], *, now: datetime, security_days: int) -> bool:
    return _age_seconds(unit.get("last_analyzed_at"), now) >= max(1, security_days) * 86400


def _run_display_status(
    run: dict[str, Any],
    identity: dict[str, str],
    units: list[dict[str, Any]],
    *,
    now: datetime,
    security_days: int,
) -> str:
    if run.get("status") != "done":
        return "failed"
    if run.get("taskId") != "analyze-security":
        return "completed"
    unit = next(
        (
            row
            for row in units
            if row.get("kind") == "security" and str(row.get("key") or "").casefold() == identity["unit_key"].casefold()
        ),
        None,
    )
    if unit is None or _stale(unit, now=now, security_days=security_days):
        return "stale"
    return "completed"


def _portfolio_stale() -> bool:
    latest = TASK_ARTIFACTS_DIR / "rate-portfolio" / "latest.json"
    universe = TASK_ARTIFACTS_DIR / "refresh-securities-universe" / "securities-universe.json"
    if not latest.is_file() or not universe.is_file():
        return True
    dependencies = [universe, *(TASK_ARTIFACTS_DIR / "analyze-security").glob("*.summary.md")]
    return latest.stat().st_mtime < max(path.stat().st_mtime for path in dependencies)


async def _memory_stats(deps: CommonDependencies) -> dict[str, Any]:
    global _memory_stats_cache, _memory_stats_cached_at
    now = time.monotonic()
    if _memory_stats_cache is not None and now - _memory_stats_cached_at < MEMORY_STATS_TTL_SECONDS:
        return _memory_stats_cache
    async with _memory_stats_lock:
        now = time.monotonic()
        if _memory_stats_cache is not None and now - _memory_stats_cached_at < MEMORY_STATS_TTL_SECONDS:
            return _memory_stats_cache
        try:
            store = await make_memory_store(deps.settings)
            try:
                result = await store.stats()
            finally:
                await store.close()
        except Exception as exc:  # noqa: BLE001 - status endpoint should survive satellite outages
            result = {"findings": None, "last_stored_at": None, "error": str(exc)}
        _memory_stats_cache = result
        _memory_stats_cached_at = now
        return result


async def _pipeline_runs(limit: int = 200) -> list[dict[str, Any]]:
    return await list_runs_for_tasks(sorted(AI_TASK_IDS), max(1, min(200, limit)))


@router.get("/models")
async def get_ai_models(deps: Annotated[CommonDependencies, Depends(get_common_deps)]) -> dict[str, Any]:
    base_url = str(await deps.settings.get("ai_llm_base_url", "http://127.0.0.1:8080/v1"))
    api_key = str(await deps.settings.get("ai_llm_api_key", "local"))
    try:
        return {"ok": True, "models": await discover_models(base_url, api_key)}
    except Exception as exc:  # noqa: BLE001 - settings must remain usable while the endpoint is offline
        return {"ok": False, "models": [], "error": str(exc)}


@router.post("/prompt")
async def create_ai_prompt(
    body: dict[str, Any],
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, str]:
    prompt = body.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise HTTPException(status_code=400, detail="prompt must be a non-empty string")

    raw_temperature = body.get("temperature")
    if raw_temperature is None:
        temperature = None
    elif isinstance(raw_temperature, bool) or not isinstance(raw_temperature, (int, float)):
        raise HTTPException(status_code=400, detail="temperature must be a finite number")
    else:
        temperature = float(raw_temperature)
        if not math.isfinite(temperature):
            raise HTTPException(status_code=400, detail="temperature must be a finite number")

    client = await LLMClient.from_settings(deps.settings)
    workspace = Path(client.ai_data_dir or SENTINEL_HOME)
    system = build_system_prompt(workspace, "ai-prompt", workspace)
    executors = ai_tools.make_tool_executors(
        client.searxng_base_url,
        client.url_summarizer_base_url,
        workspace,
        client.browser_search_base_url,
    )
    try:
        result = await client.chat(
            prompt,
            system=system,
            tools=ai_tools.TOOL_DEFINITIONS,
            executors=executors,
            work_root=workspace,
            temperature=temperature,
        )
        output = result.content if result.content.strip() else result.last_tool_result
        return {"output": output}
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        try:
            await executors.aclose()
        finally:
            await client.close()


@router.post("/chat")
async def create_ai_chat(
    body: dict[str, Any],
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> StreamingResponse:
    message = body.get("message")
    if not isinstance(message, str) or not message.strip():
        raise HTTPException(status_code=400, detail="message must be a non-empty string")
    raw_history = body.get("history", [])
    if not isinstance(raw_history, list):
        raise HTTPException(status_code=400, detail="history must be an array")
    history: list[dict[str, str]] = []
    for entry in raw_history:
        if not isinstance(entry, dict) or entry.get("role") not in {"user", "assistant"}:
            raise HTTPException(status_code=400, detail="history entries must have a user or assistant role")
        content = entry.get("content")
        if not isinstance(content, str):
            raise HTTPException(status_code=400, detail="history entry content must be a string")
        history.append({"role": entry["role"], "content": content})

    async def event_stream():
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=256)

        async def emit(event: dict[str, Any]) -> None:
            await queue.put(event)

        async def run_chat() -> None:
            client: LLMClient | None = None
            chat_tools: ResearchChatTools | None = None
            try:
                client = await LLMClient.from_settings(deps.settings)
                workspace = Path(client.ai_data_dir or SENTINEL_HOME)
                system = build_system_prompt(workspace, "research-chat", workspace)
                chat_tools = await ResearchChatTools.create(
                    searxng_base_url=client.searxng_base_url,
                    url_summarizer_base_url=client.url_summarizer_base_url,
                    browser_search_base_url=client.browser_search_base_url,
                    firefox_mcp_base_url=str(
                        await deps.settings.get("ai_firefox_mcp_base_url", "http://127.0.0.1:8892")
                    ),
                    work_root=workspace,
                )
                windowed_history, dropped = _window_chat_history(
                    history,
                    system=system,
                    tools=chat_tools.definitions,
                    message=message,
                )
                await emit(
                    {
                        "type": "context",
                        "limit_tokens": CHAT_CONTEXT_TOKEN_LIMIT,
                        "retained_messages": len(windowed_history),
                        "dropped_messages": dropped,
                    }
                )
                result = await client.chat(
                    message,
                    system=system,
                    history=windowed_history,
                    tools=chat_tools.definitions,
                    executors=chat_tools,
                    work_root=workspace,
                    on_event=emit,
                )
                output = result.content if result.content.strip() else result.last_tool_result
                await emit({"type": "done", "output": output})
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - errors must reach an already-open stream
                await emit({"type": "error", "error": str(exc)})
            finally:
                try:
                    if chat_tools is not None:
                        await chat_tools.aclose()
                finally:
                    if client is not None:
                        await client.close()
                    try:
                        queue.put_nowait(None)
                    except asyncio.QueueFull:
                        pass

        runner = asyncio.create_task(run_chat())
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        finally:
            if not runner.done():
                runner.cancel()
            await asyncio.gather(runner, return_exceptions=True)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _run_identity(run: dict[str, Any], units: list[dict[str, Any]]) -> dict[str, str]:
    task_id = str(run.get("taskId") or "")
    raw_inputs = run.get("inputs")
    inputs: dict[str, Any] = raw_inputs if isinstance(raw_inputs, dict) else {}
    if task_id in {"analyze-security", "rate-security"}:
        unit_kind = "security"
        requested = str(inputs.get("symbol") or "").strip()
    elif task_id == "rate-portfolio":
        unit_kind = "portfolio"
        requested = "portfolio"
    else:
        return {
            "unit_kind": "task",
            "unit_key": task_id,
            "unit_label": str(run.get("taskName") or task_id),
        }

    requested_folded = requested.casefold()
    unit = next(
        (
            row
            for row in units
            if row.get("kind") == unit_kind
            and requested_folded in {str(row.get("key") or "").casefold(), str(row.get("label") or "").casefold()}
        ),
        None,
    )
    return {
        "unit_kind": unit_kind,
        "unit_key": str(unit.get("key") if unit else requested),
        "unit_label": str(unit.get("label") if unit else requested or run.get("taskName") or task_id),
    }


@router.get("/status")
async def get_ai_status(deps: Annotated[CommonDependencies, Depends(get_common_deps)]) -> dict[str, Any]:
    units = load_research_units()
    task_runs = await _pipeline_runs()
    now = datetime.now(timezone.utc)
    security_days = int(await deps.settings.get("ai_stale_after_days", 7))

    running_unit = next((run for run in task_runs if run.get("status") == "running"), None)
    running = None
    if running_unit:
        started = running_unit.get("startedAt")
        identity = _run_identity(running_unit, units)
        running = {
            "kind": identity["unit_kind"],
            "key": identity["unit_key"],
            "label": identity["unit_label"],
            "task_id": running_unit.get("taskId"),
            "task_name": running_unit.get("taskName"),
            "started_at": started,
            "elapsed_seconds": None if not started else _age_seconds(started, now),
        }

    stale_counts = {"security": {"stale": 0, "total": 0}}
    most_stale: dict[str, Any] | None = None
    most_stale_age = -1.0
    for unit in units:
        kind = unit.get("kind")
        if kind in stale_counts:
            stale_counts[kind]["total"] += 1
            age = _age_seconds(unit.get("last_analyzed_at"), now)
            if _stale(unit, now=now, security_days=security_days):
                stale_counts[kind]["stale"] += 1
                if age > most_stale_age:
                    most_stale_age = age
                    most_stale = {
                        "kind": kind,
                        "key": unit.get("key"),
                        "label": unit.get("label"),
                        "age_days": None if age == float("inf") else age / 86400,
                    }

    history = [run for run in task_runs if run.get("status") in {"done", "error", "stopped"}]
    last_run = None
    if history:
        row = history[0]
        duration_ms = row.get("durationMs")
        identity = _run_identity(row, units)
        last_run = {
            "job_id": row.get("taskId"),
            **identity,
            "status": _run_display_status(
                row,
                identity,
                units,
                now=now,
                security_days=security_days,
            ),
            "duration_seconds": duration_ms / 1000 if isinstance(duration_ms, (int, float)) else None,
            "error": row.get("error"),
            "finished_at": row.get("finishedAt"),
        }

    return {
        "enabled": any(
            task.get("enabled") and (task.get("schedule") or task.get("schedulePolicy"))
            for task in list_tasks()
            if task.get("id") in AI_TASK_IDS
        ),
        "running": running,
        "queued": [
            {
                "id": run.get("id"),
                "kind": "task",
                **_run_identity(run, units),
                "task_id": run.get("taskId"),
                "task_name": run.get("taskName"),
                "created_at": run.get("createdAt"),
            }
            for run in task_runs
            if run.get("status") == "queued"
        ],
        "staleness": {**stale_counts, "most_stale": most_stale},
        "last_run": last_run,
        "memory": await _memory_stats(deps),
        "next_tick_at": None,
    }


@router.get("/units")
async def get_ai_units(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
    kind: str | None = None,
    stale_only: bool = False,
) -> dict[str, Any]:
    units = load_research_units(kind)
    task_runs = await _pipeline_runs()
    now = datetime.now(timezone.utc)
    security_days = int(await deps.settings.get("ai_stale_after_days", 7))
    out = []
    for unit in units:
        unit_kind = str(unit.get("kind") or "")
        age = _age_seconds(unit.get("last_analyzed_at"), now)
        stale = _portfolio_stale() if unit_kind == "portfolio" else _stale(unit, now=now, security_days=security_days)
        if stale_only and not stale:
            continue
        related = next(
            (
                run
                for run in task_runs
                if (
                    unit_kind == "security"
                    and run.get("taskId") in {"analyze-security", "rate-security"}
                    and str((run.get("inputs") or {}).get("symbol") or "").upper() == str(unit.get("key") or "").upper()
                )
                or (unit_kind == "portfolio" and run.get("taskId") == "rate-portfolio")
            ),
            None,
        )
        out.append(
            {
                "kind": unit.get("kind"),
                "key": unit.get("key"),
                "label": unit.get("label"),
                "last_analyzed_at": unit.get("last_analyzed_at"),
                "age_days": None if age == float("inf") else age / 86400,
                "stale": stale,
                "status": related.get("status")
                if related and related.get("status") in {"queued", "running"}
                else "idle",
                "last_error": related.get("error")
                if related and related.get("status") in {"error", "stopped"}
                else None,
                "artifacts": sorted(unit.get("artifacts", {}).keys()),
            }
        )
    return {"units": out}


@router.post("/requests", status_code=201)
async def create_ai_request(
    data: dict,
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, Any]:
    kind = str(data.get("kind") or "").strip()
    unit_kind = str(data.get("unit_kind") or "").strip()
    unit_key = str(data.get("unit_key") or "").strip()
    if kind not in {"analyze", "rate"}:
        raise HTTPException(status_code=400, detail="kind must be 'analyze' or 'rate'")
    if unit_kind != "security":
        raise HTTPException(status_code=400, detail="unit_kind must be 'security'")
    unit = get_research_unit(unit_kind, unit_key)
    if unit is None:
        raise HTTPException(status_code=404, detail="unknown AI unit")
    task_id = "rate-security" if kind == "rate" else "analyze-security"
    inputs = {"symbol": unit["key"]}
    run = await enqueue_task(task_id, inputs)
    return {"status": "queued", "request_id": run["id"]}


@router.get("/history")
async def get_ai_history(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
    limit: int = 50,
) -> dict[str, Any]:
    history = []
    units = load_research_units()
    now = datetime.now(timezone.utc)
    security_days = int(await deps.settings.get("ai_stale_after_days", 7))
    for run in await _pipeline_runs(max(1, min(200, int(limit)))):
        if run.get("status") in {"queued", "running"}:
            continue
        identity = _run_identity(run, units)
        history.append(
            {
                "job_id": run.get("taskId"),
                **identity,
                "status": _run_display_status(
                    run,
                    identity,
                    units,
                    now=now,
                    security_days=security_days,
                ),
                "duration_ms": run.get("durationMs"),
                "error": run.get("error"),
                "executed_at": datetime.fromisoformat(run["finishedAt"]).timestamp() if run.get("finishedAt") else None,
            }
        )
    return {"history": history}


@router.get("/artifacts/{kind}/{unit_key}/{name}")
async def get_ai_artifact(
    kind: str,
    unit_key: str,
    name: str,
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, Any]:
    if kind not in {"security", "portfolio"} or name not in ARTIFACT_ALLOWLIST:
        raise HTTPException(status_code=404, detail="artifact not found")
    unit = get_research_unit(kind, unit_key)
    artifacts = unit.get("artifacts", {}) if unit else {}
    relative = artifacts.get(name)
    target = (TASK_ARTIFACTS_DIR / relative).resolve() if relative else None
    root = TASK_ARTIFACTS_DIR.resolve()
    if target is None or root not in target.parents or not target.is_file():
        raise HTTPException(status_code=404, detail="artifact not found")
    return {
        "name": name,
        "content": target.read_text(encoding="utf-8"),
        "modified_at": datetime.fromtimestamp(target.stat().st_mtime).isoformat(),
    }


async def list_ai_artifact_files(prefix: str = "") -> dict[str, Any]:
    """List every generated AI artifact, including intermediate work files."""
    root = TASK_ARTIFACTS_DIR.resolve()
    start = root if not prefix.strip() else _artifact_path(prefix.strip(), require_file=False)
    if not start.exists() or not start.is_dir():
        raise HTTPException(status_code=404, detail="artifact path not found")
    files = []
    for path in sorted(item for item in start.rglob("*") if item.is_file()):
        resolved = path.resolve()
        if resolved != root and root not in resolved.parents:
            continue
        stat = path.stat()
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            }
        )
    return {"files": files}


async def get_ai_artifact_file(path: str) -> dict[str, Any]:
    """Read any generated AI artifact by path relative to the artifact root."""
    target = _artifact_path(path)
    stat = target.stat()
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="artifact is not UTF-8 text") from exc
    return {
        "path": target.relative_to(TASK_ARTIFACTS_DIR.resolve()).as_posix(),
        "content": content,
        "size": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }


async def search_ai_artifact_files(query: str, prefix: str = "") -> dict[str, Any]:
    """Search every textual AI artifact for a case-insensitive literal string."""
    needle = query.strip()
    if not needle:
        raise HTTPException(status_code=400, detail="query must be a non-empty string")
    listing = await list_ai_artifact_files(prefix)
    matches: list[dict[str, Any]] = []
    pattern = re.compile(re.escape(needle), re.IGNORECASE)
    root = TASK_ARTIFACTS_DIR.resolve()
    for item in listing["files"]:
        target = root / item["path"]
        try:
            lines = target.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if pattern.search(line):
                matches.append({"path": item["path"], "line": line_number, "text": line})
    return {"query": needle, "matches": matches}
