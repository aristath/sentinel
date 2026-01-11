# GET /api/risk/kelly-sizes/{isin}

Get Kelly-optimal position size for a specific security.

**Description:**
Returns the Kelly-optimal position size for a specific security.

**Request:**
- Method: `GET`
- Path: `/api/risk/kelly-sizes/{isin}`
- Path Parameters:
  - `isin` (string, required): Security ISIN

**Response:**
- Status: `200 OK`
- Body: Kelly-optimal size and calculation details

**Error Responses:**
- `404 Not Found`: Security not found
- `500 Internal Server Error`: Calculation error
