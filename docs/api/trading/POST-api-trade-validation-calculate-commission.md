# POST /api/trade-validation/calculate-commission

Calculate commission for a trade.

**Description:**
Calculates the commission cost for a trade based on quantity and price. Uses configured transaction cost settings (default: 2 EUR fixed + 0.2% variable).

**Request:**
- Method: `POST`
- Path: `/api/trade-validation/calculate-commission`
- Body (JSON):
  ```json
  {
    "symbol": "AAPL.US",
    "quantity": 10.0,
    "price": 150.25
  }
  ```
  - `symbol` (string, required): Security symbol
  - `quantity` (float, required): Number of shares/units
  - `price` (float, required): Trade price

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "symbol": "AAPL.US",
      "trade_value": 1502.50,
      "fixed_commission": 2.0,
      "variable_commission": 3.01,
      "total_commission": 5.01,
      "commission_currency": "EUR"
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```
  - `trade_value` (float): Total trade value (quantity × price)
  - `fixed_commission` (float): Fixed commission amount (EUR)
  - `variable_commission` (float): Variable commission (percentage of trade value)
  - `total_commission` (float): Total commission cost
  - `commission_currency` (string): Currency for commission (EUR)

**Error Responses:**
- `400 Bad Request`: Invalid request body
- `500 Internal Server Error`: Calculation error
