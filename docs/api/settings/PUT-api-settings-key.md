# PUT /api/settings/{key}

Update a setting value.

**Description:**
Updates a single setting value. If updating API credentials (tradernet_api_key or tradernet_api_secret), the tradernet client is automatically refreshed. If this is the first-time credential setup, onboarding is triggered automatically.

**Request:**
- Method: `PUT`
- Path: `/api/settings/{key}`
- Path Parameters:
  - `key` (string, required): Setting key name
- Body (JSON):
  ```json
  {
    "value": "new_value"
  }
  ```
  - `value` (any): New setting value (type depends on setting)

**Response:**
- Status: `200 OK` on success
- Body: Updated setting:
  ```json
  {
    "trading_mode": "research"
  }
  ```

**Error Responses:**
- `400 Bad Request`: Invalid key, invalid value format, or validation error
- `500 Internal Server Error`: Database error

**Side Effects:**
- If updating credentials: Tradernet client credentials are refreshed
- If first-time credential setup: Onboarding process is triggered
- SETTINGS_CHANGED event is emitted

**Example Keys:**
- `trading_mode`: "live" or "research"
- `tradernet_api_key`: API key string
- `tradernet_api_secret`: API secret string
- `buy_cooldown_days`: Integer (days)
- `min_hold_days`: Integer (days)
- `drip_enabled`: Boolean
- And many more...
