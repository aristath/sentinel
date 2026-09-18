"""Read the Clara-style research universe and results from task artifacts."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sentinel.paths import TASK_ARTIFACTS_DIR


def _task_slug(value: str) -> str:
    """Match the filename slug used by the ported Clara task scripts."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value)).strip("-") or "item"


def _read_array(path: Path, description: str) -> list[dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to read {description} from {path}: {exc}") from exc
    if not isinstance(value, list):
        raise RuntimeError(f"{path} must contain a JSON array")
    return [item for item in value if isinstance(item, dict)]


def load_security_universe() -> list[dict[str, Any]]:
    """Read the security roster produced by refresh-securities-universe."""
    path = TASK_ARTIFACTS_DIR / "refresh-securities-universe" / "securities-universe.json"
    return _read_array(path, "the securities universe")


def _artifact_paths(kind: str, key: str, label: str) -> dict[str, Path]:
    if kind == "security":
        stem = _task_slug(key)
        return {
            "report.md": TASK_ARTIFACTS_DIR / "analyze-security" / f"{stem}.md",
            "summary.md": TASK_ARTIFACTS_DIR / "analyze-security" / f"{stem}.summary.md",
            "context.md": TASK_ARTIFACTS_DIR / "analyze-security" / f"{stem}.context.md",
            "profile.json": TASK_ARTIFACTS_DIR / "analyze-security" / f"{stem}.profile.json",
            "analysis.md": TASK_ARTIFACTS_DIR / "rate-security" / stem / "analysis.md",
            "rating.json": TASK_ARTIFACTS_DIR / "rate-security" / stem / "rating.json",
            "evidence-pack.md": TASK_ARTIFACTS_DIR / "rate-security" / stem / "evidence-pack.md",
        }
    if kind == "portfolio":
        return {
            "latest.json": TASK_ARTIFACTS_DIR / "rate-portfolio" / "latest.json",
            "ratings.json": TASK_ARTIFACTS_DIR / "rate-portfolio" / "ratings.json",
        }
    return {}


def _with_artifacts(kind: str, key: str, label: str) -> dict[str, Any]:
    existing = {name: path for name, path in _artifact_paths(kind, key, label).items() if path.is_file()}
    completion_name = {"security": "summary.md", "portfolio": "latest.json"}.get(kind)
    completion = existing.get(completion_name) if completion_name else None
    analyzed_at = None
    if completion is not None:
        analyzed_at = datetime.fromtimestamp(completion.stat().st_mtime, tz=timezone.utc).isoformat()
    return {
        "kind": kind,
        "key": key,
        "label": label,
        "last_analyzed_at": analyzed_at,
        "artifacts": {name: str(path.relative_to(TASK_ARTIFACTS_DIR)) for name, path in existing.items()},
    }


def load_research_units(kind: str | None = None) -> list[dict[str, Any]]:
    """Build the UI unit roster directly from Clara-compatible task files."""
    units: list[dict[str, Any]] = []

    for security in load_security_universe():
        symbol = str(security.get("symbol") or "").strip()
        if not symbol:
            continue
        label = str(security.get("name") or "").strip() or symbol
        units.append(_with_artifacts("security", symbol, label))

    units.append(_with_artifacts("portfolio", "portfolio", "Portfolio"))
    if kind is not None:
        units = [unit for unit in units if unit["kind"] == kind]
    return sorted(units, key=lambda unit: (unit["kind"], unit["key"]))


def get_research_unit(kind: str, key: str) -> dict[str, Any] | None:
    """Find one file-backed research unit by its public API identity."""
    return next((unit for unit in load_research_units(kind) if unit["key"] == key), None)
