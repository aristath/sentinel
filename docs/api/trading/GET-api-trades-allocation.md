# GET /api/trades/allocation

Get portfolio allocation for trading context.

**Description:**
Returns current portfolio allocation including total value, cash balance, country/industry allocations, and concentration alerts. Similar to allocation endpoints but formatted for trading context.

**Request:**
- Method: `GET`
- Path: `/api/trades/allocation`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "total_value": 50000.00,
    "cash_balance": 2500.00,
    "country": [
      {
        "name": "US",
        "target_pct": 25.0,
        "current_pct": 30.0,
        "current_value": 15000.00,
        "deviation": 5.0
      }
    ],
    "industry": [
      {
        "name": "Technology",
        "target_pct": 40.0,
        "current_pct": 45.0,
        "current_value": 22500.00,
        "deviation": 5.0
      }
    ],
    "alerts": []
  }
  ```
  - `total_value` (float): Total portfolio value in EUR
  - `cash_balance` (float): Cash balance in EUR
  - `country` (array): Country allocations with targets, current values, and deviations
  - `industry` (array): Industry allocations with targets, current values, and deviations
  - `alerts` (array): Concentration alerts if any thresholds are exceeded

**Error Responses:**
- `500 Internal Server Error`: Service error
