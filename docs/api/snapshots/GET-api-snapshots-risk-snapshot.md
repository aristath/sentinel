# GET /api/snapshots/risk-snapshot

Get risk snapshot.

**Description:**
Returns a snapshot of portfolio risk metrics and concentration measures. Combines portfolio risk calculations with concentration analysis.

**Request:**
- Method: `GET`
- Path: `/api/snapshots/risk-snapshot`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "portfolio_risk": {
        "var_95": 500.00,
        "cvar_95": 750.00,
        "sharpe_ratio": 1.2,
        "sortino_ratio": 1.5
      },
      "concentration": {
        "top_position_pct": 25.0,
        "top_5_positions_pct": 60.0
      }
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```

**Error Responses:**
- `500 Internal Server Error`: Service error
