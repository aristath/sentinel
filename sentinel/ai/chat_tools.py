"""Tool catalog used by the Research Pipeline chat interface."""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
import signal
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx

from sentinel.ai import tools as pipeline_tools

ToolExecutor = Callable[[dict[str, Any]], Awaitable[Any]]


LOCAL_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a UTF-8 file from the filesystem.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or append UTF-8 content to a filesystem path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "append": {"type": "boolean"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and directories at a filesystem path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "recursive": {"type": "boolean"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a Bash command and return stdout, stderr, and the exit code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "cwd": {"type": "string"},
                    "timeout_seconds": {"type": "number"},
                },
                "required": ["command"],
            },
        },
    },
    pipeline_tools.TOOL_DEFINITIONS[2],
]

SEARXNG_MCP_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "mcp__searxng__searxng_search_suggestions",
            "description": "Return autocomplete suggestions from the configured SearXNG instance.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "language": {"type": "string", "default": "all"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mcp__searxng__searxng_instance_info",
            "description": "Discover the configured SearXNG instance capabilities from its live configuration.",
            "parameters": {
                "type": "object",
                "properties": {
                    "includeEngines": {"type": "boolean", "default": False},
                    "includeDisabled": {"type": "boolean", "default": False},
                    "category": {"type": "string"},
                    "refresh": {"type": "boolean", "default": False},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mcp__searxng__web_url_read",
            "description": (
                "Fetch a URL and return its readable content, with optional pagination or heading selection."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "startChar": {"type": "number", "minimum": 0},
                    "maxLength": {"type": "number", "minimum": 1},
                    "section": {"type": "string"},
                    "paragraphRange": {"type": "string"},
                    "readHeadings": {"type": "boolean"},
                },
                "required": ["url"],
            },
        },
    },
]


def _mcp_tool_definition(server: str, tool: Any) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": f"mcp__{server}__{tool.name}",
            "description": tool.description or f"External MCP tool {tool.name} from {server}.",
            "parameters": tool.input_schema,
        },
    }


def _adapter_tool_definition(server: str, tool: dict[str, Any]) -> dict[str, Any]:
    name = str(tool.get("name") or "")
    return {
        "type": "function",
        "function": {
            "name": f"mcp__{server}__{name}",
            "description": str(tool.get("description") or f"External MCP tool {name} from {server}."),
            "parameters": tool.get("inputSchema") or {"type": "object", "properties": {}},
        },
    }


def _result_text(result: Any) -> str:
    content = getattr(result, "content", None)
    if isinstance(content, list):
        parts = [str(block.text) for block in content if getattr(block, "type", None) == "text"]
        if parts:
            return "\n".join(parts)
    structured = getattr(result, "structured_content", None)
    if structured is not None:
        return json.dumps(structured, indent=2, ensure_ascii=False)
    if isinstance(result, dict):
        raw_content = result.get("content")
        if isinstance(raw_content, list):
            parts = [
                str(block.get("text"))
                for block in raw_content
                if isinstance(block, dict) and block.get("type") == "text" and block.get("text") is not None
            ]
            if parts:
                return "\n".join(parts)
        if "structuredContent" in result:
            return json.dumps(result["structuredContent"], indent=2, ensure_ascii=False)
        return json.dumps(result, indent=2, ensure_ascii=False)
    return str(result)


class ResearchChatTools:
    """Combined local, Sentinel MCP, SearXNG MCP, and Firefox MCP tools."""

    def __init__(
        self,
        definitions: list[dict[str, Any]],
        executors: dict[str, ToolExecutor],
        pipeline_executors: pipeline_tools.ToolExecutors,
        http_client: httpx.AsyncClient,
    ) -> None:
        self.definitions = definitions
        self._executors = executors
        self._pipeline_executors = pipeline_executors
        self._http_client = http_client

    @classmethod
    async def create(
        cls,
        *,
        searxng_base_url: str | None,
        url_summarizer_base_url: str | None,
        browser_search_base_url: str | None,
        firefox_mcp_base_url: str | None,
        work_root: Path,
    ) -> "ResearchChatTools":
        from sentinel.mcp_server import mcp

        pipeline_executors = pipeline_tools.make_tool_executors(
            searxng_base_url,
            url_summarizer_base_url,
            work_root,
            browser_search_base_url,
        )
        http_client = httpx.AsyncClient(timeout=60.0)
        definitions = list(LOCAL_TOOL_DEFINITIONS)
        executors: dict[str, ToolExecutor] = {}

        async def read_file(args: dict[str, Any]) -> str:
            return Path(_required_string(args, "path")).read_text(encoding="utf-8")

        async def write_file(args: dict[str, Any]) -> str:
            path = Path(_required_string(args, "path"))
            content = _string(args.get("content"), "content")
            mode = "a" if _boolean(args.get("append"), "append", False) else "w"
            with path.open(mode, encoding="utf-8") as handle:
                handle.write(content)
            return f"Wrote {len(content)} characters to {path}"

        async def list_directory(args: dict[str, Any]) -> str:
            path = Path(_required_string(args, "path"))
            recursive = _boolean(args.get("recursive"), "recursive", False)
            entries = path.rglob("*") if recursive else path.iterdir()
            return "\n".join(
                f"{'directory' if entry.is_dir() else 'file'}\t{entry}"
                for entry in sorted(entries, key=lambda item: str(item))
            )

        async def run_shell(args: dict[str, Any]) -> dict[str, Any]:
            command = _required_string(args, "command")
            cwd_value = args.get("cwd")
            cwd = _string(cwd_value, "cwd") if cwd_value is not None else None
            raw_timeout = args.get("timeout_seconds", 3600)
            if isinstance(raw_timeout, bool) or not isinstance(raw_timeout, (int, float)):
                raise ValueError("timeout_seconds must be a number")
            timeout = float(raw_timeout)
            if not math.isfinite(timeout):
                raise ValueError("timeout_seconds must be finite")
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=None if timeout <= 0 else timeout
                )
            except TimeoutError:
                _kill_process_group(process)
                await process.wait()
                raise RuntimeError(f"command timed out after {timeout:g} seconds") from None
            except asyncio.CancelledError:
                _kill_process_group(process)
                await process.wait()
                raise
            decoded_stdout = stdout.decode("utf-8", "replace")
            decoded_stderr = stderr.decode("utf-8", "replace")
            text = decoded_stdout
            if decoded_stderr:
                text += f"\n[stderr]\n{decoded_stderr}"
            if process.returncode:
                text += f"\n[exit code: {process.returncode}]"
            return {
                "text": text.strip() or f"Command exited with code {process.returncode}",
                "data": {
                    "stdout": decoded_stdout,
                    "stderr": decoded_stderr,
                    "exit_code": process.returncode,
                },
            }

        executors.update(
            {
                "read_file": read_file,
                "write_file": write_file,
                "list_directory": list_directory,
                "run_shell": run_shell,
            }
        )
        read_url = pipeline_executors.get("read_url")
        if read_url is not None:
            executors["read_url"] = read_url

        searx_definition = json.loads(json.dumps(pipeline_tools.TOOL_DEFINITIONS[3]))
        searx_name = "mcp__searxng__searxng_web_search"
        searx_definition["function"]["name"] = searx_name
        definitions.append(searx_definition)
        definitions.extend(SEARXNG_MCP_DEFINITIONS)
        searx_executor = pipeline_executors.get("searxng_web_search")
        if searx_executor is not None:
            executors[searx_name] = searx_executor

        searx_base = (searxng_base_url or "").rstrip("/")

        async def searx_suggestions(args: dict[str, Any]) -> str:
            query = _required_string(args, "query")
            language = args.get("language", "all")
            if not isinstance(language, str):
                raise ValueError("language must be a string")
            params = {"q": query}
            if language != "all":
                params["lang"] = language
            response = await http_client.get(f"{searx_base}/autocompleter", params=params)
            response.raise_for_status()
            payload = response.json()
            suggestions = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
            return json.dumps({"query": query, "suggestions": suggestions}, indent=2, ensure_ascii=False)

        async def searx_instance_info(args: dict[str, Any]) -> str:
            response = await http_client.get(f"{searx_base}/config")
            response.raise_for_status()
            config = response.json()
            if not isinstance(config, dict):
                raise ValueError("SearXNG returned a non-object configuration")
            category = args.get("category")
            if category is not None and not isinstance(category, str):
                raise ValueError("category must be a string")
            include_engines = _boolean(args.get("includeEngines"), "includeEngines", False)
            include_disabled = _boolean(args.get("includeDisabled"), "includeDisabled", False)
            engines = config.get("engines", [])
            filtered_engines = []
            categories: set[str] = set()
            if isinstance(engines, list):
                for engine in engines:
                    if not isinstance(engine, dict):
                        continue
                    raw_categories = engine.get("categories", [])
                    engine_categories = [item for item in raw_categories if isinstance(item, str)]
                    categories.update(engine_categories)
                    if category and category not in engine_categories:
                        continue
                    if engine.get("disabled") and not include_disabled:
                        continue
                    if include_engines:
                        filtered_engines.append(
                            {
                                "name": engine.get("name"),
                                "categories": engine_categories,
                                "disabled": bool(engine.get("disabled")),
                            }
                        )
            result = {
                "available": True,
                "categories": sorted(item for item in categories if not category or item == category),
                "defaults": {
                    "safesearch": config.get("search", {}).get("safe_search")
                    if isinstance(config.get("search"), dict)
                    else config.get("default_safe_search"),
                    "locale": config.get("default_locale"),
                    "language": config.get("default_language"),
                },
                "locales": config.get("locales"),
                "plugins": config.get("plugins", []),
            }
            if include_engines:
                result["engines"] = filtered_engines
            return json.dumps(result, indent=2, ensure_ascii=False)

        async def searx_read_url(args: dict[str, Any]) -> str:
            if read_url is None:
                raise RuntimeError("URL reader is not configured")
            result = await read_url({"url": _required_string(args, "url"), "include_content": True})
            text = str(result.get("text", "")) if isinstance(result, dict) else str(result)
            if _boolean(args.get("readHeadings"), "readHeadings", False):
                return "\n".join(line for line in text.splitlines() if line.lstrip().startswith("#"))
            section = args.get("section")
            if section is not None:
                section = _string(section, "section").casefold()
                lines = text.splitlines()
                start = next(
                    (
                        index
                        for index, line in enumerate(lines)
                        if line.lstrip().startswith("#") and section in line.casefold()
                    ),
                    None,
                )
                if start is not None:
                    level = len(lines[start]) - len(lines[start].lstrip("#"))
                    end = next(
                        (
                            index
                            for index in range(start + 1, len(lines))
                            if lines[index].startswith("#")
                            and len(lines[index]) - len(lines[index].lstrip("#")) <= level
                        ),
                        len(lines),
                    )
                    text = "\n".join(lines[start:end])
            paragraph_range = args.get("paragraphRange")
            if paragraph_range is not None:
                value = _string(paragraph_range, "paragraphRange").strip()
                match = re.fullmatch(r"(\d+)(?:-(\d*)?)?", value)
                if match is None:
                    raise ValueError("paragraphRange must look like 3, 1-5, or 10-")
                paragraphs = re.split(r"\n\s*\n", text)
                first = max(1, int(match.group(1)))
                last = int(match.group(2)) if match.group(2) else first if "-" not in value else len(paragraphs)
                text = "\n\n".join(paragraphs[first - 1 : last])
            start_char = args.get("startChar", 0)
            max_length = args.get("maxLength")
            if isinstance(start_char, bool) or not isinstance(start_char, (int, float)) or start_char < 0:
                raise ValueError("startChar must be a non-negative number")
            if max_length is not None and (
                isinstance(max_length, bool) or not isinstance(max_length, (int, float)) or max_length < 1
            ):
                raise ValueError("maxLength must be a positive number")
            start_index = int(start_char)
            return text[start_index:] if max_length is None else text[start_index : start_index + int(max_length)]

        executors["mcp__searxng__searxng_search_suggestions"] = searx_suggestions
        executors["mcp__searxng__searxng_instance_info"] = searx_instance_info
        executors["mcp__searxng__web_url_read"] = searx_read_url

        try:
            sentinel_tools = await mcp.list_tools()
        except BaseException:
            await pipeline_executors.aclose()
            await http_client.aclose()
            raise
        for tool in sentinel_tools:
            model_name = f"mcp__sentinel__{tool.name}"
            definitions.append(_mcp_tool_definition("sentinel", tool))

            async def call_sentinel(args: dict[str, Any], raw_name: str = tool.name) -> str:
                return _result_text(await mcp.call_tool(raw_name, args))

            executors[model_name] = call_sentinel

        firefox_base = (firefox_mcp_base_url or "").rstrip("/")
        if firefox_base:
            try:
                response = await http_client.get(f"{firefox_base}/tools")
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError):
                payload = {}
            firefox_tools = payload.get("tools", []) if isinstance(payload, dict) else []
            for tool in firefox_tools:
                if not isinstance(tool, dict) or not isinstance(tool.get("name"), str) or not tool["name"]:
                    continue
                model_name = f"mcp__firefox__{tool['name']}"
                definitions.append(_adapter_tool_definition("firefox", tool))

                async def call_firefox(args: dict[str, Any], raw_name: str = tool["name"]) -> str:
                    result = await http_client.post(
                        f"{firefox_base}/call",
                        json={"name": raw_name, "arguments": args},
                    )
                    result.raise_for_status()
                    return _result_text(result.json())

                executors[model_name] = call_firefox

        return cls(definitions, executors, pipeline_executors, http_client)

    def get(self, name: str) -> ToolExecutor | None:
        return self._executors.get(name)

    async def aclose(self) -> None:
        try:
            await self._pipeline_executors.aclose()
        finally:
            await self._http_client.aclose()


def _required_string(args: dict[str, Any], name: str) -> str:
    value = args.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _string(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return value


def _boolean(value: Any, name: str, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _kill_process_group(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
