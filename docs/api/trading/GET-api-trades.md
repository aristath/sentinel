# GET /api/trades

Get trade history.

**Description:**
Returns a list of executed trades sorted by execution time (most recent first). Includes trade details such as symbol, side (BUY/SELL), quantity, price, and execution timestamp.

**Request:**
- Method: `GET`
- Path: `/api/trades`
- Query Parameters:
  - `limit` (optional, integer): Maximum number of trades to return (default: 50)

**Response:**
- Status: `200 OK`
- Body: Array of trade objects:
  ```json
  [
    {
      "id": 123,
      "symbol": "AAPL.US",
      "name": "Apple Inc.",
      "side": "BUY",
      "quantity": 10.0,
      "price": 150.25,
      "executed_at": "2024-01-15T10:30:00Z",
      "order_id": "ORD-12345"
    }
  ]
  ```
  - `id` (integer): Trade ID
  - `symbol` (string): Security symbol
  - `name` (string): Security name
  - `side` (string): Trade side - "BUY" or "SELL"
  - `quantity` (float): Number of shares/units
  - `price` (float): Execution price
  - `executed_at` (string): ISO 8601 timestamp
  - `order_id` (string): Broker order ID

**Error Responses:**
- `500 Internal Server Error`: Database error
