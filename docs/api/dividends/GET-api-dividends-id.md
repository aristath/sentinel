# GET /api/dividends/{id}

Get a specific dividend by ID.

**Description:**
Returns detailed information about a single dividend record.

**Request:**
- Method: `GET`
- Path: `/api/dividends/{id}`
- Path Parameters:
  - `id` (integer, required): Dividend ID

**Response:**
- Status: `200 OK`
- Body: Dividend object (same structure as array items in GET /api/dividends)

**Error Responses:**
- `400 Bad Request`: Invalid dividend ID format
- `404 Not Found`: Dividend not found
- `500 Internal Server Error`: Database error
