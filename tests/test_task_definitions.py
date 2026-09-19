import asyncio
import contextlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio

from sentinel.database import Database
from sentinel.tasks import definitions, runtime


def test_bundled_tasks_use_uniform_step_and_task_timeouts():
    task_dirs = sorted(path for path in definitions.CORE_TASKS_DIR.iterdir() if (path / "task.json").is_file())

    assert task_dirs
    for task_dir in task_dirs:
        metadata = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
        script = (task_dir / "task.js").read_text(encoding="utf-8")
        call_count = len(re.findall(r"\b(?:prompt|run|tool)\(", script))

        assert metadata["timeout"] == 43_200, task_dir.name
        assert "const STEP_TIMEOUT_SECONDS = 3600;" in script, task_dir.name
        assert script.count("timeoutSeconds: STEP_TIMEOUT_SECONDS") == call_count, task_dir.name


@pytest.mark.parametrize("summary_state", ["missing", "empty", "outdated"])
def test_security_picker_requeues_unusable_or_stale_summary(tmp_path, summary_state):
    artifacts = tmp_path / "tasks" / "artifacts"
    universe_dir = artifacts / "refresh-securities-universe"
    universe_dir.mkdir(parents=True)
    (universe_dir / "securities-universe.json").write_text(
        json.dumps([{"symbol": "TEST", "name": "Test Security"}]),
        encoding="utf-8",
    )
    summary_dir = artifacts / "analyze-security"
    summary_dir.mkdir(parents=True)
    summary = summary_dir / "TEST.summary.md"
    if summary_state != "missing":
        summary.write_text("\n" if summary_state == "empty" else "summary\n", encoding="utf-8")
    if summary_state == "outdated":
        old = time.time() - 8 * 24 * 60 * 60
        os.utime(summary, (old, old))

    script = definitions.CORE_TASKS_DIR / "schedule-next-security-analysis" / "pick-and-queue.mjs"
    wrapper = (
        "globalThis.fetch = async (_url, options) => ({"
        "ok: true, "
        "json: async () => ({item: {id: 'queued-id'}}), "
        "text: async () => '', "
        "requestBody: JSON.parse(options.body)"
        "});"
        f"await import({json.dumps(script.as_uri())});"
    )
    env = os.environ.copy()
    env.update({"SENTINEL_TASKS_HOME": str(tmp_path), "SENTINEL_BASE_URL": "http://sentinel.test"})
    result = subprocess.run(  # noqa: S603 - fixed executable and test-owned script
        [shutil.which("node") or "node", "--input-type=module", "--eval", wrapper],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    decision = json.loads(result.stdout.strip())
    assert decision["queued"] is True
    assert decision["taskId"] == "analyze-security"
    assert decision["symbol"] == "TEST"


def make_task(root: Path, task_id: str, *, name: str | None = None, script: str = "console.log('ok');\n") -> Path:
    path = root / task_id
    path.mkdir(parents=True)
    (path / "task.json").write_text(
        json.dumps(
            {
                "name": name or task_id,
                "enabled": False,
                "cwd": "@/tasks/artifacts/{{task-id}}",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (path / "task.js").write_text(script, encoding="utf-8")
    return path


@pytest.fixture
def task_tree(tmp_path, monkeypatch):
    sentinel_home = tmp_path / ".sentinel"
    user_tasks = sentinel_home / "tasks"
    core_tasks = tmp_path / "core-tasks"
    core_tasks.mkdir()
    monkeypatch.setattr(definitions, "SENTINEL_HOME", sentinel_home)
    monkeypatch.setattr(definitions, "TASKS_DIR", user_tasks)
    monkeypatch.setattr(definitions, "CORE_TASKS_DIR", core_tasks)
    monkeypatch.setattr(definitions, "LEGACY_SEED_MARKER", user_tasks / ".defaults-seeded")
    monkeypatch.setattr(definitions, "PREVIOUS_OVERLAY_MARKER", user_tasks / ".core-overlay-migrated")
    monkeypatch.setattr(definitions, "OVERLAY_MIGRATION_MARKER", user_tasks / ".core-overlay-migrated-v2")
    monkeypatch.setattr(runtime, "SENTINEL_HOME", sentinel_home)
    yield core_tasks, user_tasks, sentinel_home


@pytest_asyncio.fixture
async def task_db(tmp_path):
    path = str(tmp_path / "tasks.db")
    db = Database(path)
    await db.connect()
    yield db
    await db.close()
    db.remove_from_cache()


def test_core_tasks_use_copy_on_write_and_delete_reveals_core(task_tree):
    core, user, _home = task_tree
    task = make_task(core, "portfolio-rating", name="Portfolio Rating")
    (task / "helper.py").write_text("print('core')\n", encoding="utf-8")

    definitions.ensure_default_tasks()
    listed = definitions.list_tasks()
    assert [(item["id"], item["source"]) for item in listed] == [("portfolio-rating", "core")]
    assert not (user / "portfolio-rating").exists()

    definitions.write_file("portfolio-rating", "helper.py", "print('user')\n")
    assert definitions.get_task("portfolio-rating")["source"] == "user"
    assert (user / "portfolio-rating" / "task.js").read_bytes() == (core / "portfolio-rating" / "task.js").read_bytes()
    assert (core / "portfolio-rating" / "helper.py").read_text(encoding="utf-8") == "print('core')\n"

    definitions.delete_task("portfolio-rating")
    assert definitions.get_task("portfolio-rating")["source"] == "core"
    with pytest.raises(PermissionError):
        definitions.delete_task("portfolio-rating")


def test_legacy_seed_migration_removes_only_unchanged_copies(task_tree):
    core, user, _home = task_tree
    make_task(core, "unchanged")
    make_task(core, "edited")
    user.mkdir(parents=True)
    shutil.copytree(core / "unchanged", user / "unchanged")
    shutil.copytree(core / "edited", user / "edited")
    (user / "edited" / "task.js").write_text("console.log('custom');\n", encoding="utf-8")
    definitions.LEGACY_SEED_MARKER.write_text("seeded\n", encoding="utf-8")

    definitions.ensure_default_tasks()

    assert not (user / "unchanged").exists()
    assert (user / "edited" / "task.js").is_file()
    assert definitions.get_task("unchanged")["source"] == "core"
    assert definitions.get_task("edited")["source"] == "user"
    assert definitions.OVERLAY_MIGRATION_MARKER.is_file()


def test_legacy_seed_migration_unfreezes_known_broken_validator(task_tree):
    core, user, _home = task_tree
    core_task = make_task(core, "rate-security")
    core_validator = core_task / "validate-rating.mjs"
    core_validator.write_text("// fixed validator\n", encoding="utf-8")
    user.mkdir(parents=True)
    shutil.copytree(core_task, user / "rate-security")
    (user / "rate-security" / "validate-rating.mjs").write_text(
        "const appRequire = true;\nappRequire.resolve('jsonrepair');\n// SENTINEL_APP_ROOT\n",
        encoding="utf-8",
    )
    definitions.LEGACY_SEED_MARKER.write_text("seeded\n", encoding="utf-8")

    definitions.ensure_default_tasks()

    assert not (user / "rate-security").exists()
    assert definitions.get_task("rate-security")["source"] == "core"


def test_previous_overlay_migration_unfreezes_known_core_fixes(task_tree):
    core, user, _home = task_tree
    core_task = make_task(core, "analyze-security")
    core_script = core_task / "fetch-profile-sources.py"
    core_script.write_text("if last_error is not None:\n    raise last_error\n", encoding="utf-8")
    user.mkdir(parents=True)
    shutil.copytree(core_task, user / "analyze-security")
    (user / "analyze-security" / "fetch-profile-sources.py").write_text(
        "    raise last_error\n",
        encoding="utf-8",
    )
    definitions.PREVIOUS_OVERLAY_MARKER.write_text("v1\n", encoding="utf-8")

    definitions.ensure_default_tasks()

    assert not (user / "analyze-security").exists()
    assert definitions.get_task("analyze-security")["source"] == "core"


def test_metadata_update_is_validated_atomically_and_preserves_unknown_fields(task_tree):
    core, user, _home = task_tree
    path = make_task(core, "scheduled")
    meta = json.loads((path / "task.json").read_text(encoding="utf-8"))
    meta["futureSetting"] = {"keep": True}
    (path / "task.json").write_text(json.dumps(meta), encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid cron"):
        definitions.update_meta("scheduled", {"schedule": "not a cron"})
    assert not (user / "scheduled").exists()

    saved = definitions.update_meta("scheduled", {"name": "Scheduled Research", "enabled": True})
    raw = json.loads((user / "scheduled" / "task.json").read_text(encoding="utf-8"))
    assert raw["futureSetting"] == {"keep": True}
    assert saved["name"] == "Scheduled Research"
    assert saved["enabled"] is True

    before = (user / "scheduled" / "task.json").read_bytes()
    with pytest.raises(ValueError, match="invalid JSON"):
        definitions.write_file("scheduled", "task.json", "{")
    assert (user / "scheduled" / "task.json").read_bytes() == before


def test_file_crud_protection_and_reference_validation(task_tree):
    core, _user, _home = task_tree
    make_task(core, "editable", script='await run("missing.py");\n')

    created = definitions.write_file("editable", "notes.txt", "one", create=True)
    assert created["name"] == "notes.txt"
    definitions.write_file("editable", "notes.txt", "two")
    assert definitions.read_file("editable", "notes.txt")["content"] == "two"
    definitions.delete_file("editable", "notes.txt")
    with pytest.raises(PermissionError):
        definitions.delete_file("editable", "task.js")
    with pytest.raises(ValueError):
        definitions.write_file("editable", "../escape.py", "")

    result = definitions.validate_task("editable")
    assert result["ok"] is False
    assert 'Referenced file "missing.py" does not exist' in result["errors"]
    definitions.write_file("editable", "missing.py", "print('ok')\n", create=True)
    assert definitions.validate_task("editable")["ok"] is True


@pytest.mark.asyncio
async def test_queue_priority_dedupe_and_recovery_preserve_checkpoint(task_db):
    alpha = await task_db.ensure_task_queue_source("alpha", "queue")
    beta = await task_db.ensure_task_queue_source("beta", "queue")
    low = await task_db.enqueue_task_work(alpha, "alpha", {}, priority=-1, dedupe_key="alpha:once")
    duplicate = await task_db.enqueue_task_work(alpha, "alpha", {"changed": "ignored"}, dedupe_key="alpha:once")
    high = await task_db.enqueue_task_work(beta, "beta", {}, priority=20)
    assert duplicate["id"] == low["id"]
    assert "run_mode" not in low

    claimed = await task_db.claim_next_task_work()
    assert claimed["id"] == high["id"]
    assert await task_db.mark_task_work_running(high["id"]) is True
    await task_db.save_task_checkpoint(high["id"], "call:0", "run", "completed.py", "complete")

    assert await task_db.recover_interrupted_task_work() == 1
    recovered = await task_db.get_task_work(high["id"])
    assert recovered["status"] == "queued"
    assert await task_db.get_task_checkpoint(high["id"], "call:0") == "complete"
    assert (await task_db.claim_next_task_work())["id"] == high["id"]


@pytest.mark.asyncio
async def test_queue_allows_distinct_inputs_for_the_same_task(task_db):
    schedule_id = await task_db.ensure_task_queue_source("analyze-security", "queue")
    first = await task_db.enqueue_task_work(
        schedule_id,
        "analyze-security",
        {"symbol": "AAA"},
        dedupe_key="analyze-security:AAA",
    )
    second = await task_db.enqueue_task_work(
        schedule_id,
        "analyze-security",
        {"symbol": "BBB"},
        dedupe_key="analyze-security:BBB",
    )

    assert first["id"] != second["id"]
    rows = await task_db.list_task_work("analyze-security")
    assert {json.loads(row["inputs_json"])["symbol"] for row in rows} == {"AAA", "BBB"}


@pytest.mark.asyncio
async def test_schedule_state_stays_running_with_other_work_queued(task_db):
    schedule_id = await task_db.ensure_task_queue_source("analyze-security", "queue")
    older = await task_db.enqueue_task_work(schedule_id, "analyze-security", {"symbol": "AAA"})
    running = await task_db.enqueue_task_work(
        schedule_id,
        "analyze-security",
        {"symbol": "BBB"},
        priority=10,
    )
    assert (await task_db.claim_next_task_work())["id"] == running["id"]
    assert await task_db.mark_task_work_running(running["id"]) is True

    await task_db.enqueue_task_work(schedule_id, "analyze-security", {"symbol": "CCC"})
    state = await (
        await task_db.conn.execute("SELECT status FROM scheduled_task_state WHERE schedule_id=?", (schedule_id,))
    ).fetchone()
    assert state["status"] == "running"

    assert await task_db.cancel_task_work(older["id"]) is True
    state = await (
        await task_db.conn.execute("SELECT status FROM scheduled_task_state WHERE schedule_id=?", (schedule_id,))
    ).fetchone()
    assert state["status"] == "running"

    await task_db.finish_task_work(running["id"], "done")
    state = await (
        await task_db.conn.execute("SELECT status FROM scheduled_task_state WHERE schedule_id=?", (schedule_id,))
    ).fetchone()
    assert state["status"] == "queued"


@pytest.mark.asyncio
async def test_task_database_enforces_foreign_keys_and_rolls_back_partial_enqueue(task_db):
    schedule_id = await task_db.ensure_task_queue_source("broken", "queue")
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        await task_db.append_task_run_event("missing-run", "log", {"text": "orphan"})
    await task_db.conn.execute(
        """CREATE TRIGGER reject_broken_task_run BEFORE INSERT ON task_runs
           WHEN NEW.task_id='broken' BEGIN SELECT RAISE(ABORT, 'forced task run failure'); END"""
    )
    await task_db.conn.commit()

    with pytest.raises(sqlite3.IntegrityError, match="forced task run failure"):
        await task_db.enqueue_task_work(schedule_id, "broken", {})

    count = await (await task_db.conn.execute("SELECT COUNT(*) FROM work_queue WHERE task_id='broken'")).fetchone()
    state = await (
        await task_db.conn.execute("SELECT status FROM scheduled_task_state WHERE schedule_id=?", (schedule_id,))
    ).fetchone()
    assert count[0] == 0
    assert state["status"] == "idle"


@pytest.mark.asyncio
async def test_stale_schedule_success_window_and_failure_backoff(task_db):
    schedule_id = "task:analysis:stale"
    await task_db.upsert_task_schedule(
        schedule_id,
        "analysis",
        {"type": "stale_after", "seconds": 3600},
        {"runWhen": "idle", "priority": 4},
    )
    assert [row["id"] for row in await task_db.list_due_stale_task_schedules()] == [schedule_id]

    work = await task_db.enqueue_task_work(schedule_id, "analysis", {})
    assert await task_db.mark_task_work_running(work["id"]) is False
    claimed = await task_db.claim_next_task_work()
    assert await task_db.mark_task_work_running(claimed["id"]) is True
    await task_db.finish_task_work(claimed["id"], "done")
    assert await task_db.list_due_stale_task_schedules() == []

    await task_db.conn.execute(
        "UPDATE scheduled_task_state SET next_eligible_at=0 WHERE schedule_id=?",
        (schedule_id,),
    )
    await task_db.conn.commit()
    work = await task_db.enqueue_task_work(schedule_id, "analysis", {})
    claimed = await task_db.claim_next_task_work()
    assert claimed["id"] == work["id"]
    assert await task_db.mark_task_work_running(work["id"]) is True
    await task_db.finish_task_work(work["id"], "error", "temporary failure")
    state = await (
        await task_db.conn.execute("SELECT * FROM scheduled_task_state WHERE schedule_id=?", (schedule_id,))
    ).fetchone()
    assert state["status"] == "backoff"
    assert state["consecutive_failures"] == 1
    assert state["next_eligible_at"] > state["last_finished_at"]


@pytest.mark.asyncio
async def test_cancelled_stale_schedule_waits_for_its_full_interval(task_db):
    schedule_id = "task:cancelled-analysis:stale"
    await task_db.upsert_task_schedule(
        schedule_id,
        "cancelled-analysis",
        {"type": "stale_after", "seconds": 3600},
        {"runWhen": "idle"},
    )
    work = await task_db.enqueue_task_work(schedule_id, "cancelled-analysis", {})
    claimed = await task_db.claim_next_task_work()
    assert claimed["id"] == work["id"]
    assert await task_db.mark_task_work_running(work["id"])

    assert await task_db.cancel_task_work(work["id"])

    state = await (
        await task_db.conn.execute("SELECT * FROM scheduled_task_state WHERE schedule_id=?", (schedule_id,))
    ).fetchone()
    assert state["status"] == "idle"
    assert state["next_eligible_at"] >= state["last_finished_at"] + 3600 * 1000
    assert await task_db.list_due_stale_task_schedules() == []


@pytest.mark.asyncio
async def test_stale_schedule_uses_current_interval_and_future_queue_is_not_busy(task_db):
    schedule_id = "task:editable-interval:stale"
    await task_db.upsert_task_schedule(
        schedule_id,
        "editable-interval",
        {"type": "stale_after", "seconds": 3600},
        {"runWhen": "idle"},
    )
    old_success = int((time.time() - 10) * 1000)
    await task_db.conn.execute(
        """UPDATE scheduled_task_state SET last_success_at=?, next_eligible_at=?
           WHERE schedule_id=?""",
        (old_success, old_success + 3_600_000, schedule_id),
    )
    await task_db.conn.commit()
    assert await task_db.list_due_stale_task_schedules() == []

    await task_db.upsert_task_schedule(
        schedule_id,
        "editable-interval",
        {"type": "stale_after", "seconds": 1},
        {"runWhen": "idle"},
    )
    assert [row["id"] for row in await task_db.list_due_stale_task_schedules()] == [schedule_id]

    queue_source = await task_db.ensure_task_queue_source("future", "queue")
    eligible_at = old_success + 7_200_000
    await task_db.enqueue_task_work(queue_source, "future", {}, eligible_at=eligible_at)
    assert await task_db.task_runtime_busy() is False
    assert await task_db.get_next_task_work_eligible_at() == eligible_at


@pytest.mark.asyncio
async def test_terminal_run_deletes_checkpoints_and_replaces_live_output(task_db):
    source = await task_db.ensure_task_queue_source("retention", "manual")
    work = await task_db.enqueue_task_work(source, "retention", {})
    await task_db.save_task_checkpoint(work["id"], "call:0", "run", "large.py", "large output")
    await task_db.replace_task_run_live_event(work["id"], {"text": "first"})
    await task_db.replace_task_run_live_event(work["id"], {"text": "second"})
    live = await (
        await task_db.conn.execute(
            "SELECT payload_json FROM task_run_events WHERE run_id=? AND event_type='live'", (work["id"],)
        )
    ).fetchall()
    assert len(live) == 1
    assert json.loads(live[0]["payload_json"])["text"] == "second"

    await task_db.finish_task_work(work["id"], "cancelled", "done")
    assert await task_db.get_task_checkpoint(work["id"], "call:0") is None


class FakeClient:
    searxng_base_url = "http://127.0.0.1:8888"
    url_summarizer_base_url = "http://127.0.0.1:8890"
    browser_search_base_url = "http://127.0.0.1:8891"

    async def close(self):
        return None


class FakeExecutors(dict):
    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_stale_evaluator_is_offset_from_portfolio_job_anchor(task_db, monkeypatch):
    class Scheduler:
        def __init__(self):
            self.added = []

        def get_jobs(self):
            return []

        def add_job(self, function, trigger, **kwargs):
            self.added.append((function, trigger, kwargs))

    scheduler = Scheduler()
    monkeypatch.setattr(runtime, "Database", lambda: task_db)
    monkeypatch.setattr(runtime, "list_tasks", lambda: [])
    before = datetime.now(timezone.utc)
    try:
        await runtime.sync_task_schedules(scheduler)
    finally:
        runtime._scheduler = None

    _, trigger, kwargs = scheduler.added[0]
    offset = (trigger.start_date - before).total_seconds()
    assert kwargs["id"] == runtime.STALE_EVALUATOR_JOB
    assert runtime.STALE_EVALUATOR_OFFSET_SECONDS - 1 <= offset <= runtime.STALE_EVALUATOR_OFFSET_SECONDS + 1


@pytest.fixture
def fake_runtime(monkeypatch, task_db):
    async def fake_from_settings(_settings):
        return FakeClient()

    monkeypatch.setattr(runtime, "Database", lambda: task_db)
    monkeypatch.setattr(runtime.LLMClient, "from_settings", fake_from_settings)
    monkeypatch.setattr(runtime.ai_tools, "make_tool_executors", lambda *_args: FakeExecutors())
    runtime._bridges.clear()
    runtime._children.clear()
    runtime._active_runs.clear()
    yield
    for execution in runtime._active_runs.values():
        execution.cancel()
    runtime._bridges.clear()
    runtime._children.clear()
    runtime._active_runs.clear()


async def wait_for_file(path: Path, timeout: float = 5) -> None:
    async with asyncio.timeout(timeout):
        while not path.exists():
            await asyncio.sleep(0.02)


@pytest.mark.asyncio
async def test_prompt_call_forwards_custom_system_prompt(tmp_path, monkeypatch):
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("Prompt", encoding="utf-8")
    captured = {}

    async def fake_prompt(*_args, **kwargs):
        captured.update(kwargs)
        return "done"

    monkeypatch.setattr(runtime, "run_prompt", fake_prompt)
    result = await runtime._handle_call(
        "run-id",
        "prompt",
        {"file": "prompt.md", "options": {"systemPrompt": "Custom instructions"}},
        {"id": "example"},
        tmp_path,
        tmp_path,
        {},
        FakeClient(),
        FakeExecutors(),
    )

    assert result == "done"
    assert captured["system"] == "Custom instructions"


@pytest.mark.asyncio
async def test_prompt_call_can_disable_tools(tmp_path, monkeypatch):
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("Prompt", encoding="utf-8")
    captured = {}

    async def fake_prompt(*_args, **kwargs):
        captured.update(kwargs)
        return "done"

    monkeypatch.setattr(runtime, "run_prompt", fake_prompt)
    result = await runtime._handle_call(
        "run-id",
        "prompt",
        {"file": "prompt.md", "options": {"useTools": False}},
        {"id": "example"},
        tmp_path,
        tmp_path,
        {},
        FakeClient(),
        FakeExecutors(),
    )

    assert result == "done"
    assert captured["use_tools"] is False


@pytest.mark.asyncio
async def test_worker_waits_for_api_readiness_before_claiming_work(monkeypatch):
    ready = asyncio.Event()
    claimed = asyncio.Event()

    class ReadinessDatabase:
        async def claim_next_task_work(self):
            claimed.set()
            runtime._shutdown = True
            return None

        async def get_next_task_work_eligible_at(self):
            return None

    async def wait_for_readiness():
        await ready.wait()

    monkeypatch.setattr(runtime, "Database", ReadinessDatabase)
    monkeypatch.setattr(runtime, "_wait_for_api_ready", wait_for_readiness)
    runtime._shutdown = False
    runtime._wake_event = asyncio.Event()
    worker = asyncio.create_task(runtime._worker_loop())
    try:
        await asyncio.sleep(0.02)
        assert not claimed.is_set()
        ready.set()
        await asyncio.wait_for(claimed.wait(), timeout=2)
        await asyncio.wait_for(worker, timeout=2)
    finally:
        runtime._shutdown = False
        if not worker.done():
            worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker


@pytest.mark.asyncio
async def test_idle_worker_waits_for_wakeup_without_polling_database(monkeypatch):
    claimed = 0

    class IdleDatabase:
        async def claim_next_task_work(self):
            nonlocal claimed
            claimed += 1
            return None

        async def get_next_task_work_eligible_at(self):
            return None

    async def ready():
        return None

    monkeypatch.setattr(runtime, "Database", IdleDatabase)
    monkeypatch.setattr(runtime, "_wait_for_api_ready", ready)
    runtime._shutdown = False
    runtime._wake_event = asyncio.Event()
    worker = asyncio.create_task(runtime._worker_loop())
    try:
        await asyncio.sleep(0.05)
        assert claimed == 1
    finally:
        runtime._shutdown = True
        runtime._wake_event.set()
        await asyncio.wait_for(worker, timeout=2)
        runtime._shutdown = False


@pytest.mark.asyncio
async def test_api_readiness_retries_until_health_endpoint_succeeds(monkeypatch):
    calls = []

    class Response:
        def __init__(self, status_code):
            self.status_code = status_code

    class Client:
        def __init__(self, *args, **kwargs):
            assert kwargs == {"timeout": runtime.API_READINESS_TIMEOUT_SECONDS, "trust_env": False}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, url):
            calls.append(url)
            return Response(503 if len(calls) == 1 else 200)

    monkeypatch.setattr(runtime.httpx, "AsyncClient", Client)
    monkeypatch.setattr(runtime, "API_READINESS_POLL_SECONDS", 0)
    monkeypatch.setenv("SENTINEL_BASE_URL", "http://127.0.0.1:9123/")
    runtime._shutdown = False

    await runtime._wait_for_api_ready()

    assert calls == ["http://127.0.0.1:9123/api/health"] * 2


def process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


async def enqueue_and_claim(db, task_id: str):
    source = await db.ensure_task_queue_source(task_id, "manual")
    row = await db.enqueue_task_work(source, task_id, {})
    claimed = await db.claim_next_task_work()
    assert claimed["id"] == row["id"]
    return claimed


@pytest.mark.asyncio
async def test_runtime_executes_task_and_propagates_mutated_environment(task_tree, task_db, fake_runtime):
    core, _user, _home = task_tree
    task = make_task(
        core,
        "runtime-smoke",
        script='process.env.SHARED = "ported"; const output = await run("echo.py"); console.log(output.trim());\n',
    )
    (task / "echo.py").write_text('import os\nprint(os.environ["SHARED"])\n', encoding="utf-8")
    item = await enqueue_and_claim(task_db, "runtime-smoke")

    await runtime._execute(item)

    row = await task_db.get_task_work(item["id"])
    events = await task_db.list_task_run_events(item["id"])
    assert row["status"] == "done"
    assert any("ported" in event["payload_json"] for event in events)


@pytest.mark.asyncio
async def test_runtime_accepts_clara_sized_results_in_the_next_bridge_call(task_tree, task_db, fake_runtime):
    core, _user, _home = task_tree
    task = make_task(
        core,
        "large-step-output",
        script=(
            'const payload = await run("large.py");\n'
            'const size = await run("measure.py", { env: { PAYLOAD: payload } });\n'
            "console.log(size.trim());\n"
        ),
    )
    (task / "large.py").write_text('print("x" * 70000)\n', encoding="utf-8")
    (task / "measure.py").write_text(
        'import os\nprint(len(os.environ["PAYLOAD"]))\n',
        encoding="utf-8",
    )
    item = await enqueue_and_claim(task_db, "large-step-output")

    await runtime._execute(item)

    row = await task_db.get_task_work(item["id"])
    events = await task_db.list_task_run_events(item["id"])
    assert row["status"] == "done"
    assert any("70001" in event["payload_json"] for event in events)


@pytest.mark.asyncio
async def test_interrupted_run_kills_child_and_replays_completed_calls_once(task_tree, task_db, fake_runtime):
    core, _user, home = task_tree
    task = make_task(
        core,
        "restartable",
        script='await run("side.py"); await run("interrupt.py"); console.log("complete");\n',
    )
    marker = home / "side-count.txt"
    interruption = home / "interrupt-once"
    pid_file = home / "child.pid"
    (task / "side.py").write_text(
        "import os, pathlib\n"
        "p = pathlib.Path(os.environ['SIDE_MARKER'])\n"
        "p.write_text(str(int(p.read_text()) + 1) if p.exists() else '1')\n",
        encoding="utf-8",
    )
    (task / "interrupt.py").write_text(
        "import os, pathlib, time\n"
        "flag = pathlib.Path(os.environ['INTERRUPT_FLAG'])\n"
        "if not flag.exists():\n"
        "    flag.write_text('started')\n"
        "    pathlib.Path(os.environ['CHILD_PID']).write_text(str(os.getpid()))\n"
        "    time.sleep(60)\n"
        "print('resumed')\n",
        encoding="utf-8",
    )
    item = await enqueue_and_claim(task_db, "restartable")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("SIDE_MARKER", str(marker))
        patch.setenv("INTERRUPT_FLAG", str(interruption))
        patch.setenv("CHILD_PID", str(pid_file))
        execution = asyncio.create_task(runtime._execute(item))
        await wait_for_file(pid_file)
        child_pid = int(pid_file.read_text(encoding="utf-8"))
        execution.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await execution
        assert not process_exists(child_pid)

        assert await task_db.recover_interrupted_task_work() == 1
        resumed = await task_db.claim_next_task_work()
        assert resumed["id"] == item["id"]
        await runtime._execute(resumed)

    row = await task_db.get_task_work(item["id"])
    assert row["status"] == "done"
    assert marker.read_text(encoding="utf-8") == "1"
    assert await task_db.get_task_checkpoint(item["id"], "call:0") is None


@pytest.mark.asyncio
async def test_recovered_scheduled_run_is_cancelled_when_task_was_disabled(task_tree, task_db, fake_runtime):
    core, _user, _home = task_tree
    task = make_task(core, "scheduled-recovery")
    meta = json.loads((task / "task.json").read_text(encoding="utf-8"))
    meta.update({"enabled": True, "schedulePolicy": {"staleAfterSeconds": 60, "runWhen": "idle"}})
    (task / "task.json").write_text(json.dumps(meta), encoding="utf-8")
    schedule_id = "task:scheduled-recovery:stale"
    await task_db.upsert_task_schedule(
        schedule_id,
        "scheduled-recovery",
        {"type": "stale_after", "seconds": 60},
        {"runWhen": "idle"},
    )
    work = await task_db.enqueue_task_work(schedule_id, "scheduled-recovery", {})
    claimed = await task_db.claim_next_task_work()
    assert claimed["id"] == work["id"]
    assert await task_db.mark_task_work_running(work["id"])
    assert await task_db.recover_interrupted_task_work() == 1

    meta["enabled"] = False
    (task / "task.json").write_text(json.dumps(meta), encoding="utf-8")
    recovered = await task_db.claim_next_task_work()
    await runtime._execute(recovered)

    row = await task_db.get_task_work(work["id"])
    assert row["status"] == "cancelled"
    assert row["error"] == "Task is no longer enabled or scheduled"


@pytest.mark.asyncio
async def test_stop_run_terminates_running_child_process(task_tree, task_db, fake_runtime):
    core, _user, home = task_tree
    task = make_task(core, "stoppable", script='await run("sleep.py");\n')
    pid_file = home / "stop-child.pid"
    (task / "sleep.py").write_text(
        "import os, pathlib, time\n"
        "pathlib.Path(os.environ['CHILD_PID']).write_text(str(os.getpid()))\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )
    item = await enqueue_and_claim(task_db, "stoppable")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("CHILD_PID", str(pid_file))
        execution = asyncio.create_task(runtime._execute(item))
        await wait_for_file(pid_file)
        child_pid = int(pid_file.read_text(encoding="utf-8"))
        assert await runtime.stop_run(item["id"]) is True
        await asyncio.wait_for(execution, timeout=5)

    row = await task_db.get_task_work(item["id"])
    assert row["status"] == "cancelled"
    assert not process_exists(child_pid)


@pytest.mark.asyncio
async def test_stop_run_cancels_active_prompt_and_cannot_restore_checkpoint(
    task_tree, task_db, fake_runtime, monkeypatch
):
    core, _user, _home = task_tree
    task = make_task(core, "stop-prompt", script='await prompt("prompt.md");\n')
    (task / "prompt.md").write_text("Wait", encoding="utf-8")
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def blocking_prompt(*_args, **_kwargs):
        started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    monkeypatch.setattr(runtime, "run_prompt", blocking_prompt)
    item = await enqueue_and_claim(task_db, "stop-prompt")
    execution = asyncio.create_task(runtime._execute(item))
    runtime._active_runs[item["id"]] = execution
    await asyncio.wait_for(started.wait(), timeout=5)

    assert await runtime.stop_run(item["id"]) is True
    assert cancelled.is_set()
    assert execution.cancelled()
    assert await task_db.get_task_checkpoint(item["id"], "call:0") is None
    assert await task_db.save_task_checkpoint(item["id"], "call:0", "prompt", "prompt.md", "late") is False
    runtime._active_runs.pop(item["id"], None)


def test_rating_validator_repairs_json_without_frontend_node_modules(tmp_path):
    context = {
        "symbol": "TEST",
        "ratingRawPath": str(tmp_path / "rating.raw.json"),
        "ratingPath": str(tmp_path / "rating.json"),
    }
    Path(context["ratingRawPath"]).write_text(
        "```json\n{symbol: 'TEST', rating: 0.7, rationale: 'First paragraph.\\n\\nSecond paragraph.',}\n```\n",
        encoding="utf-8",
    )
    script = definitions.CORE_TASKS_DIR / "rate-security" / "validate-rating.mjs"
    env = os.environ | {"CONTEXT_JSON": json.dumps(context), "SENTINEL_APP_ROOT": str(runtime.APP_ROOT)}
    result = subprocess.run(  # noqa: S603 - fixed executable and test-owned script
        [shutil.which("node") or "node", str(script)],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
        check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["valid"] is True
    assert json.loads(Path(context["ratingPath"]).read_text(encoding="utf-8"))["rating"] == 0.7


def test_rating_validator_does_not_enforce_rationale_paragraph_count(tmp_path):
    context = {
        "symbol": "TEST",
        "ratingRawPath": str(tmp_path / "rating.raw.json"),
        "ratingPath": str(tmp_path / "rating.json"),
    }
    Path(context["ratingRawPath"]).write_text(
        json.dumps({"symbol": "TEST", "rating": 0.7, "rationale": "One concise paragraph."}),
        encoding="utf-8",
    )
    script = definitions.CORE_TASKS_DIR / "rate-security" / "validate-rating.mjs"
    env = os.environ | {"CONTEXT_JSON": json.dumps(context), "SENTINEL_APP_ROOT": str(runtime.APP_ROOT)}
    result = subprocess.run(  # noqa: S603 - fixed executable and test-owned script
        [shutil.which("node") or "node", str(script)],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["valid"] is True


def test_rating_validator_rejects_the_same_leading_zero_number_as_clara(tmp_path):
    context = {
        "symbol": "TEST",
        "ratingRawPath": str(tmp_path / "rating.raw.json"),
        "ratingPath": str(tmp_path / "rating.json"),
    }
    Path(context["ratingRawPath"]).write_text(
        "{symbol: 'TEST', rating: 01, rationale: 'First paragraph.\\n\\nSecond paragraph.'}",
        encoding="utf-8",
    )
    script = definitions.CORE_TASKS_DIR / "rate-security" / "validate-rating.mjs"
    env = os.environ | {"CONTEXT_JSON": json.dumps(context), "SENTINEL_APP_ROOT": str(runtime.APP_ROOT)}
    result = subprocess.run(  # noqa: S603 - fixed executable and test-owned script
        [shutil.which("node") or "node", str(script)],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["valid"] is False
    assert payload["error"] == "Rating must be a finite number from 0.0 to 1.0"
