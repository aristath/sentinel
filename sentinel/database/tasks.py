"""Durable Clara-style task queue and run persistence."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

import aiosqlite

ACTIVE_WORK_STATUSES = ("queued", "claimed", "running")


class TaskDatabaseMixin:
    """Database methods for scheduled folder tasks."""

    conn: aiosqlite.Connection

    @asynccontextmanager
    async def _task_transaction(self) -> AsyncIterator[aiosqlite.Connection]:
        """Run one task state transition on the serialized primary connection."""
        conn = self.conn
        await conn.execute("PRAGMA foreign_keys=ON")
        try:
            await conn.execute("BEGIN IMMEDIATE")
            yield conn
            await conn.commit()
        except BaseException:
            await conn.rollback()
            raise
        finally:
            await asyncio.shield(conn.execute("PRAGMA foreign_keys=OFF"))

    async def upsert_task_schedule(
        self,
        schedule_id: str,
        task_id: str,
        trigger: dict[str, Any],
        policy: dict[str, Any],
        *,
        enabled: bool = True,
    ) -> None:
        now = int(time.time() * 1000)
        trigger_json = json.dumps(trigger)
        policy_json = json.dumps(policy)
        async with self._task_transaction() as conn:
            previous = await (
                await conn.execute("SELECT trigger_json FROM scheduled_tasks WHERE id=?", (schedule_id,))
            ).fetchone()
            await conn.execute(
                """INSERT INTO scheduled_tasks
                   (id, task_id, run_as_user_id, trigger_json, policy_json, enabled, created_at, updated_at)
                   VALUES (?, ?, 'sentinel', ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET task_id=excluded.task_id,
                     trigger_json=excluded.trigger_json, policy_json=excluded.policy_json,
                     enabled=excluded.enabled, updated_at=excluded.updated_at""",
                (schedule_id, task_id, trigger_json, policy_json, int(enabled), now, now),
            )
            await conn.execute(
                """INSERT INTO scheduled_task_state
                   (schedule_id, status, consecutive_failures, updated_at)
                   VALUES (?, ?, 0, ?)
                   ON CONFLICT(schedule_id) DO UPDATE SET
                     status=CASE WHEN excluded.status='disabled' THEN 'disabled'
                       WHEN scheduled_task_state.status='disabled' THEN 'idle'
                       ELSE scheduled_task_state.status END,
                     updated_at=excluded.updated_at""",
                (schedule_id, "idle" if enabled else "disabled", now),
            )
            if previous and previous["trigger_json"] != trigger_json:
                await conn.execute(
                    """UPDATE scheduled_task_state SET next_eligible_at=NULL, updated_at=?
                       WHERE schedule_id=? AND consecutive_failures=0""",
                    (now, schedule_id),
                )

    async def disable_missing_task_schedules(self, active_ids: set[str]) -> None:
        async with self._task_transaction() as conn:
            rows = await (
                await conn.execute(
                    "SELECT id FROM scheduled_tasks WHERE id LIKE 'task:%:cron' OR id LIKE 'task:%:stale'"
                )
            ).fetchall()
            now = int(time.time() * 1000)
            for row in rows:
                if row["id"] in active_ids:
                    continue
                await conn.execute("UPDATE scheduled_tasks SET enabled=0, updated_at=? WHERE id=?", (now, row["id"]))
                await conn.execute(
                    "UPDATE scheduled_task_state SET status='disabled', updated_at=? WHERE schedule_id=?",
                    (now, row["id"]),
                )

    async def ensure_task_queue_source(self, task_id: str, source: str) -> str:
        schedule_id = f"task:{task_id}:{source}"
        await self.upsert_task_schedule(schedule_id, task_id, {"type": source}, {"runWhen": "immediate"})
        return schedule_id

    async def recover_interrupted_task_work(self) -> int:
        now = int(time.time() * 1000)
        async with self._task_transaction() as conn:
            cursor = await conn.execute("SELECT id, schedule_id FROM work_queue WHERE status IN ('claimed', 'running')")
            rows = list(await cursor.fetchall())
            await conn.execute(
                """UPDATE work_queue SET status='queued', claimed_at=NULL, started_at=NULL,
                   error='Process restarted before this task finished; queued to resume', updated_at=?
                   WHERE status IN ('claimed', 'running')""",
                (now,),
            )
            await conn.execute(
                """UPDATE task_runs SET status='queued', current_step_id=NULL,
                   error='Process restarted before this task finished; queued to resume', updated_at=?
                   WHERE status IN ('running', 'waiting', 'interrupted')
                     AND work_item_id IN (SELECT id FROM work_queue WHERE status='queued')""",
                (now,),
            )
            await conn.execute(
                """UPDATE task_runs SET status='failed', completed_at=?, current_step_id=NULL,
                   error='Recovered an interrupted run without active queue work', updated_at=?
                   WHERE status IN ('running', 'waiting', 'interrupted')
                     AND NOT EXISTS (SELECT 1 FROM work_queue WHERE work_queue.id=task_runs.work_item_id
                                     AND work_queue.status IN ('queued','claimed','running'))""",
                (now, now),
            )
            for row in rows:
                await conn.execute(
                    """UPDATE scheduled_task_state SET status='queued',
                       last_error='Process restarted before this task finished; queued to resume', updated_at=?
                       WHERE schedule_id=?""",
                    (now, row["schedule_id"]),
                )
        return len(rows)

    async def enqueue_task_work(
        self,
        schedule_id: str,
        task_id: str,
        inputs: dict[str, str],
        *,
        title: str | None = None,
        dedupe_key: str | None = None,
        priority: int = 0,
        eligible_at: int | None = None,
    ) -> dict[str, Any]:
        async with self._task_transaction() as conn:
            if dedupe_key:
                row = await (
                    await conn.execute(
                        """SELECT * FROM work_queue WHERE dedupe_key=?
                           AND status IN ('queued','claimed','running') ORDER BY created_at LIMIT 1""",
                        (dedupe_key,),
                    )
                ).fetchone()
                if row:
                    return dict(row)

            now = int(time.time() * 1000)
            run_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO work_queue
                   (id, schedule_id, task_id, run_as_user_id, title, inputs_json, dedupe_key,
                    priority, status, eligible_at, created_at, updated_at)
                   VALUES (?, ?, ?, 'sentinel', ?, ?, ?, ?, 'queued', ?, ?, ?)""",
                (
                    run_id,
                    schedule_id,
                    task_id,
                    title,
                    json.dumps(inputs),
                    dedupe_key,
                    max(-1000, min(1000, int(priority))),
                    eligible_at or now,
                    now,
                    now,
                ),
            )
            source_mode = (
                "manual"
                if schedule_id.endswith(":manual")
                else "queued"
                if schedule_id.endswith(":queue")
                else "scheduled"
            )
            await conn.execute(
                """INSERT INTO task_runs
                   (id, task_id, mode, run_as_user_id, title, status, inputs_json,
                    output_artifacts_json, work_item_id, created_at, updated_at)
                   VALUES (?, ?, ?, 'sentinel', ?, 'queued', ?, '[]', ?, ?, ?)""",
                (run_id, task_id, source_mode, title, json.dumps(inputs), run_id, now, now),
            )
            await conn.execute(
                """UPDATE scheduled_task_state
                   SET status=CASE WHEN status='running' THEN 'running' ELSE 'queued' END,
                       last_error=NULL, updated_at=? WHERE schedule_id=?""",
                (now, schedule_id),
            )
            row = await (await conn.execute("SELECT * FROM work_queue WHERE id=?", (run_id,))).fetchone()
            if row is None:
                raise RuntimeError("Queued task disappeared before it could be returned")
            return dict(cast(Any, row))

    async def claim_next_task_work(self) -> dict[str, Any] | None:
        now = int(time.time() * 1000)
        async with self._task_transaction() as conn:
            cursor = await conn.execute(
                """UPDATE work_queue SET status='claimed', claimed_at=?, updated_at=?
                   WHERE id=(SELECT id FROM work_queue WHERE status='queued' AND eligible_at<=?
                             ORDER BY priority DESC, created_at ASC LIMIT 1)
                   RETURNING *""",
                (now, now, now),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_next_task_work_eligible_at(self) -> int | None:
        """Return the earliest future queue eligibility timestamp, in milliseconds."""
        row = await (
            await self.conn.execute("SELECT MIN(eligible_at) AS eligible_at FROM work_queue WHERE status='queued'")
        ).fetchone()
        return int(row["eligible_at"]) if row and row["eligible_at"] is not None else None

    async def mark_task_work_running(self, run_id: str) -> bool:
        now = int(time.time() * 1000)
        async with self._task_transaction() as conn:
            cursor = await conn.execute(
                "UPDATE work_queue SET status='running', started_at=?, updated_at=? WHERE id=? AND status='claimed'",
                (now, now, run_id),
            )
            if cursor.rowcount <= 0:
                return False
            await conn.execute(
                """UPDATE task_runs SET status='running', started_at=COALESCE(started_at, ?),
                   error=NULL, updated_at=? WHERE id=?""",
                (now, now, run_id),
            )
            row = await (await conn.execute("SELECT schedule_id FROM work_queue WHERE id=?", (run_id,))).fetchone()
            if row:
                await conn.execute(
                    """UPDATE scheduled_task_state SET status='running', last_started_at=?,
                       last_error=NULL, updated_at=? WHERE schedule_id=?""",
                    (now, now, row["schedule_id"]),
                )
            return True

    async def finish_task_work(self, run_id: str, status: str, error: str | None = None) -> None:
        if status not in {"done", "error", "cancelled"}:
            raise ValueError(f"Invalid work completion status: {status}")
        async with self._task_transaction() as conn:
            await self._finish_task_work(conn, run_id, status, error)

    async def _finish_task_work(self, conn: aiosqlite.Connection, run_id: str, status: str, error: str | None) -> None:
        now = int(time.time() * 1000)
        row = await (await conn.execute("SELECT schedule_id FROM work_queue WHERE id=?", (run_id,))).fetchone()
        await conn.execute(
            "UPDATE work_queue SET status=?, finished_at=?, error=?, updated_at=? WHERE id=?",
            (status, now, error, now, run_id),
        )
        run_status = {"done": "succeeded", "error": "failed", "cancelled": "cancelled"}[status]
        await conn.execute(
            "UPDATE task_runs SET status=?, completed_at=?, current_step_id=NULL, error=?, updated_at=? WHERE id=?",
            (run_status, now, error, now, run_id),
        )
        await conn.execute("DELETE FROM task_run_checkpoints WHERE run_id=?", (run_id,))
        if row:
            await self._finish_task_schedule(conn, row["schedule_id"], status, error, now)

    async def _finish_task_schedule(
        self, conn: aiosqlite.Connection, schedule_id: str, status: str, error: str | None, now: int
    ) -> None:
        schedule = await (
            await conn.execute("SELECT trigger_json FROM scheduled_tasks WHERE id=?", (schedule_id,))
        ).fetchone()
        state = await (
            await conn.execute(
                "SELECT consecutive_failures FROM scheduled_task_state WHERE schedule_id=?", (schedule_id,)
            )
        ).fetchone()
        failures = int(state["consecutive_failures"] if state else 0)
        if status == "error":
            failures += 1
        elif status == "done":
            failures = 0
        next_eligible = None
        trigger = json.loads(schedule["trigger_json"]) if schedule else {}
        if trigger.get("type") == "stale_after":
            if status == "error":
                next_eligible = now + min(60 * 60 * 1000, 60_000 * (2 ** max(0, failures - 1)))
            else:
                next_eligible = now + max(0, int(trigger.get("seconds") or 0)) * 1000
        active = await (
            await conn.execute(
                """SELECT status FROM work_queue WHERE schedule_id=?
                   AND status IN ('queued','claimed','running')
                   ORDER BY CASE status WHEN 'running' THEN 0 WHEN 'claimed' THEN 1 ELSE 2 END,
                            created_at LIMIT 1""",
                (schedule_id,),
            )
        ).fetchone()
        state_status = (
            "running"
            if active and active["status"] == "running"
            else "queued"
            if active
            else "backoff"
            if status == "error" and next_eligible
            else "idle"
        )
        await conn.execute(
            """UPDATE scheduled_task_state SET status=?, last_finished_at=?,
               last_success_at=CASE WHEN ?='done' THEN ? ELSE last_success_at END,
               next_eligible_at=?, consecutive_failures=?, last_error=?, updated_at=?
               WHERE schedule_id=?""",
            (
                state_status,
                now,
                status,
                now,
                next_eligible,
                failures,
                error,
                now,
                schedule_id,
            ),
        )

    async def cancel_task_work(self, run_id: str) -> bool:
        async with self._task_transaction() as conn:
            row = await (
                await conn.execute(
                    "SELECT status FROM work_queue WHERE id=? AND status IN ('queued','claimed','running')", (run_id,)
                )
            ).fetchone()
            if not row:
                return False
            await self._finish_task_work(conn, run_id, "cancelled", "Stopped")
            return True

    async def get_task_work(self, run_id: str) -> dict[str, Any] | None:
        row = await (await self.conn.execute("SELECT * FROM work_queue WHERE id=?", (run_id,))).fetchone()
        return dict(row) if row else None

    async def get_active_task_work(self, task_id: str) -> dict[str, Any] | None:
        row = await (
            await self.conn.execute(
                """SELECT * FROM work_queue WHERE task_id=?
                   AND status IN ('queued','claimed','running') ORDER BY created_at LIMIT 1""",
                (task_id,),
            )
        ).fetchone()
        return dict(row) if row else None

    async def list_task_work(self, task_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        if task_id:
            cursor = await self.conn.execute(
                "SELECT * FROM work_queue WHERE task_id=? ORDER BY created_at DESC LIMIT ?", (task_id, limit)
            )
        else:
            cursor = await self.conn.execute("SELECT * FROM work_queue ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(row) for row in await cursor.fetchall()]

    async def list_task_work_for_tasks(self, task_ids: list[str], limit: int = 200) -> list[dict[str, Any]]:
        if not task_ids:
            return []
        placeholders = ",".join("?" for _ in task_ids)
        cursor = await self.conn.execute(
            f"SELECT * FROM work_queue WHERE task_id IN ({placeholders}) ORDER BY created_at DESC LIMIT ?",  # noqa: S608
            (*task_ids, limit),
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def get_task_schedule(self, schedule_id: str) -> dict[str, Any] | None:
        row = await (await self.conn.execute("SELECT * FROM scheduled_tasks WHERE id=?", (schedule_id,))).fetchone()
        return dict(row) if row else None

    async def get_task_run_row(self, run_id: str) -> dict[str, Any] | None:
        row = await (await self.conn.execute("SELECT * FROM task_runs WHERE id=?", (run_id,))).fetchone()
        return dict(row) if row else None

    async def set_task_run_hash(self, run_id: str, task_hash: str) -> None:
        now = int(time.time() * 1000)
        async with self._task_transaction() as conn:
            await conn.execute("UPDATE task_runs SET task_hash=?, updated_at=? WHERE id=?", (task_hash, now, run_id))

    async def append_task_run_event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
        async with self._task_transaction() as conn:
            await conn.execute(
                "INSERT INTO task_run_events (run_id, event_type, payload_json, created_at) VALUES (?, ?, ?, ?)",
                (run_id, event_type, json.dumps(payload, ensure_ascii=False), int(time.time() * 1000)),
            )

    async def replace_task_run_live_event(self, run_id: str, payload: dict[str, Any]) -> None:
        async with self._task_transaction() as conn:
            await conn.execute("DELETE FROM task_run_events WHERE run_id=? AND event_type='live'", (run_id,))
            await conn.execute(
                "INSERT INTO task_run_events (run_id, event_type, payload_json, created_at) VALUES (?, 'live', ?, ?)",
                (run_id, json.dumps(payload, ensure_ascii=False), int(time.time() * 1000)),
            )

    async def list_task_run_events(self, run_id: str, limit: int = 500) -> list[dict[str, Any]]:
        rows = await (
            await self.conn.execute(
                """SELECT * FROM (SELECT * FROM task_run_events WHERE run_id=? ORDER BY id DESC LIMIT ?)
                   ORDER BY id""",
                (run_id, max(1, min(limit, 2000))),
            )
        ).fetchall()
        return [dict(row) for row in rows]

    async def get_task_checkpoint(self, run_id: str, call_key: str) -> str | None:
        row = await (
            await self.conn.execute(
                "SELECT output_text FROM task_run_checkpoints WHERE run_id=? AND call_key=?", (run_id, call_key)
            )
        ).fetchone()
        return str(row["output_text"]) if row else None

    async def save_task_checkpoint(self, run_id: str, call_key: str, kind: str, label: str, output: str) -> bool:
        async with self._task_transaction() as conn:
            cursor = await conn.execute(
                """INSERT INTO task_run_checkpoints (run_id, call_key, kind, label, output_text, created_at)
                   SELECT ?, ?, ?, ?, ?, ?
                   WHERE EXISTS (
                       SELECT 1 FROM work_queue WHERE id=? AND status='running'
                   )
                   ON CONFLICT(run_id, call_key) DO UPDATE SET output_text=excluded.output_text""",
                (run_id, call_key, kind, label, output, int(time.time() * 1000), run_id),
            )
            return cursor.rowcount > 0

    async def cleanup_terminal_task_checkpoints(self) -> int:
        async with self._task_transaction() as conn:
            cursor = await conn.execute(
                """DELETE FROM task_run_checkpoints WHERE run_id IN
                   (SELECT id FROM task_runs WHERE status IN ('succeeded','failed','cancelled'))"""
            )
            return max(0, cursor.rowcount)

    async def list_due_stale_task_schedules(self) -> list[dict[str, Any]]:
        now = int(time.time() * 1000)
        rows = await (
            await self.conn.execute(
                """SELECT t.*, s.status, s.last_success_at, s.next_eligible_at, s.consecutive_failures
                   FROM scheduled_tasks t JOIN scheduled_task_state s ON s.schedule_id=t.id
                   WHERE t.enabled=1 AND json_extract(t.trigger_json, '$.type')='stale_after'
                     AND s.status NOT IN ('queued','running','disabled')
                     AND COALESCE(
                       s.next_eligible_at,
                       COALESCE(s.last_success_at, 0) + json_extract(t.trigger_json, '$.seconds') * 1000
                     ) <= ?
                   ORDER BY json_extract(t.policy_json, '$.priority') DESC, t.created_at ASC""",
                (now,),
            )
        ).fetchall()
        return [dict(row) for row in rows]

    async def task_runtime_busy(self) -> bool:
        row = await (
            await self.conn.execute("SELECT 1 FROM work_queue WHERE status IN ('claimed','running') LIMIT 1")
        ).fetchone()
        return row is not None
