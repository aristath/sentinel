# GET /api/backups/r2

List all backups from Cloudflare R2.

**Description:**
Returns a list of all backup files stored in Cloudflare R2. Backups are stored as tar.gz files containing database snapshots and configuration.

**Request:**
- Method: `GET`
- Path: `/api/backups/r2`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "backups": [
      {
        "key": "sentinel-backup-2024-01-15-103000.tar.gz",
        "size": 52428800,
        "last_modified": "2024-01-15T10:30:00Z",
        "etag": "abc123def456"
      }
    ],
    "count": 5
  }
  ```

**Error Responses:**
- `200 OK` with error in body: R2 backup service not configured
- `500 Internal Server Error`: R2 connection error, timeout
