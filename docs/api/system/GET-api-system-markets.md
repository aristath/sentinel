# GET /api/system/markets

Get market status for all exchanges.

**Description:**
Returns the current market status for all configured exchanges, showing whether markets are open or closed, open/close times, and market dates.

**Request:**
- Method: `GET`
- Path: `/api/system/markets`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "markets": {
      "XNAS": {
        "name": "NASDAQ",
        "code": "XNAS",
        "status": "open",
        "open_time": "09:30",
        "close_time": "16:00",
        "date": "2024-01-15",
        "updated_at": "2024-01-15T10:30:00Z"
      }
    },
    "open_count": 2,
    "closed_count": 3,
    "last_updated": "2024-01-15T10:30:00Z"
  }
  ```
  - `markets` (object): Market status by exchange code
  - `open_count` (integer): Number of currently open markets
  - `closed_count` (integer): Number of currently closed markets
  - `last_updated` (string): Last update timestamp

**Error Responses:**
- `500 Internal Server Error`: Service error
