# POST /api/settings/trading-mode

Toggle trading mode.

**Description:**
Switches between live and research trading modes. In research mode, real trades are blocked but the system continues to operate normally for testing purposes.

**Request:**
- Method: `POST`
- Path: `/api/settings/trading-mode`
- Body: None (toggles between "live" and "research")

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "mode": "research",
    "previous_mode": "live"
  }
  ```

**Error Responses:**
- `500 Internal Server Error`: Failed to update trading mode
