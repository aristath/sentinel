# GET /api/portfolio

Get all portfolio positions with current values and metadata.

**Description:**
Returns a list of all portfolio positions including security information, quantities, prices, and market values. Positions are sorted by market value (descending).

**Request:**
- Method: `GET`
- Path: `/api/portfolio`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Array of position objects:
  ```json
  [
    {
      "symbol": "AAPL.US",
      "quantity": 10.0,
      "avg_price": 150.25,
      "current_price": 155.30,
      "currency": "USD",
      "currency_rate": 0.92,
      "market_value_eur": 1428.76,
      "last_updated": "2024-01-15T10:30:00Z",
      "stock_name": "Apple Inc.",
      "industry": "Technology",
      "country": "US",
      "fullExchangeName": "NASDAQ"
    }
  ]
  ```

**Error Responses:**
- `500 Internal Server Error`: Database error or service failure
