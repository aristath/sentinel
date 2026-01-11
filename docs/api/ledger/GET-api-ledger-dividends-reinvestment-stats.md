# GET /api/ledger/dividends/reinvestment-stats

Get dividend reinvestment statistics.

**Description:**
Returns statistics about dividend reinvestment including reinvestment rates and totals.

**Request:**
- Method: `GET`
- Path: `/api/ledger/dividends/reinvestment-stats`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Reinvestment statistics object

**Error Responses:**
- `500 Internal Server Error`: Database error
