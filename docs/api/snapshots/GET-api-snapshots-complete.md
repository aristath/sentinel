# GET /api/snapshots/complete

Get complete system snapshot.

**Description:**
Returns a comprehensive snapshot of the entire system state including portfolio, market context, risk metrics, and adaptive weights. Useful for system state inspection and monitoring.

**Request:**
- Method: `GET`
- Path: `/api/snapshots/complete`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "portfolio": {
        "total_value": 50000.00,
        "cash_balances": {
          "EUR": 2500.00,
          "USD": 1000.00
        },
        "position_count": 15
      },
      "market_context": {
        "regime_score": 0.75,
        "discrete_regime": "bull",
        "market_open": true,
        "adaptive_weights": {
          "quality": 0.45,
          "opportunity": 0.30
        }
      },
      "risk": {
        "volatility": 0.15,
        "var_95": 2500.00
      }
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z",
      "snapshot_id": 1705320600
    }
  }
  ```

**Error Responses:**
- `500 Internal Server Error`: Service error
