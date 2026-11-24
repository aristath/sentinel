#!/usr/bin/env python3
"""Validate local Markdown links and Sentinel API documentation coverage."""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_FILES = sorted(
    path for path in ROOT.rglob("*.md") if not {".git", ".venv", "node_modules"}.intersection(path.parts)
)
LINK_RE = re.compile(r"(?<!!)\[[^]]*]\(([^)]+)\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
API_HEADING_RE = re.compile(r"^#{1,6}\s+`?(GET|POST|PUT|PATCH|DELETE)\s+([^`\s]+)`?\s*$", re.MULTILINE)
PATH_CONVERTER_RE = re.compile(r"\{([^{}:]+):[^{}]+\}")
OPENAPI_METHODS = {"get", "post", "put", "patch", "delete", "trace"}


def github_anchor(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"[`*_~]", "", value)
    value = unicodedata.normalize("NFKD", value).lower().strip()
    value = re.sub(r"[^\w\- ]", "", value, flags=re.UNICODE)
    return re.sub(r"[ ]+", "-", value)


def split_target(raw: str) -> tuple[str, str]:
    target = raw.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    else:
        target = target.split(maxsplit=1)[0]
    path, marker, anchor = target.partition("#")
    return unquote(path), unquote(anchor) if marker else ""


def check_links() -> list[str]:
    failures: list[str] = []
    anchor_cache: dict[Path, set[str]] = {}
    for source in MARKDOWN_FILES:
        text = source.read_text(encoding="utf-8")
        prose = re.sub(r"^```.*?^```\s*$", "", text, flags=re.MULTILINE | re.DOTALL)
        for raw in LINK_RE.findall(prose):
            if raw.startswith(("http://", "https://", "mailto:", "data:", "#")):
                if not raw.startswith("#"):
                    continue
                path_text, anchor = "", raw[1:]
            else:
                path_text, anchor = split_target(raw)
            target = source if not path_text else (source.parent / path_text).resolve()
            try:
                target.relative_to(ROOT)
            except ValueError:
                failures.append(f"{source.relative_to(ROOT)}: link escapes repository: {raw}")
                continue
            if not target.exists():
                failures.append(f"{source.relative_to(ROOT)}: missing target: {raw}")
                continue
            if anchor and target.is_file() and target.suffix.lower() == ".md":
                anchors = anchor_cache.setdefault(
                    target,
                    {github_anchor(value) for value in HEADING_RE.findall(target.read_text(encoding="utf-8"))},
                )
                if anchor.lower() not in anchors:
                    failures.append(f"{source.relative_to(ROOT)}: missing anchor: {raw}")
    return failures


def documented_operations() -> set[tuple[str, str]]:
    operations: set[tuple[str, str]] = set()
    for path in sorted((ROOT / "docs" / "api").glob("*.md")):
        for method, route in API_HEADING_RE.findall(path.read_text(encoding="utf-8")):
            route_template = PATH_CONVERTER_RE.sub(r"{\1}", route)
            operations.add((method, route_template.rstrip("/")))
    return operations


def application_operations() -> set[tuple[str, str]]:
    from sentinel.app import app

    return {
        (method.upper(), path.rstrip("/"))
        for path, item in app.openapi()["paths"].items()
        if path.startswith("/api/")
        for method in OPENAPI_METHODS.intersection(item)
    }


def check_json_examples() -> list[str]:
    failures: list[str] = []
    skipped_parts = {"tradernet", "history", "plans", "clara"}
    fence_re = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)
    for path in MARKDOWN_FILES:
        if skipped_parts.intersection(path.parts):
            continue
        for index, match in enumerate(fence_re.finditer(path.read_text(encoding="utf-8")), start=1):
            try:
                json.loads(match.group(1))
            except json.JSONDecodeError as exc:
                failures.append(f"{path.relative_to(ROOT)}: invalid JSON example {index}: {exc.msg}")
    return failures


def main() -> int:
    failures = check_links() + check_json_examples()
    actual = application_operations()
    documented = documented_operations()
    for method, path in sorted(actual - documented):
        failures.append(f"undocumented API operation: {method} {path}")
    for method, path in sorted(documented - actual):
        failures.append(f"documented API operation does not exist: {method} {path}")

    from sentinel.jobs.runner import TASK_REGISTRY
    from sentinel.settings import DEFAULTS

    configuration = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")
    for key in DEFAULTS:
        if f"`{key}`" not in configuration:
            failures.append(f"undocumented setting: {key}")
    for relative in ("AGENTS.md", "docs/scheduler.md", "docs/api/jobs.md"):
        content = (ROOT / relative).read_text(encoding="utf-8")
        for job_type in TASK_REGISTRY:
            if f"`{job_type}`" not in content:
                failures.append(f"{relative}: undocumented fixed job: {job_type}")

    if failures:
        print("Documentation validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"Documentation validation passed: {len(MARKDOWN_FILES)} Markdown files, {len(actual)} API operations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
