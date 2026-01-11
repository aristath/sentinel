# POST /api/system/deployment/deploy

Trigger manual deployment.

**Description:**
Triggers a manual deployment that checks for updates, downloads new binaries if available, and restarts services. Deployment checks the git repository and GitHub Actions for new releases.

**Request:**
- Method: `POST`
- Path: `/api/system/deployment/deploy`
- Body: None

**Response:**
- Status: `200 OK` on success, `500 Internal Server Error` on failure
- Body (success):
  ```json
  {
    "success": true,
    "deployed": true,
    "commit_before": "abc123",
    "commit_after": "def456",
    "services": ["sentinel", "frontend"],
    "sketch_deployed": false,
    "duration": "45s",
    "error": null
  }
  ```
- Body (failure):
  ```json
  {
    "success": false,
    "deployed": false,
    "commit_before": "abc123",
    "commit_after": "abc123",
    "services": [],
    "sketch_deployed": false,
    "duration": "10s",
    "error": "Failed to download binaries"
  }
  ```

**Error Responses:**
- `500 Internal Server Error`: Deployment failed, service error

**Side Effects:**
- Checks git repository for updates
- Downloads new binaries from GitHub Actions if available
- Deploys Go services, frontend, display app, sketch
- Restarts services automatically
