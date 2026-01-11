# GET /api/ledger/dividends/pending-reinvestments

Get pending reinvestments.

**Description:**
Returns dividends that are pending reinvestment.

**Request:**
- Method: `GET`
- Path: `/api/ledger/dividends/pending-reinvestments`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Array of pending dividend records

**Error Responses:**
- `500 Internal Server Error`: Database error
