# GET /api/settings

Get all system settings.

**Description:**
Returns all configuration settings as a key-value map. Includes trading mode, API credentials (masked), and all other system configuration.

**Request:**
- Method: `GET`
- Path: `/api/settings`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Object mapping setting keys to values:
  ```json
  {
    "trading_mode": "live",
    "tradernet_api_key": "***",
    "buy_cooldown_days": 30,
    "min_hold_days": 90,
    "drip_enabled": true
  }
  ```

**Error Responses:**
- `500 Internal Server Error`: Database error
