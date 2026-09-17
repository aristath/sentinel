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

## `GET /api/ai/status`

Returns the pipeline dashboard state:

| Field | Meaning |
|---|---|
| `enabled` | At least one AI task has an active schedule/policy |
| `running` | Current unit/task identity, start time, and elapsed seconds |
| `queued` | Queued AI task runs |
| `staleness` | Macro/security stale and total counts plus most-stale unit |
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
| `kind` | `security`, `macro`, `portfolio`, or omitted | all kinds |
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
- `unit_kind`: `security` or `macro`
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

Reads an allowlisted generated artifact for a `security`, `macro`, or
`portfolio` unit. The response contains `name`, textual `content`, and
`modified_at`. Unknown units, disallowed names, missing files, and paths outside
the artifact root return 404.

Allowlisted filenames are `analysis.md`, `evidence-pack.md`, `latest.json`,
`profile.json`, `rating.json`, `ratings.json`, `report.md`, and `summary.md`.
