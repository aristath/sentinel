# GET /api/snapshots/portfolio-state

Get portfolio state snapshot.

**Description:**
Returns a detailed snapshot of portfolio state including all positions, cash balances, and metrics.

**Request:**
- Method: `GET`
- Path: `/api/snapshots/portfolio-state`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "positions": [
        {
          "symbol": "AAPL.US",
          "quantity": 10.0,
          "avg_price": 150.00,
          "current_price": 155.00,
          "market_value_eur": 1550.00,
          "name": "Apple Inc.",
          "country": "US",
          "industry": "Technology"
        }
      ],
      "cash_balances": {
        "EUR": 2500.00
      },
      "metrics": {
        "total_value": 50000.00,
        "total_cost_basis": 48000.00,
        "total_unrealized_pnl": 2000.00
      }
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```

**Error Responses:**
- `500 Internal Server Error`: Service error
