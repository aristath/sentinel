# GET /api/ledger/cash-flows/withdrawals

Get withdrawal cash flows.

**Description:**
Returns cash flow records filtered to withdrawals only.

**Request:**
- Method: `GET`
- Path: `/api/ledger/cash-flows/withdrawals`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Array of withdrawal records

**Error Responses:**
- `500 Internal Server Error`: Database error
