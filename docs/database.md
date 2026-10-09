# Database

## Ownership and location

Sentinel uses SQLite through `aiosqlite`. Application code obtains the shared
`Database` service and calls its async methods; route, planner, job, and task
modules must not open independent SQLite connections or add ad-hoc SQL.

The database file is:

```text
$SENTINEL_DATA_DIR/sentinel.db
```

`SENTINEL_DATA_DIR` defaults to the repository's `data/` directory. SQLite may
also create `sentinel.db-wal` and `sentinel.db-shm` while the database is open.
Those three files form one live database state.

## Schema groups

The canonical `CREATE TABLE` definitions and migrations are in
`sentinel/database/main.py`. The current tables are:

| Group | Tables | Purpose |
|---|---|---|
| Configuration | `settings` | JSON-encoded runtime configuration |
| Universe | `securities`, `positions`, `prices` | Tradable securities, current holdings, OHLCV history |
| Benchmarks | `benchmarks`, `benchmark_prices` | Non-tradable index metadata and prices |
| Broker history | `trades`, `cash_balances`, `cash_flows`, `dividends`, `fx_rates_history` | Synced account history and valuation inputs |
| Cache | `cache` | Persistent key/value cache with optional expiry |
| Fixed scheduler | `job_schedules`, `job_history` | Core job cadence and execution records |
| Folder-task scheduler | `scheduled_tasks`, `scheduled_task_state`, `work_queue` | Editable-task schedule state and durable queue |
| Folder-task execution | `task_runs`, `task_run_events`, `task_run_checkpoints` | Run metadata, logs/live output, replayable call checkpoints |
| Forecasting | `forecast_runs`, `forecast_points`, `forecast_scores`, `forecast_evaluations` | Provider runs, quantiles, planner scores, evaluation |
| Portfolio history | `portfolio_snapshots` | Daily positions/cash snapshot JSON |
| Strategy | `strategy_state`, `planner_state` | Per-symbol tranche/rotation state and durable planner coordination |

Foreign keys protect benchmark and task relationships. Historical transaction
tables must not be deleted merely because a security becomes inactive.

## Initialization and migrations

`Database.connect()` creates missing tables, applies idempotent column/table
migrations, removes explicitly retired settings/schedules, and seeds defaults.
Schema changes must support an existing production database:

1. Update the canonical schema.
2. Add an idempotent migration for existing databases.
3. Add a test starting from the previous shape.
4. Update this document and affected API documentation.

Do not require an operator to run raw SQL as the normal upgrade path.

AI ratings have no database default. `ai_research_multiplier` and its source,
analysis and update timestamp are `NULL` until a rating is explicitly recorded.
Initialization never fills a missing score or manufactures a rating timestamp.
The nullable-score migration removes legacy defaults and clears unauthored
`0.5`/`1.0` values with migration provenance and no analysis. Genuine ratings,
including explicit neutral, zero and maximum scores, retain their metadata.
The upgrade preserves security rowids and history and invalidates planner caches.

## Concurrency

All database operations use the shared async database layer. Long multi-step
operations use the project's database operation pipeline/serialization paths
where provided. A second process directly mutating the live database can bypass
those guarantees and cause locks or inconsistent read-modify-write sequences.

Never copy, replace, or inspect a live database in a way that ignores its WAL.
For a consistent backup, use Sentinel's backup implementation or stop the
service before copying `sentinel.db` and any sidecars as a unit.

## Backup and restore

The `backup:r2` job snapshots the database before packaging the configured data
directory and `$SENTINEL_HOME` when it is separate. The API exposes backup run
and status endpoints; see [Backup API](api/backup.md).

Before any manual restore:

1. Stop `sentinel.service`.
2. Preserve the current database and sidecars in a timestamped directory.
3. Restore the intended consistent snapshot.
4. Remove stale sidecars only when they do not belong to the restored snapshot.
5. Start the service and verify `/api/health`, schema initialization, jobs, and
   representative portfolio/history endpoints.

Production commands and rollback boundaries are in [Deployment](deployment.md).

## Data retention

- Securities can be made inactive without losing transaction history.
- Permanent security deletion is guarded when positions, trades, or dividends
  exist.
- Task-run history and checkpoints support recovery and audit; delete runs only
  through the task API/runtime.
- Forecast runs and evaluations are operational history used to assess forecast
  quality.
- Portfolio snapshots are reconstructed by `snapshot:backfill` when needed.

## Testing

Database changes require targeted database/migration tests plus the full suite.
Use isolated temporary databases or the simulation database; never point tests
at `data/sentinel.db`. See [Testing](testing.md).
