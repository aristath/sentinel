# POST /api/system/sync/securities-data

Sync securities data.

**Description:**
Triggers synchronization of securities metadata and fundamental data from external sources.

**Request:**
- Method: `POST`
- Path: `/api/system/sync/securities-data`
- Body: None

**Response:**
- Status: `200 OK` on success
- Body: Sync result

**Error Responses:**
- `500 Internal Server Error`: Sync failed

**Side Effects:**
- Updates security metadata
- Fetches fundamental data
- Updates security information


### System Job Triggers

All job trigger endpoints accept `POST` requests to manually trigger background jobs. Jobs are enqueued in the job queue and executed asynchronously. All trigger endpoints follow the same pattern:

**Common Request:**
- Method: `POST`
- Path: `/api/system/jobs/{job_name}`
- Body: None

**Common Response:**
- Status: `200 OK` on success
- Body:
  ```json
  {
    "status": "success",
    "message": "Job triggered successfully"
  }
  ```

**Common Error Responses:**
- `200 OK` with error in body: Job not registered yet
- `500 Internal Server Error`: Failed to enqueue job

**Common Side Effects:**
- Job is enqueued in the job queue
- Job executes asynchronously
- Results are available via job status endpoints

**Available Job Triggers:**

#### POST /api/system/jobs/health-check

Trigger a background job manually.

**Request:**
- Method: `POST`
- Path: `/api/system/jobs/{job_name}`
- Path Parameters:
  - `job_name` (required): Name of the job to trigger (e.g., `sync-cycle`, `planner-batch`, `health-check`)
- Body: None

**Response:**
- Status: `200 OK` on success, `400 Bad Request` if job name invalid
- Body: Job execution result

**Available Job Names:**
- `health-check` - Trigger health check job
- `sync-cycle` - Trigger sync cycle
- `dividend-reinvestment` - Trigger dividend reinvestment
- `planner-batch` - Trigger planner batch
- `event-based-trading` - Trigger event-based trading
- `tag-update` - Trigger tag update
- `sync-trades` - Sync trades
- `sync-cash-flows` - Sync cash flows
- `sync-portfolio` - Sync portfolio
- `sync-prices` - Sync prices
- `check-negative-balances` - Check for negative balances
- `update-display-ticker` - Update display ticker
- And many more (see individual job sections below)
