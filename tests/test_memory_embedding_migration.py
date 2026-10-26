"""BGE defaults, batch integrity, owner isolation and safe migration resumption."""

import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from sentinel.ai.errors import MemoryStoreError
from sentinel.ai.memory import MemoryStore, make_memory_store
from sentinel.database.memory_embeddings import (
    MemoryEmbeddingMigration,
    embedding_batches,
    prepare_collection,
    rebuild_collection,
    save_vectors,
    verify_collection,
)
from sentinel.settings import DEFAULTS


def plan(**overrides):
    return MemoryEmbeddingMigration(
        **{
            "source": "clara_memories",
            "target": "sentinel_memories",
            "user_id": "clara",
            "model": "BAAI/bge-m3",
            "dimensions": 3,
        }
        | overrides
    )


def store(client):
    return MemoryStore(
        user_id="clara",
        collection="sentinel_memories",
        pg_host="localhost",
        pg_port=5432,
        pg_database="unused",
        pg_user="unused",
        pg_password="",
        embed_base_url="http://embed/v1",
        embed_model="BAAI/bge-m3",
        embed_dims=3,
        session=client,
    )


@pytest.mark.asyncio
async def test_store_and_settings_use_the_same_bge_defaults():
    settings = MagicMock()
    settings.get = AsyncMock(side_effect=lambda key, default=None: default)
    memory = await make_memory_store(settings)
    try:
        assert memory.embed_model == DEFAULTS["ai_embed_model"] == "BAAI/bge-m3"
        assert memory.embed_dims == DEFAULTS["ai_embed_dims"] == 1024
        assert memory.collection == DEFAULTS["ai_memory_collection"] == "sentinel_memories"
        assert memory.dedup_threshold == 0.96
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_batch_embeddings_follow_response_indices():
    def respond(request):
        body = json.loads(request.content)
        assert body == {"model": "BAAI/bge-m3", "dimensions": 3, "input": ["first", "second"]}
        return httpx.Response(
            200, json={"data": [{"index": 1, "embedding": [0, 1, 0]}, {"index": 0, "embedding": [1, 0, 0]}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        assert await store(client).embed_many(["first", "second"]) == [[1, 0, 0], [0, 1, 0]]


@pytest.mark.asyncio
@pytest.mark.parametrize("row", [{"index": 1, "embedding": [1, 0, 0]}, {"index": 0, "embedding": [1, 0]}])
async def test_batch_rejects_invalid_indices_and_dimensions(row):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"data": [row]}))
    ) as client:
        with pytest.raises(MemoryStoreError):
            await store(client).embed_many(["memory"])


@pytest.mark.asyncio
async def test_capacity_failure_splits_batch_without_dropping_inputs():
    calls = []

    def respond(request):
        texts = json.loads(request.content)["input"]
        calls.append(texts)
        if isinstance(texts, list):
            return httpx.Response(400, text="input exceeds context size")
        return httpx.Response(200, json={"data": [{"embedding": [1, 0, 0] if texts == "first" else [0, 1, 0]}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        assert await store(client).embed_many(["first", "second"]) == [[1, 0, 0], [0, 1, 0]]
    assert calls == [["first", "second"], "first", "second"]


@pytest.mark.asyncio
async def test_noncapacity_failure_is_not_retried():
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(503, text="unavailable")

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(MemoryStoreError, match="503"):
            await store(client).embed_many(["a", "b"])
    assert len(calls) == 1


@pytest.mark.parametrize(
    "overrides", [{"source": "sentinel_memories"}, {"target": "x;DROP TABLE x"}, {"dimensions": 0}, {"user_id": ""}]
)
def test_plan_refuses_in_place_or_invalid_migration(overrides):
    with pytest.raises(ValueError):
        plan(**overrides)


def test_batches_preserve_records_and_isolate_long_inputs():
    rows = [{"content": s} for s in ["a", "b", "long memory", "d"]]
    assert embedding_batches(rows, 2, 5) == [rows[:2], rows[2:3], rows[3:]]
    with pytest.raises(ValueError, match="no embeddable"):
        embedding_batches([{"content": " "}], 2, 10)


@pytest.mark.asyncio
async def test_existing_unmarked_destination_is_never_overwritten():
    connection = MagicMock()
    connection.fetchval = AsyncMock(side_effect=["sentinel_memories", None])
    connection.execute = AsyncMock()
    with pytest.raises(ValueError, match="different migration identity"):
        await prepare_collection(connection, plan())
    connection.execute.assert_not_called()


@pytest.mark.asyncio
async def test_destination_with_wrong_dimensions_cannot_resume():
    p = plan()
    connection = MagicMock()
    connection.fetchval = AsyncMock(side_effect=["sentinel_memories", p.marker, "vector(768)"])
    with pytest.raises(ValueError, match="dimensions"):
        await prepare_collection(connection, p)


@pytest.mark.asyncio
async def test_writes_preserve_payload_and_condition_on_unchanged_owner_scoped_source():
    connection = MagicMock()
    connection.executemany = AsyncMock()
    row = {"id": "original-id", "payload": '{"user_id":"clara","data":"original text","tags":["research"]}'}
    await save_vectors(connection, plan(), [row], [[1, 0, 0]])
    sql, values = connection.executemany.call_args.args
    assert 'INSERT INTO "sentinel_memories"' in sql
    assert 'SELECT 1 FROM "clara_memories"' in sql
    assert "s.payload=$3::jsonb AND s.payload->>'user_id'=$4" in sql
    assert values[0][0] == row["id"]
    assert values[0][2] == row["payload"]
    assert values[0][3] == "clara"
    assert not any(s in sql.upper() for s in ["DELETE ", 'UPDATE "CLARA_MEMORIES"', "ALTER TABLE"])


@pytest.mark.asyncio
@pytest.mark.parametrize("vectors", [[], [[0, 0, 0]], [[1, 0]], [[float("nan"), 0, 1]]])
async def test_invalid_vectors_are_rejected_before_publishing(vectors):
    connection = MagicMock()
    connection.executemany = AsyncMock()
    with pytest.raises(ValueError):
        await save_vectors(connection, plan(), [{"id": "id", "payload": "{}"}], vectors)
    connection.executemany.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["missing", "extra", "invalid"])
async def test_incomplete_or_cross_owner_destination_fails_verification(field):
    result = {"source_records": 2, "target_records": 2, "missing": 0, "extra": 0, "invalid": 0, field: 1}
    connection = MagicMock()
    connection.fetchrow = AsyncMock(return_value=result)
    with pytest.raises(ValueError, match="incomplete or changed"):
        await verify_collection(connection, plan())


@pytest.mark.asyncio
async def test_resume_only_embeds_pending_records(monkeypatch):
    import sentinel.database.memory_embeddings as migration

    row = {"id": "pending", "content": "new text", "payload": "{}"}
    monkeypatch.setattr(migration, "prepare_collection", AsyncMock())
    monkeypatch.setattr(migration, "pending_records", AsyncMock(return_value=[row]))
    saved = AsyncMock()
    monkeypatch.setattr(migration, "save_vectors", saved)
    expected = {"source_records": 12, "target_records": 12, "missing": 0, "extra": 0, "invalid": 0}
    monkeypatch.setattr(migration, "verify_collection", AsyncMock(return_value=expected))
    embed = AsyncMock(return_value=[[1, 0, 0]])
    assert await rebuild_collection(MagicMock(), plan(), embed) == expected
    embed.assert_awaited_once_with(["new text"])
    assert saved.call_args.args[2] == [row]
