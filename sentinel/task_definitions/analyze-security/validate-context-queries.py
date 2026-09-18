"""Validate the bounded external-context query list emitted by the LLM.
Environment: QUERIES_JSON."""

import json
import os
import re

raw = json.loads(os.environ["QUERIES_JSON"])
if not isinstance(raw, list):
    raise SystemExit("external-context queries must be a JSON array")


def clean(value):
    text = re.sub(r"^\s*(?:[-*]\s+|\d{1,2}[.)]\s+)", "", str(value or "")).strip()
    return " ".join(text.split()).strip()


queries = [clean(value) for value in raw if isinstance(value, str) and clean(value)]
if not 3 <= len(queries) <= 5:
    raise SystemExit("external-context query list must contain 3-5 usable strings")
if len(set(queries)) != len(queries):
    raise SystemExit("external-context query list contains duplicates")

print(json.dumps(queries, ensure_ascii=False))
