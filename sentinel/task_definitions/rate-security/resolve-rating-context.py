"""
Resolve the rating context for one security (manual `symbol` input).

Looks the symbol up in the universe, recreates a clean per-symbol scratch dir
(guarded to stay under this task's artifacts), and emits every path the rest of
the rating pipeline needs.

Environment: SYMBOL (requested symbol), SENTINEL_TASKS_HOME.
"""

import os
import json
import pathlib
import re
import shutil

requested = str(os.environ.get("SYMBOL") or "").strip().upper()
if not requested:
    raise SystemExit('Manual input "symbol" is required')

data_dir = os.environ.get("SENTINEL_TASKS_HOME")
if not data_dir:
    raise SystemExit("SENTINEL_TASKS_HOME is required")
artifacts = pathlib.Path(data_dir) / "tasks" / "artifacts"
universe_root = artifacts / "refresh-securities-universe"
root = artifacts / "rate-security"
universe_path = universe_root / "securities-universe.json"
if not universe_path.exists():
    raise SystemExit("Missing securities-universe.json. Run refresh-securities-universe first.")


def safe_symbol(value):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "")) or "security"


universe = json.loads(universe_path.read_text(encoding="utf-8"))
if not isinstance(universe, list):
    raise SystemExit("securities-universe.json must contain a JSON array")

selected = None
for entry in universe:
    if not isinstance(entry, dict):
        continue
    if str(entry.get("symbol") or "").strip().upper() == requested:
        selected = dict(entry)
        break
if selected is None:
    raise SystemExit(f'Security "{requested}" not found in securities-universe.json')

symbol = str(selected.get("symbol") or "").strip()
name = str(selected.get("name") or "").strip()

work_root = root / safe_symbol(symbol)
case_root = str(work_root)
home = pathlib.Path.home()
expected_prefix = str(home / ".sentinel" / "tasks" / "artifacts" / "rate-security")
if not case_root.startswith(expected_prefix):
    raise SystemExit(f"Refusing to clean unexpected scratchpad path: {case_root}")
shutil.rmtree(work_root, ignore_errors=True)
work_root.mkdir(parents=True, exist_ok=True)

print(
    json.dumps(
        {
            "symbol": symbol,
            "safeSymbol": safe_symbol(symbol),
            "name": name,
            "workRoot": str(work_root),
            "evidencePackPath": str(work_root / "evidence-pack.md"),
            "analysisPath": str(work_root / "analysis.md"),
            "ratingRawPath": str(work_root / "rating.raw.json"),
            "ratingPath": str(work_root / "rating.json"),
        },
        ensure_ascii=False,
    )
)
