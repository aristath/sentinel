# GET /api/securities/{isin}

Get detailed security information by ISIN.

**Description:**
Returns detailed information about a specific security identified by ISIN, including all scores, metadata, and current position information.

**Request:**
- Method: `GET`
- Path: `/api/securities/{isin}`
- Path Parameters:
  - `isin` (string, required): ISIN identifier (12 characters, format: 2 letters + 9 alphanumeric + 1 digit)

**Response:**
- Status: `200 OK`
- Body: Security detail object (similar structure to GET /api/securities items)

**Error Responses:**
- `400 Bad Request`: Invalid ISIN format
- `404 Not Found`: Security not found
- `500 Internal Server Error`: Database error
