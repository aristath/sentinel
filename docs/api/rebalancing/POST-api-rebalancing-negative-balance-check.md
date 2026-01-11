# POST /api/rebalancing/negative-balance-check

Check for negative balance scenarios.

**Description:**
Validates that proposed trades will not result in negative cash balances for any currency.

**Request:**
- Method: `POST`
- Path: `/api/rebalancing/negative-balance-check`
- Body (JSON):
  ```json
  {
    "trades": [
      {
        "symbol": "AAPL.US",
        "side": "BUY",
        "quantity": 10.0,
        "price": 150.25,
        "currency": "USD"
      }
    ],
    "cash_balances": {
      "EUR": 1000.00,
      "USD": 500.00
    }
  }
  ```
  - `trades` (array, required): Proposed trades
  - `cash_balances` (object, required): Current cash balances by currency

**Response:**
- Status: `200 OK`
- Body: Validation result indicating if negative balances would occur

**Error Responses:**
- `400 Bad Request`: Invalid request body
- `500 Internal Server Error`: Validation error
