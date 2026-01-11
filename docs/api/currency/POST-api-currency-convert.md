# POST /api/currency/convert

Convert currency amount.

**Description:**
Converts an amount from one currency to another using current exchange rates.

**Request:**
- Method: `POST`
- Path: `/api/currency/convert`
- Body (JSON):
  ```json
  {
    "from_currency": "USD",
    "to_currency": "EUR",
    "amount": 1000.00
  }
  ```
  - `from_currency` (string, required): Source currency code
  - `to_currency` (string, required): Target currency code
  - `amount` (float, required): Amount to convert (must be > 0)

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "from_currency": "USD",
      "to_currency": "EUR",
      "from_amount": 1000.00,
      "to_amount": 920.00,
      "rate": 0.92
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```

**Error Responses:**
- `400 Bad Request`: Missing currencies, invalid amount
- `500 Internal Server Error`: Exchange rate not available, service error
