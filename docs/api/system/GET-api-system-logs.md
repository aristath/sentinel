# GET /api/system/logs

Get system logs.

**Description:**
Returns log entries from system log files with optional filtering by file, lines, and log level.

**Request:**
- Method: `GET`
- Path: `/api/system/logs`
- Query Parameters:
  - `file` (optional, string): Log file name
  - `lines` (optional, integer): Number of lines to retrieve (default: 100)
  - `level` (optional, string): Log level filter (debug, info, warn, error)

**Response:**
- Status: `200 OK`
- Body: Array of log entries with timestamps and log levels

**Error Responses:**
- `400 Bad Request`: Invalid parameters
- `500 Internal Server Error`: Failed to read logs
