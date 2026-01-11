# GET /api/optimizer

Get optimizer status and last run information.

**Description:**
Returns the current status of the portfolio optimizer including settings, last run results (if available), and current state. Settings include optimizer blend (adaptive blend used, not user setting), target return, minimum cash reserve, and minimum trade amount.

**Request:**
- Method: `GET`
- Path: `/api/optimizer`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "settings": {
      "optimizer_blend": 0.75,
      "optimizer_target_return": 0.08,
      "min_cash_reserve": 500.00,
      "min_trade_amount": 50.00
    },
    "last_run": {
      "success": true,
      "target_weights": {
        "AAPL.US": 0.10,
        "MSFT.US": 0.08
      },
      "blend_used": 0.75,
      "duration_seconds": 12.5
    },
    "last_run_time": "2024-01-15T10:30:00Z",
    "status": "ready"
  }
  ```
  - `settings.optimizer_blend`: Actual blend used (adaptive), not user setting
  - `settings.min_trade_amount`: Calculated from transaction costs (€2 fixed + 0.2%)
  - `last_run`: null if optimizer has never run
  - `status`: "ready" when optimizer is available

**Error Responses:**
- `500 Internal Server Error`: Failed to get settings
