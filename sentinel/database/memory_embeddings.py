"""Resumable, owner-scoped pgvector rebuilds without changing source records."""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from typing import Any

import asyncpg


@dataclass(frozen=True)
class MemoryEmbeddingMigration:
    source: str
    target: str
    user_id: str
    model: str
    dimensions: int

    def __post_init__(self) -> None:
        for name in (self.source, self.target):
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                raise ValueError("Memory collection names must be SQL identifiers")
        if self.source == self.target:
            raise ValueError("Rebuild into a separate collection; never replace the shared source")
        if not self.user_id or not self.model or self.dimensions <= 0:
            raise ValueError("Memory owner, model and positive dimensions are required")

    @property
    def marker(self) -> str:
        return json.dumps({"sentinel_embedding_migration": 1, **asdict(self)}, sort_keys=True)


async def prepare_collection(connection: asyncpg.Connection, plan: MemoryEmbeddingMigration) -> None:
    """Create a dedicated target, or verify that a resumable target belongs to this plan."""
    async with connection.transaction():
        exists = await connection.fetchval("SELECT to_regclass($1)::text", plan.target)
        if exists:
            marker = await connection.fetchval("SELECT obj_description($1::regclass, 'pg_class')", plan.target)
            if marker != plan.marker:
                raise ValueError("Target collection already exists with a different migration identity")
        else:
            await connection.execute(
                f'CREATE TABLE "{plan.target}" (id uuid PRIMARY KEY, vector vector({plan.dimensions}), '  # noqa: S608
                "payload jsonb NOT NULL)"
            )
            # Quote the marker through PostgreSQL itself; model names and owners are data, not SQL.
            quoted = await connection.fetchval("SELECT quote_literal($1::text)", plan.marker)
            await connection.execute(f'COMMENT ON TABLE "{plan.target}" IS {quoted}')  # noqa: S608
        actual = await connection.fetchval(
            "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
            "WHERE attrelid=$1::regclass AND attname='vector' AND NOT attisdropped",
            plan.target,
        )
        if actual != f"vector({plan.dimensions})":
            raise ValueError("Target vector dimensions do not match the migration")


async def pending_records(connection: asyncpg.Connection, plan: MemoryEmbeddingMigration) -> list[asyncpg.Record]:
    """Return only this consumer's missing or changed records, in length order."""
    return await connection.fetch(
        f"SELECT s.id, s.payload, s.payload->>'data' AS content FROM \"{plan.source}\" s "  # noqa: S608
        f'LEFT JOIN "{plan.target}" d ON d.id=s.id '
        "WHERE s.payload->>'user_id'=$1 AND (d.id IS NULL OR d.payload IS DISTINCT FROM s.payload) "
        "ORDER BY length(s.payload->>'data'), s.id",
        plan.user_id,
    )


def embedding_batches(records: list[Any], batch_size: int, max_chars: int) -> list[list[Any]]:
    """Keep similarly sized texts together without padding a short batch to a large outlier."""
    if batch_size < 1 or max_chars < 1:
        raise ValueError("Batch size and character budget must be positive")
    batches: list[list[Any]] = []
    batch: list[Any] = []
    chars = 0
    for record in records:
        text = record["content"]
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Source memory has no embeddable text; refusing to silently skip it")
        if batch and (len(batch) >= batch_size or chars + len(text) > max_chars):
            batches.append(batch)
            batch, chars = [], 0
        batch.append(record)
        chars += len(text)
    if batch:
        batches.append(batch)
    return batches


async def save_vectors(
    connection: asyncpg.Connection,
    plan: MemoryEmbeddingMigration,
    records: list[Any],
    vectors: list[list[float]],
) -> None:
    """Publish only snapshots that still match the source; preserve UUIDs and complete payloads."""
    import math

    if len(records) != len(vectors):
        raise ValueError("Embedding batch count does not match the source records")
    values = []
    for record, vector in zip(records, vectors, strict=True):
        if (
            len(vector) != plan.dimensions
            or not all(math.isfinite(x) for x in vector)
            or not any(x != 0 for x in vector)
        ):
            raise ValueError("Invalid vector returned during memory migration")
        values.append(
            (record["id"], "[" + ",".join(repr(float(x)) for x in vector) + "]", record["payload"], plan.user_id)
        )
    await connection.executemany(
        f'INSERT INTO "{plan.target}" (id, vector, payload) '  # noqa: S608
        "SELECT $1::uuid, $2::vector, $3::jsonb "
        f'WHERE EXISTS (SELECT 1 FROM "{plan.source}" s WHERE s.id=$1::uuid '
        "AND s.payload=$3::jsonb AND s.payload->>'user_id'=$4) "
        "ON CONFLICT (id) DO UPDATE SET vector=EXCLUDED.vector, payload=EXCLUDED.payload",
        values,
    )


async def verify_collection(connection: asyncpg.Connection, plan: MemoryEmbeddingMigration) -> dict[str, int]:
    """Require an exact owner-scoped copy with the new dimensions before any settings switch."""
    row = await connection.fetchrow(
        "SELECT "  # noqa: S608 - identifiers are validated by MemoryEmbeddingMigration.
        f"(SELECT count(*) FROM \"{plan.source}\" WHERE payload->>'user_id'=$1) AS source_records, "  # noqa: S608
        f'(SELECT count(*) FROM "{plan.target}") AS target_records, '
        f'(SELECT count(*) FROM "{plan.source}" s LEFT JOIN "{plan.target}" d ON d.id=s.id '
        "WHERE s.payload->>'user_id'=$1 AND (d.id IS NULL OR d.payload IS DISTINCT FROM s.payload)) AS missing, "
        f'(SELECT count(*) FROM "{plan.target}" d LEFT JOIN "{plan.source}" s ON s.id=d.id '
        "WHERE s.id IS NULL OR s.payload->>'user_id' IS DISTINCT FROM $1) AS extra, "
        f'(SELECT count(*) FROM "{plan.target}" WHERE vector IS NULL '
        "OR vector_dims(vector)<>$2 OR payload->>'user_id' IS DISTINCT FROM $1) AS invalid",
        plan.user_id,
        plan.dimensions,
    )
    if row is None:
        raise ValueError("Could not verify rebuilt memory collection")
    result = {k: int(row[k]) for k in ["source_records", "target_records", "missing", "extra", "invalid"]}
    if (
        result["missing"]
        or result["extra"]
        or result["invalid"]
        or result["source_records"] != result["target_records"]
    ):
        raise ValueError(f"Memory collection is incomplete or changed: {result}")
    return result


async def rebuild_collection(
    connection: asyncpg.Connection,
    plan: MemoryEmbeddingMigration,
    embed: Callable[[list[str]], Awaitable[list[list[float]]]],
    *,
    batch_size: int = 32,
    max_chars: int = 8000,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, int]:
    """A failed run is resumable; no source row or application setting is modified."""
    await prepare_collection(connection, plan)
    records = await pending_records(connection, plan)
    completed = 0
    for batch in embedding_batches(records, batch_size, max_chars):
        vectors = await embed([record["content"] for record in batch])
        await save_vectors(connection, plan, batch, vectors)
        completed += len(batch)
        if progress:
            progress({"completed_this_run": completed, "pending_at_start": len(records)})
    return await verify_collection(connection, plan)
