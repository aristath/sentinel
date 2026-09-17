"""LLM client with full tool-loop parity to Clara's task pipeline.

Behavioral port of the production request path against the local
``inference-router`` (:8080, OpenAI-compatible):

- ``POST {base}/chat/completions`` with ``stream: true`` and no
  ``max_tokens`` / ``tool_choice`` / ``top_p``; ``temperature`` only when
  passed. ``Authorization: Bearer {key}``.
- SSE quirks of local backends: missing ``index`` (falls back to last seen),
  ``function.name`` split across chunks, missing tool-call ids (``acc-{n}``),
  empty ``arguments`` (``"{}"``), nameless partials dropped.
- 429 cooldowns owned here (SDK ``maxRetries: 0`` parity): up to 8 retries,
  delay from ``retry-after-ms`` / ``retry-after`` headers, else
  ``min(65000, 5000 * 2**attempt)`` ms.
- Exact-repeat output loop guard: 256KB window, 30 repeats, 5s check
  interval. On detection the turn is aborted and re-streamed with a
  corrective user message (up to 3 retries, cumulative); the 4th detection
  raises ``LLMError``.
- Tool execution chain (Clara task path): JSON-parse arguments (failure →
  ``Error: malformed arguments: {raw}``), path-expand every string field,
  dispatch, wrap failures as ``Error running tool "{name}": {error}``,
  unknown tools → ``Tool "{name}" not found in any connected MCP server``.
"""

from __future__ import annotations

import asyncio
import copy
import json
import math
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Protocol, cast

import httpx

from sentinel.ai import tools as ai_tools
from sentinel.ai.errors import AIPipelineError, LLMError

LOOP_WINDOW_BYTES = 256 * 1024
LOOP_REPEATS = 30
LOOP_CHECK_INTERVAL_S = 5.0
MAX_CORRECTIVE_RETRIES = 3
MAX_EMPTY_RESPONSE_RETRIES = 2
MAX_RATE_LIMIT_RETRIES = 8
RATE_LIMIT_COOLDOWN_MS = 65_000
DEFAULT_MAX_TOOL_ROUNDS = 40
MODEL_DISCOVERY_TIMEOUT_SECONDS = 2.0
JSON_REPAIR_SCRIPT = Path(__file__).resolve().parent.parent / "tasks" / "repair-json.mjs"

_CORRECTIVE_TEXTS = (
    "[INTERRUPT - automated Clara notice] The previous attempt entered a thinking/output loop. "
    "Step back, identify the real next concrete action, and proceed without restating "
    "analysis you've already done.",
    "[INTERRUPT - automated Clara notice] Two attempts have looped. Skip all deliberation and "
    "produce the next tool call or concrete output directly.",
    "[INTERRUPT - automated Clara notice] The loop repeated again. Use the shortest "
    "non-repetitive path forward: one concrete tool call or one concrete answer, no thinking, "
    "no commentary.",
)

# A tool executor receives already-expanded args and returns either a string
# or {"text": str, "data": dict, "artifacts": list} (Clara ToolResult shape).
ToolExecutor = Callable[[dict], Awaitable[Any]]


class ExecutorLookup(Protocol):
    """Anything that can resolve a tool name to an executor (dict or ToolExecutors)."""

    def get(self, name: str) -> ToolExecutor | None:  # pragma: no cover - protocol
        ...


async def discover_models(
    base_url: str,
    api_key: str,
    *,
    timeout: float = MODEL_DISCOVERY_TIMEOUT_SECONDS,
    client: httpx.AsyncClient | None = None,
) -> list[str]:
    """Return model IDs reported by an OpenAI-compatible endpoint."""
    owns_client = client is None
    session = client or httpx.AsyncClient(timeout=timeout)
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        response = await session.get(f"{base_url.rstrip('/')}/models", headers=headers)
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        models: list[str] = []
        seen: set[str] = set()
        for row in rows:
            model_id = row.get("id") if isinstance(row, dict) else None
            if isinstance(model_id, str) and model_id and model_id not in seen:
                seen.add(model_id)
                models.append(model_id)
        return models
    except (httpx.HTTPError, ValueError) as exc:
        raise LLMError(f"Could not list models: {exc}") from exc
    finally:
        if owns_client:
            await session.aclose()


_acc_counter = 0


class _LoopDetected(Exception):
    """Internal: the exact-repeat guard tripped during a turn."""

    def __init__(self, period: int) -> None:
        super().__init__(f"LLM output loop detected: exact block repeated {LOOP_REPEATS} times ({period} byte period)")
        self.period = period


@dataclass
class ChatResult:
    content: str
    last_tool_result: str


# --- tool result helpers (Clara parity) -------------------------------------


def tool_result_to_text(result: Any) -> str:
    if isinstance(result, str):
        return result
    details = [result.get("text", "")]
    data = result.get("data")
    if data:
        details.append(f"[data]\n{json.dumps(data, indent=2, ensure_ascii=False)}")
    artifacts = result.get("artifacts")
    if artifacts:
        details.append(f"[artifacts]\n{json.dumps(artifacts, indent=2, ensure_ascii=False)}")
    return "\n".join(d for d in details if d)


# --- path expansion (Clara workspace.ts, Sentinel-adapted) -------------------

_TASK_CWD_CALL_RE = re.compile(r"\bTask_CWD\(\s*(?:(['\"])([^'\"]+)\1)?\s*\)")
_TASK_CWD_PLACEHOLDER_RE = re.compile(r"\bTASK_CWD\b")
_TASK_CWD_MALFORMED_RE = re.compile(r"\bTask_CWD\s*\(")
_TASK_CWD_PLACEHOLDER_CALL_RE = re.compile(r"\bTASK_CWD\s*\(")


def _resolve_task_cwd(explicit_id: str | None, work_root: Path | None) -> str:
    if explicit_id is not None:
        from sentinel.tasks.definitions import get_task, resolve_cwd, validate_task_id

        task_id = validate_task_id(explicit_id)
        try:
            return str(resolve_cwd(get_task(task_id)))
        except FileNotFoundError:
            if work_root is None:
                raise AIPipelineError(f'Task_CWD("{task_id}") could not resolve the Sentinel task data root') from None
            return str(work_root.parent / task_id)
    if work_root is None:
        raise AIPipelineError(
            "TASK_CWD and Task_CWD() require a task execution context; run the prompt with a working directory"
        )
    return str(work_root)


def _is_shell_env_offset(value: str, start: int) -> bool:
    prev1 = value[start - 1] if start > 0 else ""
    prev2 = value[start - 2] if start > 1 else ""
    return prev1 == "$" or (prev1 == "{" and prev2 == "$")


def _expand_task_cwd(s: str, work_root: Path | None) -> str:
    s = _TASK_CWD_CALL_RE.sub(lambda m: _resolve_task_cwd(m.group(2), work_root), s)
    out: list[str] = []
    pos = 0
    for m in _TASK_CWD_PLACEHOLDER_RE.finditer(s):
        start, end = m.span()
        out.append(s[pos:start])
        if _is_shell_env_offset(s, start) or (end < len(s) and s[end] == "("):
            out.append(m.group(0))
        else:
            out.append(_resolve_task_cwd(None, work_root))
        pos = end
    out.append(s[pos:])
    s = "".join(out)
    if _TASK_CWD_MALFORMED_RE.search(s) or _TASK_CWD_PLACEHOLDER_CALL_RE.search(s):
        raise AIPipelineError('Malformed task cwd shorthand. Use TASK_CWD, Task_CWD(), or Task_CWD("task-id").')
    return s


def _expand_base_path(s: str, ai_data_dir: Path | None) -> str:
    if "@/" in s:
        if ai_data_dir is None:
            raise AIPipelineError("@/ path shorthand requires an AI data dir")
        s = s.replace("@/", f"{ai_data_dir}/")
    return s.replace("~/", f"{Path.home()}/")


def expand_path(s: str, *, ai_data_dir: Path | None, work_root: Path | None) -> str:
    return _expand_base_path(_expand_task_cwd(s, work_root), ai_data_dir)


def expand_paths(value: Any, *, ai_data_dir: Path | None, work_root: Path | None) -> Any:
    if isinstance(value, str):
        return expand_path(value, ai_data_dir=ai_data_dir, work_root=work_root)
    if isinstance(value, list):
        return [expand_paths(v, ai_data_dir=ai_data_dir, work_root=work_root) for v in value]
    if isinstance(value, dict):
        return {k: expand_paths(v, ai_data_dir=ai_data_dir, work_root=work_root) for k, v in value.items()}
    return value


def _string_uses_task_cwd(value: str) -> bool:
    if _TASK_CWD_CALL_RE.search(value):
        return True
    for m in _TASK_CWD_PLACEHOLDER_RE.finditer(value):
        if not _is_shell_env_offset(value, m.start()):
            return True
    return False


def _value_uses_task_cwd(value: Any) -> bool:
    if isinstance(value, str):
        return _string_uses_task_cwd(value)
    if isinstance(value, list):
        return any(_value_uses_task_cwd(v) for v in value)
    if isinstance(value, dict):
        return any(_value_uses_task_cwd(v) for v in value.values())
    return False


# --- system prompt (Sentinel adaptation of Clara's task system prompt) -------


def build_system_prompt(
    ai_data_dir: str | Path,
    task_id: str,
    task_cwd: str | Path,
) -> str:
    now = datetime.now()
    weekday = (
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    )[now.weekday()]
    datetime_str = f"{now:%Y-%m-%d %H:%M:%S} ({weekday})"
    return "\n".join(
        [
            f"Today's date and time is {datetime_str}.",
            f"Your profile workspace is {ai_data_dir}. Use @/ for Sentinel's data root and ~/ for the home directory.",
            f"Current task: {task_id}. During this task, TASK_CWD and Task_CWD() expand to {task_cwd}, "
            'and Task_CWD("task-id") expands to another task\'s working directory.',
        ]
    )


# --- prompt template handling (Clara orchestrator-runner / step-output parity)


def substitute(template: str, context: dict[str, Any]) -> str:
    for key, value in context.items():
        placeholder = "{{" + key + "}}"
        replacement = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        template = template.replace(placeholder, replacement)
    return template


_JSON_FENCE_RE = __import__("re").compile(r"^```(?:json)?[ \t]*\r?\n([\s\S]*?)\r?\n```$", re.IGNORECASE)


def strip_json_fence(raw: str) -> str:
    m = _JSON_FENCE_RE.match(raw)
    if m:
        return m.group(1).strip()
    return raw


def _embedded_json(raw: str) -> str | None:
    object_start = raw.find("{")
    array_start = raw.find("[")
    starts = [i for i in (object_start, array_start) if i >= 0]
    if not starts:
        return None
    start = min(starts)
    end = max(raw.rfind("}"), raw.rfind("]"))
    if end < start:
        return None
    return raw[start : end + 1].strip()


def parse_json_output(raw: str) -> Any:
    trimmed = strip_json_fence(raw.strip())
    if trimmed == "":
        raise AIPipelineError("Step produced no output")
    try:
        return json.loads(trimmed)
    except json.JSONDecodeError as original_error:
        embedded = _embedded_json(trimmed)
        candidate = embedded if embedded is not None else trimmed
        candidate_start = candidate.lstrip()[:1]
        if embedded is None and candidate_start not in ("{", "["):
            raise original_error
        try:
            return json.loads(_repair_json(candidate))
        except Exception:
            raise original_error from None


def _repair_json(raw: str) -> str:
    node = shutil.which("node")
    if node is None:
        raise AIPipelineError("Node.js is required to repair task JSON output")
    result = subprocess.run(  # noqa: S603 - fixed executable and bundled script, no shell
        [node, str(JSON_REPAIR_SCRIPT)],
        input=raw,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode != 0:
        raise AIPipelineError(result.stderr.strip() or "JSON repair failed")
    return result.stdout


# --- tool-call accumulation (Clara ToolCallAccumulator parity) ---------------


class _ToolCallAccumulator:
    def __init__(self) -> None:
        self._by_index: dict[int, dict[str, str]] = {}
        self._last_index = 0

    def add(self, delta: dict) -> None:
        index = delta.get("index")
        if index is None:
            index = self._last_index
        self._last_index = index
        call = self._by_index.get(index) or {"id": "", "name": "", "arguments": ""}
        if delta.get("id"):
            call["id"] = delta["id"]
        fn = delta.get("function") or {}
        if fn.get("name"):
            call["name"] += fn["name"]
        if fn.get("arguments"):
            call["arguments"] += fn["arguments"]
        self._by_index[index] = call

    def result(self) -> list[dict[str, str]]:
        global _acc_counter
        calls: list[dict[str, str]] = []
        for index in sorted(self._by_index):
            call = self._by_index[index]
            if call["name"] == "":
                continue
            call_id = call["id"]
            if not call_id:
                _acc_counter += 1
                call_id = f"acc-{_acc_counter}"
            calls.append({"id": call_id, "name": call["name"], "arguments": call["arguments"] or "{}"})
        return calls


# --- exact-repeat loop guard (Clara repetition-guard.ts parity) --------------


def _z_function(data: bytes) -> list[int]:
    n = len(data)
    z = [0] * n
    if n == 0:
        return z
    z[0] = n
    left = 0
    right = 0
    for i in range(1, n):
        if i < right:
            z[i] = min(z[i - left], right - i)
        while i + z[i] < n and data[z[i]] == data[i + z[i]]:
            z[i] += 1
        if i + z[i] > right:
            left = i
            right = i + z[i]
    return z


class _ExactRepeatDetector:
    def __init__(self, max_bytes: int, repeats: int) -> None:
        self._max_bytes = max(1, int(max_bytes))
        self._repeats = max(2, int(repeats))
        self._buf = b""

    def append(self, data: bytes) -> None:
        if not data:
            return
        if len(data) >= self._max_bytes:
            self._buf = data[-self._max_bytes :]
            return
        if len(self._buf) + len(data) <= self._max_bytes:
            self._buf += data
            return
        excess = len(self._buf) + len(data) - self._max_bytes
        self._buf = self._buf[excess:] + data

    def scan(self) -> int:
        n = len(self._buf)
        k = self._repeats
        if n < k:
            return 0
        z = _z_function(self._buf[::-1])
        max_period = n // k
        needed = k - 1
        for period in range(1, max_period + 1):
            if z[period] >= needed * period:
                return period
        return 0


class _LoopGuard:
    """Throttled exact-repeat guard over one streamed turn.

    Production runs the scan on a 5s timer; the port scans on chunk arrival
    once 5s have elapsed (a stalled stream produces no output to loop on).
    """

    def __init__(self) -> None:
        self._detector = _ExactRepeatDetector(LOOP_WINDOW_BYTES, LOOP_REPEATS)
        self._next_scan: float | None = None

    def observe(self, text: str) -> int:
        if not text:
            return 0
        self._detector.append(text.encode("utf-8"))
        now = time.monotonic()
        if self._next_scan is None:
            self._next_scan = now + LOOP_CHECK_INTERVAL_S
            return 0
        if now < self._next_scan:
            return 0
        self._next_scan = now + LOOP_CHECK_INTERVAL_S
        return self._detector.scan()


# --- rate limit delay (Clara rateLimitRetryDelayMs parity) --------------------


def _header_str(headers: httpx.Headers, name: str) -> str | None:
    value = headers.get(name)
    return value if isinstance(value, str) else None


def _header_number(headers: httpx.Headers, name: str) -> float | None:
    value = _header_str(headers, name)
    if not value:
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _rate_limit_delay_ms(headers: httpx.Headers, attempt: int) -> float:
    retry_after_ms = _header_number(headers, "retry-after-ms")
    if retry_after_ms is not None and retry_after_ms >= 0:
        return float(retry_after_ms)
    retry_after = _header_str(headers, "retry-after")
    if retry_after:
        try:
            seconds = float(retry_after)
        except ValueError:
            seconds = math.nan
        if math.isfinite(seconds) and seconds >= 0:
            return seconds * 1000.0
        try:
            parsed_dt = parsedate_to_datetime(retry_after)
            if parsed_dt.tzinfo is None:
                parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
            date_ms = parsed_dt.timestamp() * 1000.0
        except (TypeError, ValueError):
            date_ms = math.nan
        if math.isfinite(date_ms):
            return max(0.0, date_ms - time.time() * 1000.0)
    remaining = _header_number(headers, "x-ratelimit-remaining-tokens-minute")
    limit = _header_number(headers, "x-ratelimit-limit-tokens-minute")
    if (remaining is not None and remaining == 0) or limit is not None:
        return float(RATE_LIMIT_COOLDOWN_MS)
    return min(float(RATE_LIMIT_COOLDOWN_MS), 5000.0 * (2**attempt))


# --- message builders (Clara agent/history.ts parity) -------------------------


def _reasoning_delta(delta: dict) -> str:
    raw = delta.get("reasoning_content")
    thinking = delta.get("thinking")
    out = ""
    if isinstance(raw, str):
        out += raw
    if isinstance(thinking, str):
        out += thinking
    return out


def _build_assistant_message(content: str, tool_calls: list[dict]) -> dict:
    message: dict[str, Any] = {"role": "assistant", "content": content if content else None}
    if tool_calls:
        message["tool_calls"] = [
            {
                "id": c["id"],
                "type": "function",
                "function": {"name": c["name"], "arguments": c["arguments"]},
            }
            for c in tool_calls
        ]
    return message


@dataclass
class _Turn:
    content: str
    tool_calls: list[dict[str, str]]


# --- the client ----------------------------------------------------------------


class LLMClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        timeout: float = 600.0,
        max_rounds: int = DEFAULT_MAX_TOOL_ROUNDS,
        ai_data_dir: Path | None = None,
        searxng_base_url: str | None = None,
        url_summarizer_base_url: str | None = None,
        browser_search_base_url: str | None = None,
        session: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_rounds = max(1, min(100, int(max_rounds)))
        self.ai_data_dir = ai_data_dir
        self.searxng_base_url = searxng_base_url
        self.url_summarizer_base_url = url_summarizer_base_url
        self.browser_search_base_url = browser_search_base_url
        self._owns_session = session is None
        self._client = session or httpx.AsyncClient(timeout=timeout)

    @classmethod
    async def from_settings(cls, settings: Any) -> "LLMClient":
        from sentinel.paths import SENTINEL_HOME

        return cls(
            await settings.get("ai_llm_base_url", "http://127.0.0.1:8080/v1"),
            await settings.get("ai_llm_api_key", "local"),
            await settings.get("ai_llm_model", "qwen3.8-27b-udq4kxl"),
            timeout=float(await settings.get("ai_llm_timeout_seconds", 600)),
            max_rounds=int(await settings.get("ai_max_tool_calls", 40)),
            ai_data_dir=SENTINEL_HOME,
            searxng_base_url=await settings.get("ai_searxng_base_url", "http://127.0.0.1:8888"),
            url_summarizer_base_url=await settings.get("ai_url_summarizer_base_url", "http://127.0.0.1:8890"),
            browser_search_base_url=await settings.get("ai_browser_search_base_url", "http://127.0.0.1:8891"),
        )

    async def close(self) -> None:
        if self._owns_session:
            await self._client.aclose()

    # -- public API ------------------------------------------------------------

    async def chat(
        self,
        user_content: str,
        *,
        system: str | None = None,
        tools: list[dict] | None = None,
        executors: ExecutorLookup | None = None,
        work_root: Path | None = None,
        temperature: float | None = None,
    ) -> ChatResult:
        """Run the full tool loop; return the last turn's content.

        Mirrors Clara's runAgent: the model gets one finalization chance
        after the round budget is exhausted, and only then does the loop
        raise.
        """
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user_content})
        tool_defs = tools or None
        executor_lookup = cast(ExecutorLookup, executors if executors is not None else {})
        rounds = 0
        empty_response_retries = 0
        content = ""
        last_tool_result = ""
        while True:
            turn = await self._stream_turn(messages, tool_defs, temperature)
            content = turn.content
            if not turn.tool_calls:
                if not content.strip() and not last_tool_result and empty_response_retries < MAX_EMPTY_RESPONSE_RETRIES:
                    empty_response_retries += 1
                    continue
                return ChatResult(content=content, last_tool_result=last_tool_result)
            empty_response_retries = 0
            messages.append(_build_assistant_message(turn.content, turn.tool_calls))
            if rounds >= self.max_rounds:
                raise LLMError(f"LLM tool loop exceeded {self.max_rounds} rounds without producing a final answer")
            rounds += 1
            for call in turn.tool_calls:
                result = await self._execute_tool_call(call, executor_lookup, work_root)
                last_tool_result = result
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})

    # -- one protected turn (corrective retries) --------------------------------

    async def _stream_turn(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        temperature: float | None,
    ) -> _Turn:
        request_messages = copy.deepcopy(messages)
        attempt = 0
        while True:
            guard = _LoopGuard()
            try:
                return await self._stream_once(request_messages, tools, temperature, guard)
            except _LoopDetected as exc:
                if attempt >= MAX_CORRECTIVE_RETRIES:
                    raise LLMError(str(exc)) from exc
                request_messages.append({"role": "user", "content": _CORRECTIVE_TEXTS[attempt]})
                attempt += 1

    # -- one streamed request (429 retries) --------------------------------------

    async def _stream_once(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        temperature: float | None,
        guard: _LoopGuard,
    ) -> _Turn:
        body: dict[str, Any] = {"model": self.model, "messages": messages, "stream": True}
        if tools:
            body["tools"] = tools
        if temperature is not None:
            body["temperature"] = temperature
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        attempt = 0
        while True:
            try:
                request = self._client.build_request(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    json=body,
                    headers=headers,
                )
                response = await self._client.send(request, stream=True)
            except httpx.HTTPError as exc:
                raise LLMError(f"LLM request failed: {exc}") from exc
            if response.status_code == 429:
                retry_headers = response.headers
                await response.aclose()
                if attempt >= MAX_RATE_LIMIT_RETRIES:
                    raise LLMError(f"LLM request failed with 429: rate limited after {MAX_RATE_LIMIT_RETRIES} retries")
                delay_ms = _rate_limit_delay_ms(retry_headers, attempt)
                await asyncio.sleep(delay_ms / 1000.0)
                attempt += 1
                continue
            if response.status_code >= 400:
                text = (await response.aread()).decode("utf-8", "replace")
                await response.aclose()
                raise LLMError(f"LLM request failed with {response.status_code}: {text[:500]}")
            return await self._parse_turn(response, guard)

    async def _parse_turn(self, response: httpx.Response, guard: _LoopGuard) -> _Turn:
        content = ""
        accumulator = _ToolCallAccumulator()
        try:
            async for line in response.aiter_lines():
                if not line or line.startswith(":"):
                    continue
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                for choice in chunk.get("choices") or []:
                    delta = choice.get("delta") or {}
                    reasoning = _reasoning_delta(delta)
                    if reasoning:
                        period = guard.observe(reasoning)
                        if period:
                            raise _LoopDetected(period)
                    c = delta.get("content")
                    if c:
                        content += c
                        period = guard.observe(c)
                        if period:
                            raise _LoopDetected(period)
                    tool_calls = delta.get("tool_calls")
                    if tool_calls:
                        period = guard.observe(json.dumps(tool_calls, ensure_ascii=False, separators=(",", ":")))
                        if period:
                            raise _LoopDetected(period)
                        for tc in tool_calls:
                            accumulator.add(tc)
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc
        finally:
            await response.aclose()
        return _Turn(content=content, tool_calls=accumulator.result())

    # -- tool execution (Clara execute.ts + tool-loop.ts run() parity) ----------

    async def _execute_tool_call(self, call: dict, executors: ExecutorLookup, work_root: Path | None) -> str:
        raw = call.get("arguments") or "{}"
        try:
            args = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return f"Error: malformed arguments: {raw}"
        if not isinstance(args, dict):
            return f"Error: malformed arguments: {raw}"
        return await self._run_tool(call["name"], args, executors, work_root)

    async def _run_tool(
        self,
        name: str,
        args: dict,
        executors: ExecutorLookup,
        work_root: Path | None,
    ) -> str:
        try:
            if work_root is not None and _value_uses_task_cwd(args):
                (work_root / ".work").mkdir(parents=True, exist_ok=True)
            resolved = expand_paths(args, ai_data_dir=self.ai_data_dir, work_root=work_root)
            executor = executors.get(name)
            if executor is None:
                return f'Tool "{name}" not found in any connected MCP server'
            result = await executor(resolved)
            return tool_result_to_text(result)
        except Exception as exc:  # noqa: BLE001 - parity: tool errors become tool content
            return f'Error running tool "{name}": {exc}'


# --- run_prompt (Clara executePrompt + yieldTokens parity) --------------------


async def run_prompt(
    client: LLMClient,
    name: str,
    *,
    task_id: str,
    task_cwd: str | Path,
    context: dict[str, Any] | None = None,
    system: str | None = None,
    temperature: float | None = None,
    as_json: bool = False,
    use_tools: bool = True,
) -> Any:
    """Run a markdown prompt template through the full tool loop.

    ``name`` is the absolute path of a prompt belonging to the active folder
    task. Returns the final output text, or the parsed object when ``as_json``.
    """
    prompt_path = Path(name)
    if not prompt_path.is_absolute():
        raise AIPipelineError("Task prompt path must be absolute")
    template = prompt_path.read_text(encoding="utf-8")
    if context:
        template = substitute(template, context)
    work_root = Path(task_cwd)
    base_system = build_system_prompt(client.ai_data_dir or "", task_id, work_root)
    system_prompt = f"{base_system}\n\n{system}" if system else base_system
    executors = ai_tools.make_tool_executors(
        client.searxng_base_url,
        client.url_summarizer_base_url,
        work_root,
        client.browser_search_base_url,
    )
    try:
        result = await client.chat(
            template,
            system=system_prompt,
            tools=ai_tools.TOOL_DEFINITIONS if use_tools else None,
            executors=executors if use_tools else None,
            work_root=work_root,
            temperature=temperature,
        )
    finally:
        await executors.aclose()
    output = result.content if result.content.strip() else result.last_tool_result
    if not output.strip():
        raise AIPipelineError(f'Prompt "{name}" produced no output')
    if as_json:
        return parse_json_output(output)
    return output
