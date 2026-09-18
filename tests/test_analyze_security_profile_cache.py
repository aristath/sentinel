import json
import os
import subprocess
import sys
import time
from pathlib import Path

from sentinel.tasks import definitions

PROFILE_MAX_AGE_SECONDS = 30 * 24 * 60 * 60


def _profile_sidecar(profile: str = "Test profile [1].") -> dict:
    return {
        "version": 1,
        "symbol": "TEST",
        "name": "Test Security",
        "profile": profile,
        "sources": [{"index": 1, "title": "Primary source", "url": "https://example.com/profile"}],
        "source": "fresh-profile-run",
        "createdAt": int(time.time()),
    }


def _report(profile: str = "Report profile [1].") -> str:
    return (
        "# Test Security\n\n"
        "## Profile\n\n"
        f"{profile}\n\n"
        "## Sources\n\n"
        "[1] https://example.com/profile — Primary source\n"
    )


def _run_resolver(tmp_path: Path) -> tuple[dict, Path]:
    home = tmp_path / "home"
    data_dir = home / ".sentinel"
    universe_dir = data_dir / "tasks" / "artifacts" / "refresh-securities-universe"
    universe_dir.mkdir(parents=True, exist_ok=True)
    (universe_dir / "securities-universe.json").write_text(
        json.dumps([{"symbol": "TEST", "name": "Test Security"}]) + "\n",
        encoding="utf-8",
    )
    script = definitions.CORE_TASKS_DIR / "analyze-security" / "resolve-security.py"
    result = subprocess.run(  # noqa: S603 - fixed executable and repository-owned script
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        env=os.environ
        | {
            "HOME": str(home),
            "SENTINEL_TASKS_HOME": str(data_dir),
            "SYMBOL": "TEST",
        },
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)[0], data_dir / "tasks" / "artifacts" / "analyze-security"


def _set_age(path: Path, age_seconds: float) -> float:
    mtime = time.time() - age_seconds
    os.utime(path, (mtime, mtime))
    return mtime


def test_profile_discovery_query_uses_ten_year_strategy():
    task = (definitions.CORE_TASKS_DIR / "analyze-security" / "task.js").read_text(encoding="utf-8")

    assert 'query: `strategy of "${item.name}" for the next 10 years`' in task


def test_external_context_search_is_bounded_and_uses_fixed_month():
    task = (definitions.CORE_TASKS_DIR / "analyze-security" / "task.js").read_text(encoding="utf-8")

    assert 'time_range: "month"' in task
    assert "num_results: 5" in task
    assert 'prompt("generate-context-queries.md"' in task
    assert "useTools: false" in task


def test_fresh_profile_sidecar_is_reused(tmp_path):
    task_root = tmp_path / "home" / ".sentinel" / "tasks" / "artifacts" / "analyze-security"
    task_root.mkdir(parents=True)
    sidecar = task_root / "TEST.profile.json"
    sidecar.write_text(json.dumps(_profile_sidecar()) + "\n", encoding="utf-8")
    _set_age(sidecar, PROFILE_MAX_AGE_SECONDS - 3600)

    item, _ = _run_resolver(tmp_path)

    assert item["profileCacheHit"] is True
    assert item["profileCacheSource"] == "sidecar"
    assert (Path(item["workRoot"]) / "profile.md").read_text(encoding="utf-8") == "Test profile [1].\n"
    context_root = Path(item["contextRoot"])
    assert context_root == Path(item["workRoot"]) / "external-context"
    assert (context_root / "query-source-summaries").is_dir()
    assert (context_root / "query-source-index").is_dir()
    assert (context_root / "query-findings").is_dir()
    assert item["contextReportPath"].endswith("/TEST.context.md")


def test_external_context_query_validator_enforces_bounds(tmp_path):
    script = definitions.CORE_TASKS_DIR / "analyze-security" / "validate-context-queries.py"

    valid = subprocess.run(  # noqa: S603 - fixed executable and repository-owned script
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        env=os.environ | {"QUERIES_JSON": json.dumps(["one", "two", "three"])},
        timeout=15,
        check=False,
    )
    assert valid.returncode == 0, valid.stderr
    assert json.loads(valid.stdout) == ["one", "two", "three"]

    invalid = subprocess.run(  # noqa: S603 - fixed executable and repository-owned script
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        env=os.environ | {"QUERIES_JSON": json.dumps(["one", "two"])},
        timeout=15,
        check=False,
    )
    assert invalid.returncode != 0
    assert "3-5" in invalid.stderr


def test_query_source_loader_rejects_zero_fetched_sources(tmp_path):
    script = definitions.CORE_TASKS_DIR / "analyze-security" / "load-query-source-summaries.py"
    summaries = tmp_path / "summaries.md"
    summaries.write_text("", encoding="utf-8")

    result = subprocess.run(  # noqa: S603 - fixed executable and repository-owned script
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        env=os.environ | {"SOURCE_SUMMARIES_PATH": str(summaries)},
        timeout=15,
        check=False,
    )

    assert result.returncode != 0
    assert "No usable source summaries were fetched" in result.stderr


def test_query_source_loader_returns_fetched_summaries_without_citation_validation(tmp_path):
    script = definitions.CORE_TASKS_DIR / "analyze-security" / "load-query-source-summaries.py"
    summaries = tmp_path / "summaries.md"
    summaries.write_text("A usable source summary without citation markup.\n", encoding="utf-8")

    result = subprocess.run(  # noqa: S603 - fixed executable and repository-owned script
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        env=os.environ | {"SOURCE_SUMMARIES_PATH": str(summaries)},
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "A usable source summary without citation markup.\n\n"


def test_security_report_contains_per_security_context_without_broker_classification(tmp_path):
    work_root = tmp_path / "work"
    work_root.mkdir()
    report_path = tmp_path / "TEST.md"
    item = {
        "symbol": "TEST",
        "name": "Test Security",
        "industry": "Broker Industry",
        "geography": "US",
        "workRoot": str(work_root),
        "reportPath": str(report_path),
    }
    script = definitions.CORE_TASKS_DIR / "analyze-security" / "finalize-security-report.py"
    result = subprocess.run(  # noqa: S603 - fixed executable and repository-owned script
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        env=os.environ
        | {
            "ITEM_JSON": json.dumps(item),
            "PROFILE": "Source-backed profile.",
            "DISTILL_OUTPUT": "- Security finding https://example.com/security",
            "CONTEXT_OUTPUT": "Future context https://example.com/context",
            "SENTINEL_BASE_URL": "http://127.0.0.1:9",
        },
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "Industry:" not in report
    assert "Geography:" not in report
    assert "## External Context" in report
    assert "Future context https://example.com/context" in report
    output = json.loads(result.stdout)
    assert output["findings"] == 1
    assert output["externalContextFindings"] == 1


def test_expired_profile_sidecar_is_not_resurrected_from_fresh_report(tmp_path):
    task_root = tmp_path / "home" / ".sentinel" / "tasks" / "artifacts" / "analyze-security"
    task_root.mkdir(parents=True)
    sidecar = task_root / "TEST.profile.json"
    sidecar.write_text(json.dumps(_profile_sidecar("Expired sidecar profile [1].")) + "\n", encoding="utf-8")
    _set_age(sidecar, PROFILE_MAX_AGE_SECONDS + 3600)
    (task_root / "TEST.md").write_text(_report("Fresh report copy of expired profile [1]."), encoding="utf-8")

    item, _ = _run_resolver(tmp_path)

    assert item["profileCacheHit"] is False
    assert item["profileCacheSource"] == ""
    assert not (Path(item["workRoot"]) / "profile.md").exists()


def test_expired_legacy_report_profile_is_not_reused(tmp_path):
    task_root = tmp_path / "home" / ".sentinel" / "tasks" / "artifacts" / "analyze-security"
    task_root.mkdir(parents=True)
    report = task_root / "TEST.md"
    report.write_text(_report(), encoding="utf-8")
    _set_age(report, PROFILE_MAX_AGE_SECONDS + 3600)

    item, _ = _run_resolver(tmp_path)

    assert item["profileCacheHit"] is False
    assert not (task_root / "TEST.profile.json").exists()


def test_fresh_legacy_report_profile_preserves_its_age_when_migrated(tmp_path):
    task_root = tmp_path / "home" / ".sentinel" / "tasks" / "artifacts" / "analyze-security"
    task_root.mkdir(parents=True)
    report = task_root / "TEST.md"
    report.write_text(_report(), encoding="utf-8")
    report_mtime = _set_age(report, PROFILE_MAX_AGE_SECONDS - 3600)

    item, _ = _run_resolver(tmp_path)

    sidecar = task_root / "TEST.profile.json"
    assert item["profileCacheHit"] is True
    assert item["profileCacheSource"] == "existing-artifacts"
    assert sidecar.stat().st_mtime == report_mtime
