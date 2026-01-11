# GET /api/system/deployment/status

Get deployment status.

**Description:**
Returns the current deployment status including whether deployment is enabled, last deployment time, and system uptime.

**Request:**
- Method: `GET`
- Path: `/api/system/deployment/status`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "status": {
      "enabled": true,
      "last_deployment": "2024-01-15T10:00:00Z",
      "auto_deploy": true
    },
    "uptime": "72h30m15s"
  }
  ```

**Error Responses:**
- `500 Internal Server Error`: Failed to get deployment status
