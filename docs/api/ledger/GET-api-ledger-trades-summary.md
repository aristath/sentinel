# GET /api/ledger/trades/summary

Get trades summary statistics.

**Description:**
Returns aggregate statistics about trades including counts, totals, and breakdowns.

**Request:**
- Method: `GET`
- Path: `/api/ledger/trades/summary`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Trade summary statistics object

**Error Responses:**
- `500 Internal Server Error`: Database error
