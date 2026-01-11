# GET /api/ledger/dividends/history

Get dividend history.

**Description:**
Returns dividend payment history from the ledger.

**Request:**
- Method: `GET`
- Path: `/api/ledger/dividends/history`
- Query Parameters:
  - `limit` (optional, integer): Maximum number of records

**Response:**
- Status: `200 OK`
- Body: Array of dividend records

**Error Responses:**
- `500 Internal Server Error`: Database error
