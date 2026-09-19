# Model Context Protocol

Sentinel exposes a Streamable HTTP MCP server at `/mcp` (and `/mcp/`). It runs inside the
existing FastAPI application, on the same port and with the same lifespan. The
production URL is therefore:

```text
http://clara.local:8000/mcp
```

There is no second service, port, database connection, or MCP-specific
configuration. MCP tools call the same application operations as the web API,
so settings persistence, task execution, job scheduling, broker access, and
research/live trading behavior remain identical.

An MCP client that accepts URL-based server configuration can use the endpoint
directly. The exact surrounding configuration format depends on the client;
the server entry itself is simply:

```json
{
  "url": "http://clara.local:8000/mcp"
}
```

## Tools

### System and portfolio

| Tool | Purpose |
|---|---|
| `sentinel_status` | Health, version, broker connection, and trading mode |
| `portfolio_get` | Current positions, cash, and value |
| `portfolio_composition_get` | Composition and portfolio metrics |
| `portfolio_performance_get` | P/L history for a selected period |
| `portfolio_period_stats_get` | Return statistics for every supported period |
| `portfolio_projection_get` | Long-range portfolio-value projection |
| `portfolio_plan_get` | Buy/sell recommendations and twelve-month target portfolio |
| `portfolio_alignment_get` | Allocation deviation and rebalance status |
| `markets_get` | Relevant market open/closed state |
| `exchange_rates_get` | Stored exchange rates to EUR |

Synchronization tools delegate directly to Sentinel's existing
operations and preserve their return values and failure behavior.

### Securities and account history

| Tool | Purpose |
|---|---|
| `securities_overview_get` | Unified positions, prices, allocation, and plan view |
| `securities_list` | Active and inactive universe rows |
| `security_get` | One security and its controls |
| `security_prices_get` | Validated historical prices |
| `security_prices_sync` | Synchronize one security's historical prices |
| `security_add` | Add or re-enable a broker security |
| `security_update` | Update aliases, execution controls, or AI multiplier |
| `security_remove` | Apply the normal safe universe-removal rules |
| `trades_get` | Filtered, paginated trade history |
| `cashflow_summary_get` | Aggregated EUR cash flows and portfolio profit |
| `security_buy` | Submit a buy through Sentinel's trading path |
| `security_sell` | Submit a sell through Sentinel's trading path |

`security_buy` and `security_sell` do not bypass Sentinel. They instantiate the
same `Security` service used by the HTTP API, including its trading-mode,
broker, quantity, and price protections.

### Settings and scheduled jobs

| Tool | Purpose |
|---|---|
| `settings_get` | Read all database-backed settings |
| `setting_set` | Persist one setting and perform normal cache invalidation |
| `strategy_settings_set` | Atomically validate and replace all strategy settings |
| `job_status_get` | Running job, next three scheduled jobs, and recent activity |
| `job_schedules_get` | Schedule definitions and runtime timestamps |
| `job_history_get` | All or per-job execution history |
| `job_run` | Run a registered job immediately |
| `job_schedule_update` | Update and reschedule a registered job |

`job_schedule_update` accepts the same fields as `PUT
/api/jobs/schedules/{job_type}`: `interval_minutes`,
`interval_market_open_minutes`, and `market_timing`.

`strategy_settings_set` exposes Sentinel's existing complete-group strategy
settings operation. `setting_set` exposes the existing individual-setting
operation without adding MCP-specific restrictions.

### Editable tasks

| Tool | Purpose |
|---|---|
| `tasks_list` | List task definitions |
| `task_get` | Read a task definition |
| `task_create` | Create a task |
| `task_meta_update` | Update metadata and resync the schedule |
| `task_delete` | Delete an idle task |
| `task_validate` | Validate a task definition |
| `task_files_list` | List a task's files |
| `task_file_get` | Read a task file |
| `task_file_save` | Create or replace a task file |
| `task_file_delete` | Delete a task file |
| `task_runs_enqueue` | Queue immediate or delayed task runs, individually or in batches |
| `task_runs_get` | List a task's executions |
| `task_run_get` | Read one execution and its output |
| `task_run_stop` | Stop queued or running work |

Edits use the same active-run protection and schedule resynchronization as the
web task editor. `task_meta_update` exposes the supported metadata fields
directly: `name`, `description`, `tags`, `enabled`, `schedule`, `cwd`,
`statePath`, `timeout`, and `schedulePolicy`.

`task_runs_enqueue` accepts one or more task requests. `eligibleAt` is a Unix
timestamp in seconds or milliseconds; a task remains queued until that time.
Each request may also carry `inputs`, `title`, `dedupeKey`, and `priority`.
Requests are passed to Sentinel's existing scheduler operation in their supplied
order, preserving its validation, deduplication, and enqueue behavior.

### AI research and forecasts

| Tool | Purpose |
|---|---|
| `ai_status_get` | Pipeline queue, running unit, staleness, and last run |
| `ai_prompt` | Run a prompt through Sentinel's configured LLM and standard tool loop |
| `ai_units_get` | List research units, optionally filtered or stale-only |
| `ai_history_get` | Completed and failed research work |
| `ai_artifact_get` | Read an allowlisted research artifact |
| `ai_artifact_files_list` | List every generated artifact, including intermediate work files |
| `ai_artifact_file_get` | Read any artifact by its artifact-root-relative path |
| `ai_artifact_search` | Search all textual artifacts for a literal string |
| `ai_research_run` | Queue analysis or rating for a research unit |
| `ai_models_get` | Discover models available to the configured AI service |
| `forecast_status_get` | Forecast service and recent-run status |
| `forecast_get` | Latest path, scores, and evaluation for a symbol |

`ai_prompt` accepts the user prompt and an optional temperature. It does not
accept a system prompt; Sentinel always supplies its existing system prompt. The
model receives the same search, browser fallback, URL-reading, and workspace file
tools used by editable AI tasks, so a prompt can gather current evidence instead
of relying only on model knowledge.

The three artifact-tree tools expose the generated files beneath
`$SENTINEL_HOME/tasks/artifacts`, including `.work` query, source, summary, and
finding intermediates. They complement `ai_artifact_get`, which remains the
canonical unit-oriented artifact reader.

### Backups

| Tool | Purpose |
|---|---|
| `backup_status_get` | List backup configuration state and available R2 backups |

## Implementation

The server definition and tool adapters live in `sentinel/mcp_server.py`.
`sentinel/app.py` mounts its ASGI application before the frontend catch-all and
runs the MCP session manager inside the existing application lifespan.

The dependency is the official Python MCP SDK, pinned to the compatible major
release in `pyproject.toml` and resolved in `uv.lock`.
