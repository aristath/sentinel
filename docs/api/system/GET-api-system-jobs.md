# GET /api/system/jobs

Get background job status.

**Description:**
Returns status information for all background jobs including execution history, schedules, last run times, and next run times.

**Request:**
- Method: `GET`
- Path: `/api/system/jobs`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "total_jobs": 25,
    "jobs": [
      {
        "name": "sync-cycle",
        "schedule": "0 2 * * *",
        "last_run": "2024-01-15T02:00:00Z",
        "next_run": "2024-01-16T02:00:00Z",
        "status": "active"
      }
    ],
    "last_run": "2024-01-15T02:00:00Z",
    "next_run": "2024-01-15T10:00:00Z"
  }
  ```
  - `total_jobs` (integer): Total number of registered jobs
  - `jobs` (array): Array of job information objects
  - `last_run` (string, optional): Last job execution time
  - `next_run` (string, optional): Next scheduled job execution time

**Error Responses:**
- `500 Internal Server Error`: Service error
