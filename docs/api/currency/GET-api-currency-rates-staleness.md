# GET /api/currency/rates/staleness

Get exchange rate staleness information.

**Description:**
Returns information about how stale exchange rate data is, indicating when rates were last updated.

**Request:**
- Method: `GET`
- Path: `/api/currency/rates/staleness`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Staleness metrics object
