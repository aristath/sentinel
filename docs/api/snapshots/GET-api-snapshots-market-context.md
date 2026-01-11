# GET /api/snapshots/market-context

Get market context snapshot.

**Description:**
Returns a snapshot of current market context including regime, market hours, and adaptive parameters.

**Request:**
- Method: `GET`
- Path: `/api/snapshots/market-context`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Market context object with regime, market status, and adaptive weights

**Error Responses:**
- `500 Internal Server Error`: Service error
