# POST /api/currency/balance-check

Check if sufficient balance exists for a currency.

**Description:**
Checks if the portfolio has sufficient balance in a specific currency to cover a requested amount. Used for trade validation before executing trades.

**Request:**
- Method: `POST`
- Path: `/api/currency/balance-check`
- Body (JSON):
  ```json
  {
    "currency": "USD",
    "amount": 1000.00
  }
  ```
  - `currency` (string, required): Currency code (e.g., "USD", "EUR")
  - `amount` (float, required): Required amount (must be > 0)

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "currency": "USD",
      "required_amount": 1000.00,
      "available_balance": 1500.00,
      "sufficient": true,
      "shortfall": 0.0
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```
  - `sufficient` (boolean): Whether balance is sufficient
  - `shortfall` (float): Amount short if insufficient (0 if sufficient)

**Error Responses:**
- `400 Bad Request`: Invalid currency code or negative amount
- `500 Internal Server Error`: Service error
