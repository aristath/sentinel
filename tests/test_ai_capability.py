"""Capability-layer tests: LLM client, tool executors, and the pgvector memory store.

Ground-truth values for the lemmatizer / to_millis were captured from the
production mem0 bundle and the JS Date parser, respectively — do not "fix"
them to look prettier.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx
import pytest

import sentinel.ai.llm as llm
from sentinel.ai.errors import AIPipelineError, LLMError, MemoryStoreError
from sentinel.ai.llm import (
    LLMClient,
    _ExactRepeatDetector,
    _rate_limit_delay_ms,
    _ToolCallAccumulator,
    build_system_prompt,
    discover_models,
    expand_path,
    expand_paths,
    parse_json_output,
    run_prompt,
    strip_json_fence,
    substitute,
    tool_result_to_text,
)
from sentinel.ai.memory import (
    MemoryStore,
    clamp_similarity,
    compact_whitespace,
    dedup_metadata_filters,
    derive_memory_dedup_query,
    find_deterministic_memory_duplicate,
    first_words,
    format_memory_dedup_candidates,
    lemmatize_for_bm25,
    normalize_memory_content,
    normalize_memory_store_metadata,
    strip_leading_date,
    to_millis,
    to_pgvector_record,
    to_pgvector_search_match,
    truncate_content,
)
from sentinel.ai.tools import (
    TOOL_DEFINITIONS,
    _json_error,
    _network_error,
    _normalize_language,
    _normalize_safesearch,
    _normalize_time_range,
    _server_error,
    build_search_url,
    format_search_response,
    make_tool_executors,
    validate_search_args,
)

# --- fakes --------------------------------------------------------------------

_PG_PASSWORD = "p"  # noqa: S105


class FakeResponse:
    _REASONS = {
        200: "OK",
        403: "Forbidden",
        404: "Not Found",
        418: "I'm a teapot",
        429: "Too Many Requests",
        500: "Internal Server Error",
        502: "Bad Gateway",
    }

    def __init__(
        self,
        status_code: int = 200,
        lines: list[str] | None = None,
        headers: dict | None = None,
        body: bytes = b"",
    ) -> None:
        self.status_code = status_code
        self._lines = lines or []
        self.headers = httpx.Headers(headers or {})
        self._body = body
        self.reason_phrase = self._REASONS.get(status_code, "Status")

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def aclose(self) -> None:
        pass

    async def aread(self) -> bytes:
        return self._body

    @property
    def text(self) -> str:
        return self._body.decode("utf-8", "replace")

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def ok(self) -> bool:
        return self.is_success

    def json(self) -> Any:
        return json.loads(self._body)


def sse_lines(payloads: list[dict]) -> list[str]:
    lines = [f"data: {json.dumps(p)}" for p in payloads]
    lines.append("data: [DONE]")
    return lines


class FakeSession:
    """Duck-typed httpx.AsyncClient: build_request + send + a queued response list."""

    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[dict] = []

    def build_request(self, method: str, url: str, json: Any = None, headers: dict | None = None) -> dict:
        request = {"method": method, "url": url, "json": json, "headers": headers or {}}
        self.requests.append(request)
        return request

    async def send(self, request: dict, stream: bool = True) -> FakeResponse:
        return self._responses.pop(0)

    async def aclose(self) -> None:
        pass


def make_client(responses: list[FakeResponse], **kwargs: Any) -> LLMClient:
    session = FakeSession(responses)
    client = LLMClient("http://llm/v1", "test-key", "test-model", session=session, **kwargs)
    client._test_session = session  # type: ignore[attr-defined]
    return client


def content_stream(text: str) -> FakeResponse:
    return FakeResponse(lines=sse_lines([{"choices": [{"delta": {"content": text}}]}]))


def tool_call_stream(name: str, arguments: str, call_id: str = "call_1", content: str = "") -> FakeResponse:
    delta: dict[str, Any] = {}
    if content:
        delta["content"] = content
    delta["tool_calls"] = [{"index": 0, "id": call_id, "function": {"name": name, "arguments": arguments}}]
    return FakeResponse(lines=sse_lines([{"choices": [{"delta": delta}]}]))


class FakeHttp:
    """Duck-typed httpx.AsyncClient for the tool executors."""

    def __init__(self, response: Any = None, exc: Exception | None = None) -> None:
        self._response = response
        self._exc = exc
        self.calls: list[dict] = []

    async def get(self, url: str, timeout: Any = None) -> Any:
        self.calls.append({"url": url, "timeout": timeout})
        if self._exc is not None:
            raise self._exc
        return self._response

    async def post(self, url: str, json: Any = None) -> Any:
        self.calls.append({"url": url, "json": json})
        if self._exc is not None:
            raise self._exc
        return self._response

    async def aclose(self) -> None:
        pass


class FakePool:
    def __init__(
        self,
        rows: list[dict] | None = None,
        fetch_error: Exception | None = None,
        execute_error: Exception | None = None,
    ) -> None:
        self._rows = rows or []
        self._fetch_error = fetch_error
        self._execute_error = execute_error
        self.calls: list[tuple[str, str, tuple]] = []

    async def fetch(self, sql: str, *params: Any) -> list[dict]:
        self.calls.append(("fetch", sql, params))
        if self._fetch_error is not None:
            raise self._fetch_error
        return self._rows

    async def execute(self, sql: str, *params: Any) -> str:
        self.calls.append(("execute", sql, params))
        if self._execute_error is not None:
            raise self._execute_error
        return "OK"

    async def close(self) -> None:
        pass


class MissingStoreError(Exception):
    sqlstate = "42P01"


def make_store(
    pool: FakePool,
    embed_responses: list[FakeResponse] | None = None,
    embed_exc: Exception | None = None,
) -> MemoryStore:
    session = FakeHttp(response=None, exc=embed_exc)
    if embed_responses is not None:
        session = FakeEmbedSession(embed_responses)
    store = MemoryStore(
        user_id="clara",
        collection="clara_memories",
        pg_host="h",
        pg_port=5432,
        pg_database="d",
        pg_user="u",
        pg_password=_PG_PASSWORD,
        embed_base_url="http://embed/v1",
        embed_model="test-embed",
        embed_dims=2,
        dedup_threshold=0.96,
        pool=pool,
        session=session,
    )
    store._test_embed = session  # type: ignore[attr-defined]
    return store


class FakeEmbedSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def post(self, url: str, json: Any = None, headers: dict | None = None, timeout: Any = None) -> FakeResponse:
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        return self._responses.pop(0)

    async def aclose(self) -> None:
        pass


def embed_response(vector: list[float] | None = None, status: int = 200, body: str = "") -> FakeResponse:
    if vector is not None:
        body = json.dumps({"data": [{"embedding": vector}]})
    return FakeResponse(status_code=status, body=body.encode("utf-8"))


# --- model discovery -----------------------------------------------------------


@pytest.mark.asyncio
async def test_discover_models_uses_openai_endpoint_and_preserves_reported_order() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://llm/v1/models"
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={"data": [{"id": "model-b"}, {"id": "model-a"}, {"id": "model-b"}, {"missing": "id"}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await discover_models("http://llm/v1/", "test-key", client=client) == ["model-b", "model-a"]


@pytest.mark.asyncio
async def test_discover_models_reports_endpoint_errors() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(503, text="offline"))
    ) as client:
        with pytest.raises(LLMError, match="Could not list models"):
            await discover_models("http://llm/v1", "", client=client)


# --- substitute ----------------------------------------------------------------


class TestSubstitute:
    def test_string_values_inserted_verbatim(self) -> None:
        assert substitute("Hello {{name}}", {"name": "World"}) == "Hello World"

    def test_non_string_values_json_stringified_compact(self) -> None:
        assert substitute("{{a}}", {"a": {"b": [1, 2]}}) == '{"b":[1,2]}'

    def test_non_string_unicode_not_escaped(self) -> None:
        assert substitute("{{a}}", {"a": {"s": "héllo"}}) == '{"s":"héllo"}'

    def test_missing_placeholder_untouched(self) -> None:
        assert substitute("keep {{missing}}", {}) == "keep {{missing}}"

    def test_multiple_occurrences_replaced(self) -> None:
        assert substitute("{{x}}-{{x}}", {"x": "1"}) == "1-1"


# --- parse_json_output ----------------------------------------------------------


class TestParseJsonOutput:
    def test_plain_json(self) -> None:
        assert parse_json_output('{"a": 1}') == {"a": 1}

    def test_fenced_json(self) -> None:
        assert parse_json_output('```json\n{"a": 1}\n```') == {"a": 1}

    def test_fenced_bare(self) -> None:
        assert parse_json_output("```\n[1, 2]\n```") == [1, 2]

    def test_embedded_json(self) -> None:
        assert parse_json_output('Here you go: {"a": 1} hope that helps') == {"a": 1}

    def test_repair_trailing_comma(self) -> None:
        assert parse_json_output('{"a": 1,}') == {"a": 1}

    def test_repair_treats_leading_zero_number_as_string_like_clara(self) -> None:
        assert parse_json_output('{"rating": 01}') == {"rating": "01"}

    def test_malformed_non_json_raises_decode_error(self) -> None:
        with pytest.raises(json.JSONDecodeError):
            parse_json_output("no json here at all")

    def test_empty_raises(self) -> None:
        with pytest.raises(AIPipelineError, match="Step produced no output"):
            parse_json_output("   ")

    def test_strip_json_fence_no_fence(self) -> None:
        assert strip_json_fence('{"a":1}') == '{"a":1}'


# --- tool call accumulator -------------------------------------------------------


class TestToolCallAccumulator:
    def test_missing_index_falls_back_to_last(self) -> None:
        # Parity: a delta with no index is attributed to the last-seen index
        # (qwen3.8-27b quirk), so it merges into the same call bucket.
        acc = _ToolCallAccumulator()
        acc.add({"index": 0, "id": "c1", "function": {"name": "a", "arguments": '{"x": 1'}})
        acc.add({"id": "c2", "function": {"name": "b", "arguments": "}"}})
        result = acc.result()
        assert len(result) == 1
        assert result[0]["id"] == "c2"  # last id wins
        assert result[0]["name"] == "ab"
        assert result[0]["arguments"] == '{"x": 1}'

    def test_explicit_index_starts_new_call(self) -> None:
        acc = _ToolCallAccumulator()
        acc.add({"index": 0, "id": "c1", "function": {"name": "a", "arguments": "{}"}})
        acc.add({"index": 1, "id": "c2", "function": {"name": "b", "arguments": "{}"}})
        assert [c["id"] for c in acc.result()] == ["c1", "c2"]

    def test_name_split_across_chunks(self) -> None:
        acc = _ToolCallAccumulator()
        acc.add({"index": 0, "id": "c1", "function": {"name": "read", "arguments": '{"pat'}})
        acc.add({"index": 0, "function": {"name": "_file", "arguments": 'h": "a.txt"}'}})
        result = acc.result()
        assert result[0]["name"] == "read_file"
        assert result[0]["arguments"] == '{"path": "a.txt"}'

    def test_missing_id_gets_acc_prefix(self) -> None:
        acc = _ToolCallAccumulator()
        acc.add({"index": 0, "function": {"name": "a", "arguments": "{}"}})
        result = acc.result()
        assert result[0]["id"].startswith("acc-")

    def test_empty_arguments_become_empty_object(self) -> None:
        acc = _ToolCallAccumulator()
        acc.add({"index": 0, "id": "c1", "function": {"name": "a"}})
        assert acc.result()[0]["arguments"] == "{}"

    def test_nameless_call_dropped(self) -> None:
        acc = _ToolCallAccumulator()
        acc.add({"index": 0, "id": "c1", "function": {"arguments": "{}"}})
        acc.add({"index": 1, "id": "c2", "function": {"name": "b", "arguments": "{}"}})
        assert [c["name"] for c in acc.result()] == ["b"]

    def test_result_sorted_by_index(self) -> None:
        acc = _ToolCallAccumulator()
        acc.add({"index": 2, "id": "c3", "function": {"name": "c", "arguments": "{}"}})
        acc.add({"index": 0, "id": "c1", "function": {"name": "a", "arguments": "{}"}})
        assert [c["id"] for c in acc.result()] == ["c1", "c3"]


# --- repeat detector --------------------------------------------------------------


class TestRepeatDetector:
    def test_detects_exact_repeat(self) -> None:
        detector = _ExactRepeatDetector(256 * 1024, 30)
        for _ in range(31):
            detector.append(b"ab")
        assert detector.scan() == 2

    def test_no_repeat(self) -> None:
        detector = _ExactRepeatDetector(256 * 1024, 30)
        detector.append(b"the quick brown fox jumps over the lazy dog")
        assert detector.scan() == 0

    def test_window_truncation(self) -> None:
        detector = _ExactRepeatDetector(100, 3)
        detector.append(b"x" * 90)
        detector.append(b"ab" * 15)
        assert len(detector._buf) == 100
        assert detector.scan() == 2


# --- tool result helpers ------------------------------------------------------------


class TestToolResultHelpers:
    def test_string_result_passthrough(self) -> None:
        assert tool_result_to_text("plain") == "plain"

    def test_dict_with_data(self) -> None:
        out = tool_result_to_text({"text": "t", "data": {"a": 1}})
        assert out == 't\n[data]\n{\n  "a": 1\n}'

    def test_dict_with_artifacts(self) -> None:
        out = tool_result_to_text({"text": "t", "artifacts": ["a.md"]})
        assert out == 't\n[artifacts]\n[\n  "a.md"\n]'

    def test_empty_text_filtered(self) -> None:
        assert tool_result_to_text({"text": ""}) == ""


# --- path expansion -------------------------------------------------------------------


class TestExpandPath:
    def test_task_cwd_placeholder(self, tmp_path: Path) -> None:
        assert expand_path("TASK_CWD/a.md", ai_data_dir=None, work_root=tmp_path) == str(tmp_path / "a.md")

    def test_task_cwd_call_no_args(self, tmp_path: Path) -> None:
        assert expand_path("Task_CWD()/x", ai_data_dir=None, work_root=tmp_path) == str(tmp_path / "x")

    def test_shell_env_offset_preserved(self, tmp_path: Path) -> None:
        assert expand_path("$TASK_CWD/a", ai_data_dir=None, work_root=tmp_path) == "$TASK_CWD/a"
        assert expand_path("${TASK_CWD}/a", ai_data_dir=None, work_root=tmp_path) == "${TASK_CWD}/a"

    def test_explicit_task_id_uses_named_task_working_directory(self, tmp_path: Path) -> None:
        current = tmp_path / "current"
        assert expand_path('Task_CWD("x")/a', ai_data_dir=None, work_root=current) == str(tmp_path / "x" / "a")

    def test_home_shorthand(self, tmp_path: Path) -> None:
        assert expand_path("~/a", ai_data_dir=None, work_root=tmp_path) == str(Path.home() / "a")

    def test_at_shorthand(self) -> None:
        assert expand_path("@/a/b", ai_data_dir=Path("/data"), work_root=None) == "/data/a/b"

    def test_at_shorthand_without_data_dir(self) -> None:
        with pytest.raises(AIPipelineError, match="@/ path shorthand requires an AI data dir"):
            expand_path("@/a", ai_data_dir=None, work_root=None)

    def test_task_cwd_without_work_root(self) -> None:
        with pytest.raises(AIPipelineError, match="require a task execution context"):
            expand_path("TASK_CWD/a", ai_data_dir=None, work_root=None)

    def test_expand_paths_nested(self) -> None:
        out = expand_paths({"a": ["TASK_CWD/x", 1, {"b": "TASK_CWD/y"}]}, ai_data_dir=None, work_root=Path("/w"))
        assert out == {"a": ["/w/x", 1, {"b": "/w/y"}]}


# --- system prompt ----------------------------------------------------------------------


class TestBuildSystemPrompt:
    def test_shape(self) -> None:
        prompt = build_system_prompt("/data", "analyze-security", "/work")
        lines = prompt.split("\n")
        assert len(lines) == 3
        assert re.fullmatch(
            r"Today's date and time is \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} "
            r"\((Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\)\.",
            lines[0],
        )
        assert lines[1] == (
            "Your profile workspace is /data. Use @/ for Sentinel's data root and ~/ for the home directory."
        )
        assert lines[2] == (
            "Current task: analyze-security. During this task, TASK_CWD and Task_CWD() expand to /work, and "
            'Task_CWD("task-id") expands to another task\'s working directory.'
        )


# --- rate limit delay ---------------------------------------------------------------------


class TestRateLimitDelay:
    def test_retry_after_ms(self) -> None:
        assert _rate_limit_delay_ms(httpx.Headers({"retry-after-ms": "1234"}), 0) == 1234.0

    def test_retry_after_ms_zero(self) -> None:
        assert _rate_limit_delay_ms(httpx.Headers({"retry-after-ms": "0"}), 3) == 0.0

    def test_retry_after_ms_negative_falls_through(self) -> None:
        assert _rate_limit_delay_ms(httpx.Headers({"retry-after-ms": "-5"}), 0) == 5000.0

    def test_retry_after_seconds(self) -> None:
        assert _rate_limit_delay_ms(httpx.Headers({"retry-after": "2.5"}), 0) == 2500.0

    def test_retry_after_past_date(self) -> None:
        assert _rate_limit_delay_ms(httpx.Headers({"retry-after": "Wed, 21 Oct 2015 07:28:00 GMT"}), 0) == 0.0

    def test_retry_after_future_date(self) -> None:
        delay = _rate_limit_delay_ms(httpx.Headers({"retry-after": "Wed, 02 Jan 2126 00:00:00 GMT"}), 0)
        assert delay > 1e9

    def test_retry_after_garbage(self) -> None:
        assert _rate_limit_delay_ms(httpx.Headers({"retry-after": "garbage"}), 0) == 5000.0

    def test_ratelimit_remaining_zero(self) -> None:
        assert _rate_limit_delay_ms(httpx.Headers({"x-ratelimit-remaining-tokens-minute": "0"}), 0) == 65000.0

    def test_ratelimit_limit_present(self) -> None:
        assert _rate_limit_delay_ms(httpx.Headers({"x-ratelimit-limit-tokens-minute": "100"}), 0) == 65000.0

    def test_backoff_schedule(self) -> None:
        assert _rate_limit_delay_ms(httpx.Headers({}), 0) == 5000.0
        assert _rate_limit_delay_ms(httpx.Headers({}), 1) == 10000.0
        assert _rate_limit_delay_ms(httpx.Headers({}), 3) == 40000.0
        assert _rate_limit_delay_ms(httpx.Headers({}), 10) == 65000.0


# --- chat end-to-end -----------------------------------------------------------------------


class TestChat:
    @pytest.mark.asyncio
    async def test_plain_chat_request_shape(self) -> None:
        client = make_client([content_stream("Hello world")])
        result = await client.chat("Hi", system="sys prompt")
        assert result.content == "Hello world"
        req = client._test_session.requests[0]  # type: ignore[attr-defined]
        body = req["json"]
        assert body["model"] == "test-model"
        assert body["stream"] is True
        assert "max_tokens" not in body
        assert "tool_choice" not in body
        assert "top_p" not in body
        assert "temperature" not in body
        assert body["messages"] == [{"role": "system", "content": "sys prompt"}, {"role": "user", "content": "Hi"}]
        assert req["headers"]["Authorization"] == "Bearer test-key"
        assert req["url"] == "http://llm/v1/chat/completions"

    @pytest.mark.asyncio
    async def test_temperature_included_when_set(self) -> None:
        client = make_client([content_stream("ok")])
        await client.chat("Hi", temperature=0.2)
        assert client._test_session.requests[0]["json"]["temperature"] == 0.2  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_chat_history_is_inserted_before_the_new_user_message(self) -> None:
        client = make_client([content_stream("ok")])
        history = [
            {"role": "user", "content": "Earlier question"},
            {"role": "assistant", "content": "Earlier answer"},
        ]

        await client.chat("Follow-up", system="sys", history=history)

        messages = client._test_session.requests[0]["json"]["messages"]  # type: ignore[attr-defined]
        assert messages == [
            {"role": "system", "content": "sys"},
            *history,
            {"role": "user", "content": "Follow-up"},
        ]

    @pytest.mark.asyncio
    async def test_tool_loop_executes_and_finalizes(self) -> None:
        async def fake_read(args: dict) -> str:
            assert args == {"path": "a.txt"}
            return "FILE-CONTENT"

        client = make_client(
            [
                tool_call_stream("read_file", '{"path": "a.txt"}', content="Let me check.\n"),
                content_stream("File says hi"),
            ]
        )
        result = await client.chat("Read it", tools=[{"type": "function"}], executors={"read_file": fake_read})
        assert result.content == "File says hi"
        messages = client._test_session.requests[1]["json"]["messages"]  # type: ignore[attr-defined]
        assert messages[0] == {"role": "user", "content": "Read it"}
        tool_call = {
            "id": "call_1",
            "type": "function",
            "function": {"name": "read_file", "arguments": '{"path": "a.txt"}'},
        }
        assert messages[1] == {
            "role": "assistant",
            "content": "Let me check.\n",
            "tool_calls": [tool_call],
        }
        assert messages[2] == {"role": "tool", "tool_call_id": "call_1", "content": "FILE-CONTENT"}

    @pytest.mark.asyncio
    async def test_unknown_tool_becomes_tool_content(self) -> None:
        client = make_client(
            [
                tool_call_stream("nope", "{}"),
                content_stream("done"),
            ]
        )
        result = await client.chat("x")
        assert result.content == "done"
        messages = client._test_session.requests[1]["json"]["messages"]  # type: ignore[attr-defined]
        assert messages[2]["content"] == 'Tool "nope" not found in any connected MCP server'

    @pytest.mark.asyncio
    async def test_malformed_arguments_become_tool_content(self) -> None:
        client = make_client(
            [
                tool_call_stream("read_file", "not json"),
                content_stream("done"),
            ]
        )
        await client.chat("x")
        messages = client._test_session.requests[1]["json"]["messages"]  # type: ignore[attr-defined]
        assert messages[2]["content"] == "Error: malformed arguments: not json"

    @pytest.mark.asyncio
    async def test_tool_exception_wrapped(self) -> None:
        async def boom(args: dict) -> str:
            raise RuntimeError("kaboom")

        client = make_client(
            [
                tool_call_stream("read_file", "{}"),
                content_stream("done"),
            ]
        )
        await client.chat("x", executors={"read_file": boom})
        messages = client._test_session.requests[1]["json"]["messages"]  # type: ignore[attr-defined]
        assert messages[2]["content"] == 'Error running tool "read_file": kaboom'

    @pytest.mark.asyncio
    async def test_tool_result_is_not_capped_for_task_path(self) -> None:
        async def big(args: dict) -> str:
            return "y" * 70000

        client = make_client(
            [
                tool_call_stream("read_file", "{}"),
                content_stream("done"),
            ]
        )
        await client.chat("x", executors={"read_file": big})
        messages = client._test_session.requests[1]["json"]["messages"]  # type: ignore[attr-defined]
        assert messages[2]["content"] == "y" * 70000

    @pytest.mark.asyncio
    async def test_empty_final_turn_retries_without_adding_an_empty_assistant_message(self) -> None:
        client = make_client(
            [
                FakeResponse(lines=sse_lines([{"choices": [{"delta": {"reasoning_content": "thinking"}}]}])),
                content_stream("recovered"),
            ]
        )

        result = await client.chat("x")

        assert result.content == "recovered"
        requests = client._test_session.requests  # type: ignore[attr-defined]
        assert len(requests) == 2
        assert requests[1]["json"]["messages"] == requests[0]["json"]["messages"]

    @pytest.mark.asyncio
    async def test_empty_final_turn_after_tool_reuses_history_without_rerunning_tool(self) -> None:
        calls = 0

        async def execute(_args: dict) -> str:
            nonlocal calls
            calls += 1
            return ""

        client = make_client(
            [
                tool_call_stream("read_file", "{}"),
                FakeResponse(lines=sse_lines([])),
                content_stream("recovered"),
            ]
        )

        result = await client.chat("x", executors={"read_file": execute})

        assert result.content == "recovered"
        assert calls == 1
        requests = client._test_session.requests  # type: ignore[attr-defined]
        assert requests[2]["json"]["messages"] == requests[1]["json"]["messages"]

    @pytest.mark.asyncio
    async def test_max_rounds_exceeded_raises(self) -> None:
        client = make_client(
            [
                tool_call_stream("read_file", "{}", call_id="c1"),
                tool_call_stream("read_file", "{}", call_id="c2"),
            ],
            max_rounds=1,
        )

        async def noop(args: dict) -> str:
            return "ok"

        with pytest.raises(LLMError, match="exceeded 1 rounds"):
            await client.chat("x", executors={"read_file": noop})


class TestRateLimitRetry:
    @pytest.mark.asyncio
    async def test_429_retries_with_header_delay(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sleeps: list[float] = []

        async def fake_sleep(delay: float) -> None:
            sleeps.append(delay)

        monkeypatch.setattr(llm.asyncio, "sleep", fake_sleep)
        client = make_client(
            [
                FakeResponse(status_code=429, headers={"retry-after-ms": "1234"}),
                content_stream("recovered"),
            ]
        )
        result = await client.chat("x")
        assert result.content == "recovered"
        assert sleeps == [1.234]
        assert len(client._test_session.requests) == 2  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_429_exhausted_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def fake_sleep(delay: float) -> None:
            pass

        monkeypatch.setattr(llm.asyncio, "sleep", fake_sleep)
        responses = [FakeResponse(status_code=429) for _ in range(9)]
        client = make_client(responses)
        with pytest.raises(LLMError, match="rate limited after 8 retries"):
            await client.chat("x")
        assert len(client._test_session.requests) == 9  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_server_error_includes_body(self) -> None:
        client = make_client([FakeResponse(status_code=500, body=b'{"error": "boom"}')])
        with pytest.raises(LLMError, match="LLM request failed with 500:"):
            await client.chat("x")


class TestLoopGuard:
    @pytest.mark.asyncio
    async def test_loop_triggers_corrective_retry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(llm, "LOOP_CHECK_INTERVAL_S", 0.0)
        loop_lines = sse_lines([{"choices": [{"delta": {"content": "ab"}}]} for _ in range(31)])
        client = make_client(
            [
                FakeResponse(lines=loop_lines),
                content_stream("Done."),
            ]
        )
        result = await client.chat("x")
        assert result.content == "Done."
        second_messages = client._test_session.requests[1]["json"]["messages"]  # type: ignore[attr-defined]
        assert second_messages[-1]["role"] == "user"
        assert second_messages[-1]["content"].startswith("[INTERRUPT - automated Clara notice] The previous attempt")

    @pytest.mark.asyncio
    async def test_loop_exhaustion_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(llm, "LOOP_CHECK_INTERVAL_S", 0.0)
        loop_lines = sse_lines([{"choices": [{"delta": {"content": "ab"}}]} for _ in range(31)])
        client = make_client([FakeResponse(lines=loop_lines) for _ in range(4)])
        with pytest.raises(LLMError, match="output loop detected"):
            await client.chat("x")
        assert len(client._test_session.requests) == 4  # type: ignore[attr-defined]


class TestRunPrompt:
    @pytest.mark.asyncio
    async def test_bare_template_with_context(self, tmp_path: Path) -> None:
        prompt = tmp_path / "p.md"
        prompt.write_text("Hello {{name}}", encoding="utf-8")
        client = make_client([content_stream("Hello world")])
        out = await run_prompt(client, str(prompt), task_id="t1", task_cwd=tmp_path, context={"name": "world"})
        assert out == "Hello world"
        body = client._test_session.requests[0]["json"]  # type: ignore[attr-defined]
        assert body["messages"][0]["role"] == "system"
        assert "Current task: t1" in body["messages"][0]["content"]
        assert str(tmp_path) in body["messages"][0]["content"]
        assert body["messages"][1] == {"role": "user", "content": "Hello world"}

    @pytest.mark.asyncio
    async def test_as_json_parses_fenced_output(self, tmp_path: Path) -> None:
        prompt = tmp_path / "p.md"
        prompt.write_text("answer", encoding="utf-8")
        client = make_client([content_stream('```json\n{"a": 1}\n```')])
        out = await run_prompt(client, str(prompt), task_id="t1", task_cwd=tmp_path, as_json=True)
        assert out == {"a": 1}

    @pytest.mark.asyncio
    async def test_falls_back_to_last_tool_result(self, tmp_path: Path) -> None:
        # Turn 1: tool call. Turn 2: empty content, no tool calls -> loop ends.
        client = make_client([tool_call_stream("read_file", '{"path": "x"}'), content_stream("")])

        class _FakeExec:
            def get(self, name: str):
                async def exec(_args: dict) -> str:
                    return "FROM-TOOL"

                return exec

        result = await client.chat("go", tools=TOOL_DEFINITIONS, executors=_FakeExec(), work_root=tmp_path)
        assert result.content == ""
        assert result.last_tool_result == "FROM-TOOL"

    @pytest.mark.asyncio
    async def test_no_output_raises(self, tmp_path: Path) -> None:
        prompt = tmp_path / "empty.md"
        prompt.write_text("go", encoding="utf-8")
        client = make_client([FakeResponse(lines=sse_lines([])) for _ in range(3)])
        with pytest.raises(AIPipelineError, match='Prompt ".*empty\\.md" produced no output'):
            await run_prompt(client, str(prompt), task_id="t1", task_cwd=tmp_path)
        assert len(client._test_session.requests) == 3  # type: ignore[attr-defined]


# --- tool definitions ------------------------------------------------------------------------


class TestToolDefinitions:
    def test_four_tools_in_order(self) -> None:
        names = [t["function"]["name"] for t in TOOL_DEFINITIONS]
        assert names == ["read_file", "write_file", "read_url", "searxng_web_search"]

    def test_all_function_type(self) -> None:
        assert all(t["type"] == "function" for t in TOOL_DEFINITIONS)

    def test_searxng_definition_pinned(self) -> None:
        searxng = TOOL_DEFINITIONS[3]["function"]
        assert searxng["description"] == "External MCP tool searxng_web_search from searxng."
        props = searxng["parameters"]["properties"]
        assert props["safesearch"]["enum"] == ["0", "1", "2"]
        assert props["time_range"]["enum"] == ["day", "week", "month", "year"]
        assert props["response_format"]["enum"] == ["text", "json"]
        assert props["result_detail"]["enum"] == ["compact", "full"]
        assert searxng["parameters"]["required"] == ["query"]
        assert "description" not in props["query"]

    def test_read_url_required(self) -> None:
        assert TOOL_DEFINITIONS[2]["function"]["parameters"]["required"] == ["url"]


# --- search args validation -------------------------------------------------------------------


class TestValidateSearchArgs:
    def test_minimal_valid(self) -> None:
        assert validate_search_args({"query": "x"}) is True

    def test_full_valid(self) -> None:
        args = {
            "query": "x",
            "pageno": 2,
            "time_range": "year",
            "language": "el",
            "safesearch": "2",
            "min_score": 0.5,
            "num_results": 20,
            "categories": "news",
            "engines": "google",
            "response_format": "json",
            "result_detail": "compact",
        }
        assert validate_search_args(args) is True

    @pytest.mark.parametrize(
        "args",
        [
            None,
            "x",
            {},
            {"query": 5},
            {"query": "x", "pageno": 0},
            {"query": "x", "pageno": 1.5},
            {"query": "x", "pageno": True},
            {"query": "x", "pageno": float("nan")},
            {"query": "x", "time_range": "decade"},
            {"query": "x", "language": 123},
            {"query": "x", "safesearch": "3"},
            {"query": "x", "safesearch": True},
            {"query": "x", "min_score": 1.5},
            {"query": "x", "min_score": "0.5"},
            {"query": "x", "min_score": float("nan")},
            {"query": "x", "num_results": 0},
            {"query": "x", "num_results": 21},
            {"query": "x", "num_results": 0.5},
            {"query": "x", "response_format": "xml"},
            {"query": "x", "result_detail": "brief"},
            {"query": "x", "categories": 5},
            {"query": "x", "engines": 5},
        ],
    )
    def test_invalid(self, args: Any) -> None:
        assert validate_search_args(args) is False

    def test_numeric_safesearch_accepted(self) -> None:
        assert validate_search_args({"query": "x", "safesearch": 1}) is True


# --- build_search_url ----------------------------------------------------------------------------


class TestBuildSearchUrl:
    def test_parameter_order(self) -> None:
        url = build_search_url(
            "http://127.0.0.1:8888",
            query="Greece banks",
            pageno=2,
            time_range="year",
            language="el",
            safesearch=1,
            categories="news",
            engines="google",
        )
        assert url == (
            "http://127.0.0.1:8888/search?q=Greece+banks&format=json&pageno=2"
            "&time_range=year&language=el&safesearch=1&categories=news&engines=google"
        )

    def test_base_with_trailing_slash(self) -> None:
        url = build_search_url(
            "http://h:1/",
            query="q",
            pageno=1,
            time_range=None,
            language=None,
            safesearch=None,
            categories=None,
            engines=None,
        )
        assert url == "http://h:1/search?q=q&format=json&pageno=1"

    def test_base_with_path(self) -> None:
        url = build_search_url(
            "http://h/sx",
            query="q",
            pageno=1,
            time_range=None,
            language=None,
            safesearch=None,
            categories=None,
            engines=None,
        )
        assert url == "http://h/sx/search?q=q&format=json&pageno=1"

    def test_language_all_omitted(self) -> None:
        url = build_search_url(
            "http://h",
            query="q",
            pageno=1,
            time_range=None,
            language="all",
            safesearch=None,
            categories=None,
            engines=None,
        )
        assert "language" not in url

    def test_bad_time_range_omitted(self) -> None:
        url = build_search_url(
            "http://h",
            query="q",
            pageno=1,
            time_range="decade",
            language=None,
            safesearch=None,
            categories=None,
            engines=None,
        )
        assert "time_range" not in url

    def test_blank_categories_omitted(self) -> None:
        url = build_search_url(
            "http://h",
            query="q",
            pageno=1,
            time_range=None,
            language=None,
            safesearch=None,
            categories="   ",
            engines="",
        )
        assert "categories" not in url and "engines" not in url

    def test_normalize_helpers(self) -> None:
        assert _normalize_time_range("month") == "month"
        assert _normalize_time_range("decade") is None
        assert _normalize_language("el") == "el"
        assert _normalize_language("all") is None
        assert _normalize_language("") is None
        assert _normalize_safesearch(1) == "1"
        assert _normalize_safesearch("2") == "2"
        assert _normalize_safesearch(3) is None
        assert _normalize_safesearch("abc") is None
        assert _normalize_safesearch(None) is None


# --- search response formatting -------------------------------------------------------------------


class TestFormatSearchResponse:
    def test_json_compact(self) -> None:
        out = format_search_response(
            {"results": [{"title": "t", "url": "u", "content": "c"}]},
            query="q",
            results=[{"title": "t", "url": "u", "content": "c", "score": 1.0, "extra": "gone"}],
            response_format="json",
            result_detail="compact",
        )
        expected = {"results": [{"title": "t", "url": "u", "content": "c"}]}
        assert out == json.dumps(expected, indent=2, ensure_ascii=False)

    def test_json_full_spreads_data_and_overrides_results(self) -> None:
        data = {"q": "q", "results": [{"old": 1}], "number": 1}
        out = format_search_response(
            data,
            query="q",
            results=[{"new": 2}],
            response_format="json",
            result_detail="full",
        )
        parsed = json.loads(out)
        assert list(parsed.keys()) == ["q", "results", "number"]
        assert parsed["results"] == [{"new": 2}]

    def test_text_full_all_fields(self) -> None:
        r = {
            "title": "T\n1",
            "content": "desc",
            "url": "http://x",
            "score": 0.1234,
            "engines": ["a", "b", ""],
            "category": "general",
            "publishedDate": "2024-01-01",
            "thumbnail": "http://img",
            "img_src": "http://img2",
        }
        out = format_search_response(
            {"results": [r]},
            query="q",
            results=[r],
            response_format="text",
            result_detail="full",
        )
        assert out == (
            "Title: T 1\nDescription: desc\nURL: http://x\nRelevance Score: 0.123\n"
            "Engines: a, b\nCategory: general\nPublished Date: 2024-01-01\n"
            "Thumbnail: http://img\nImage Source: http://img2"
        )

    def test_text_compact(self) -> None:
        r = {"title": "t", "content": "c", "url": "u", "score": 0.9}
        out = format_search_response(
            {"results": [r]},
            query="q",
            results=[r],
            response_format="text",
            result_detail="compact",
        )
        assert out == "Title: t\nDescription: c\nURL: u"

    def test_no_results_full_with_metadata(self) -> None:
        data = {"results": [], "answers": ["42"], "suggestions": ["a", "b"]}
        out = format_search_response(
            data,
            query="q1",
            results=[],
            response_format="text",
            result_detail="full",
        )
        assert out == (
            "Direct answer: 42\n\nSuggestions: a, b\n\n---\n\n"
            '🔍 No results found for "q1". Try different search terms or check if SearXNG search engines are working.'
        )

    def test_no_results_compact_no_leading(self) -> None:
        out = format_search_response(
            {"results": []},
            query="q1",
            results=[],
            response_format="text",
            result_detail="compact",
        )
        expected = (
            '🔍 No results found for "q1". Try different search terms or check if SearXNG search engines are working.'
        )
        assert out == expected

    def test_metadata_sections(self) -> None:
        data = {
            "results": [],
            "corrections": ["typo"],
            "infoboxes": [
                {
                    "infobox": "Greece",
                    "content": "A country",
                    "urls": [{"title": "Wikipedia", "url": "https://en.wikipedia.org/wiki/Greece"}],
                }
            ],
        }
        out = format_search_response(data, query="q", results=[], response_format="text", result_detail="full")
        leading = out.split("\n\n---\n\n")[0]
        assert leading == (
            'Spelling correction: did you mean "typo"?\n\n'
            "Infobox: Greece\nA country\nWikipedia: https://en.wikipedia.org/wiki/Greece"
        )


# --- searxng error constructors ----------------------------------------------------------------------


class TestSearxngErrors:
    def test_server_errors(self) -> None:
        expected_403 = "🚫 SearXNG server Error (403): Authentication required or IP blocked"
        assert str(_server_error(403, "Forbidden")) == expected_403
        assert str(_server_error(404, "Not Found")) == "🚫 SearXNG server Error (404): Search endpoint not found"
        assert str(_server_error(429, "Too Many Requests")) == "🚫 SearXNG server Error (429): Rate limit exceeded"
        assert str(_server_error(502, "Bad Gateway")) == "🚫 SearXNG server Error (502): Internal server error"
        assert str(_server_error(418, "I'm a teapot")) == "🚫 SearXNG server Error (418): I'm a teapot"

    def test_json_error_preview(self) -> None:
        body = ("x" * 120) + "\n" + "y"
        msg = str(_json_error(body))
        assert msg.startswith('🔍 SearXNG Response Error: Invalid JSON format. Response: "')
        assert "x" * 100 in msg
        assert "y" not in msg.split('"')[1]
        expected_suffix = (
            '". Enable - json under search.formats in your SearXNG settings.yml, or set SEARXNG_HTML_FALLBACK=true.'
        )
        assert msg.endswith(expected_suffix)

    def test_json_error_newline_only_replacement(self) -> None:
        body = "a\nb\rc"
        msg = str(_json_error(body))
        assert 'Response: "a b\\rc"' in msg.replace("a b\rc", "a b\\rc") or "a b" in msg

    def test_network_error_refused(self) -> None:
        exc = httpx.ConnectError("[Errno 111] Connection refused")
        msg = str(_network_error(exc, "http://h/search"))
        assert msg == "🌐 Connection Error: SearXNG server is not responding (http://h/search)"

    def test_network_error_dns(self) -> None:
        exc = httpx.ConnectError("[Errno -3] Temporary failure in name resolution")
        msg = str(_network_error(exc, "http://badhost/search"))
        assert msg == '🌐 DNS Error: Cannot resolve hostname "badhost"'

    def test_network_error_timeout(self) -> None:
        exc = httpx.ReadTimeout("timed out")
        assert str(_network_error(exc, "http://h/search")) == "🌐 Timeout Error: SearXNG server is too slow to respond"

    def test_network_error_generic(self) -> None:
        exc = httpx.ConnectError("boom")
        msg = str(_network_error(exc, "http://h/search"))
        expected = (
            "🌐 Network Error: fetch failed. Check if the SEARXNG_URL is correct and the SearXNG server is available"
        )
        assert msg == expected


# --- file executors ---------------------------------------------------------------------------------


class TestReadFile:
    @pytest.mark.asyncio
    async def test_reads_raw_utf8(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "a.txt"
        target.write_text("héllo\n", encoding="utf-8")
        ex = make_tool_executors(None, None, None)
        try:
            assert await ex.get("read_file")({"path": str(target)}) == "héllo\n"
        finally:
            await ex.aclose()

    @pytest.mark.asyncio
    async def test_relative_resolves_against_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        (tmp_path / "rel.txt").write_text("rel", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        ex = make_tool_executors(None, None, None)
        try:
            assert await ex.get("read_file")({"path": "rel.txt"}) == "rel"
        finally:
            await ex.aclose()

    @pytest.mark.asyncio
    async def test_validation(self, tmp_path: Path) -> None:
        ex = make_tool_executors(None, None, None)
        try:
            with pytest.raises(AIPipelineError, match="path must be a string"):
                await ex.get("read_file")({})
            with pytest.raises(AIPipelineError, match="path must be a string"):
                await ex.get("read_file")({"path": 5})
            with pytest.raises(AIPipelineError, match="path is required"):
                await ex.get("read_file")({"path": "   "})
        finally:
            await ex.aclose()


class TestWriteFile:
    @pytest.mark.asyncio
    async def test_writes_relative_to_work_root(self, tmp_path: Path) -> None:
        ex = make_tool_executors(None, None, tmp_path)
        try:
            out = await ex.get("write_file")({"path": "a.txt", "content": "hello"})
            assert out == "OK - wrote 5 bytes to a.txt"
            assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "hello"
        finally:
            await ex.aclose()

    @pytest.mark.asyncio
    async def test_utf16_byte_count_for_emoji(self, tmp_path: Path) -> None:
        ex = make_tool_executors(None, None, tmp_path)
        try:
            out = await ex.get("write_file")({"path": "e.txt", "content": "a\U0001f600"})
            assert out == "OK - wrote 3 bytes to e.txt"
        finally:
            await ex.aclose()

    @pytest.mark.asyncio
    async def test_absolute_inside_allowed_and_echoed_raw(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        ex = make_tool_executors(None, None, tmp_path)
        try:
            target = str(sub / "x.txt")
            out = await ex.get("write_file")({"path": target, "content": "z"})
            assert out == f"OK - wrote 1 bytes to {target}"
            assert (sub / "x.txt").read_text(encoding="utf-8") == "z"
        finally:
            await ex.aclose()

    @pytest.mark.asyncio
    async def test_missing_parent_raises_file_not_found(self, tmp_path: Path) -> None:
        ex = make_tool_executors(None, None, tmp_path)
        try:
            with pytest.raises(FileNotFoundError):
                await ex.get("write_file")({"path": "no/such/dir/a.txt", "content": "x"})
        finally:
            await ex.aclose()

    @pytest.mark.asyncio
    async def test_absolute_outside_rejected(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "outside.txt"
        ex = make_tool_executors(None, None, tmp_path)
        try:
            with pytest.raises(AIPipelineError, match="write_file path is outside the working directory"):
                await ex.get("write_file")({"path": str(outside), "content": "x"})
        finally:
            await ex.aclose()

    @pytest.mark.asyncio
    async def test_traversal_rejected(self, tmp_path: Path) -> None:
        ex = make_tool_executors(None, None, tmp_path)
        try:
            with pytest.raises(AIPipelineError, match="outside the working directory"):
                await ex.get("write_file")({"path": "../escape.txt", "content": "x"})
        finally:
            await ex.aclose()

    @pytest.mark.asyncio
    async def test_append_mode(self, tmp_path: Path) -> None:
        ex = make_tool_executors(None, None, tmp_path)
        try:
            await ex.get("write_file")({"path": "a.txt", "content": "one"})
            await ex.get("write_file")({"path": "a.txt", "content": "two", "append": True})
            assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "onetwo"
        finally:
            await ex.aclose()

    @pytest.mark.asyncio
    async def test_validation_order(self, tmp_path: Path) -> None:
        ex = make_tool_executors(None, None, tmp_path)
        try:
            with pytest.raises(AIPipelineError, match="path must be a string"):
                await ex.get("write_file")({"content": "x"})
            with pytest.raises(AIPipelineError, match="content must be a string"):
                await ex.get("write_file")({"path": "a.txt"})
            with pytest.raises(AIPipelineError, match="append must be a boolean"):
                await ex.get("write_file")({"path": "a.txt", "content": "x", "append": "yes"})
        finally:
            await ex.aclose()

    @pytest.mark.asyncio
    async def test_requires_work_root(self) -> None:
        ex = make_tool_executors(None, None, None)
        try:
            with pytest.raises(AIPipelineError, match="write_file requires a working directory"):
                await ex.get("write_file")({"path": "a.txt", "content": "x"})
        finally:
            await ex.aclose()


# --- read_url executor ---------------------------------------------------------------------------------


def summarizer_payload(**overrides: Any) -> dict:
    payload = {
        "ok": True,
        "url": "http://final.example/a",
        "cacheStatus": "hit",
        "status": "ok",
        "method": "fetch",
        "summary": "The summary.",
        "content": "The content.",
        "finalUrl": "http://final.example/b",
        "contentChars": 12,
    }
    payload.update(overrides)
    return payload


class TestReadUrl:
    @pytest.mark.asyncio
    async def test_request_body_always_sends_include_content(self) -> None:
        fake = FakeHttp(response=FakeHttpJson(summarizer_payload()))
        ex = make_tool_executors(None, "http://summ", None)
        ex._client = fake  # type: ignore[assignment]
        result = await ex.get("read_url")({"url": "http://x"})
        assert fake.calls[0]["url"] == "http://summ/v1/articles/read"
        assert fake.calls[0]["json"] == {"url": "http://x", "refresh": False, "includeContent": True}
        assert "## Content" not in result["text"]
        await ex.aclose()

    @pytest.mark.asyncio
    async def test_text_assembly_with_content(self) -> None:
        fake = FakeHttp(response=FakeHttpJson(summarizer_payload()))
        ex = make_tool_executors(None, "http://summ", None)
        ex._client = fake  # type: ignore[assignment]
        result = await ex.get("read_url")({"url": "http://x", "include_content": True, "refresh": True})
        assert fake.calls[0]["json"]["refresh"] is True
        assert result["text"] == (
            "URL: http://final.example/a\nCache: hit\n\n## Summary\nThe summary.\n\n## Content\nThe content."
        )
        assert result["data"] == {
            "url": "http://final.example/a",
            "cache_status": "hit",
            "final_url": "http://final.example/b",
            "status": "ok",
            "method": "fetch",
            "summary_chars": 12,
            "content_chars": 12,
        }
        await ex.aclose()

    @pytest.mark.asyncio
    async def test_empty_summary_forces_content(self) -> None:
        fake = FakeHttp(response=FakeHttpJson(summarizer_payload(summary="")))
        ex = make_tool_executors(None, "http://summ", None)
        ex._client = fake  # type: ignore[assignment]
        result = await ex.get("read_url")({"url": "http://x"})
        # Parity: empty summary skips the Summary heading, leaving the trailing
        # blank line + the content section's leading blank line (3 newlines total).
        assert result["text"] == "URL: http://final.example/a\nCache: hit\n\n\n## Content\nThe content."
        await ex.aclose()

    @pytest.mark.asyncio
    async def test_cache_status_default_miss(self) -> None:
        fake = FakeHttp(response=FakeHttpJson(summarizer_payload(cacheStatus="weird")))
        ex = make_tool_executors(None, "http://summ", None)
        ex._client = fake  # type: ignore[assignment]
        result = await ex.get("read_url")({"url": "http://x"})
        assert result["data"]["cache_status"] == "miss"
        await ex.aclose()

    @pytest.mark.asyncio
    async def test_ok_false_with_error(self) -> None:
        fake = FakeHttp(response=FakeHttpJson({"ok": False, "error": "read failed"}))
        ex = make_tool_executors(None, "http://summ", None)
        ex._client = fake  # type: ignore[assignment]
        with pytest.raises(AIPipelineError, match="read failed"):
            await ex.get("read_url")({"url": "http://x"})
        await ex.aclose()

    @pytest.mark.asyncio
    async def test_ok_false_falls_back_to_input_url(self) -> None:
        fake = FakeHttp(response=FakeHttpJson({"ok": False, "status": "blocked"}))
        ex = make_tool_executors(None, "http://summ", None)
        ex._client = fake  # type: ignore[assignment]
        with pytest.raises(AIPipelineError, match="could not read http://input: blocked"):
            await ex.get("read_url")({"url": "http://input"})
        await ex.aclose()

    @pytest.mark.asyncio
    async def test_http_error(self) -> None:
        fake = FakeHttp(response=FakeResponse(status_code=500, body=b"down"))
        ex = make_tool_executors(None, "http://summ", None)
        ex._client = fake  # type: ignore[assignment]
        with pytest.raises(AIPipelineError, match="URL summarizer returned HTTP 500: down"):
            await ex.get("read_url")({"url": "http://x"})
        await ex.aclose()

    @pytest.mark.asyncio
    async def test_non_object_payload(self) -> None:
        fake = FakeHttp(response=FakeHttpJson(["nope"]))
        ex = make_tool_executors(None, "http://summ", None)
        ex._client = fake  # type: ignore[assignment]
        with pytest.raises(AIPipelineError, match="non-object response"):
            await ex.get("read_url")({"url": "http://x"})
        await ex.aclose()

    @pytest.mark.asyncio
    async def test_base_checked_before_url(self) -> None:
        ex = make_tool_executors(None, None, None)
        try:
            with pytest.raises(AIPipelineError, match="URL summarizer base URL is not configured"):
                await ex.get("read_url")({"url": "http://x"})
        finally:
            await ex.aclose()

    @pytest.mark.asyncio
    async def test_include_content_validated_first(self) -> None:
        ex = make_tool_executors(None, "http://summ", None)
        try:
            with pytest.raises(AIPipelineError, match="include_content must be a boolean"):
                await ex.get("read_url")({"url": "http://x", "include_content": "yes"})
        finally:
            await ex.aclose()


class FakeHttpJson:
    def __init__(self, payload: Any) -> None:
        self._payload = payload
        self.status_code = 200
        self.text = json.dumps(payload)
        self.is_success = True
        self.reason_phrase = "OK"

    def json(self) -> Any:
        return self._payload


# --- searxng executor ------------------------------------------------------------------------------------


def searxng_ok(results: list[dict], **extra: Any) -> FakeResponse:
    payload = {"results": results, **extra}
    return FakeResponse(body=json.dumps(payload).encode("utf-8"))


class TestSearxngExecutor:
    @pytest.mark.asyncio
    async def test_text_search_happy_path(self) -> None:
        fake = FakeHttp(response=searxng_ok([{"title": "T", "content": "C", "url": "http://u"}]))
        ex = make_tool_executors("http://sx", None, None)
        ex._client = fake  # type: ignore[assignment]
        out = await ex.get("searxng_web_search")({"query": "greece banks", "language": "all", "pageno": 1})
        assert fake.calls[0]["url"] == "http://sx/search?q=greece+banks&format=json&pageno=1"
        assert out == "Title: T\nDescription: C\nURL: http://u"
        await ex.aclose()

    @pytest.mark.asyncio
    async def test_safesearch_string_coerced(self) -> None:
        fake = FakeHttp(response=searxng_ok([]))
        ex = make_tool_executors("http://sx", None, None)
        ex._client = fake  # type: ignore[assignment]
        await ex.get("searxng_web_search")({"query": "q", "safesearch": "1"})
        assert "safesearch=1" in fake.calls[0]["url"]
        await ex.aclose()

    @pytest.mark.asyncio
    async def test_min_score_filter_and_slice(self) -> None:
        results = [
            {"title": "low", "content": "l", "url": "http://l", "score": 0.1},
            {"title": "mid", "content": "m", "url": "http://m", "score": 0.6},
            {"title": "high", "content": "h", "url": "http://h", "score": 0.9},
        ]
        fake = FakeHttp(response=searxng_ok(results))
        ex = make_tool_executors("http://sx", None, None)
        ex._client = fake  # type: ignore[assignment]
        args = {"query": "q", "min_score": 0.5, "num_results": 1, "result_detail": "compact"}
        out = await ex.get("searxng_web_search")(args)
        # Filter keeps mid (0.6) and high (0.9) in original order; slice(0,1) -> mid.
        assert out == "Title: mid\nDescription: m\nURL: http://m"
        await ex.aclose()

    @pytest.mark.asyncio
    async def test_invalid_args(self) -> None:
        ex = make_tool_executors("http://sx", None, None)
        try:
            with pytest.raises(AIPipelineError, match="Invalid arguments for web search"):
                await ex.get("searxng_web_search")({"pageno": 1})
        finally:
            await ex.aclose()

    @pytest.mark.asyncio
    async def test_base_unconfigured(self) -> None:
        ex = make_tool_executors(None, None, None)
        try:
            with pytest.raises(AIPipelineError, match="SearXNG base URL is not configured"):
                await ex.get("searxng_web_search")({"query": "q"})
        finally:
            await ex.aclose()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status,expected",
        [
            (403, "🚫 SearXNG server Error (403): Authentication required or IP blocked"),
            (404, "🚫 SearXNG server Error (404): Search endpoint not found"),
            (429, "🚫 SearXNG server Error (429): Rate limit exceeded"),
            (502, "🚫 SearXNG server Error (502): Internal server error"),
        ],
    )
    async def test_server_errors(self, status: int, expected: str) -> None:
        fake = FakeHttp(response=FakeResponse(status_code=status, body=b"nope"))
        ex = make_tool_executors("http://sx", None, None)
        ex._client = fake  # type: ignore[assignment]
        with pytest.raises(AIPipelineError, match=re.escape(expected)):
            await ex.get("searxng_web_search")({"query": "q"})
        await ex.aclose()

    @pytest.mark.asyncio
    async def test_invalid_json(self) -> None:
        fake = FakeHttp(response=FakeResponse(body=b"<html>rate limited</html>"))
        ex = make_tool_executors("http://sx", None, None)
        ex._client = fake  # type: ignore[assignment]
        with pytest.raises(AIPipelineError, match="Invalid JSON format"):
            await ex.get("searxng_web_search")({"query": "q"})
        await ex.aclose()

    @pytest.mark.asyncio
    async def test_missing_results_array(self) -> None:
        fake = FakeHttp(response=FakeResponse(body=b'{"nope": 1}'))
        ex = make_tool_executors("http://sx", None, None)
        ex._client = fake  # type: ignore[assignment]
        with pytest.raises(AIPipelineError, match="Missing results array in response"):
            await ex.get("searxng_web_search")({"query": "q"})
        await ex.aclose()

    @pytest.mark.asyncio
    async def test_network_refused(self) -> None:
        fake = FakeHttp(exc=httpx.ConnectError("refused"))
        ex = make_tool_executors("http://sx", None, None)
        ex._client = fake  # type: ignore[assignment]
        with pytest.raises(AIPipelineError, match="SearXNG server is not responding"):
            await ex.get("searxng_web_search")({"query": "q"})
        await ex.aclose()

    @pytest.mark.asyncio
    async def test_network_timeout(self) -> None:
        fake = FakeHttp(exc=httpx.ReadTimeout("slow"))
        ex = make_tool_executors("http://sx", None, None)
        ex._client = fake  # type: ignore[assignment]
        with pytest.raises(AIPipelineError, match="too slow to respond"):
            await ex.get("searxng_web_search")({"query": "q"})
        await ex.aclose()

    @pytest.mark.asyncio
    async def test_no_results_uses_clara_browser_search_fallback(self) -> None:
        class SearchHttp:
            def __init__(self) -> None:
                self.calls: list[dict[str, Any]] = []

            async def get(self, url: str, timeout: Any = None) -> FakeResponse:
                self.calls.append({"method": "GET", "url": url, "timeout": timeout})
                return searxng_ok([])

            async def post(self, url: str, json: Any = None, timeout: Any = None) -> FakeResponse:
                self.calls.append({"method": "POST", "url": url, "json": json, "timeout": timeout})
                return FakeResponse(body=b"Title: Browser result\nDescription: Fallback\nURL: https://result.test")

            async def aclose(self) -> None:
                pass

        fake = SearchHttp()
        ex = make_tool_executors("http://sx", None, None, "http://browser:8891")
        ex._client = fake  # type: ignore[assignment]
        out = await ex.get("searxng_web_search")({"query": "q", "num_results": 3})

        assert out == "Title: Browser result\nDescription: Fallback\nURL: https://result.test"
        assert fake.calls[1]["url"] == "http://browser:8891/search"
        assert fake.calls[1]["json"] == {"query": "q", "limit": 3}
        await ex.aclose()

    @pytest.mark.asyncio
    async def test_searxng_error_uses_clara_browser_search_fallback(self) -> None:
        class SearchHttp:
            async def get(self, _url: str, timeout: Any = None) -> FakeResponse:
                return FakeResponse(status_code=429, body=b"rate limited")

            async def post(self, _url: str, json: Any = None, timeout: Any = None) -> FakeResponse:
                return FakeResponse(body=b"Title: Browser result\nURL: https://result.test")

            async def aclose(self) -> None:
                pass

        ex = make_tool_executors("http://sx", None, None, "http://browser:8891")
        ex._client = SearchHttp()  # type: ignore[assignment]
        assert "https://result.test" in await ex.get("searxng_web_search")({"query": "q"})
        await ex.aclose()

    @pytest.mark.asyncio
    async def test_browser_search_failure_reports_both_paths(self) -> None:
        class SearchHttp:
            async def get(self, _url: str, timeout: Any = None) -> FakeResponse:
                return searxng_ok([])

            async def post(self, _url: str, json: Any = None, timeout: Any = None) -> FakeResponse:
                return FakeResponse(status_code=502, body=b"browser unavailable")

            async def aclose(self) -> None:
                pass

        ex = make_tool_executors("http://sx", None, None, "http://browser:8891")
        ex._client = SearchHttp()  # type: ignore[assignment]
        with pytest.raises(AIPipelineError, match="SearXNG failed.*browser-search fallback failed"):
            await ex.get("searxng_web_search")({"query": "q"})
        await ex.aclose()


# --- memory pure functions ------------------------------------------------------------------------------------


class TestToMillis:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("2024-01-15T12:34:56.789Z", 1705322096789),
            ("1969-12-31T23:59:59.000Z", -1000),
            ("2024-06-01T00:00:00+02:00", 1717192800000),
            ("2026-08-18T09:00:00.000Z", 1787043600000),
            ("1970-01-01T00:00:00Z", 0),
            ("2024-01-15T12:34:56", 1705322096000),
            ("not a date", None),
            ("", None),
            (None, None),
            (5, None),
        ],
    )
    def test_values(self, value: Any, expected: Any) -> None:
        assert to_millis(value) == expected


class TestLemmatize:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("the quick brown fox jumps", "quick brown fox jump"),
            ("running companies are growing quickly", "run running compani grow growing quickli"),
            (
                "2024-01-15 | NTSE | Research: bank earnings beat expectations",
                "2024 01 15 ntse research bank earn beat expect",
            ),
            ("Hellenic Bank expects improved profitability in 2026", "hellen bank expect improv profit 2026"),
            ("a", ""),
            ("", ""),
            ("!!!", "!!!"),
            ("PORTFOLIO", "portfolio"),
            ("it's a test — don't worry", "s test don t worri"),
            ("inter-connections & micro-lending", "inter connect micro lend lending"),
            ("analysis of the AET Group ETF performance", "analysi aet group etf perform"),
        ],
    )
    def test_lemmatize(self, text: str, expected: str) -> None:
        assert lemmatize_for_bm25(text) == expected


class TestDedupHelpers:
    def test_strip_leading_date(self) -> None:
        assert strip_leading_date("2024-01-15 | NTSE | text") == "NTSE | text"
        assert strip_leading_date("no date") == "no date"

    def test_compact_whitespace(self) -> None:
        assert compact_whitespace("  a \n\t b  ") == "a b"

    def test_truncate_content(self) -> None:
        short = "a b"
        assert truncate_content(short) == short
        long = " ".join(f"w{i}" for i in range(200))
        out = truncate_content(long)
        assert len(out) <= 603
        assert out.endswith("...")

    def test_first_words(self) -> None:
        assert first_words("one two three four", 2) == "one two"

    def test_derive_dedup_query_three_parts(self) -> None:
        # 2 parts after date-strip -> the surviving pipe is preserved.
        content = "2024-01-15 | NTSE | " + " ".join(f"w{i}" for i in range(40))
        query = derive_memory_dedup_query(content)
        assert query.count(" ") == 23  # 24-word cap
        assert query.startswith("NTSE | w0")

    def test_derive_dedup_query_genuine_three_parts(self) -> None:
        # 3 parts after date-strip -> all joined with spaces (pipes dropped).
        query = derive_memory_dedup_query("2024-01-15 | A | B | " + " ".join(f"w{i}" for i in range(40)))
        assert query.startswith("A B w0")
        assert "|" not in query

    def test_derive_dedup_query_no_parts(self) -> None:
        query = derive_memory_dedup_query(" ".join(f"w{i}" for i in range(40)))
        assert query.count(" ") == 23

    def test_clamp_similarity(self) -> None:
        assert clamp_similarity(0.5) == 0.5
        assert clamp_similarity(-1) == 0.0
        assert clamp_similarity(2) == 1.0
        assert clamp_similarity(float("nan")) is None
        assert clamp_similarity(True) is None
        assert clamp_similarity("0.5") is None

    def test_normalize_memory_content(self) -> None:
        content = "2024-01-15 | AETF.GR | Bank X https://a.b/ grew fast!"
        assert normalize_memory_content(content) == "aetf gr bank x grew fast"

    def test_format_candidates_truncates(self) -> None:
        records = [
            {"id": "1", "content": "x" * 1000, "similarity": 0.97},
            {"id": "2", "content": "y", "relevance": "bad"},
        ]
        out = format_memory_dedup_candidates(records)
        assert out[0]["content"].endswith("...")
        assert out[0]["similarity"] == 0.97
        assert out[1]["relevance"] is None
        assert out[1]["similarity"] is None

    def test_find_duplicate_exact_normalized(self) -> None:
        candidates = [{"id": "c1", "content": "Bank X grew fast", "similarity": 0.5}]
        out = find_deterministic_memory_duplicate("2024-01-15 | BANK x  GREW fast", candidates, 0.96)
        assert out == {"id": "c1", "reason": "exact normalized content match"}

    def test_find_duplicate_semantic(self) -> None:
        candidates = [{"id": "c1", "content": "totally different", "similarity": 0.97}]
        out = find_deterministic_memory_duplicate("something else", candidates, 0.96)
        assert out is not None
        assert out["reason"] == "high semantic similarity (similarity=0.970)"

    def test_find_duplicate_below_threshold(self) -> None:
        candidates = [{"id": "c1", "content": "different", "similarity": 0.9}]
        assert find_deterministic_memory_duplicate("something else", candidates, 0.96) is None

    def test_find_duplicate_empty_content(self) -> None:
        assert find_deterministic_memory_duplicate("!!!", [{"id": "c1", "content": "x", "similarity": 0.99}]) is None

    def test_dedup_filters_symbol_branch(self) -> None:
        assert dedup_metadata_filters({"domain": "securities", "symbol": "AETF.GR", "kind": "external-context"}) == {
            "domain": "securities",
            "symbol": "AETF.GR",
        }

    def test_dedup_filters_kind_theme_branch(self) -> None:
        assert dedup_metadata_filters({"domain": "securities", "kind": "external-context", "theme": "greece"}) == {
            "domain": "securities",
            "kind": "external-context",
            "theme": "greece",
        }

    def test_dedup_filters_none(self) -> None:
        assert dedup_metadata_filters(None) is None
        assert dedup_metadata_filters({}) is None
        assert dedup_metadata_filters({"kind": "  "}) is None


class TestMetadataNormalization:
    def test_tags_merged_deduped_order_preserved(self) -> None:
        out = normalize_memory_store_metadata(
            "content",
            ["b", "a", "b"],
            {"tags": ["a", "c"], "kind": "external-context"},
        )
        assert out is not None
        assert out["tags"] == ["a", "c", "b"]
        assert out["kind"] == "external-context"

    def test_sector_keys_popped(self) -> None:
        out = normalize_memory_store_metadata("c", None, {"primary_sector": "securities", "sector": "x", "kind": "k"})
        assert out is not None
        assert "primary_sector" not in out
        assert "sector" not in out

    def test_provenance_normalized_or_dropped(self) -> None:
        metadata = {"provenance": {"source": " web ", "confidence": 0.5, "junk": 1}}
        out = normalize_memory_store_metadata("c", None, metadata)
        assert out is not None
        assert out["provenance"] == {"source": "web", "confidence": 0.5}
        assert normalize_memory_store_metadata("c", None, {"provenance": {"blank": "  "}}) is None

    def test_empty_returns_none(self) -> None:
        assert normalize_memory_store_metadata("c", None, None) is None


class TestRecordMapping:
    def test_to_pgvector_record_excludes_internal_keys(self) -> None:
        payload = {
            "data": "content",
            "user_id": "clara",
            "hash": "h",
            "textLemmatized": "t",
            "createdAt": "2024-01-15T12:34:56.789Z",
            "updatedAt": "2024-01-16T00:00:00.000Z",
            "last_seen_at": "2024-01-17T00:00:00.000Z",
            "tags": ["a"],
            "kind": "external-context",
            "salience": 0.7,
        }
        record = to_pgvector_record("id-1", payload)
        assert record["id"] == "id-1"
        assert record["content"] == "content"
        assert record["created_at"] == 1705322096789
        assert record["updated_at"] == 1705363200000
        assert record["last_seen_at"] == 1705449600000
        assert record["salience"] == 0.7
        assert "user_id" not in record["metadata"]
        assert "hash" not in record["metadata"]
        assert "data" not in record["metadata"]
        assert record["metadata"]["kind"] == "external-context"

    def test_last_seen_camelcase_fallback(self) -> None:
        record = to_pgvector_record("id", {"data": "x", "lastSeenAt": "1970-01-01T00:00:00Z"})
        assert record["last_seen_at"] == 0

    def test_search_match_similarity_clamped(self) -> None:
        match = to_pgvector_search_match("id", {"data": "x"}, 1.5)
        assert match["relevance"] == 1.0
        assert match["similarity"] == 1.0
        match2 = to_pgvector_search_match("id", {"data": "x"}, -0.5, similarity_eligible=False)
        assert match2["relevance"] == 0.0
        assert match2["similarity"] is None

    def test_search_match_bad_similarity(self) -> None:
        match = to_pgvector_search_match("id", {"data": "x"}, "nonsense")
        assert match["similarity"] == 0.0


# --- MemoryStore with fakes ------------------------------------------------------------------------------


def search_row(content: str, similarity: float, row_id: str = "id-1") -> dict:
    return {
        "id": row_id,
        "payload": {"data": content, "user_id": "clara", "createdAt": "2024-01-15T00:00:00.000Z"},
        "similarity": similarity,
    }


class TestMemoryStore:
    @pytest.mark.asyncio
    async def test_store_happy_path(self) -> None:
        pool = FakePool(rows=[])
        store = make_store(pool, embed_responses=[embed_response([0.1, 0.2]), embed_response([0.3, 0.4])])
        result = await store.store(
            "  Bank   X grew fast in 2024 ",
            tags=["securities", "AETF.GR"],
            metadata={"domain": "securities", "symbol": "AETF.GR", "kind": "research-summary"},
        )
        assert result["action"] == "stored"
        assert result["status"] == "stored"
        assert result["reason"] == "No high-confidence duplicate found."
        assert result["candidateCount"] == 0
        assert result["stored"]["content"] == "Bank X grew fast in 2024"

        embed_calls = store._test_embed.calls  # type: ignore[attr-defined]
        assert embed_calls[0]["url"] == "http://embed/v1/embeddings"
        assert embed_calls[0]["json"]["model"] == "test-embed"
        assert embed_calls[0]["json"]["dimensions"] == 2
        assert embed_calls[0]["timeout"] == httpx.Timeout(5.0)
        assert len(embed_calls[0]["json"]["input"].split(" ")) <= 24
        assert embed_calls[1]["timeout"] == httpx.Timeout(30.0)
        assert embed_calls[1]["json"]["input"] == "Bank X grew fast in 2024"

        inserts = [c for c in pool.calls if c[0] == "execute"]
        assert len(inserts) == 1
        expected_sql = 'INSERT INTO "clara_memories" (id, vector, payload) VALUES ($1, $2::vector, $3::jsonb)'
        assert inserts[0][1].startswith(expected_sql)
        payload = json.loads(inserts[0][2][2])
        assert payload["user_id"] == "clara"
        assert payload["data"] == "Bank X grew fast in 2024"
        assert payload["tags"] == ["securities", "AETF.GR"]
        assert payload["kind"] == "research-summary"
        assert "hash" in payload and "textLemmatized" in payload and "createdAt" in payload
        assert inserts[0][2][1].startswith("[") and inserts[0][2][1].endswith("]")

    @pytest.mark.asyncio
    async def test_store_exact_duplicate_reinforces(self) -> None:
        pool = FakePool(rows=[search_row("bank x  grew fast", 0.5)])
        store = make_store(pool, embed_responses=[embed_response([0.1, 0.2])])
        result = await store.store("2024-01-15 | BANK X | grew fast")
        assert result["action"] == "reinforced"
        assert result["status"] == "duplicate"
        assert result["duplicateId"] == "id-1"
        assert result["reason"] == "exact normalized content match"
        executes = [c for c in pool.calls if c[0] == "execute"]
        assert len(executes) == 1
        assert executes[0][1].strip().startswith("UPDATE")

    @pytest.mark.asyncio
    async def test_store_semantic_duplicate_reinforces(self) -> None:
        pool = FakePool(rows=[search_row("something else entirely", 0.97)])
        store = make_store(pool, embed_responses=[embed_response([0.1, 0.2])])
        result = await store.store("new content here")
        assert result["action"] == "reinforced"
        assert result["reason"] == "high semantic similarity (similarity=0.970)"

    @pytest.mark.asyncio
    async def test_store_search_failure_skips(self) -> None:
        # Embed succeeds; the DB fetch raises a non-missing error -> skipped.
        pool = FakePool(fetch_error=RuntimeError("pg down"))
        store = make_store(pool, embed_responses=[embed_response([0.1, 0.2])])
        result = await store.store("some content")
        assert result["action"] == "skipped"
        assert result["status"] == "search_failed"
        assert result["reason"] == "Memory duplicate search failed; skipped store so this can be retried later."
        assert result["candidates"] == []
        assert result["error"] == "pg down"
        assert [c for c in pool.calls if c[0] == "execute"] == []  # no insert attempted

    @pytest.mark.asyncio
    async def test_store_missing_store_search_tolerated(self) -> None:
        # Missing table on search is tolerated (returns []); insert then works.
        pool = FakePool(fetch_error=MissingStoreError())
        store = make_store(pool, embed_responses=[embed_response([0.1, 0.2]), embed_response([0.3, 0.4])])
        result = await store.store("some content")
        assert result["action"] == "stored"

    @pytest.mark.asyncio
    async def test_store_missing_store_insert_refuses(self) -> None:
        # Missing table on the INSERT raises a hard error (we never auto-create).
        pool = FakePool(execute_error=MissingStoreError())
        store = make_store(pool, embed_responses=[embed_response([0.1, 0.2]), embed_response([0.3, 0.4])])
        with pytest.raises(MemoryStoreError, match="is missing; refusing to create it"):
            await store.store("some content")

    @pytest.mark.asyncio
    async def test_store_empty_content_raises(self) -> None:
        pool = FakePool(rows=[])
        store = make_store(pool, embed_responses=[])
        with pytest.raises(MemoryStoreError, match="Memory content is required"):
            await store.store("   ")

    @pytest.mark.asyncio
    async def test_fetch_filters_and_ordering_sql(self) -> None:
        rows = [
            {
                "id": "id-2",
                "payload": {
                    "data": "newer",
                    "user_id": "clara",
                    "tags": ["a", "b"],
                    "updatedAt": "2024-02-01T00:00:00.000Z",
                },
            },
            {"id": "id-1", "payload": {"data": "   ", "user_id": "clara"}},
        ]
        pool = FakePool(rows=rows)
        store = make_store(pool)
        records = await store.fetch(["a", "b"], since="2024-01-01", limit=10, offset=0)
        assert len(records) == 1
        assert records[0]["content"] == "newer"
        sql = pool.calls[0][1]
        assert "payload->>'user_id' = $1" in sql
        assert "payload->'tags' ? $2" in sql
        assert "payload->'tags' ? $3" in sql
        assert "payload->>'as_of' >= $4" in sql
        assert pool.calls[0][2][:4] == ("clara", "a", "b", "2024-01-01")
        assert "ORDER BY COALESCE(payload->>'updatedAt', payload->>'createdAt', '') DESC, id::text ASC" in sql

    @pytest.mark.asyncio
    async def test_fetch_missing_store_returns_empty(self) -> None:
        pool = FakePool(fetch_error=MissingStoreError())
        store = make_store(pool)
        assert await store.fetch(["a"]) == []

    @pytest.mark.asyncio
    async def test_fetch_invalid_collection_raises(self) -> None:
        pool = FakePool(rows=[])
        store = make_store(pool)
        store.collection = "bad-name"
        with pytest.raises(MemoryStoreError, match="Invalid pgvector collection name"):
            await store.fetch(["a"])

    @pytest.mark.asyncio
    async def test_embed_http_error(self) -> None:
        pool = FakePool(rows=[])
        store = make_store(pool, embed_responses=[embed_response(None, status=413, body="too big")])
        with pytest.raises(MemoryStoreError, match="Embedding request failed with 413: too big"):
            await store._embed("text")

    @pytest.mark.asyncio
    async def test_embed_count_mismatch(self) -> None:
        pool = FakePool(rows=[])
        payload = json.dumps({"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]})
        store = make_store(pool, embed_responses=[FakeResponse(body=payload.encode())])
        with pytest.raises(MemoryStoreError, match="count mismatch: got 2, expected 1"):
            await store._embed("text")

    @pytest.mark.asyncio
    async def test_embed_dimension_mismatch(self) -> None:
        pool = FakePool(rows=[])
        store = make_store(pool, embed_responses=[embed_response([0.1, 0.2, 0.3])])
        with pytest.raises(MemoryStoreError, match="Embedding dimension mismatch: got 3, expected 2"):
            await store._embed("text")
