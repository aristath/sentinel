# GET /api/ledger/cash-flows/summary

Get cash flows summary.

**Description:**
Returns aggregate statistics about cash flows from the ledger.

**Request:**
- Method: `GET`
- Path: `/api/ledger/cash-flows/summary`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Cash flows summary object

**Error Responses:**
- `500 Internal Server Error`: Database error
