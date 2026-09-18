"""Fetch + summarise profile-overview sources via the url-summarizer; write
profile-summaries.md and profile-index.json. If nothing usable is fetched, bump the
report mtime (or write a placeholder stub) and abort so the picker rotates on.
Environment: SEARCH_TEXT, ITEM_JSON."""

import os
import json
import pathlib
import re
import time
import urllib.request
from urllib.parse import urlparse

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


def host_matches(host, skipped):
    return host == skipped or host.endswith("." + skipped)


def url_summarizer_base_url():
    return str(os.environ.get("SENTINEL_URL_SUMMARIZER_BASE_URL") or "http://127.0.0.1:8890").rstrip("/")


def read_article(service_base_url, candidate):
    payload = json.dumps(
        {
            "url": candidate["url"],
            "title": candidate["title"],
            "includeContent": False,
        }
    ).encode("utf-8")
    last_error = None
    for attempt in range(3):
        request = urllib.request.Request(
            f"{service_base_url}/v1/articles/read",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as error:
            last_error = error
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    if last_error is not None:
        raise last_error
    raise RuntimeError("URL summarizer failed without an error")


candidates = []
seen_urls = set()
pattern = re.compile(
    r"Title:\s*(?P<title>.*?)\n"
    r"Description:\s*(?P<description>.*?)\n"
    r"URL:\s*(?P<url>\S+)(?:\nRelevance Score:\s*(?P<score>[^\n]+))?",
    re.S,
)
for match in pattern.finditer(str(search_text or "")):
    url = match.group("url").strip()
    title = " ".join(match.group("title").split())
    if not url.startswith(("http://", "https://")) or not title or url in seen_urls:
        continue
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path.lower()
    if any(host_matches(host, skipped) for skipped in skip_hosts):
        continue
    if "[pdf]" in title.lower() or path.endswith(".pdf") or path.endswith("/download") or "/bitstreams/" in path:
        continue
    seen_urls.add(url)
    candidates.append({"title": title, "url": url})

service_base_url = url_summarizer_base_url()
saved = []
with summaries_path.open("a", encoding="utf-8") as handle:
    for candidate in candidates:
        try:
            fetched = read_article(service_base_url, candidate)
        except Exception:
            continue
        if not fetched.get("ok"):
            continue
        summary = str(fetched.get("summary") or "").strip()
        if not summary:
            continue
        idx = len(saved) + 1
        title = fetched.get("title") or candidate["title"]
        url = fetched.get("url") or candidate["url"]
        saved.append({"index": idx, "title": title, "url": url})
        handle.write(f"\n\n## Source {idx}: {title}\n")
        handle.write(f"URL: {url}\n\n")
        handle.write(summary)
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
            "(No usable profile sources fetched yet. The web search returned "
            "only filtered-out URLs — typically PDFs, social media, or "
            "paywalled stubs. Will retry next scheduled cycle.)\n"
        )
        tmp = report_path.with_suffix(report_path.suffix + ".tmp")
        tmp.write_text(stub, encoding="utf-8")
        tmp.replace(report_path)
    raise SystemExit("No usable profile sources were fetched")

index_path.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
