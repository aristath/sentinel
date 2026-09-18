"""Persist the distilled per-security external context.
Environment: ITEM_JSON, CONTEXT_OUTPUT."""

import datetime as dt
import json
import os
import pathlib

item = json.loads(os.environ["ITEM_JSON"])
symbol = str(item.get("symbol") or "").strip()
name = str(item.get("name") or "").strip()
path = pathlib.Path(item["contextReportPath"])
raw = str(os.environ.get("CONTEXT_OUTPUT") or "").strip()
if not raw:
    raise SystemExit("distill-context-findings produced no output")

lines = [
    f"# External Context for {symbol} — {name}",
    f"As of: {dt.date.today().isoformat()}",
    "",
    raw,
]
path.parent.mkdir(parents=True, exist_ok=True)
tmp = path.with_suffix(path.suffix + ".tmp")
tmp.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
tmp.replace(path)
print(json.dumps({"contextReport": str(path)}, ensure_ascii=False))
