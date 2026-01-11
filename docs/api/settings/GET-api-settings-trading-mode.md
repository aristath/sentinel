# GET /api/settings/trading-mode

Get current trading mode.

**Description:**
Returns the current trading mode (live or research).

**Request:**
- Method: `GET`
- Path: `/api/settings/trading-mode`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "mode": "live"
  }
  ```
  - `mode` (string): "live" or "research"
