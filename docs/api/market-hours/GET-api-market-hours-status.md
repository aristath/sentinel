# GET /api/market-hours/status

Get market status.

**Description:**
Returns the current market status including whether markets are open, closing times, and market information.

**Request:**
- Method: `GET`
- Path: `/api/market-hours/status`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Market status object with open/closed status and timing information

**Error Responses:**
- `500 Internal Server Error`: Service error
