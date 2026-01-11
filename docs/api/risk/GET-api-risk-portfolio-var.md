# GET /api/risk/portfolio/var

Get portfolio Value at Risk (VaR).

**Description:**
Calculates portfolio Value at Risk at 95% and 99% confidence levels using historical simulation method. VaR represents the maximum expected loss over a specified time period at a given confidence level.

**Request:**
- Method: `GET`
- Path: `/api/risk/portfolio/var`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "var_95": 2500.00,
      "var_99": 3500.00,
      "portfolio_value": 50000.00,
      "var_pct_95": 5.0,
      "var_pct_99": 7.0,
      "method": "historical",
      "period": "252d"
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```
  - `var_95` (float): VaR at 95% confidence (EUR)
  - `var_99` (float): VaR at 99% confidence (EUR)
  - `portfolio_value` (float): Total portfolio value (EUR)
  - `var_pct_95` (float): VaR as percentage at 95% confidence
  - `var_pct_99` (float): VaR as percentage at 99% confidence
  - `method` (string): Calculation method ("historical")
  - `period` (string): Historical period used ("252d" = 1 year of trading days)

**Error Responses:**
- `500 Internal Server Error`: Database error, insufficient price data

**Calculation Method:**
Uses historical simulation with 252 trading days (1 year) of daily returns. Portfolio returns are calculated as weighted combination of individual security returns.
