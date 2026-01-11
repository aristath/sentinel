# GET /api/portfolio/summary

Get portfolio summary with total value, cash balance, and country allocations.

**Description:**
Returns high-level portfolio metrics including total portfolio value in EUR, cash balance, and percentage allocations by region (EU, ASIA, US).

**Request:**
- Method: `GET`
- Path: `/api/portfolio/summary`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "total_value": 50000.00,
    "cash_balance": 2500.00,
    "allocations": {
      "EU": 45.0,
      "ASIA": 30.0,
      "US": 25.0
    }
  }
  ```
  - `total_value` (float): Total portfolio value in EUR
  - `cash_balance` (float): Available cash balance in EUR
  - `allocations` (object): Percentage allocations by region (values are percentages, e.g., 45.0 = 45%)

**Error Responses:**
- `500 Internal Server Error`: Service error or database failure
