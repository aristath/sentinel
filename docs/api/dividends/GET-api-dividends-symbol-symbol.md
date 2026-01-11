# GET /api/dividends/symbol/{symbol}

Get dividends for a specific security.

**Description:**
Returns all dividend records for a specific security symbol.

**Request:**
- Method: `GET`
- Path: `/api/dividends/symbol/{symbol}`
- Path Parameters:
  - `symbol` (string, required): Security symbol

**Response:**
- Status: `200 OK`
- Body: Array of dividend objects for the specified symbol

**Error Responses:**
- `500 Internal Server Error`: Database error
