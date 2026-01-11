# GET /api/system/logs/errors

Get error logs only.

**Description:**
Returns only error-level log entries from system log files.

**Request:**
- Method: `GET`
- Path: `/api/system/logs/errors`
- Query Parameters:
  - `file` (optional, string): Log file name
  - `lines` (optional, integer): Number of lines to retrieve (default: 100)

**Response:**
- Status: `200 OK`
- Body: Array of error log entries

**Error Responses:**
- `400 Bad Request`: Invalid parameters
- `500 Internal Server Error`: Failed to read logs


### System Sync Operations
