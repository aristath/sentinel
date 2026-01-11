# GET /api/market-hours/open-markets

Get list of currently open markets.

**Description:**
Returns a list of all markets that are currently open for trading.

**Request:**
- Method: `GET`
- Path: `/api/market-hours/open-markets`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Array of open market objects with exchange names and status

**Error Responses:**
- `500 Internal Server Error`: Service error
