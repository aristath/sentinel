# GET /api/ledger/trades

Get trade history from ledger.

**Description:**
Returns trade history from the immutable ledger database. This is the authoritative source of all executed trades. Supports filtering by symbol and side.

**Request:**
- Method: `GET`
- Path: `/api/ledger/trades`
- Query Parameters:
  - `limit` (optional, integer): Maximum number of trades to return (default: 100)
  - `symbol` (optional, string): Filter by security symbol
  - `side` (optional, string): Filter by trade side ("BUY" or "SELL")

**Response:**
- Status: `200 OK`
- Body: Array of trade records with complete trade details:
  ```json
  [
    {
      "id": 123,
      "symbol": "AAPL.US",
      "isin": "US0378331005",
      "side": "BUY",
      "quantity": 10.0,
      "price": 150.25,
      "executed_at": "2024-01-15T10:30:00Z",
      "order_id": "ORD-12345",
      "currency": "USD",
      "currency_rate": 0.92,
      "value_eur": 1382.30,
      "source": "manual",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
  ```

**Error Responses:**
- `500 Internal Server Error`: Database error
