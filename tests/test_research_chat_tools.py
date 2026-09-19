from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from sentinel.ai import chat_tools


class FakeResponse:
    def __init__(self, payload, status_code: int = 200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class FakeHttpClient:
    def __init__(self):
        self.calls = []
        self.closed = False

    async def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        if url.endswith("/tools"):
            return FakeResponse(
                {
                    "tools": [
                        {
                            "name": "navigate_page",
                            "description": "Navigate Firefox.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {"url": {"type": "string"}},
                                "required": ["url"],
                            },
                        }
                    ]
                }
            )
        if url.endswith("/autocompleter"):
            return FakeResponse(["cat", ["catl", "caterpillar"]])
        if url.endswith("/config"):
            return FakeResponse(
                {
                    "default_locale": "en",
                    "default_language": "all",
                    "search": {"safe_search": 0},
                    "engines": [
                        {"name": "google", "categories": ["general"], "disabled": False},
                        {"name": "old", "categories": ["general"], "disabled": True},
                    ],
                    "plugins": [],
                }
            )
        raise AssertionError(url)

    async def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return FakeResponse({"content": [{"type": "text", "text": "Firefox moved"}]})

    async def aclose(self):
        self.closed = True


class FakePipelineExecutors:
    def __init__(self):
        self.closed = False

    def get(self, name):
        if name == "read_url":

            async def read_url(args):
                return {"text": f"# Heading\n\nParagraph one\n\nParagraph two from {args['url']}"}

            return read_url
        if name == "searxng_web_search":

            async def search(args):
                return f"Search: {args['query']}"

            return search
        return None

    async def aclose(self):
        self.closed = True


@pytest.fixture
def chat_tool_dependencies(monkeypatch):
    from sentinel.mcp_server import mcp

    pipeline = FakePipelineExecutors()
    http = FakeHttpClient()
    monkeypatch.setattr(chat_tools.pipeline_tools, "make_tool_executors", lambda *args: pipeline)
    monkeypatch.setattr(chat_tools.httpx, "AsyncClient", lambda **kwargs: http)
    monkeypatch.setattr(
        mcp,
        "list_tools",
        AsyncMock(
            return_value=[
                SimpleNamespace(
                    name="portfolio_get",
                    description="Get the portfolio.",
                    input_schema={"type": "object", "properties": {}},
                )
            ]
        ),
    )
    monkeypatch.setattr(
        mcp,
        "call_tool",
        AsyncMock(
            return_value=SimpleNamespace(
                content=[SimpleNamespace(type="text", text='{"total": 100}')],
                structured_content=None,
            )
        ),
    )
    return pipeline, http, mcp


@pytest.mark.asyncio
async def test_research_chat_exposes_all_requested_tool_sources(tmp_path, chat_tool_dependencies):
    pipeline, http, mcp = chat_tool_dependencies
    tools = await chat_tools.ResearchChatTools.create(
        searxng_base_url="http://search",
        url_summarizer_base_url="http://reader",
        browser_search_base_url="http://fallback",
        firefox_mcp_base_url="http://firefox",
        work_root=tmp_path,
    )

    names = {item["function"]["name"] for item in tools.definitions}
    assert {
        "read_file",
        "write_file",
        "list_directory",
        "run_shell",
        "read_url",
        "mcp__searxng__searxng_web_search",
        "mcp__searxng__searxng_search_suggestions",
        "mcp__searxng__searxng_instance_info",
        "mcp__searxng__web_url_read",
        "mcp__sentinel__portfolio_get",
        "mcp__firefox__navigate_page",
    } <= names

    assert await tools.get("mcp__sentinel__portfolio_get")({}) == '{"total": 100}'
    assert await tools.get("mcp__firefox__navigate_page")({"url": "https://example.com"}) == "Firefox moved"
    mcp.call_tool.assert_awaited_once_with("portfolio_get", {})

    await tools.aclose()
    assert pipeline.closed is True
    assert http.closed is True


@pytest.mark.asyncio
async def test_research_chat_filesystem_shell_and_searx_tools(tmp_path, chat_tool_dependencies):
    tools = await chat_tools.ResearchChatTools.create(
        searxng_base_url="http://search",
        url_summarizer_base_url="http://reader",
        browser_search_base_url="http://fallback",
        firefox_mcp_base_url="http://firefox",
        work_root=tmp_path,
    )
    target = tmp_path / "notes.txt"

    await tools.get("write_file")({"path": str(target), "content": "alpha"})
    await tools.get("write_file")({"path": str(target), "content": " beta", "append": True})
    assert await tools.get("read_file")({"path": str(target)}) == "alpha beta"
    assert str(target) in await tools.get("list_directory")({"path": str(tmp_path)})

    shell = await tools.get("run_shell")({"command": "printf shell-ok", "cwd": str(tmp_path)})
    assert shell["data"] == {"stdout": "shell-ok", "stderr": "", "exit_code": 0}

    suggestions = json.loads(await tools.get("mcp__searxng__searxng_search_suggestions")({"query": "cat"}))
    assert suggestions["suggestions"] == ["catl", "caterpillar"]
    info = json.loads(
        await tools.get("mcp__searxng__searxng_instance_info")({"includeEngines": True, "includeDisabled": False})
    )
    assert info["engines"] == [{"name": "google", "categories": ["general"], "disabled": False}]
    content = await tools.get("mcp__searxng__web_url_read")({"url": "https://example.com", "paragraphRange": "2-"})
    assert content == "Paragraph one\n\nParagraph two from https://example.com"

    await tools.aclose()
