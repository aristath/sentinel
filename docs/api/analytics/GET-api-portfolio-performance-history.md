# GET /api/portfolio/performance/history

Get historical performance data.

**Description:**
Returns historical portfolio performance metrics including returns over time periods.

**Request:**
- Method: `GET`
- Path: `/api/portfolio/performance/history`
- Query Parameters:
  - `period` (optional, string): Time period (e.g., "1M", "3M", "1Y", default: "1M")

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "period": "1M",
      "total_return_pct": 5.2,
      "total_gain_loss": 2600.00,
      "total_cost_basis": 50000.00,
      "current_value": 52600.00
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```

**Error Responses:**
- `500 Internal Server Error`: Service error
