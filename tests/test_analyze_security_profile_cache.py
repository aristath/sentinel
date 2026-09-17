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


def test_profile_discovery_query_is_security_agnostic():
    task = (definitions.CORE_TASKS_DIR / "analyze-security" / "task.js").read_text(encoding="utf-8")

    assert (
        'query: `What is "${item.name}" trying to become over the next decade, '
        "and through what fundamental mechanisms?`" in task
    )
    assert "company business model long-term strategy" not in task


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
