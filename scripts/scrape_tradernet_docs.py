#!/usr/bin/env python3
"""
Scrape Tradernet API documentation from tradernet.com/tradernet-api/get-example
and refresh the local Markdown copies under docs/tradernet/.

Port of the legacy Go script scripts/scrape_tradernet_docs/main.go on the
legacy-go branch.

Usage:
    python scripts/scrape_tradernet_docs.py            # scrape all slugs
    python scripts/scrape_tradernet_docs.py auth-login # just one
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs" / "tradernet"
BASE_URL = "https://tradernet.com/tradernet-api/get-example?id={slug}"
REQUEST_DELAY_S = 0.5
TIMEOUT_S = 30
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://tradernet.com/tradernet-api/",
}

DOC_SECTIONS: dict[str, list[str]] = {
    "Authentication": [
        "auth-login",
        "auth-api",
        "auth-get-opq",
        "auth-get-sidinfo",
        "public-api-client",
        "python-sdk",
    ],
    "Security Sessions": [
        "security-get-list",
        "open-security-session",
    ],
    "Securities Management": [
        "quotes-get-lists",
        "quotes-add-list",
        "quotes-update-list",
        "quotes-delete-list",
        "quotes-make-list-selected",
        "quotes-add-list-ticker",
        "quotes-delete-list-ticker",
    ],
    "Quotes & Market Data": [
        "market-status",
        "quotes-get-info",
        "get-options-by-mkt",
        "quotes-get-top-securities",
        "quotes-get-changes",
        "quotes-get",
        "quotes-orderbook",
        "quotes-get-hloc",
        "get-trades",
        "get-trades-history",
        "quotes-finder",
        "quotes-get-news",
        "securities",
        "check-allowed-ticker-and-ban-on-trade",
    ],
    "Portfolio & Orders": [
        "portfolio-get-changes",
        "orders-get-current-history",
        "get-orders-history",
        "orders-send",
        "stop-loss",
        "orders-delete",
    ],
    "Alerts & Requests": [
        "alerts-get-list",
        "alerts-add",
        "alerts-delete",
        "get-client-cps-history",
        "get-cps-files",
    ],
    "Reports": [
        "broker-report",
        "broker-report-url",
        "depositary-report",
        "broker-depositary-report-url",
        "get-cashflows",
    ],
    "Currencies & WebSocket": [
        "cross-rates-for-date",
        "currency",
        "websocket",
        "websocket-sessions",
        "websocket-portfolio",
        "websocket-orders",
        "websocket-markets",
    ],
    "Miscellaneous": [
        "reception-types",
        "special-files-list",
        "mkt",
        "instruments",
        "cps-types-list",
        "anketa-fields",
        "passport-type",
        "order-statuses",
        "safety",
        "type-codes",
    ],
}

# Map jsdoc/phpdoc/etc. (used on the docs site) to fenced-block languages.
CODE_LANG_MAP = {
    "jsdoc": "json",
    "phpdoc": "php",
    "php": "php",
    "python": "python",
    "javascript": "javascript",
    "js": "javascript",
    "bash": "bash",
    "sh": "bash",
}

# Tags we drop entirely along with their contents.
DROP_TAGS = {"script", "style"}

# Inline UI noise: span buttons (HTTP method/protocol badges) — drop element
# but keep neighbouring text. Detected by the uk-button class.


def slug_dir(category: str) -> str:
    """Match the snake_case directory convention already in docs/tradernet/."""
    return category.replace("&", "and").replace("  ", " ").strip().lower().replace(" ", "_")


def fetch(slug: str) -> str | None:
    # The URL is a fixed https template — ruff S310 worries about file:// /
    # custom schemes, which aren't reachable here.
    req = urllib.request.Request(  # noqa: S310
        BASE_URL.format(slug=slug), headers=HEADERS
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:  # noqa: S310
            if resp.status != 200:
                return None
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace")
    except (urllib.error.URLError, TimeoutError):
        return None


# ---------------------------------------------------------------------------
# HTML -> Markdown converter
#
# The docs pages have a small, predictable tag set (h1-h4, p, code/pre, table,
# ul/li, strong/em/dfn/br/a/span/div). We walk the tree with html.parser and
# emit Markdown directly. This is intentionally minimal and tuned to these
# pages — not a general HTML->MD library.
# ---------------------------------------------------------------------------


class _Node:
    __slots__ = ("tag", "attrs", "children", "text")

    def __init__(self, tag: str, attrs: dict[str, str] | None = None) -> None:
        self.tag = tag
        self.attrs = attrs or {}
        self.children: list[_Node | str] = []
        self.text = ""


VOID_TAGS = {"br", "hr", "img", "meta", "link", "input"}

# Tags that, when started, should implicitly close an open `<p>` (HTML5 rule).
# The docs site emits invalid HTML like `<p><h3>X</h3><ul>...</ul></p>`, which
# without this fix collapses the whole tail into inline text in a paragraph.
_CLOSES_P = {
    "address",
    "article",
    "aside",
    "blockquote",
    "div",
    "dl",
    "fieldset",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "ul",
}


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("__root__")
        self.stack: list[_Node] = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _CLOSES_P and self.stack[-1].tag == "p":
            self.stack.pop()
        attr_dict = {k: (v or "") for k, v in attrs}
        node = _Node(tag, attr_dict)
        self.stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = {k: (v or "") for k, v in attrs}
        node = _Node(tag, attr_dict)
        self.stack[-1].children.append(node)

    def handle_endtag(self, tag: str) -> None:
        # Close down the stack until we find a matching tag.
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return
        # No matching open tag — ignore.

    def handle_data(self, data: str) -> None:
        if data:
            self.stack[-1].children.append(data)


def _classes(node: _Node) -> set[str]:
    return set((node.attrs.get("class") or "").split())


def _has_alnum(s: str) -> bool:
    return any(ch.isalnum() for ch in s)


# Language preference for `<code class="...">` blocks. Real-language classes
# beat the generic doc classes (`jsdoc` defaults to JSON but appears on JS
# samples too — see orders-send.md where `<code class="javascript jsdoc hljs">`
# would otherwise be mistaken for JSON when iteration picks `jsdoc` first).
_CODE_CLASS_PRIORITY = (
    "javascript",
    "js",
    "python",
    "php",
    "bash",
    "sh",
    "phpdoc",
    "jsdoc",
)


def _inner_text(node: _Node) -> str:
    """Plain text with whitespace collapsed (for headings, table cells, etc.)."""
    parts: list[str] = []
    for child in node.children:
        if isinstance(child, str):
            parts.append(child)
        elif child.tag == "br":
            parts.append(" ")
        elif child.tag not in DROP_TAGS:
            parts.append(_inner_text(child))
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _inline_md(node: _Node) -> str:
    """Render an inline-flow node to Markdown."""
    parts: list[str] = []
    for child in node.children:
        if isinstance(child, str):
            parts.append(child)
            continue
        t = child.tag
        if t in DROP_TAGS:
            continue
        if t == "br":
            parts.append(" ")
            continue
        if t == "span" and "uk-button" in _classes(child):
            # HTTP method/protocol badges — drop.
            continue
        if t == "a" and "uk-button" in _classes(child):
            # "online example" JSBin/Tonic links — drop the whole element.
            continue
        inner = _inline_md(child)
        if t == "strong" or t == "b":
            s = inner.strip()
            if not s:
                continue
            # Punctuation-only payloads (e.g. <strong>*</strong> used as a
            # stylized footnote marker) would collide with Markdown emphasis
            # syntax — pass through as plain text.
            parts.append(s if not _has_alnum(s) else f"**{s}**")
        elif t == "em" or t == "i":
            s = inner.strip()
            if not s:
                continue
            parts.append(s if not _has_alnum(s) else f"*{s}*")
        elif t == "dfn":
            # The docs site uses <dfn> for short prose intros like "Getting
            # a response if successful." — render plain to avoid italic noise.
            parts.append(inner)
        elif t == "code":
            # A <code> with hljs/jsdoc/lang class wraps a <pre> block — those
            # should never appear in inline flow; if we get here it's a true
            # inline code reference like `cmd`.
            if any(c in _classes(child) for c in ("hljs", "jsdoc")):
                continue
            parts.append(f"`{inner.strip()}`" if inner.strip() else "")
        elif t == "a":
            href = child.attrs.get("href", "")
            text = inner.strip() or href
            if href.startswith(("http://", "https://")):
                parts.append(f"[{text}]({href})")
            else:
                parts.append(text)
        else:
            parts.append(inner)
    return re.sub(r"[ \t]+", " ", "".join(parts))


def _code_block(node: _Node) -> str:
    """A `<code class="X hljs"><pre>...</pre></code>` or `<pre>` block."""
    # Find the inner <pre>, else use the node itself.
    pre: _Node | None = None
    for c in node.children:
        if isinstance(c, _Node) and c.tag == "pre":
            pre = c
            break
    raw = _raw_text(pre if pre is not None else node)
    raw = _clean_code(raw)
    cls = _classes(node)
    lang = ""
    for candidate in _CODE_CLASS_PRIORITY:
        if candidate in cls:
            lang = CODE_LANG_MAP[candidate]
            break
    # `jsdoc` is used inconsistently — both for JSON request/response examples
    # and for JS code samples. Sniff the content to pick a saner fence.
    if lang == "json":
        stripped = raw.lstrip()
        if stripped.startswith(("/**", "//", "/*", "var ", "let ", "const ", "function")):
            lang = "javascript"
    fence = f"```{lang}" if lang else "```"
    return f"{fence}\n{raw}\n```\n"


def _clean_code(raw: str) -> str:
    """Clean a <pre> block: trim per-line trailing whitespace, drop leading/
    trailing blank lines, and remove common leading indentation.
    """
    # The docs site escapes literal `<` and `>` inside code samples as
    # `&lsaquo;` / `&rsaquo;` (single guillemets). HTMLParser decodes those
    # to U+2039/U+203A — substitute back to angle brackets so code reads as
    # normal source. Legacy converter did the same.
    raw = raw.replace("‹", "<").replace("›", ">")
    lines = raw.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return ""
    indents = [len(ln) - len(ln.lstrip(" \t")) for ln in lines if ln.strip()]
    common = min(indents) if indents else 0
    return "\n".join((ln[common:] if ln.strip() else "").rstrip() for ln in lines)


def _raw_text(node: _Node) -> str:
    """Verbatim text (preserves whitespace) — for <pre>/<code>."""
    parts: list[str] = []
    for child in node.children:
        if isinstance(child, str):
            parts.append(child)
        else:
            parts.append(_raw_text(child))
    return "".join(parts)


def _table_md(node: _Node) -> str:
    """Render <table> as a GitHub MD table, prefixed by **caption** if present."""
    caption = ""
    rows: list[list[str]] = []
    has_thead = False
    for c in node.children:
        if not isinstance(c, _Node):
            continue
        if c.tag == "caption":
            caption = _inner_text(c)
        elif c.tag == "thead":
            has_thead = True
            for tr in c.children:
                if isinstance(tr, _Node) and tr.tag == "tr":
                    rows.append(_row_cells(tr, is_header=True))
        elif c.tag == "tbody":
            for tr in c.children:
                if isinstance(tr, _Node) and tr.tag == "tr":
                    rows.append(_row_cells(tr))
        elif c.tag == "tr":
            # First row is treated as header only if there's no <thead>.
            is_header = not has_thead and not rows
            rows.append(_row_cells(c, is_header=is_header))
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    out: list[str] = []
    if caption:
        out.append(f"**{caption}**\n")

    # Match legacy convention to minimize cosmetic diff vs. the previous Go
    # converter: leading pipe only (no trailing pipe), single-space empty
    # cells, header separator pipes on both ends.
    def _row(cells: list[str]) -> str:
        parts = [f" {c if c.strip() else ' '} " for c in cells]
        return ("|" + "|".join(parts)).rstrip()

    out.append(_row(rows[0]))
    out.append("|" + "|".join(["---"] * width) + "|")
    for row in rows[1:]:
        out.append(_row(row))
    return "\n".join(out) + "\n"


def _row_cells(tr: _Node, is_header: bool = False) -> list[str]:
    cells: list[str] = []
    for c in tr.children:
        if isinstance(c, _Node) and c.tag in ("td", "th"):
            # In a <thead>, the docs site wraps every header label in
            # <strong>. Treat the row as plain text — bolded headers are
            # cosmetic noise in Markdown tables.
            if is_header:
                txt = _inner_text(c)
            else:
                txt = _inline_md(c).strip()
            # Don't escape `|` inside cells — leave content like `null|float`
            # readable in the source. Strict GitHub MD parses an unescaped
            # pipe as a column break, but the docs site's type lists are the
            # only place this matters and the legacy converter rendered them
            # the same way; preserve that to keep diffs focused on content.
            txt = txt.replace("\n", " ")
            cells.append(txt)
    # Legacy emitted cells joined by "| " without a trailing pipe, so each
    # row ends after the last cell. The cell strings themselves stay raw.
    return cells


_BLOCK_INSIDE_LI = {
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "pre",
    "table",
    "ul",
    "ol",
    "blockquote",
}


def _li_has_block_child(li: _Node) -> bool:
    for c in li.children:
        if isinstance(c, _Node):
            if c.tag in _BLOCK_INSIDE_LI:
                return True
            if c.tag == "code" and any(k in _classes(c) for k in ("hljs", "jsdoc")):
                return True
    return False


def _list_md(node: _Node) -> str:
    """
    Render <ul>/<ol>. When an <li> contains block-level children (headings,
    code blocks, tables), unwrap it — the docs site uses <ul><li><h3>Lang</h3>
    <code><pre>...</pre></code></li></ul> as language-tab UI, which reads
    better as section headings in Markdown.
    """
    items = [c for c in node.children if isinstance(c, _Node) and c.tag == "li"]
    if not items:
        return ""
    # If any item has block content, unwrap all of them as block content.
    if any(_li_has_block_child(li) for li in items):
        parts: list[str] = []
        for li in items:
            for c in li.children:
                if isinstance(c, str):
                    txt = c.strip()
                    if txt:
                        parts.append(txt + "\n\n")
                else:
                    parts.append(_block_md(c))
        return "".join(parts)
    # Otherwise emit bullets.
    bullets = []
    for li in items:
        txt = _inline_md(li).strip()
        if txt:
            bullets.append(f"- {txt}")
    return ("\n".join(bullets) + "\n") if bullets else ""


def _block_md(node: _Node, depth: int = 0) -> str:
    """Convert a block-level node to Markdown."""
    t = node.tag
    if t in DROP_TAGS:
        return ""
    if t == "a" and "uk-button" in _classes(node):
        # "online example" JSBin/Tonic links sometimes appear at block level
        # — drop the whole element rather than letting it leak as bare text.
        return ""
    if t in ("h1", "h2", "h3", "h4", "h5", "h6"):
        level = int(t[1])
        return f"{'#' * level} {_inner_text(node)}\n\n"
    if t == "p":
        text = _inline_md(node).strip()
        return f"{text}\n\n" if text else ""
    if t == "ul" or t == "ol":
        # The tab-label list (e.g. `<ul class="uk-tab">` with bullets "JS",
        # "PHP", "Python") restates section headings — but legacy converters
        # emitted "## Examples" here as a visual divider, so do the same for
        # diff stability. Skip the bullets themselves.
        if "uk-tab" in _classes(node):
            return "## Examples\n\n"
        body = _list_md(node)
        return body + "\n" if body else ""
    if t == "table":
        body = _table_md(node)
        return body + "\n" if body else ""
    if t == "pre":
        return _code_block(node) + "\n"
    if t == "code" and any(c in _classes(node) for c in ("hljs", "jsdoc")):
        return _code_block(node) + "\n"
    if "uk-alert" in _classes(node):
        # Strip alert boxes (auth notes, deprecation banners) — they show up
        # consistently across many pages and add noise. If we ever want them
        # back, just remove this branch.
        return ""
    if t in ("div", "section", "article", "main", "body", "html", "__root__"):
        out: list[str] = []
        for c in node.children:
            if isinstance(c, str):
                txt = c.strip()
                if txt:
                    out.append(txt + "\n\n")
            else:
                out.append(_block_md(c, depth + 1))
        return "".join(out)
    # Inline-ish element used at block level — render inline.
    text = _inline_md(node).strip()
    return f"{text}\n\n" if text else ""


_FENCE_RE = re.compile(r"```[^\n]*\n.*?\n```", re.DOTALL)


def html_to_markdown(html: str) -> str:
    builder = _TreeBuilder()
    builder.feed(html)
    md = _block_md(builder.root)
    # Final cleanup: collapse 3+ blank lines OUTSIDE code fences. Inside a
    # fenced block, blank lines can be semantically meaningful (e.g. JSDoc
    # spacing in legacy examples), so we splice them out for the regex pass.
    placeholders: list[str] = []

    def _stash(match: re.Match[str]) -> str:
        placeholders.append(match.group(0))
        return f"\x00FENCE{len(placeholders) - 1}\x00"

    md = _FENCE_RE.sub(_stash, md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    for i, block in enumerate(placeholders):
        md = md.replace(f"\x00FENCE{i}\x00", block, 1)
    return md.strip() + "\n"


# ---------------------------------------------------------------------------
# Index (README.md) — keep the structure that's already there.
# ---------------------------------------------------------------------------


def title_case(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-"))


def write_readme() -> None:
    from datetime import datetime

    lines: list[str] = [
        "# Tradernet API Documentation",
        "",
        (
            "This directory contains the complete Tradernet API documentation "
            "scraped from https://tradernet.com/tradernet-api/"
        ),
        "",
        "## Documentation Structure",
        "",
        "The documentation is organized into the following categories:",
        "",
    ]
    for category, slugs in DOC_SECTIONS.items():
        lines.append(f"### {category}")
        lines.append("")
        for slug in slugs:
            lines.append(f"- [{title_case(slug)}](./{slug_dir(category)}/{slug}.md)")
        lines.append("")
    lines.extend(
        [
            "## Scraping",
            "",
            ("The documentation was scraped using the script at `scripts/scrape_tradernet_docs.py`."),
            "",
            "To re-scrape the documentation:",
            "",
            "```bash",
            "python scripts/scrape_tradernet_docs.py",
            "```",
            "",
            "Scrape a single endpoint:",
            "",
            "```bash",
            "python scripts/scrape_tradernet_docs.py auth-login",
            "```",
            "",
            "## Source",
            "",
            (
                "All documentation content is copyright Tradernet and sourced "
                "from their official API documentation website."
            ),
            "",
            f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
    )
    (DOCS_DIR / "README.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------


def scrape_one(slug: str, category: str) -> tuple[bool, str]:
    out_dir = DOCS_DIR / slug_dir(category)
    out_dir.mkdir(parents=True, exist_ok=True)
    html = fetch(slug)
    if not html:
        return False, "fetch failed"
    md = html_to_markdown(html)
    if len(md) < 80:
        return False, f"suspiciously small ({len(md)} chars)"
    (out_dir / f"{slug}.md").write_text(md, encoding="utf-8")
    return True, f"{len(md)} chars"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "slugs",
        nargs="*",
        help="Optional: scrape only these slugs (any category).",
    )
    parser.add_argument(
        "--no-readme",
        action="store_true",
        help="Skip rewriting docs/tradernet/README.md.",
    )
    args = parser.parse_args()

    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    targets: list[tuple[str, str]] = []
    if args.slugs:
        wanted = set(args.slugs)
        for category, slugs in DOC_SECTIONS.items():
            for slug in slugs:
                if slug in wanted:
                    targets.append((slug, category))
        missing = wanted - {s for s, _ in targets}
        if missing:
            print(f"Unknown slug(s): {sorted(missing)}", file=sys.stderr)
            return 2
    else:
        for category, slugs in DOC_SECTIONS.items():
            for slug in slugs:
                targets.append((slug, category))

    print(f"Scraping {len(targets)} doc page(s) -> {DOCS_DIR}")
    ok = 0
    failed: list[str] = []
    for i, (slug, category) in enumerate(targets, 1):
        success, msg = scrape_one(slug, category)
        marker = "OK" if success else "FAIL"
        print(f"  [{i:>3}/{len(targets)}] {category:<24} {slug:<40} {marker}  {msg}")
        if success:
            ok += 1
        else:
            failed.append(slug)
        if i < len(targets):
            time.sleep(REQUEST_DELAY_S)

    if not args.no_readme and not args.slugs:
        write_readme()
        print(f"Wrote {DOCS_DIR / 'README.md'}")

    print("---")
    print(f"Success: {ok}/{len(targets)}")
    if failed:
        print(f"Failed: {failed}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
