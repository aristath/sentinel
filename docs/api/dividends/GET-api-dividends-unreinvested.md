# GET /api/dividends/unreinvested

Get unreinvested dividends.

**Description:**
Returns dividends that have not yet been reinvested. Used by the dividend reinvestment job. Optionally filters by minimum amount.

**Request:**
- Method: `GET`
- Path: `/api/dividends/unreinvested`
- Query Parameters:
  - `min_amount_eur` (optional, float): Minimum dividend amount in EUR (default: 0.0)

**Response:**
- Status: `200 OK`
- Body: Array of unreinvested dividend objects

**Error Responses:**
- `500 Internal Server Error`: Database error

**Note:** This endpoint is used internally by the dividend reinvestment job.
