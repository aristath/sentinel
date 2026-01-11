# GET /api/historical/exchange-rates/current

Get current exchange rates.

**Description:**
Returns the most recent exchange rates for all currency pairs.

**Request:**
- Method: `GET`
- Path: `/api/historical/exchange-rates/current`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Object mapping currency pairs to current exchange rates

**Error Responses:**
- `500 Internal Server Error`: Database error
