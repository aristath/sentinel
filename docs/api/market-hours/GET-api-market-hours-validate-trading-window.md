# GET /api/market-hours/validate-trading-window

Validate trading window.

**Description:**
Validates whether trading is allowed at the current time, considering market hours, holidays, and trading windows.

**Request:**
- Method: `GET`
- Path: `/api/market-hours/validate-trading-window`
- Query Parameters:
  - `exchange` (optional, string): Exchange to validate (default: all)
  - `time` (optional, string): Time to validate (ISO 8601 format, default: current time)

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "valid": true,
    "reason": "Market is open",
    "next_open": "2024-01-16T09:30:00Z",
    "next_close": "2024-01-15T16:00:00Z"
  }
  ```

**Error Responses:**
- `400 Bad Request`: Invalid time format
- `500 Internal Server Error`: Service error
