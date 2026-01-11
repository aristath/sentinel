# GET /api/rebalancing/min-trade-amount

Get minimum trade amount.

**Description:**
Returns the minimum trade amount based on transaction costs. Trades below this amount are not economically viable due to fixed and variable transaction costs.

**Request:**
- Method: `GET`
- Path: `/api/rebalancing/min-trade-amount`
- Query Parameters:
  - `fixed_cost` (optional, float): Fixed transaction cost (default: 2.0 EUR)
  - `percent_cost` (optional, float): Variable transaction cost percentage (default: 0.002 = 0.2%)
  - `max_cost_ratio` (optional, float): Maximum cost ratio (default: 0.01 = 1%)

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "min_trade_amount": 200.00,
    "fixed_cost": 2.0,
    "percent_cost": 0.002,
    "max_cost_ratio": 0.01
  }
  ```

**Error Responses:**
- `400 Bad Request`: Invalid parameter values
