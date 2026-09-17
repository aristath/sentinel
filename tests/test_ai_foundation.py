"""Tests for the file-backed AI research pipeline administration API."""

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import HTTPException

from sentinel.ai import universe
from sentinel.api.routers import ai as ai_router
from sentinel.api.routers.ai import (
    _run_identity,
    create_ai_prompt,
    create_ai_request,
    get_ai_artifact,
    get_ai_models,
    get_ai_units,
)
from sentinel.database import Database


@pytest_asyncio.fixture
async def temp_db(tmp_path):
    db = Database(str(tmp_path / "sentinel.db"))
    await db.connect()
    yield db
    await db.close()
    db.remove_from_cache()


@pytest.fixture
def artifact_root(tmp_path, monkeypatch):
    root = tmp_path / ".sentinel" / "tasks" / "artifacts"
    monkeypatch.setattr(universe, "TASK_ARTIFACTS_DIR", root)
    monkeypatch.setattr(ai_router, "TASK_ARTIFACTS_DIR", root)
    return root


def _write_array(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


@pytest.mark.asyncio
async def test_schema_does_not_create_ai_projection_tables(temp_db):
    cursor = await temp_db.conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
    tables = {row["name"] for row in await cursor.fetchall()}
    assert "ai_units" not in tables
    assert "ai_requests" not in tables


@pytest.mark.asyncio
async def test_migration_removes_legacy_ai_units_table(temp_db):
    await temp_db.conn.execute(
        """CREATE TABLE ai_units (
            kind TEXT NOT NULL,
            key TEXT NOT NULL,
            label TEXT NOT NULL,
            last_analyzed_at TEXT,
            artifacts TEXT,
            PRIMARY KEY (kind, key)
        )"""
    )
    await temp_db.conn.commit()

    await temp_db._migrate_schema()

    cursor = await temp_db.conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'ai_units'")
    assert await cursor.fetchone() is None


def test_units_come_from_clara_style_rosters_and_artifacts(artifact_root):
    _write_array(
        artifact_root / "refresh-securities-universe" / "securities-universe.json",
        [
            {"symbol": "AAA", "name": "Alpha Corp"},
            {"symbol": "BBB", "name": ""},
            {"name": "Missing Symbol"},
        ],
    )
    _write_array(
        artifact_root / "refresh-macro-buckets" / "macro-buckets.json",
        [
            {
                "bucket": "United States + Semiconductors",
                "country_code": "US",
                "industry": "Semiconductors",
            }
        ],
    )
    security_dir = artifact_root / "analyze-security"
    security_dir.mkdir(parents=True)
    (security_dir / "AAA.md").write_text("report\n", encoding="utf-8")
    (security_dir / "AAA.summary.md").write_text("summary\n", encoding="utf-8")
    rating_dir = artifact_root / "rate-security" / "AAA"
    rating_dir.mkdir(parents=True)
    (rating_dir / "rating.json").write_text("{}\n", encoding="utf-8")
    macro_dir = artifact_root / "analyze-macro-bucket"
    macro_dir.mkdir(parents=True)
    (macro_dir / "United-States-Semiconductors.md").write_text("macro\n", encoding="utf-8")
    portfolio_dir = artifact_root / "rate-portfolio"
    portfolio_dir.mkdir(parents=True)
    (portfolio_dir / "latest.json").write_text("{}\n", encoding="utf-8")

    units = universe.load_research_units()
    by_id = {(unit["kind"], unit["key"]): unit for unit in units}

    assert set(by_id) == {
        ("macro", "us-semiconductors"),
        ("portfolio", "portfolio"),
        ("security", "AAA"),
        ("security", "BBB"),
    }
    assert by_id[("security", "BBB")]["label"] == "BBB"
    assert by_id[("security", "AAA")]["last_analyzed_at"] is not None
    assert by_id[("security", "AAA")]["artifacts"] == {
        "report.md": "analyze-security/AAA.md",
        "summary.md": "analyze-security/AAA.summary.md",
        "rating.json": "rate-security/AAA/rating.json",
    }
    assert by_id[("macro", "us-semiconductors")]["last_analyzed_at"] is not None
    assert by_id[("portfolio", "portfolio")]["last_analyzed_at"] is not None
    assert [unit["key"] for unit in universe.load_research_units("security")] == ["AAA", "BBB"]


def test_security_freshness_requires_the_canonical_summary(artifact_root):
    _write_array(
        artifact_root / "refresh-securities-universe" / "securities-universe.json",
        [{"symbol": "TEST", "name": "Test Security"}],
    )
    security_dir = artifact_root / "analyze-security"
    security_dir.mkdir(parents=True)
    profile = security_dir / "TEST.profile.json"
    profile.write_text("{}\n", encoding="utf-8")

    unit = universe.get_research_unit("security", "TEST")
    assert unit["artifacts"] == {"profile.json": "analyze-security/TEST.profile.json"}
    assert unit["last_analyzed_at"] is None

    (security_dir / "TEST.md").write_text("full report\n", encoding="utf-8")
    assert universe.get_research_unit("security", "TEST")["last_analyzed_at"] is None

    summary = security_dir / "TEST.summary.md"
    summary.write_text("complete\n", encoding="utf-8")
    assert universe.get_research_unit("security", "TEST")["last_analyzed_at"] is not None

    profile.unlink()
    (security_dir / "TEST.md").unlink()
    summary.unlink()
    unit = universe.get_research_unit("security", "TEST")
    assert unit["artifacts"] == {}
    assert unit["last_analyzed_at"] is None


def test_missing_rosters_leave_only_the_synthetic_portfolio_unit(artifact_root):
    assert universe.load_research_units() == [
        {
            "kind": "portfolio",
            "key": "portfolio",
            "label": "Portfolio",
            "last_analyzed_at": None,
            "artifacts": {},
        }
    ]


def test_malformed_roster_is_reported(artifact_root):
    path = artifact_root / "refresh-securities-universe" / "securities-universe.json"
    path.parent.mkdir(parents=True)
    path.write_text("{broken", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Unable to read the securities universe"):
        universe.load_research_units()


@pytest.mark.asyncio
async def test_units_endpoint_is_read_only():
    settings = SimpleNamespace(get=AsyncMock(return_value=7))

    class NoDatabaseAccess:
        def __getattr__(self, name):
            raise AssertionError(f"unexpected database access: {name}")

    deps: Any = SimpleNamespace(settings=settings, db=NoDatabaseAccess())
    units = [
        {
            "kind": "security",
            "key": "AAA",
            "label": "Alpha",
            "last_analyzed_at": None,
            "artifacts": {},
        }
    ]
    with (
        patch("sentinel.api.routers.ai.load_research_units", return_value=units),
        patch("sentinel.api.routers.ai._pipeline_runs", new=AsyncMock(return_value=[])),
    ):
        result = await get_ai_units(deps, kind=None, stale_only=False)

    assert result["units"][0]["key"] == "AAA"
    assert result["units"][0]["stale"] is True


@pytest.mark.asyncio
async def test_manual_macro_request_enqueues_exact_bucket_name():
    unit = {
        "kind": "macro",
        "key": "us-semiconductors",
        "label": "United States + Semiconductors",
        "last_analyzed_at": None,
        "artifacts": {},
    }
    queued = {"id": "run-1"}
    with (
        patch("sentinel.api.routers.ai.get_research_unit", return_value=unit),
        patch("sentinel.api.routers.ai.enqueue_task", new=AsyncMock(return_value=queued)) as enqueue,
    ):
        result = await create_ai_request(
            {"kind": "analyze", "unit_kind": "macro", "unit_key": "us-semiconductors"},
            SimpleNamespace(),
        )

    enqueue.assert_awaited_once_with(
        "analyze-macro-bucket",
        {"bucket": "United States + Semiconductors"},
    )
    assert result == {"status": "queued", "request_id": "run-1"}


@pytest.mark.asyncio
async def test_artifact_endpoint_reads_the_canonical_file(artifact_root):
    _write_array(
        artifact_root / "refresh-securities-universe" / "securities-universe.json",
        [{"symbol": "AAA", "name": "Alpha Corp"}],
    )
    summary = artifact_root / "analyze-security" / "AAA.summary.md"
    summary.parent.mkdir(parents=True)
    summary.write_text("canonical summary\n", encoding="utf-8")

    result = await get_ai_artifact("security", "AAA", "summary.md", SimpleNamespace())

    assert result["name"] == "summary.md"
    assert result["content"] == "canonical summary\n"


class TestRunnerIntegration:
    def test_default_jobs_keep_15m_timeout(self):
        from sentinel.jobs import runner

        assert runner.job_timeout("sync:prices") == runner.JOB_TIMEOUT == 15 * 60


def test_pipeline_run_identity_uses_security_and_macro_units():
    units = [
        {"kind": "security", "key": "AAA", "label": "Alpha"},
        {"kind": "macro", "key": "us-tech", "label": "US + Technology"},
    ]

    security = _run_identity(
        {"taskId": "analyze-security", "taskName": "Analyze Security", "inputs": {"symbol": "AAA"}},
        units,
    )
    macro = _run_identity(
        {
            "taskId": "analyze-macro-bucket",
            "taskName": "Analyze Macro Bucket",
            "inputs": {"bucket": "US + Technology"},
        },
        units,
    )

    assert security == {"unit_kind": "security", "unit_key": "AAA", "unit_label": "Alpha"}
    assert macro == {"unit_kind": "macro", "unit_key": "us-tech", "unit_label": "US + Technology"}


@pytest.mark.asyncio
async def test_model_discovery_endpoint_uses_settings_and_survives_offline_llm():
    values = {"ai_llm_base_url": "http://llm/v1", "ai_llm_api_key": "test-key"}
    settings = SimpleNamespace(get=AsyncMock(side_effect=lambda key, default: values.get(key, default)))
    deps: Any = SimpleNamespace(settings=settings)

    with patch("sentinel.api.routers.ai.discover_models", new=AsyncMock(return_value=["model-b", "model-a"])):
        assert await get_ai_models(deps) == {"ok": True, "models": ["model-b", "model-a"]}

    with patch("sentinel.api.routers.ai.discover_models", new=AsyncMock(side_effect=RuntimeError("offline"))):
        assert await get_ai_models(deps) == {"ok": False, "models": [], "error": "offline"}


@pytest.mark.asyncio
async def test_direct_prompt_inherits_system_prompt_and_omits_temperature():
    client = SimpleNamespace(
        ai_data_dir=None,
        chat=AsyncMock(return_value=SimpleNamespace(content="Answer")),
        close=AsyncMock(),
    )
    deps = SimpleNamespace(settings=SimpleNamespace())
    with patch("sentinel.api.routers.ai.LLMClient.from_settings", new=AsyncMock(return_value=client)):
        result = await create_ai_prompt({"prompt": "Question"}, deps)

    assert result == {"output": "Answer"}
    _, kwargs = client.chat.await_args
    assert kwargs["temperature"] is None
    assert "Today's date and time is" in kwargs["system"]
    assert "Current task: ai-prompt." in kwargs["system"]
    client.close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_direct_prompt_forwards_temperature_without_system_override():
    client = SimpleNamespace(
        ai_data_dir=None,
        chat=AsyncMock(return_value=SimpleNamespace(content="Answer")),
        close=AsyncMock(),
    )
    deps = SimpleNamespace(settings=SimpleNamespace())
    with patch("sentinel.api.routers.ai.LLMClient.from_settings", new=AsyncMock(return_value=client)):
        await create_ai_prompt({"prompt": "Question", "temperature": 0.25}, deps)

    _, kwargs = client.chat.await_args
    assert kwargs["temperature"] == 0.25
    assert set(kwargs) == {"system", "temperature"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {},
        {"prompt": ""},
        {"prompt": "Question", "temperature": True},
        {"prompt": "Question", "temperature": float("inf")},
    ],
)
async def test_direct_prompt_rejects_invalid_input_before_opening_client(body):
    deps = SimpleNamespace(settings=SimpleNamespace())
    with (
        patch("sentinel.api.routers.ai.LLMClient.from_settings", new=AsyncMock()) as create_client,
        pytest.raises(HTTPException) as exc_info,
    ):
        await create_ai_prompt(body, deps)

    assert exc_info.value.status_code == 400
    create_client.assert_not_awaited()
