# GET /api/risk/portfolio/cvar

Get portfolio Conditional Value at Risk (CVaR).

**Description:**
Calculates portfolio Conditional Value at Risk (Expected Shortfall) at 95% and 99% confidence levels. CVaR represents the expected loss given that the loss exceeds the VaR threshold.

**Request:**
- Method: `GET`
- Path: `/api/risk/portfolio/cvar`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "cvar_95": 3000.00,
      "cvar_99": 4000.00,
      "contributions": [
        {
          "isin": "US0378331005",
          "contribution": 500.00,
          "weight": 0.10
        }
      ]
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```
  - `cvar_95` (float): CVaR at 95% confidence (EUR)
  - `cvar_99` (float): CVaR at 99% confidence (EUR)
  - `contributions` (array): Individual security contributions to portfolio CVaR

**Error Responses:**
- `500 Internal Server Error`: Database error, insufficient data
