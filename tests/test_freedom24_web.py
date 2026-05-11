"""Tests for the freedom24 web-session client parser.

Only the parser is unit-tested here. The full login + fetch flow has been
validated end-to-end against the real freedom24 endpoint via the spike at
.tmp/freedom24_spike.py; mocking httpx for the client glue would add more
indirection than the glue itself contains.
"""

from __future__ import annotations

import json

from sentinel.freedom24_web import _extract_props

# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _wrap_html(props_json: str) -> str:
    return f"<!doctype html><html><body><script>const props = {props_json};</script></body></html>"


def test_extract_props_minimal():
    html = _wrap_html('{"portfolioAnalysis":{"netAssets":"123.45"}}')
    out = _extract_props(html)
    assert out == {"portfolioAnalysis": {"netAssets": "123.45"}}


def test_extract_props_with_braces_in_strings():
    # Braces inside string values must not throw off the depth counter.
    payload = {
        "portfolioAnalysis": {
            "userTitle": "CY #1462137",
            "note": "weird { content } in here",
            "regex": "a\\}b",
        }
    }
    html = _wrap_html(json.dumps(payload))
    out = _extract_props(html)
    assert out == payload


def test_extract_props_missing_returns_none():
    assert _extract_props("<html>no props here</html>") is None


def test_extract_props_truncated_returns_none():
    # A `const props = {` without a matching closing brace must not hang or
    # raise — it must return None.
    out = _extract_props('const props = { "a": 1, "b":')
    assert out is None


def test_extract_props_invalid_json_returns_none():
    out = _extract_props("const props = { not-valid-json };")
    assert out is None
