# GET /api/ledger/drip-tracking

Get DRIP tracking information.

**Description:**
Returns dividend reinvestment plan (DRIP) tracking data showing reinvestment history and status.

**Request:**
- Method: `GET`
- Path: `/api/ledger/drip-tracking`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: DRIP tracking object

**Error Responses:**
- `500 Internal Server Error`: Database error
