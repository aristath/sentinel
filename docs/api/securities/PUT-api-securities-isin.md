# PUT /api/securities/{isin}

Update a security.

**Description:**
Updates security metadata (name, symbol, country, industry, etc.). After update, scores are automatically recalculated to reflect any changes. Tags cannot be updated (they are auto-assigned internally).

**Request:**
- Method: `PUT`
- Path: `/api/securities/{isin}`
- Path Parameters:
  - `isin` (string, required): ISIN of the security to update
- Body (JSON): Security update object with fields to update (same structure as POST /api/securities, but tags field is rejected)

**Response:**
- Status: `200 OK` on success
- Body: Updated security object with metadata and updated score

**Error Responses:**
- `400 Bad Request`: Invalid ISIN format, invalid update data, tags field provided (tags cannot be updated), no updates provided
- `404 Not Found`: Security not found
- `500 Internal Server Error`: Update failed, score calculation failed

**Side Effects:**
- Updates security metadata in database
- Recalculates scores after update
- Emits SECURITY_UPDATED event
