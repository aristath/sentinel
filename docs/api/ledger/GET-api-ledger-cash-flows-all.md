# GET /api/ledger/cash-flows/all

Get all cash flows.

**Description:**
Returns all cash flow records from the ledger including deposits, withdrawals, fees, and other movements.

**Request:**
- Method: `GET`
- Path: `/api/ledger/cash-flows/all`
- Query Parameters:
  - `limit` (optional, integer): Maximum number of records

**Response:**
- Status: `200 OK`
- Body: Array of cash flow records

**Error Responses:**
- `500 Internal Server Error`: Database error
