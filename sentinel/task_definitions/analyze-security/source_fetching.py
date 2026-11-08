"""Shared search-result parsing and bounded usable-source collection."""

import concurrent.futures
import json
import re
import subprocess
import time
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlparse

BATCH_SIZE = 5
TARGET_SOURCE_COUNT = 5
MAX_CONTENT_CHARS = 20_000
MAX_DOWNLOAD_BYTES = 20_000_000

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
            "includeContent": True,
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


class PageText(HTMLParser):
    """Read visible prose and tables without the summarizer's article gates."""

    def __init__(self):
        super().__init__()
        self.parts = []
        self.article = []
        self.main = []
        self.stack = []

    def handle_starttag(self, tag, attrs):
        if tag not in {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }:
            self.stack.append(tag)
        if tag in {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "td", "th"}:
            self.handle_data("\n" if tag not in {"td", "th"} else " | ")

    def handle_endtag(self, tag):
        if tag in self.stack:
            index = len(self.stack) - 1 - self.stack[::-1].index(tag)
            del self.stack[index:]
        if tag in {"p", "div", "tr", "li", "h1", "h2", "h3"}:
            self.handle_data("\n")

    def handle_data(self, data):
        if any(tag in self.stack for tag in {"script", "style", "noscript", "nav", "header", "footer", "svg"}):
            return
        self.parts.append(data)
        if "article" in self.stack:
            self.article.append(data)
        if "main" in self.stack:
            self.main.append(data)

    def text(self):
        parts = self.article or self.main or self.parts
        return "\n".join(line for part in "".join(parts).splitlines() if (line := " ".join(part.split())))


def read_raw_content(candidate):
    request = urllib.request.Request(candidate["url"], headers={"User-Agent": "Sentinel research/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read(MAX_DOWNLOAD_BYTES + 1)
        media_type = response.headers.get_content_type()
        charset = response.headers.get_content_charset() or "utf-8"
    if len(body) > MAX_DOWNLOAD_BYTES:
        raise ValueError("source exceeds 20 MB download limit")
    if media_type == "application/pdf" or body.startswith(b"%PDF-"):
        result = subprocess.run(
            ["pdftotext", "-layout", "-", "-"], input=body, capture_output=True, timeout=30, check=True
        )
        content = result.stdout.decode("utf-8", "replace")
    elif media_type in {"text/html", "application/xhtml+xml"}:
        page = PageText()
        page.feed(body.decode(charset, "replace"))
        content = page.text()
    elif media_type in {"text/plain", "text/markdown", "text/x-markdown"}:
        content = body.decode(charset, "replace")
    else:
        raise ValueError(f"unsupported source content type: {media_type}")
    content = content.strip()
    if len(content) < 80:
        raise ValueError("no usable raw source text")
    if any(
        marker in content[:2000].lower()
        for marker in (
            "verify you are human",
            "enable javascript and cookies",
            "just a moment...",
            "access denied",
        )
    ):
        raise ValueError("raw source contains an access challenge")
    return content


def collect_usable_sources(candidates, service_base_url, target_count=TARGET_SOURCE_COUNT, allow_raw=False):
    """Prefer summaries; only use unsummarized content after search recovery."""
    saved = []
    attempted = 0
    failures = []
    rejected = []
    for offset in range(0, len(candidates), BATCH_SIZE):
        batch = candidates[offset : offset + BATCH_SIZE]
        attempted += len(batch)
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(batch)) as executor:
            futures = [executor.submit(_read_article, service_base_url, candidate) for candidate in batch]
            fetched_batch = []
            for future in futures:
                try:
                    fetched_batch.append(future.result())
                except Exception as error:
                    fetched_batch.append({"ok": False, "error": str(error)})

        for candidate, fetched in zip(batch, fetched_batch, strict=True):
            summary = str(fetched.get("summary") or "").strip()
            if not fetched.get("ok") or not summary:
                failures.append(
                    {
                        "url": candidate["url"],
                        "stage": "summary",
                        "error": fetched.get("error") or fetched.get("status") or "empty summary",
                    }
                )
                rejected.append((candidate, fetched))
                continue
            saved.append(
                {
                    "title": fetched.get("title") or candidate["title"],
                    "url": fetched.get("url") or candidate["url"],
                    "summary": summary,
                    "contentKind": "summary",
                }
            )
            if len(saved) >= target_count:
                return saved, attempted, failures
    if allow_raw:
        for candidate, fetched in rejected:
            try:
                content = str(fetched.get("content") or "").strip() or read_raw_content(candidate)
                if len(content) > MAX_CONTENT_CHARS:
                    content = content[:MAX_CONTENT_CHARS] + "\n[Source content truncated at 20,000 characters.]"
                saved.append(
                    {
                        "title": fetched.get("title") or candidate["title"],
                        "url": fetched.get("url") or candidate["url"],
                        "summary": content,
                        "contentKind": "raw",
                    }
                )
            except Exception as error:
                failures.append({"url": candidate["url"], "stage": "raw", "error": str(error)})
            if len(saved) >= target_count:
                break
    return saved, attempted, failures
