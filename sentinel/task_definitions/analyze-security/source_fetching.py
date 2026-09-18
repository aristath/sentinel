"""Shared search-result parsing and bounded usable-source collection."""

import concurrent.futures
import json
import re
import time
import urllib.request
from urllib.parse import urlparse

BATCH_SIZE = 5
TARGET_SOURCE_COUNT = 5

SEARCH_RESULT_PATTERN = re.compile(
    r"Title:\s*(?P<title>.*?)\n"
    r"Description:\s*(?P<description>.*?)\n"
    r"URL:\s*(?P<url>\S+)(?:\nRelevance Score:\s*(?P<score>[^\n]+))?",
    re.S,
)


def _host_matches(host, skipped):
    return host == skipped or host.endswith("." + skipped)


def parse_candidates(search_text, skip_hosts):
    candidates = []
    seen = set()
    for match in SEARCH_RESULT_PATTERN.finditer(str(search_text or "")):
        url = match.group("url").strip()
        title = " ".join(match.group("title").split())
        if not url.startswith(("http://", "https://")) or not title or url in seen:
            continue
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        if any(_host_matches(host, skipped) for skipped in skip_hosts):
            continue
        seen.add(url)
        candidates.append({"title": title, "url": url})
    return candidates


def _read_article(service_base_url, candidate):
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


def collect_usable_sources(candidates, service_base_url, target_count=TARGET_SOURCE_COUNT):
    """Try ordered batches until target_count non-empty summaries are collected."""
    saved = []
    attempted = 0
    for offset in range(0, len(candidates), BATCH_SIZE):
        batch = candidates[offset : offset + BATCH_SIZE]
        attempted += len(batch)
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(batch)) as executor:
            futures = [executor.submit(_read_article, service_base_url, candidate) for candidate in batch]
            fetched_batch = []
            for future in futures:
                try:
                    fetched_batch.append(future.result())
                except Exception:
                    fetched_batch.append(None)

        for candidate, fetched in zip(batch, fetched_batch, strict=True):
            if not fetched or not fetched.get("ok"):
                continue
            summary = str(fetched.get("summary") or "").strip()
            if not summary:
                continue
            saved.append(
                {
                    "title": fetched.get("title") or candidate["title"],
                    "url": fetched.get("url") or candidate["url"],
                    "summary": summary,
                }
            )
            if len(saved) >= target_count:
                return saved, attempted
    return saved, attempted
