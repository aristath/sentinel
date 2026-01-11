# GET /api/ledger/trades/{id}

Get trade by ID.

**Description:**
Returns a specific trade record by its ID from the ledger.

**Request:**
- Method: `GET`
- Path: `/api/ledger/trades/{id}`
- Path Parameters:
  - `id` (integer, required): Trade ID

**Response:**
- Status: `200 OK`
- Body: Trade record object

**Error Responses:**
- `404 Not Found`: Trade not found
- `500 Internal Server Error`: Database error
