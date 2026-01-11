# GET /api/system/tradernet

Get Tradernet connection status.

**Description:**
Returns the connection status of the Tradernet broker API, including whether the connection is active and last check time.

**Request:**
- Method: `GET`
- Path: `/api/system/tradernet`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "connected": true,
    "last_check": "2024-01-15T10:30:00Z",
    "message": "Connection active"
  }
  ```
  - `connected` (boolean): Whether Tradernet is connected
  - `last_check` (string): Last connection check time (ISO 8601)
  - `message` (string, optional): Status message

**Error Responses:**
- `500 Internal Server Error`: Service error
