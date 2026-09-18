"""Build the memory-only evidence pack used to rate one security.

Assembles a 6-month window of security-specific and external-context mem0 records.

Environment: CONTEXT_JSON (resolve-rating-context output),
             SENTINEL_BASE_URL (optional, default http://127.0.0.1:8000).
"""

import os
import datetime as dt
import json
import pathlib
import urllib.error
import urllib.parse
import urllib.request

ctx = json.loads(os.environ["CONTEXT_JSON"])
symbol = ctx["symbol"]
name = ctx["name"]
evidence_pack_path = pathlib.Path(ctx["evidencePackPath"])

evidence_pack_path.parent.mkdir(parents=True, exist_ok=True)

today = dt.date.today()
# 6-month historical window for mem0 retrieval.
window_start = today - dt.timedelta(days=183)


def fetch_memories(tag_list, limit=200):
    qs = urllib.parse.urlencode({"tag": ",".join(tag_list), "limit": str(limit)})
    url = f"{os.environ.get('SENTINEL_BASE_URL', 'http://127.0.0.1:8000')}/api/memory/memories?{qs}"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError) as error:
        return [], str(error)
    items = payload.get("items") if isinstance(payload, dict) else None
    return items or [], None


def parse_as_of(metadata):
    raw = (metadata or {}).get("as_of") or (metadata or {}).get("asOf")
    if not raw:
        return None
    try:
        return dt.date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


# --- Security research memories, last 6 months ---
research_memories, research_err = fetch_memories(["securities", symbol, "query-source-summary"])
research_summary_memories, research_summary_err = fetch_memories(["securities", symbol, "research-summary"])
context_memories, context_err = fetch_memories(["securities", symbol, "external-context"])


def render_memory_lines(memories, label):
    rendered = []
    kept = 0
    for record in memories:
        metadata = record.get("metadata") or {}
        as_of = parse_as_of(metadata)
        if not as_of or as_of < window_start:
            continue
        category = metadata.get("category") or metadata.get("kind") or ""
        content = (record.get("content") or "").strip()
        if not content:
            continue
        urls = metadata.get("source_urls") or []
        url_str = ""
        if isinstance(urls, list) and urls:
            url_str = f" — source: {urls[0]}"
        elif isinstance(urls, str) and urls:
            url_str = f" — source: {urls}"
        line = f"- {as_of.isoformat()} [{category}] {content}{url_str}"
        rendered.append(line)
        kept += 1
    return rendered, kept


research_lines, research_count = render_memory_lines(research_memories, "research")
research_summary_lines, research_summary_count = render_memory_lines(research_summary_memories, "research-summary")
context_lines, context_count = render_memory_lines(context_memories, "external-context")

historical_sections = []
historical_sections.append("### Security findings (last 6 months from mem0)")
if research_lines:
    historical_sections.extend(research_lines)
else:
    historical_sections.append("(no security findings in the 6-month window)")
historical_sections.append("")
historical_sections.append("### Prior research summaries (last 6 months from mem0)")
if research_summary_lines:
    historical_sections.extend(research_summary_lines)
else:
    historical_sections.append("(no prior research summaries in the 6-month window)")
historical_sections.append("")
historical_sections.append("### External-context findings (last 6 months from mem0)")
if context_lines:
    historical_sections.extend(context_lines)
else:
    historical_sections.append("(no external-context findings in the 6-month window)")

# --- Assemble the memory-only evidence pack ---
lines = [
    f"# Evidence Pack for {symbol} — {name}",
    f"As of: {today.isoformat()}",
    "",
    "Investment horizon: 5-10 years. Day-to-day and quarterly performance are noise; structural trajectory is signal.",
    "",
    "## Research Memory (last 6 months)",
]
lines.extend(historical_sections)

evidence_pack_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

print(
    json.dumps(
        {
            "evidencePack": str(evidence_pack_path),
            "historicalResearchCount": research_count,
            "historicalResearchSummaryCount": research_summary_count,
            "historicalExternalContextCount": context_count,
            "memoryReadErrors": [e for e in [research_err, research_summary_err, context_err] if e],
        },
        ensure_ascii=False,
    )
)
