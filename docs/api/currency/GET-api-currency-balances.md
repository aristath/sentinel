# GET /api/currency/balances

Get currency balances.

**Description:**
Returns cash balances for all currencies in the portfolio.

**Request:**
- Method: `GET`
- Path: `/api/currency/balances`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "balances": {
      "EUR": 2500.00,
      "USD": 1000.00,
      "GBP": 500.00
    },
    "total_eur": 4380.00
  }
  ```
  - `balances` (object): Cash balances by currency
  - `total_eur` (float): Total value in EUR (converted using current rates)
