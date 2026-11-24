# Sentinel Agent Guide

This file contains the rules and high-frequency facts needed when modifying
Sentinel. The canonical explanatory documentation is indexed from
[`docs/README.md`](docs/README.md).

## Commands

Activate the Python 3.13+ environment before running Python tools:

```bash
source .venv/bin/activate
python main.py
pytest
ruff check .
ruff format .
pyright
```

Create or refresh the environment with:

```bash
uv sync --locked --extra dev
```

Frontend commands run from `web/`:

```bash
npm install
npm run dev
npm run build
```

Tracked development defaults are Vite `5173` and Sentinel `8000`. Use
invocation-only overrides for workstation-specific ports.

## Current architecture

- `main.py` starts Uvicorn; the default port is `8000`.
- `sentinel/app.py` owns FastAPI lifespan, dependencies, scheduler, folder-task
  runtime, LED controller, API routers, and production static serving.
- `sentinel/database/` owns all SQLite schema and operations.
- `sentinel/services/` owns reusable portfolio valuation/state services.
- `sentinel/planner/` owns ideal allocation and executable recommendations.
- `sentinel/strategy/contrarian.py` owns deterministic price signals.
- `sentinel/forecasting/` owns the provider-neutral client, scoring, series
  preparation, and optional forecasting service.
- `sentinel/ai/` owns LLM, research-unit, memory, and tool integrations.
- `sentinel/tasks/` owns editable folder-task storage and durable execution.
- `sentinel/task_definitions/` contains bundled task definitions and prompts.
- `sentinel/jobs/` owns fixed application jobs and APScheduler integration.
- `sentinel/led/`, `arduino-app/`, and `firmware/` own optional hardware output.
- `web/src/` is a JavaScript frontend using Lit, Web Awesome, and
  CodeMirror. It is not React and does not use Mantine.
- `TUI/` is the separate Go terminal client.

See [Architecture](docs/architecture.md) for data flow and ownership.

## API routers

All application routes are mounted under `/api` except the production frontend
fallback:

| File | Prefixes |
|---|---|
| `ai.py` | `/api/ai` |
| `backup.py` | `/api/backup` |
| `forecasts.py` | `/api/forecasts` |
| `jobs.py` | `/api/jobs` |
| `memory.py` | `/api/memory` |
| `planner.py` | `/api/planner` |
| `portfolio.py` | `/api/portfolio` |
| `securities.py` | `/api/securities`, `/api/prices`, `/api/unified` |
| `settings.py` | `/api/settings`, `/api/led` |
| `system.py` | `/api/health`, `/api/version`, `/api/cache`, `/api/backtest`, `/api/exchange-rates`, `/api/markets`, `/api/meta`, `/api/pulse` |
| `tasks.py` | `/api/tasks`, `/api/task-runs`, `/api/scheduler` |
| `trading.py` | `/api/trades`, `/api/cashflows`, direct `/api/securities/{symbol}/buy|sell` |

The hand-written contract is [docs/api/README.md](docs/api/README.md); running
OpenAPI is available at `/openapi.json`, `/docs`, and `/redoc`.

## Fixed scheduled jobs

The exact registry is `TASK_REGISTRY` in `sentinel/jobs/runner.py`:

| Job type | Function |
|---|---|
| `sync:portfolio` | `sync_portfolio` |
| `sync:prices` | `sync_prices` |
| `sync:quotes` | `sync_quotes` |
| `sync:metadata` | `sync_metadata` |
| `sync:exchange_rates` | `sync_exchange_rates` |
| `sync:trades` | `sync_trades` |
| `sync:cashflows` | `sync_cashflows` |
| `sync:dividends` | `sync_dividends` |
| `sync:benchmarks` | `sync_benchmarks` |
| `decay:ai_research_multipliers` | `decay_ai_research_multipliers` |
| `snapshot:backfill` | `snapshot_backfill` |
| `trading:check_markets` | `trading_check_markets` |
| `trading:execute` | `trading_execute` |
| `trading:rebalance` | `trading_rebalance` |
| `trading:balance_fix` | `trading_balance_fix` |
| `planning:refresh` | `planning_refresh` |
| `forecast:run` | `forecast_run` |
| `forecast:evaluate` | `forecast_evaluate` |
| `backup:r2` | `backup_r2` |

Editable AI tasks are a separate durable task runtime; do not add them to this
registry. See [Tasks](docs/tasks.md) and [Scheduler](docs/scheduler.md).

## Required conventions

### Database

- Use async methods on `sentinel.database.Database`; do not add ad-hoc SQL in
  application modules.
- The default database is `data/sentinel.db`; `SENTINEL_DATA_DIR` changes the
  containing directory.
- Schema creation and idempotent migrations live in `sentinel/database/`.
- Preserve historical trades, dividends, cash flows, and task runs.

### Settings

- Runtime configuration belongs in `sentinel/settings.py` and the database.
- New settings require a default, validation where appropriate, UI/API handling
  if editable, tests, and an update to [Configuration](docs/configuration.md).
- Settings are cached by the service objects that consume them; use existing
  update/invalidation paths.

### Trading

- `research` must never submit a live broker order.
- `live` may submit real orders. UI-only work must preserve this behavior.
- Preserve price-anomaly guards, lot sizing, trade permissions, market checks,
  fee handling, and cash constraints unless the requested strategy change
  explicitly alters them.

### Frontend

- Use Lit custom elements for application behavior and Web Awesome for
  interface components. Use native HTML for document and table semantics.
- Use Web Awesome's built-in theme and tokens for color, type, and spacing.
  Keep component-specific CSS with its component and shared layout in
  `web/src/sentinel.css`.
- Preserve light-DOM children; do not replace `innerHTML` or `textContent` around
  Lit `ChildPart` markers.
- Build output is tracked in `web/dist/` and served by FastAPI.

### Testing and formatting

- A red test, lint, build, or type-check result is a failure.
- Preserve unrelated worktree and index changes.
- Run the narrowest relevant checks while developing and the full appropriate
  gates before delivery. See [Testing](docs/testing.md).

## Common changes

### Add an API endpoint

1. Add the route in `sentinel/api/routers/`.
2. Export/import and mount it in `sentinel/app.py` when using a new router.
3. Add API tests.
4. Add the operation to `docs/api/` and keep route coverage exact.

### Change the database schema

1. Update the canonical schema in `sentinel/database/main.py`.
2. Add an idempotent migration in the database initialization path.
3. Add migration and method tests.
4. Update [Database](docs/database.md).

### Add a fixed job

1. Add the async function to `sentinel/jobs/tasks.py`.
2. Register it in `sentinel/jobs/runner.py`.
3. Seed its default schedule in `Database.seed_default_job_schedules()`.
4. Add task and runner tests.
5. Update [Scheduler](docs/scheduler.md), this file, and `docs/api/jobs.md`.

### Add or change an editable AI task

Follow [Tasks](docs/tasks.md). Bundled task definitions live under
`sentinel/task_definitions`; user overrides live under
`$SENTINEL_HOME/tasks`.

## Deployment

Production is `aristath@clara.local`, inside the `clara` toolbox container. The
user service tracks `origin/main`, starts `main.py --host 0.0.0.0`, and therefore
uses port `8000`. Read [Deployment and recovery](docs/deployment.md) before
changing service or database state.
