# AI research

Base path: `/api/ai`

These endpoints observe and enqueue the editable-task research pipeline. See
[AI pipeline](../ai-pipeline.md) for task dependencies and artifacts.

## `GET /api/ai/models`

Discovers model IDs from the configured OpenAI-compatible inference endpoint.
Satellite failure is reported in the response rather than making the endpoint
fail:

```json
{
  "ok": true,
  "models": ["model-id"]
}
```

On failure, `ok` is false, `models` is empty, and `error` contains the reason.

## `POST /api/ai/prompt`

Runs a prompt through the configured LLM and Sentinel's standard tool loop. The
model can use the same search, browser fallback, URL-reading, and workspace file
tools as editable AI tasks. Sentinel supplies its existing system prompt and it
cannot be overridden. `temperature` is optional; when omitted, Sentinel leaves
it out of the inference request so the backend default applies.

```json
{
  "prompt": "Summarize the investment case for AIR.EU.",
  "temperature": 0.2
}
```

The response is `{ "output": "..." }`. An empty or non-string prompt returns
400, and an LLM failure returns 502.

## `POST /api/ai/chat`

Runs one multi-turn Research chat message. Sentinel supplies the inherited
system prompt. The model receives the complete Sentinel MCP catalog, the
SearXNG and Firefox MCP catalogs, URL-reading tools, Bash, and filesystem
tools.

```json
{
  "message": "Compare CATL's current report with the evidence files.",
  "history": [
    { "role": "user", "content": "Open the CATL artifacts." },
    { "role": "assistant", "content": "I found the security unit." }
  ]
}
```

`history` is optional. Entries use `user` or `assistant` roles. Sentinel keeps
the newest complete messages that fit after the inherited system prompt,
current message, and tool schemas in a 128k-token request window.

The response is a Server-Sent Events stream. Every frame contains one JSON
object in its `data` field. Event object types are:

| Type | Meaning |
|---|---|
| `context` | The context limit and retained/dropped history counts |
| `reasoning_delta` | Incremental model reasoning for one inference turn |
| `content_delta` | Incremental assistant-visible output |
| `tool_start` | Tool name and complete arguments immediately before execution |
| `tool_result` | The complete result returned to the model |
| `turn_reset` | A streamed turn was discarded by the repetition guard |
| `done` | Final answer and successful stream completion |
| `error` | The stream failed; `error` contains the message |

The Research UI stores one conversation in browser-local storage, so its
answers, reasoning, and tool records survive page reloads and browser restarts.

## `GET /api/ai/status`

Returns the pipeline dashboard state:

| Field | Meaning |
|---|---|
| `enabled` | At least one AI task has an active schedule/policy |
| `running` | Current unit/task identity, start time, and elapsed seconds |
| `queued` | Queued AI task runs |
| `staleness` | Security stale and total counts plus most-stale unit |
| `last_run` | Most recent completed or failed AI run |
| `memory` | Memory finding count, most recent write, or satellite error |
| `next_tick_at` | Reserved; currently `null` |

Memory statistics are cached briefly and memory outages do not take down this
status endpoint.

## `GET /api/ai/units`

Lists research units and their artifact/status state.

Query parameters:

| Parameter | Values | Default |
|---|---|---|
| `kind` | `security`, `portfolio`, or omitted | all kinds |
| `stale_only` | boolean | `false` |

Response: `{ "units": [...] }`. Each unit includes `kind`, `key`, `label`,
`last_analyzed_at`, `age_days`, `stale`, `status`, `last_error`, and available
artifact names.

## `POST /api/ai/requests`

Queues one analysis or security-rating task.

```json
{
  "kind": "analyze",
  "unit_kind": "security",
  "unit_key": "AIR.EU"
}
```

- `kind`: `analyze` or `rate`
- `unit_kind`: `security`
- `unit_key`: an existing unit key
- Rating is supported only for security units.

Success returns status 201:

```json
{
  "status": "queued",
  "request_id": "run-id"
}
```

## `GET /api/ai/history`

Returns completed/failed AI task history as `{ "history": [...] }`. `limit`
defaults to 50 and is clamped to 1 through 200. Each row contains task and unit
identity, normalized status, duration, error, and execution time.

## `GET /api/ai/artifacts/{kind}/{unit_key}/{name}`

Reads an allowlisted generated artifact for a `security` or `portfolio` unit.
The response contains `name`, textual `content`, and
`modified_at`. Unknown units, disallowed names, missing files, and paths outside
the artifact root return 404.

Allowlisted filenames are `analysis.md`, `context.md`, `evidence-pack.md`,
`latest.json`, `profile.json`, `rating.json`, `ratings.json`, `report.md`, and
`summary.md`.
