"""Collect profile sources, optionally falling back to unsummarized content.
Environment: SEARCH_TEXT, ITEM_JSON, ALLOW_RAW_CONTENT (optional)."""

import os
import json
import pathlib

from source_fetching import collect_usable_sources, parse_candidates

item = json.loads(os.environ["ITEM_JSON"])
search_text = os.environ.get("SEARCH_TEXT", "")
work_root = pathlib.Path(item["workRoot"])
summaries_path = work_root / "profile-summaries.md"
index_path = work_root / "profile-index.json"
summaries_path.parent.mkdir(parents=True, exist_ok=True)
summaries_path.write_text("", encoding="utf-8")

skip_hosts = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "discussions.apple.com",
}


def url_summarizer_base_url():
    return str(os.environ.get("SENTINEL_URL_SUMMARIZER_BASE_URL") or "http://127.0.0.1:8890").rstrip("/")


service_base_url = url_summarizer_base_url()
candidates = parse_candidates(search_text, skip_hosts)
fetched_sources, attempted_count, failures = collect_usable_sources(
    candidates, service_base_url, allow_raw=os.environ.get("ALLOW_RAW_CONTENT") == "true"
)
saved = []
with summaries_path.open("a", encoding="utf-8") as handle:
    for fetched in fetched_sources:
        idx = len(saved) + 1
        title = fetched["title"]
        url = fetched["url"]
        saved.append({"index": idx, "title": title, "url": url, "contentKind": fetched["contentKind"]})
        handle.write(f"\n\n## Source {idx}: {title}\n")
        handle.write(f"URL: {url}\n\n")
        if fetched["contentKind"] == "raw":
            handle.write("Unsummarized source content:\n\n")
        handle.write(fetched["summary"])
        handle.write("\n")

index_path.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
print(
    json.dumps(
        {
            "candidateCount": len(candidates),
            "attemptedCount": attempted_count,
            "sourceCount": len(saved),
            "rawSourceCount": sum(source["contentKind"] == "raw" for source in saved),
            "failures": failures,
        },
        ensure_ascii=False,
    )
)
