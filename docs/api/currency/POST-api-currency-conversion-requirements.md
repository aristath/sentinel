# POST /api/currency/conversion-requirements

Calculate currency conversion requirements for a trade.

**Description:**
Calculates currency conversion requirements for a proposed trade, including required conversions and amounts. Useful for trade planning and validation. Calculates trade value, commission, and determines if currency conversion is needed (if trade currency differs from EUR).

**Request:**
- Method: `POST`
- Path: `/api/currency/conversion-requirements`
- Body (JSON):
  ```json
  {
    "symbol": "AAPL.US",
    "side": "BUY",
    "quantity": 10.0,
    "price": 150.25,
    "currency": "USD"
  }
  ```
  - `symbol` (string, required): Security symbol
  - `side` (string, required): Trade side ("BUY" or "SELL")
  - `quantity` (float, required): Trade quantity (must be > 0)
  - `price` (float, required): Trade price per share (must be > 0)
  - `currency` (string, optional): Trade currency code (default: "EUR")

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "trade": {
        "symbol": "AAPL.US",
        "side": "BUY",
        "quantity": 10.0,
        "price": 150.25,
        "currency": "USD",
        "trade_value": 1502.50,
        "commission": 5.01
      },
      "requirements": {
        "total_required_in_currency": 1507.51,
        "needs_conversion": true,
        "conversion_path": ["EUR", "USD"]
      }
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```
  - Commission calculation: €2 fixed + 0.2% of trade value
  - `needs_conversion`: true if trade currency differs from EUR
  - `conversion_path`: Currency conversion path if conversion needed

**Error Responses:**
- `400 Bad Request`: Invalid request body, invalid side, negative quantity/price
- `500 Internal Server Error`: Service error
