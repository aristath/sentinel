# GET /api/ledger/cash-flows/deposits

Get deposit cash flows.

**Description:**
Returns cash flow records filtered to deposits only.

**Request:**
- Method: `GET`
- Path: `/api/ledger/cash-flows/deposits`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Array of deposit records

**Error Responses:**
- `500 Internal Server Error`: Database error
