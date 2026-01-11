# GET /api/planning/status

Get planning job status.

**Description:**
Returns the current status of the planning job, including whether it's running, completed, or failed.

**Request:**
- Method: `GET`
- Path: `/api/planning/status`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Status object:
  ```json
  {
    "status": "completed",
    "last_run": "2024-01-15T10:30:00Z",
    "duration_seconds": 45.2,
    "error": null
  }
  ```

**Error Responses:**
- `500 Internal Server Error`: Service error
