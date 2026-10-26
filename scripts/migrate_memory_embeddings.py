"""Rebuild Sentinel's owner-scoped memories, then explicitly activate the verified collection.

Run with Sentinel's virtualenv from the repository root. The source table is never
altered. Stop Sentinel's writers before --activate; a normal rebuild can run online.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg  # noqa: E402

from sentinel.ai.memory import make_memory_store  # noqa: E402
from sentinel.ai.memory_config import (  # noqa: E402
    DEFAULT_EMBED_BASE_URL,
    DEFAULT_EMBED_DIMS,
    DEFAULT_EMBED_MODEL,
    DEFAULT_MEMORY_COLLECTION,
)
from sentinel.database import Database  # noqa: E402
from sentinel.database.memory_embeddings import MemoryEmbeddingMigration, rebuild_collection  # noqa: E402
from sentinel.settings import Settings  # noqa: E402


async def migrate(args: argparse.Namespace) -> None:
    db = await Database().connect()
    settings = Settings()
    source_store = await make_memory_store(settings)
    target_store = None
    connection = None
    try:
        plan = MemoryEmbeddingMigration(
            source=args.source_collection,
            target=args.target_collection,
            user_id=source_store.user_id,
            model=DEFAULT_EMBED_MODEL,
            dimensions=DEFAULT_EMBED_DIMS,
        )
        # Do not edit live settings to obtain a client for the staged target.
        from dataclasses import replace

        target_store = replace(
            source_store,
            collection=plan.target,
            embed_model=plan.model,
            embed_dims=plan.dimensions,
            embed_base_url=args.embedding_base,
        )
        await target_store.embed_many(["BGE-M3 migration readiness check."])
        connection = await asyncpg.connect(
            host=source_store.pg_host,
            port=source_store.pg_port,
            database=source_store.pg_database,
            user=source_store.pg_user,
            password=source_store.pg_password,
            timeout=15,
            server_settings={"application_name": "sentinel-memory-embedding-migration"},
        )
        # Prevent two operators from populating the same destination simultaneously.
        locked = await connection.fetchval("SELECT pg_try_advisory_lock(hashtext($1))", plan.target)
        if not locked:
            raise ValueError("Another migration is rebuilding this destination")
        print(
            json.dumps({"source": plan.source, "target": plan.target, "owner": plan.user_id, "model": plan.model}),
            flush=True,
        )
        result = await rebuild_collection(
            connection,
            plan,
            target_store.embed_many,
            progress=lambda status: print(json.dumps(status), flush=True),
        )
        if args.activate:
            current = await settings.get("ai_memory_collection")
            if current not in (plan.source, plan.target):
                raise ValueError("Configured memory collection changed; refusing activation")
            await db.set_settings_batch(
                {
                    "ai_embed_base_url": args.embedding_base,
                    "ai_embed_model": plan.model,
                    "ai_embed_dims": plan.dimensions,
                    "ai_memory_collection": plan.target,
                }
            )
        print(json.dumps({"verified": result, "activated": args.activate}), flush=True)
    finally:
        if connection is not None:
            await connection.close()
        if target_store is not None:
            await target_store.close()
        await source_store.close()
        await db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-collection", required=True)
    parser.add_argument("--target-collection", default=DEFAULT_MEMORY_COLLECTION)
    parser.add_argument("--embedding-base", default=DEFAULT_EMBED_BASE_URL)
    parser.add_argument(
        "--activate", action="store_true", help="Update settings atomically after verification; stop writers first"
    )
    try:
        asyncio.run(migrate(parser.parse_args()))
    except Exception as exc:  # noqa: BLE001
        # Database exception messages can contain connection details or input text.
        print(
            f"Memory embedding migration failed ({type(exc).__name__}); settings were not activated.", file=sys.stderr
        )
        raise SystemExit(1) from None
