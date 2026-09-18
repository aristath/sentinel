"""Fetch + summarise profile-overview sources via the url-summarizer; write
profile-summaries.md and profile-index.json. If nothing usable is fetched, bump the
report mtime (or write a placeholder stub) and abort so the picker rotates on.
Environment: SEARCH_TEXT, ITEM_JSON."""

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
fetched_sources, _attempted_count = collect_usable_sources(candidates, service_base_url)
saved = []
with summaries_path.open("a", encoding="utf-8") as handle:
    for fetched in fetched_sources:
        idx = len(saved) + 1
        title = fetched["title"]
        url = fetched["url"]
        saved.append({"index": idx, "title": title, "url": url})
        handle.write(f"\n\n## Source {idx}: {title}\n")
        handle.write(f"URL: {url}\n\n")
        handle.write(fetched["summary"])
        handle.write("\n")

if not saved:
    # No usable sources this run. We still need schedule-next-security-analysis
    # to see a fresh mtime so it rotates to the next symbol instead of
    # re-picking this one every cycle. But NEVER clobber an existing analysis:
    # if a real report is already on disk, just bump its mtime and leave the
    # content intact. Only write a placeholder stub when nothing exists yet.
    report_path = pathlib.Path(item["reportPath"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if report_path.exists():
        report_path.touch()
    else:
        import datetime as dt

        today = dt.date.today().isoformat()
        symbol = item.get("symbol")
        name = item.get("name")
        stub = (
            f"# {symbol} — {name}\n"
            f"As of: {today}\n\n"
            "(No usable profile sources fetched yet. None of the returned URLs "
            "yielded extractable content. Will retry next scheduled cycle.)\n"
        )
        tmp = report_path.with_suffix(report_path.suffix + ".tmp")
        tmp.write_text(stub, encoding="utf-8")
        tmp.replace(report_path)
    raise SystemExit("No usable profile sources were fetched")

index_path.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
