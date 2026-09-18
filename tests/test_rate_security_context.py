import json
import os
import subprocess
import sys
from pathlib import Path

from sentinel.tasks import definitions


def test_rating_context_needs_only_the_security_universe(tmp_path):
    home = tmp_path / "home"
    data_dir = home / ".sentinel"
    universe_dir = data_dir / "tasks" / "artifacts" / "refresh-securities-universe"
    universe_dir.mkdir(parents=True)
    (universe_dir / "securities-universe.json").write_text(
        json.dumps(
            [
                {
                    "symbol": "TEST",
                    "name": "Test Security",
                    "geography": "US",
                    "industry": "Broker Classification",
                }
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    script = definitions.CORE_TASKS_DIR / "rate-security" / "resolve-rating-context.py"
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
    context = json.loads(result.stdout)
    assert context["symbol"] == "TEST"
    assert context["name"] == "Test Security"
    assert "buckets" not in context
    assert "geography" not in context
    assert "industry" not in context
    assert "securityPath" not in context
    assert Path(context["workRoot"]).is_dir()


def test_rating_evidence_pack_uses_only_memories(tmp_path):
    work_root = tmp_path / "rate-security" / "TEST"
    context = {
        "symbol": "TEST",
        "name": "Test Security",
        "workRoot": str(work_root),
        "evidencePackPath": str(work_root / "evidence-pack.md"),
    }
    script = definitions.CORE_TASKS_DIR / "rate-security" / "compose-evidence-pack.py"
    result = subprocess.run(  # noqa: S603 - fixed executable and repository-owned script
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        env=os.environ
        | {
            "CONTEXT_JSON": json.dumps(context),
            "SENTINEL_BASE_URL": "http://127.0.0.1:9",
        },
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    pack = Path(context["evidencePackPath"]).read_text(encoding="utf-8")
    assert "## Research Memory (last 6 months)" in pack
    assert "Current Security Research" not in pack
    assert "security-research file missing" not in pack
    output = json.loads(result.stdout)
    assert "securityFileAgeDays" not in output
