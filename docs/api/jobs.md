# Jobs

Base path: `/api/jobs`

Manage the APScheduler-based job system: trigger jobs manually, inspect schedules, and review execution history.

---

## `GET /api/jobs`

Returns the current running job (if any), the next scheduled jobs, and recent job history.

**Response**
```json
{
  "current": null,
  "upcoming": [
    { "job_type": "sync:quotes", "next_run": "2026-04-27T11:00:00" }
  ],
  "recent": [
    { "job_type": "sync:portfolio", "status": "completed", "executed_at": 1745748000 }
  ]
}
```

---

## `POST /api/jobs/{job_type}/run`

Manually trigger a job by type. Runs immediately, regardless of schedule.

**Path params**
- `job_type` — Job type string (see table below)

**Available job types**

| Job type | Description |
|---|---|
| `sync:portfolio` | Sync positions from broker |
| `sync:prices` | Fetch 20-year historical prices for all securities |
| `sync:quotes` | Refresh live quote data |
| `sync:metadata` | Sync security metadata from broker |
| `sync:exchange_rates` | Fetch current FX rates |
| `sync:trades` | Sync trade history |
| `sync:cashflows` | Sync cash flow history |
| `sync:dividends` | Sync dividend records |
| `sync:benchmarks` | Refresh the benchmark-indices roster from Tradernet and price-sync every known benchmark. Auto-discovers any new index Tradernet exposes. |
| `decay:user_multipliers` | Daily walk over `securities`: any row whose slider is ≥ 7 days old gets one step closer to neutral via `value = 0.5 + (value − 0.5) × 0.9`. Touching the slider resets the timer. |
| `snapshot:backfill` | Reconstruct missing portfolio snapshots |
| `trading:check_markets` | Check market open status |
| `trading:execute` | Sync broker state, calculate a fresh current-window plan, and submit at most one transaction |
| `trading:rebalance` | Generate new trade recommendations via Planner |
| `trading:balance_fix` | Fix quantity mismatches between DB and broker |
| `planning:refresh` | Refresh planner state without generating trades |
| `backup:r2` | Upload DB backup to Cloudflare R2 |

**Response**
```json
{ "status": "ok", "job_type": "sync:portfolio" }
```

**Errors**
- `404` — Unknown job type

---

## `POST /api/jobs/refresh-all`

Resets the `last_run` timestamp for all jobs to zero and reschedules them in APScheduler. Useful after configuration changes to force all jobs to run at their next opportunity.

**Response**
```json
{ "status": "ok", "message": "All jobs rescheduled" }
```

---

## `GET /api/jobs/schedules`

Returns all job schedule configurations, enriched with last execution info and next scheduled run time.

**Response**
```json
{
  "schedules": [
    {
      "job_type": "sync:portfolio",
      "interval_minutes": 60,
      "interval_market_open_minutes": 15,
      "market_timing": 0,
      "market_timing_label": "Any time",
      "description": "Sync positions from broker",
      "category": "sync",
      "last_run": "2026-04-27T10:00:00",
      "last_status": "completed",
      "next_run": "2026-04-27T11:00:00"
    }
  ]
}
```

**`market_timing` values**

| Value | Meaning |
|---|---|
| `0` | Any time |
| `1` | After market close |
| `2` | During market open |
| `3` | All markets closed |

---

## `PUT /api/jobs/schedules/{job_type}`

Update the schedule configuration for a job. Takes effect immediately — the job is rescheduled in APScheduler.

**Path params**
- `job_type` — Job type string

**Request body** (all fields optional)
```json
{
  "interval_minutes": 60,
  "interval_market_open_minutes": 15,
  "market_timing": 2
}
```

**Constraints**
- `interval_minutes` and `interval_market_open_minutes` must be 1–10080 (one week max)
- `market_timing` must be 0, 1, 2, or 3

**Response**
```json
{ "status": "ok" }
```

**Errors**
- `404` — Unknown job type
- `400` — Validation failure

---

## `GET /api/jobs/history`

Returns recent job execution history.

**Query params**
- `job_type` (string, optional) — Filter to a specific job type
- `limit` (int, default `50`) — Maximum number of records to return

**Response**
```json
{
  "history": [
    {
      "job_id": "sync:portfolio",
      "job_type": "sync:portfolio",
      "status": "completed",
      "error": null,
      "duration_ms": 312,
      "executed_at": 1745748000,
      "retry_count": 0
    }
  ]
}
```

| Field | Description |
|---|---|
| `job_id` | Scheduler job identifier (usually same as `job_type`) |
| `status` | `completed` or `failed` |
| `retry_count` | Number of retries before this execution |
