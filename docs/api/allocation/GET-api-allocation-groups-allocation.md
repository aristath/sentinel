# GET /api/allocation/groups/allocation

Get group allocation summary.

**Description:**
Returns current portfolio allocation aggregated by country and industry groups, showing total value, cash balance, and group allocations.

**Request:**
- Method: `GET`
- Path: `/api/allocation/groups/allocation`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "total_value": 50000.00,
    "cash_balance": 2500.00,
    "country": {
      "EU": 0.45,
      "ASIA": 0.30
    },
    "industry": {
      "Tech": 0.40,
      "Finance": 0.25
    }
  }
  ```
  - `total_value` (float): Total portfolio value in EUR
  - `cash_balance` (float): Cash balance in EUR
  - `country` (object): Allocation percentages by country group
  - `industry` (object): Allocation percentages by industry group

**Error Responses:**
- `500 Internal Server Error`: Service error
