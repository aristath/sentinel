# POST /api/system/deployment/hard-update

Trigger hard update deployment.

**Description:**
Forces a hard update deployment that overwrites existing files even if no changes are detected. Useful for recovery or forced updates. Forces deployment of all services, frontend, display app, and sketch regardless of change detection.

**Request:**
- Method: `POST`
- Path: `/api/system/deployment/hard-update`
- Body: None

**Response:**
- Status: `200 OK` on success, `500 Internal Server Error` on failure
- Body (success):
  ```json
  {
    "status": "success",
    "success": true,
    "deployed": true,
    "commit_before": "abc123",
    "commit_after": "def456",
    "services": ["sentinel", "frontend"],
    "sketch_deployed": true,
    "duration": "45s",
    "error": null,
    "message": "Hard update completed successfully"
  }
  ```
- Body (failure):
  ```json
  {
    "status": "error",
    "success": false,
    "deployed": false,
    "commit_before": "abc123",
    "commit_after": "abc123",
    "services": [],
    "sketch_deployed": false,
    "duration": "10s",
    "error": "Failed to download binaries",
    "message": "Failed to download binaries"
  }
  ```

**Error Responses:**
- `500 Internal Server Error`: Hard update failed

**Side Effects:**
- Forces deployment even if no changes detected
- Overwrites all service binaries and files
- Deploys Go services, frontend, display app, sketch
- Restarts services automatically
