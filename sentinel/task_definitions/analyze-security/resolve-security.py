"""Resolve the security (manual `symbol` input), seed any cached profile from prior
artifacts, recreate the per-symbol scratch dirs, and emit the selected security
augmented with all working paths as a single-element JSON array.
Environment: SYMBOL, SENTINEL_TASKS_HOME."""

import os
import json
import pathlib
import re
import shutil
import time

requested = str(os.environ.get("SYMBOL") or "").strip()
if not requested:
    raise SystemExit('Manual input "symbol" is required')

data_dir = os.environ.get("SENTINEL_TASKS_HOME")
if not data_dir:
    raise SystemExit("SENTINEL_TASKS_HOME is required")
artifacts = pathlib.Path(data_dir) / "tasks" / "artifacts"
universe_root = artifacts / "refresh-securities-universe"
task_root = artifacts / "analyze-security"
universe_path = universe_root / "securities-universe.json"
if not universe_path.exists():
    raise SystemExit("Missing securities-universe.json. Run refresh-securities-universe first.")


def slug(value):
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value)).strip("-") or "item"


universe = json.loads(universe_path.read_text(encoding="utf-8"))
if not isinstance(universe, list):
    raise SystemExit("securities-universe.json must contain a JSON array")

selected = None
for item in universe:
    if not isinstance(item, dict):
        continue
    symbol = str(item.get("symbol") or "").strip()
    if symbol.upper() == requested.upper():
        selected = dict(item)
        break
if selected is None:
    raise SystemExit(f'Security "{requested}" not found in securities-universe.json')

symbol = str(selected.get("symbol") or "").strip()
work_root = task_root / ".work" / slug(symbol)
report_path = task_root / f"{slug(symbol)}.md"
profile_sidecar_path = task_root / f"{slug(symbol)}.profile.json"
case_root = str(work_root)
home = pathlib.Path.home()
expected_prefix = str(home / ".sentinel" / "tasks" / "artifacts" / "analyze-security")
if not case_root.startswith(expected_prefix):
    raise SystemExit(f"Refusing to clean unexpected scratchpad path: {case_root}")

PROFILE_MAX_AGE_SECONDS = 30 * 24 * 60 * 60


def extract_section(text, heading):
    start = re.search(rf"^##\s+{re.escape(heading)}\s*$", text, re.M)
    if not start:
        return ""
    rest = text[start.end() :]
    end = re.search(r"^##\s+", rest, re.M)
    section = rest[: end.start()] if end else rest
    return section.strip()


def valid_profile(profile):
    profile = str(profile or "").strip()
    if not profile:
        return False
    lowered = profile.lower()
    bad_fragments = [
        "(no profile available)",
        "cannot write a factual profile",
        "does not mention",
        "does not provide any details",
        "no usable profile sources",
    ]
    return not any(fragment in lowered for fragment in bad_fragments)


def normalize_sources(raw):
    if not isinstance(raw, list):
        return []
    sources = []
    seen = set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        url = str(entry.get("url") or "").strip()
        title = str(entry.get("title") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        sources.append(
            {
                "index": len(sources) + 1,
                "title": title,
                "url": url,
            }
        )
    return sources


def sources_from_report(text):
    sources = {}
    for line in extract_section(text, "Sources").splitlines():
        match = re.match(r"^\[(\d+)\]\s+(\S+)(?:\s+—\s+(.*))?$", line.strip())
        if not match:
            continue
        sources[int(match.group(1))] = {
            "title": (match.group(3) or "").strip(),
            "url": match.group(2),
        }
    return sources


def profile_citation_numbers(profile):
    refs = set(int(value) for value in re.findall(r"\[Source\s+(\d+)\]", profile, re.I))
    refs.update(int(value) for value in re.findall(r"(?<!Source )\[(\d+)\]", profile))
    return sorted(refs)


def profile_artifact_is_fresh(path):
    try:
        age_seconds = time.time() - path.stat().st_mtime
    except OSError:
        return False
    return age_seconds <= PROFILE_MAX_AGE_SECONDS


def sidecar_profile(path):
    if not profile_artifact_is_fresh(path):
        return "", []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return "", []
    if not isinstance(raw, dict):
        return "", []
    profile = str(raw.get("profile") or "").strip()
    sources = normalize_sources(raw.get("sources"))
    if not valid_profile(profile) or not sources:
        return "", []
    return profile, sources


def seed_profile_from_existing_artifacts(report_path, old_profile_index_path):
    if not profile_artifact_is_fresh(report_path):
        return "", []
    text = report_path.read_text(encoding="utf-8")
    profile = extract_section(text, "Profile")
    if not valid_profile(profile):
        return "", []

    if old_profile_index_path.exists():
        try:
            # The scratch profile index is valid only if it belongs to the report
            # we are seeding from. A newer index can come from an interrupted run.
            if old_profile_index_path.stat().st_mtime <= report_path.stat().st_mtime + 1:
                sources = normalize_sources(json.loads(old_profile_index_path.read_text(encoding="utf-8")))
                if sources:
                    return profile, sources
        except Exception:
            pass

    report_sources = sources_from_report(text)
    cited = profile_citation_numbers(profile)
    if not cited:
        return "", []
    max_cited = max(cited)
    profile_sources = [report_sources[index] for index in range(1, max_cited + 1) if index in report_sources]
    sources = normalize_sources(profile_sources)
    if len(sources) == max_cited:
        return profile, sources
    return "", []


def write_profile_sidecar(path, profile, sources, source, source_mtime=None):
    created_at = source_mtime if source_mtime is not None else time.time()
    payload = {
        "version": 1,
        "symbol": symbol,
        "name": str((selected or {}).get("name") or "").strip(),
        "profile": profile,
        "sources": normalize_sources(sources),
        "source": source,
        "createdAt": int(created_at),
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    if source_mtime is not None:
        os.utime(path, (source_mtime, source_mtime))


def write_profile_work_files(profile, sources):
    (work_root / "profile.md").write_text(profile + "\n", encoding="utf-8")
    (work_root / "profile-index.json").write_text(
        json.dumps(normalize_sources(sources), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


sidecar_exists = profile_sidecar_path.exists()
sidecar_fresh = profile_artifact_is_fresh(profile_sidecar_path)
cached_profile, cached_sources = sidecar_profile(profile_sidecar_path)
cached_profile_source = "sidecar" if cached_profile else ""
if not cached_profile and (not sidecar_exists or sidecar_fresh):
    cached_profile, cached_sources = seed_profile_from_existing_artifacts(
        report_path,
        work_root / "profile-index.json",
    )
    cached_profile_source = "existing-artifacts" if cached_profile else ""
shutil.rmtree(work_root, ignore_errors=True)
work_root.mkdir(parents=True, exist_ok=True)
(work_root / "query-source-summaries").mkdir(parents=True, exist_ok=True)
(work_root / "query-source-index").mkdir(parents=True, exist_ok=True)
(work_root / "query-findings").mkdir(parents=True, exist_ok=True)

if cached_profile:
    if cached_profile_source != "sidecar":
        write_profile_sidecar(
            profile_sidecar_path,
            cached_profile,
            cached_sources,
            cached_profile_source,
            report_path.stat().st_mtime,
        )
    write_profile_work_files(cached_profile, cached_sources)

selected["workRoot"] = str(work_root)
selected["reportPath"] = str(report_path)
selected["queriesPath"] = str(work_root / "queries.json")
selected["profileCacheHit"] = bool(cached_profile)
selected["profileCacheSource"] = cached_profile_source
selected["profileSidecarPath"] = str(profile_sidecar_path)
print(json.dumps([selected], ensure_ascii=False))
