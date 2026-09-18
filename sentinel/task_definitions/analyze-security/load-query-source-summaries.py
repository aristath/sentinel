"""Print one query's source summaries for the findings prompt.
Environment: SOURCE_SUMMARIES_PATH."""

import os
import pathlib

path = pathlib.Path(os.environ["SOURCE_SUMMARIES_PATH"])
content = path.read_text(encoding="utf-8") if path.exists() else ""
if not content.strip():
    raise SystemExit("No usable source summaries were fetched for this query")
print(content)
