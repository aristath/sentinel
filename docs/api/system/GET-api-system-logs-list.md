# GET /api/system/logs/list

List available log files.

**Description:**
Returns a list of available log files in the logs directory.

**Request:**
- Method: `GET`
- Path: `/api/system/logs/list`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Array of log file names

**Error Responses:**
- `500 Internal Server Error`: Failed to list log files
