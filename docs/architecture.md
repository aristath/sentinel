# Architecture

## Runtime overview

```text
Browser / Go TUI / Arduino app
              │
              ▼
      FastAPI on port 8000
              │
     ┌────────┼───────────────┐
     ▼        ▼               ▼
 Portfolio  Planner      Administration APIs
 services   + strategy   settings/jobs/tasks/AI
     │        │               │
     └────────┴───────┬───────┘
                      ▼
                 SQLite database
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
   TraderNet/Freedom24     Optional satellites
                          LLM/search/memory/
                          summarizer/forecasting
```

`main.py` starts Uvicorn. The FastAPI lifespan in `sentinel/app.py` initializes
shared services, the database, fixed jobs, the editable folder-task runtime, and
the optional LED controller. Shutdown stops those runtimes and closes shared
resources.

The same process exposes a built-in [MCP server](mcp.md) at `/mcp`. MCP is a
transport adapter over the same services and runtimes, not a separate control
plane or process.

## Major packages

| Path | Ownership |
|---|---|
| `sentinel/api/routers/` | HTTP contracts and dependency wiring |
| `sentinel/services/` | Reusable portfolio state and valuation |
| `sentinel/database/` | SQLite connection, schema, migrations, and queries |
| `sentinel/planner/` | Ideal weights, cash constraints, recommendation construction |
| `sentinel/strategy/` | Deterministic contrarian price signal |
| `sentinel/jobs/` | Fixed APScheduler jobs and their registry |
| `sentinel/tasks/` | Editable folder-task definitions, queue, worker, checkpoints |
| `sentinel/task_definitions/` | Bundled AI research tasks and prompts |
| `sentinel/ai/` | LLM client, tools, research units, pgvector memory |
| `sentinel/forecasting/` | Forecast service/client, series construction, scoring |
| `sentinel/led/` | Optional LED controller and bridge state |
| `sentinel/mcp_server.py` | MCP tool definitions and FastAPI-mounted ASGI application |
| `web/src/` | Lit/Teract browser application |
| `TUI/` | Independent Go terminal client |
| `arduino-app/`, `firmware/` | UNO Q application and MCU sketches |

## Portfolio data flow

1. Fixed sync jobs read positions, prices, quotes, trades, cash flows, dividends,
   exchange rates, security metadata, and benchmarks from the broker.
2. `Database` persists the normalized state in SQLite.
3. Portfolio services calculate current EUR valuation from positions, cash, live
   prices, and exchange rates.
4. `AllocationCalculator` combines AI research ratings, portfolio constraints,
   deterministic opportunity signals, recent-event memory, and optional forecast
   scores into ideal weights.
5. `RebalanceEngine` turns target gaps into lot-aware, fee-aware recommendations
   across all markets, regardless of opening hours. Funding sells only exist to
   support a planned buy, apart from explicit safety/exit rules.
6. In `research` mode the result is advisory. In `live` mode
   `trading:execute` may submit at most one ranked transaction per execution
   window and replans from broker-confirmed state on the next cycle. Only trades
   on open markets execute. All planned sells must complete before any buy;
   closed-market buys do not block other buys.

## Two scheduling systems

Sentinel deliberately has two scheduling layers:

- Fixed jobs in `sentinel/jobs/runner.py` operate core portfolio infrastructure.
- Editable folder tasks in `sentinel/tasks/runtime.py` operate the AI research
  pipeline and user-defined workflows.

They share APScheduler and SQLite persistence but have different registries,
payloads, and APIs. See [Scheduler](scheduler.md) and [Tasks](tasks.md).

## Frontend serving

During development Vite serves modules and proxies `/api`. In production,
FastAPI serves `web/dist/` and uses a catch-all route for client navigation.
The frontend uses light-DOM custom elements so Teract components and application
components participate in the same inherited terminal theme.

## External systems

| System | Purpose | Failure behavior |
|---|---|---|
| TraderNet/Freedom24 | Portfolio, quotes, history, orders, Favorites | Sync/job failure is recorded; live execution cannot proceed without required state |
| Inference router | OpenAI-compatible LLM for folder-task prompts | AI task fails; portfolio API remains available |
| SearXNG/browser search | Research discovery | Individual tool/task call fails |
| URL summarizer | Source extraction | Individual research step fails |
| PostgreSQL/pgvector | Shared research memory | Memory endpoints/status report the failure; portfolio logic continues |
| Forecasting service | Optional time-series forecasts | Status reports outage; planner uses deterministic score without fresh forecast input |
| Arduino UNO Q | Ambient display | Bridge health becomes stale; core service continues |

## Source-of-truth boundaries

- Runtime configuration: `Settings` plus `DEFAULTS` in `sentinel/settings.py`
- SQLite schema: schema strings and migrations in `sentinel/database/`
- Fixed job names: `TASK_REGISTRY` in `sentinel/jobs/runner.py`
- Bundled task definitions: `sentinel/task_definitions/`
- User task overrides/artifacts: `$SENTINEL_HOME`
- HTTP discovery: running `/openapi.json`
- Production launch contract: `systemd/sentinel.service`
