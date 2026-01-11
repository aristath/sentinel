# POST /api/backups/r2

Create a new backup to R2.

**Description:**
Triggers an immediate backup job that creates a backup of all databases and configuration, then uploads it to Cloudflare R2. The backup runs asynchronously as a background job.

**Request:**
- Method: `POST`
- Path: `/api/backups/r2`
- Body: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "status": "success",
    "message": "Backup job enqueued",
    "job_id": "manual-r2-backup-1705320600000000000"
  }
  ```

**Error Responses:**
- `200 OK` with error in body: R2 backup service not configured
- `500 Internal Server Error`: Failed to enqueue backup job

**Side Effects:**
- Enqueues a backup job in the job queue
- Job runs asynchronously and creates backup file
- Backup is uploaded to R2 when job executes
