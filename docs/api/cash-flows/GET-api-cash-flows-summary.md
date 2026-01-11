# GET /api/cash-flows/summary

Get cash flow summary statistics.

**Description:**
Returns aggregate statistics about cash flows including total transactions, breakdown by type, total deposits, withdrawals, and net cash flow.

**Request:**
- Method: `GET`
- Path: `/api/cash-flows/summary`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Summary statistics object:
  ```json
  {
    "total_transactions": 50,
    "by_type": {
      "deposit": {
        "count": 12,
        "total": 5000.00
      },
      "withdrawal": {
        "count": 2,
        "total": 1000.00
      },
      "fee": {
        "count": 36,
        "total": 50.00
      }
    },
    "total_deposits": 5000.00,
    "total_withdrawals": 1000.00,
    "net_cash_flow": 3950.00
  }
  ```
  - `total_transactions` (integer): Total number of cash flow records
  - `by_type` (object): Breakdown by transaction type with count and total for each type
  - `total_deposits` (float): Sum of all deposit-type transactions (EUR)
  - `total_withdrawals` (float): Sum of all withdrawal-type transactions (EUR)
  - `net_cash_flow` (float): Net cash flow (deposits - withdrawals) in EUR

**Error Responses:**
- `500 Internal Server Error`: Database error
