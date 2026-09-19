"""Tests for the file-backed AI research pipeline administration API."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import HTTPException

from sentinel.ai import universe
from sentinel.api.routers import ai as ai_router
from sentinel.api.routers.ai import (
    _run_display_status,
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
    security_dir = artifact_root / "analyze-security"
    security_dir.mkdir(parents=True)
    (security_dir / "AAA.md").write_text("report\n", encoding="utf-8")
    (security_dir / "AAA.summary.md").write_text("summary\n", encoding="utf-8")
    (security_dir / "AAA.context.md").write_text("context\n", encoding="utf-8")
    rating_dir = artifact_root / "rate-security" / "AAA"
    rating_dir.mkdir(parents=True)
    (rating_dir / "rating.json").write_text("{}\n", encoding="utf-8")
    portfolio_dir = artifact_root / "rate-portfolio"
    portfolio_dir.mkdir(parents=True)
    (portfolio_dir / "latest.json").write_text("{}\n", encoding="utf-8")

    units = universe.load_research_units()
    by_id = {(unit["kind"], unit["key"]): unit for unit in units}

    assert set(by_id) == {
        ("portfolio", "portfolio"),
        ("security", "AAA"),
        ("security", "BBB"),
    }
    assert by_id[("security", "BBB")]["label"] == "BBB"
    assert by_id[("security", "AAA")]["last_analyzed_at"] is not None
    assert by_id[("security", "AAA")]["artifacts"] == {
        "report.md": "analyze-security/AAA.md",
        "summary.md": "analyze-security/AAA.summary.md",
        "context.md": "analyze-security/AAA.context.md",
        "rating.json": "rate-security/AAA/rating.json",
    }
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
    summary.write_text("\n", encoding="utf-8")
    assert universe.get_research_unit("security", "TEST")["last_analyzed_at"] is None

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
async def test_manual_request_rejects_removed_macro_units():
    with pytest.raises(HTTPException) as exc_info:
        await create_ai_request(
            {"kind": "analyze", "unit_kind": "macro", "unit_key": "us-semiconductors"},
            SimpleNamespace(),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "unit_kind must be 'security'"


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


def test_pipeline_run_identity_uses_security_units():
    units = [{"kind": "security", "key": "AAA", "label": "Alpha"}]

    security = _run_identity(
        {"taskId": "analyze-security", "taskName": "Analyze Security", "inputs": {"symbol": "AAA"}},
        units,
    )
    assert security == {"unit_kind": "security", "unit_key": "AAA", "unit_label": "Alpha"}


@pytest.mark.parametrize(
    ("last_analyzed_at", "expected"),
    [
        (None, "stale"),
        ("2026-01-01T00:00:00+00:00", "stale"),
        ("2026-09-19T00:00:00+00:00", "completed"),
    ],
)
def test_completed_security_run_display_depends_on_current_summary(last_analyzed_at, expected):
    run = {"taskId": "analyze-security", "status": "done"}
    identity = {"unit_kind": "security", "unit_key": "AAA", "unit_label": "Alpha"}
    units = [
        {
            "kind": "security",
            "key": "AAA",
            "label": "Alpha",
            "last_analyzed_at": last_analyzed_at,
            "artifacts": {},
        }
    ]

    assert (
        _run_display_status(
            run,
            identity,
            units,
            now=datetime(2026, 9, 19, 12, tzinfo=timezone.utc),
            security_days=7,
        )
        == expected
    )


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
        searxng_base_url="http://search",
        url_summarizer_base_url="http://summarizer",
        browser_search_base_url="http://browser-search",
        chat=AsyncMock(return_value=SimpleNamespace(content="Answer", last_tool_result="")),
        close=AsyncMock(),
    )
    executors = SimpleNamespace(aclose=AsyncMock())
    deps = SimpleNamespace(settings=SimpleNamespace())
    with (
        patch("sentinel.api.routers.ai.LLMClient.from_settings", new=AsyncMock(return_value=client)),
        patch("sentinel.api.routers.ai.ai_tools.make_tool_executors", return_value=executors) as make_executors,
    ):
        result = await create_ai_prompt({"prompt": "Question"}, deps)

    assert result == {"output": "Answer"}
    _, kwargs = client.chat.await_args
    assert kwargs["temperature"] is None
    assert "Today's date and time is" in kwargs["system"]
    assert "Current task: ai-prompt." in kwargs["system"]
    assert kwargs["tools"] is ai_router.ai_tools.TOOL_DEFINITIONS
    assert kwargs["executors"] is executors
    assert kwargs["work_root"] == ai_router.SENTINEL_HOME
    make_executors.assert_called_once_with(
        "http://search",
        "http://summarizer",
        ai_router.SENTINEL_HOME,
        "http://browser-search",
    )
    executors.aclose.assert_awaited_once_with()
    client.close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_direct_prompt_forwards_temperature_without_system_override():
    client = SimpleNamespace(
        ai_data_dir=None,
        searxng_base_url="http://search",
        url_summarizer_base_url="http://summarizer",
        browser_search_base_url="http://browser-search",
        chat=AsyncMock(return_value=SimpleNamespace(content="Answer", last_tool_result="")),
        close=AsyncMock(),
    )
    executors = SimpleNamespace(aclose=AsyncMock())
    deps = SimpleNamespace(settings=SimpleNamespace())
    with (
        patch("sentinel.api.routers.ai.LLMClient.from_settings", new=AsyncMock(return_value=client)),
        patch("sentinel.api.routers.ai.ai_tools.make_tool_executors", return_value=executors),
    ):
        await create_ai_prompt({"prompt": "Question", "temperature": 0.25}, deps)

    _, kwargs = client.chat.await_args
    assert kwargs["temperature"] == 0.25
    assert set(kwargs) == {"system", "tools", "executors", "work_root", "temperature"}


@pytest.mark.asyncio
async def test_direct_prompt_returns_last_tool_result_and_closes_resources_on_empty_final_content():
    client = SimpleNamespace(
        ai_data_dir=None,
        searxng_base_url="http://search",
        url_summarizer_base_url="http://summarizer",
        browser_search_base_url="http://browser-search",
        chat=AsyncMock(return_value=SimpleNamespace(content="", last_tool_result="Search evidence")),
        close=AsyncMock(),
    )
    executors = SimpleNamespace(aclose=AsyncMock())
    deps = SimpleNamespace(settings=SimpleNamespace())
    with (
        patch("sentinel.api.routers.ai.LLMClient.from_settings", new=AsyncMock(return_value=client)),
        patch("sentinel.api.routers.ai.ai_tools.make_tool_executors", return_value=executors),
    ):
        result = await create_ai_prompt({"prompt": "Research this"}, deps)

    assert result == {"output": "Search evidence"}
    executors.aclose.assert_awaited_once_with()
    client.close.assert_awaited_once_with()


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
