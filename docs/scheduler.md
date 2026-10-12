# Scheduler

Sentinel has two scheduling systems sharing one application process:

1. Fixed portfolio jobs registered in `sentinel/jobs/runner.py`.
2. Editable folder tasks managed by `sentinel/tasks/runtime.py`.

Both start during the FastAPI lifespan. They use different database tables and
APIs and should not be confused.

## Fixed jobs

| Job type | Closed/default interval | Market-open interval | Timing | Purpose |
|---|---:|---:|---|---|
| `sync:portfolio` | 30 min | 5 min | any | Sync broker positions |
| `sync:prices` | 30 min | 5 min | any | Maintain historical prices |
| `sync:quotes` | 1440 min | 1440 min | any | Refresh current quotes |
| `sync:metadata` | 1440 min | 1440 min | any | Refresh security metadata and reconcile Favorites |
| `sync:exchange_rates` | 60 min | 60 min | any | Refresh FX rates |
| `sync:trades` | 60 min | 60 min | any | Sync trade history |
| `sync:cashflows` | 1440 min | 1440 min | any | Sync deposits, withdrawals, fees, and taxes |
| `sync:dividends` | 1440 min | 1440 min | any | Sync dividends |
| `sync:benchmarks` | 1440 min | 1440 min | any | Discover and price benchmark indices |
| `decay:ai_research_multipliers` | 1440 min | 1440 min | any | Move stale research ratings toward neutral |
| `snapshot:backfill` | 1440 min | 1440 min | any | Fill missing portfolio snapshots |
| `trading:check_markets` | 30 min | 30 min | market open | Refresh market state |
| `trading:execute` | 30 min | 15 min | market open | Replan and submit at most one ranked transaction |
| `trading:rebalance` | 60 min | 60 min | any | Generate recommendations |
| `trading:balance_fix` | 15 min | 15 min | any | Repair negative currency balances |
| `planning:refresh` | 60 min | 30 min | any | Refresh the current plan without execution |
| `forecast:run` | 10080 min | 10080 min | all markets closed | Generate weekly forecasts |
| `forecast:evaluate` | 1440 min | 1440 min | any | Evaluate matured forecasts |
| `backup:r2` | 1440 min | 1440 min | any | Upload a data backup to R2 |

Intervals and timing are seeded only when a schedule does not already exist;
stored production values may differ. `/api/jobs/schedules` is the current
runtime view.

Timing codes are `0` any time, `1` after market close, `2` during market open,
and `3` all markets closed. The runner re-evaluates market-dependent intervals
periodically.

Fixed jobs can be inspected, run, and rescheduled through the
[Jobs API](api/jobs.md). Manual `run` bypasses the schedule timing gate but does
not bypass the job's internal safety logic.

`trading:execute` replans across all markets from refreshed broker state. Market
hours only determine which planned trades may execute. While any planned sell
remains, it may submit an open-market sell but no buy. Sales may execute out of
rank order when their markets open. With no remaining sells, it submits the
highest-ranked open-market buy, skipping closed-market buys. An outstanding
submitted order must be reconciled before another transaction is submitted.

## Editable task schedules

An enabled folder task may define either or both:

- `schedule`: a five-field crontab expression.
- `schedulePolicy.staleAfterSeconds`: eligibility after the previous successful
  result becomes stale.

`schedulePolicy.runWhen` is `immediate` or `idle`. Idle stale tasks wait until
the folder-task runtime has no active work. `priority` affects durable queue
ordering. The stale-policy evaluator runs every minute, offset from startup.

Scheduled task queue entries use a stable dedupe key so the same schedule does
not accumulate duplicate active runs. A task disabled or rescheduled while work
is queued is checked again before execution.

See [Editable tasks](tasks.md) and [Tasks API](api/tasks.md).

## Startup and recovery

At startup Sentinel:

1. Recovers interrupted folder-task work into a runnable state.
2. Removes checkpoints belonging to terminal runs.
3. Synchronizes task definitions into persisted schedule rows.
4. Installs the stale-policy evaluator.
5. Starts the durable queue worker after `/api/health` becomes reachable.
6. Initializes fixed APScheduler jobs and startup catch-up behavior.

Fixed job executions are recorded in `job_history`. Folder-task runs, events,
and checkpoints are stored separately. A process restart must not be represented
as successful completion.

## Operational checks

```bash
curl --fail http://localhost:8000/api/jobs
curl --fail http://localhost:8000/api/jobs/schedules
curl --fail http://localhost:8000/api/tasks
```

Use the status bar/UI or these endpoints to distinguish a currently running
fixed job from an AI folder-task run.
