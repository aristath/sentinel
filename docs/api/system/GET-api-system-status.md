# GET /api/system/status

Get comprehensive system status.

**Description:**
Returns detailed system status including cash balances, security counts, position counts, and last sync time. Provides a comprehensive view of system health and portfolio state.

**Request:**
- Method: `GET`
- Path: `/api/system/status`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "status": "healthy",
    "cash_balance_eur": 2500.00,
    "cash_balance_total": 3000.00,
    "cash_balance": 3000.00,
    "security_count": 50,
    "position_count": 15,
    "active_positions": 15,
    "last_sync": "2024-01-15 10:30",
    "universe_active": 50
  }
  ```
  - `status` (string): System status ("healthy" or "unhealthy")
  - `cash_balance_eur` (float): Cash balance in EUR only
  - `cash_balance_total` (float): Total cash balance in EUR (all currencies converted)
  - `cash_balance` (float): Backward compatibility alias for cash_balance_total
  - `security_count` (integer): Number of active securities in universe
  - `position_count` (integer): Total number of positions (including cash)
  - `active_positions` (integer): Number of non-cash positions
  - `last_sync` (string): Last portfolio sync time (YYYY-MM-DD HH:MM format)
  - `universe_active` (integer): Number of active securities (same as security_count)

**Error Responses:**
- `500 Internal Server Error`: Database error, service error
