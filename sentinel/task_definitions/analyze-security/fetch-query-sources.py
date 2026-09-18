"""For one research query, fetch + summarise its sources via the url-summarizer,
writing per-query summaries/index files keyed by a query hash. Emits the paths and
source count for the findings prompt.
Environment: WORK_ROOT, QUERY, SEARCH_TEXT."""

import os
import hashlib
import json
import pathlib

from source_fetching import collect_usable_sources, parse_candidates

work_root = pathlib.Path(os.environ["WORK_ROOT"])
query = " ".join(str(os.environ.get("QUERY") or "").split())
if not query:
    raise SystemExit("query is empty")

query_hash = hashlib.sha1(query.encode("utf-8")).hexdigest()[:16]
source_summaries_path = work_root / "query-source-summaries" / f"{query_hash}.md"
source_index_path = work_root / "query-source-index" / f"{query_hash}.json"
source_summaries_path.parent.mkdir(parents=True, exist_ok=True)
source_index_path.parent.mkdir(parents=True, exist_ok=True)
source_summaries_path.write_text("", encoding="utf-8")

search_text = str(os.environ.get("SEARCH_TEXT") or "")

skip_hosts = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "youtube.com",
}


def url_summarizer_base_url():
    return str(os.environ.get("SENTINEL_URL_SUMMARIZER_BASE_URL") or "http://127.0.0.1:8890").rstrip("/")


service_base_url = url_summarizer_base_url()
candidates = parse_candidates(search_text, skip_hosts)
fetched_sources, attempted_count = collect_usable_sources(candidates, service_base_url)
saved = []
with source_summaries_path.open("a", encoding="utf-8") as handle:
    for fetched in fetched_sources:
        idx = len(saved) + 1
        title = fetched["title"]
        url = fetched["url"]
        saved.append({"index": idx, "title": title, "url": url})
        handle.write(f"\n\n## Source {idx}: {title}\n")
        handle.write(f"URL: {url}\n\n")
        handle.write(fetched["summary"])
        handle.write("\n")

source_index_path.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")

print(
    json.dumps(
        {
            "query": query,
            "queryHash": query_hash,
            "sourceSummariesPath": str(source_summaries_path),
            "sourceIndexPath": str(source_index_path),
            "findingsPath": str(work_root / "query-findings" / f"{query_hash}.md"),
            "candidateCount": len(candidates),
            "attemptedCount": attempted_count,
            "sourceCount": len(saved),
        },
        ensure_ascii=False,
    )
)
