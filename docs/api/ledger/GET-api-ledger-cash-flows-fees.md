# GET /api/ledger/cash-flows/fees

Get fee cash flows.

**Description:**
Returns cash flow records filtered to fees only.

**Request:**
- Method: `GET`
- Path: `/api/ledger/cash-flows/fees`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Array of fee records

**Error Responses:**
- `500 Internal Server Error`: Database error
