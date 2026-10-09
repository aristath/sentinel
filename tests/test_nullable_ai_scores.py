"""Missing ratings remain missing, including upgrades from legacy defaults."""

import sqlite3

import pytest

from sentinel.database import Database
from sentinel.database.main import SCHEMA
from sentinel.planner.preferences import is_explicit_downgrade, preference_snapshot


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy_default", ["1.0", "0.5"])
async def test_legacy_defaults_removed_without_losing_ratings_or_history(tmp_path, legacy_default):
    path = str(tmp_path / "legacy.db")
    with sqlite3.connect(path) as conn:
        conn.executescript(
            SCHEMA.replace(
                "ai_research_multiplier REAL,", f"ai_research_multiplier REAL DEFAULT {legacy_default},"
            ).replace(
                "ai_research_multiplier_source TEXT,",
                "ai_research_multiplier_source TEXT NOT NULL DEFAULT 'migration',",
            )
        )
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("INSERT INTO securities(symbol) VALUES ('UNRATED')")
        conn.execute(
            "INSERT INTO securities(symbol, ai_research_multiplier_updated_at) VALUES ('OLD_UNRATED', '2026-10-05')"
        )
        conn.executemany(
            """INSERT INTO securities(symbol, ai_research_multiplier, ai_research_multiplier_source,
               ai_research_multiplier_analysis, ai_research_multiplier_updated_at) VALUES (?, ?, ?, ?, ?)""",
            [
                ("MAX", 1.0, "ai_research", "Valid maximum", "2026-10-01"),
                ("ZERO", 0.0, "manual", "Avoid", "2026-10-01"),
                ("NEUTRAL", 0.5, "ai_research", "Neutral", "2026-10-01"),
                ("LEGACY_ANALYSIS", 1.0, "migration", "Retain recorded rationale", None),
            ],
        )
        conn.execute("INSERT INTO positions(symbol, quantity) VALUES ('UNRATED', 4)")
        conn.execute("INSERT INTO prices(symbol, date, close) VALUES ('UNRATED', '2026-10-01', 20)")
        conn.execute("CREATE INDEX custom_score_index ON securities(ai_research_multiplier)")
        conn.execute("INSERT INTO cache(key, value) VALUES ('planner:allocation_snapshot:v2', 'stale')")
        conn.execute("INSERT INTO cache(key, value) VALUES ('keep', 'unrelated')")
        before_rowids = conn.execute("SELECT rowid, symbol FROM securities ORDER BY rowid").fetchall()

    db = Database(path)
    try:
        await db.connect()
        cursor = await db.conn.execute("PRAGMA table_info(securities)")
        columns = {r["name"]: r for r in await cursor.fetchall()}
        assert columns["ai_research_multiplier"]["dflt_value"] is None
        assert columns["ai_research_multiplier_source"]["dflt_value"] is None
        assert not columns["ai_research_multiplier_source"]["notnull"]
        for symbol in ("UNRATED", "OLD_UNRATED"):
            row = await db.get_security(symbol)
            assert all(row[key] is None for key in row if key.startswith("ai_research_multiplier"))
        for symbol, expected in (("MAX", 1.0), ("ZERO", 0.0), ("NEUTRAL", 0.5), ("LEGACY_ANALYSIS", 1.0)):
            assert (await db.get_security(symbol))["ai_research_multiplier"] == expected
        assert (await db.get_position("UNRATED"))["quantity"] == 4
        assert (await db.get_prices("UNRATED", days=10000))[0]["close"] == 20
        cursor = await db.conn.execute("SELECT rowid, symbol FROM securities ORDER BY rowid")
        assert [tuple(r) for r in await cursor.fetchall()] == before_rowids
        cursor = await db.conn.execute("PRAGMA index_info(custom_score_index)")
        assert (await cursor.fetchone())["name"] == "ai_research_multiplier"
        assert await db.cache_get("planner:allocation_snapshot:v2") is None
        assert await db.cache_get("keep") == "unrelated"
        await db.upsert_security("NEW")
        await db.close()
        await db.connect()
        assert (await db.get_security("NEW"))["ai_research_multiplier"] is None
        assert (await db.get_security("MAX"))["ai_research_multiplier"] == 1.0
        cursor = await db.conn.execute("PRAGMA foreign_key_check")
        assert await cursor.fetchall() == []
    finally:
        await db.close()
        db.remove_from_cache()


@pytest.mark.parametrize(
    "security",
    [
        {},
        {"ai_research_multiplier": None},
        {"ai_research_multiplier": None, "ai_research_multiplier_updated_at": "2026-10-01"},
    ],
)
def test_missing_rating_is_not_a_score_or_a_downgrade(security):
    snapshot = preference_snapshot(security)
    assert snapshot["ai_research_multiplier"] is None
    assert snapshot["ai_research_multiplier_age_weeks"] is None
    assert not is_explicit_downgrade(security)
