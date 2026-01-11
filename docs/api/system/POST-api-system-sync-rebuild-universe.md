# POST /api/system/sync/rebuild-universe

Rebuild security universe.

**Description:**
Triggers a rebuild of the security universe, recalculating security data, scores, and relationships. This is a comprehensive operation that may take time.

**Request:**
- Method: `POST`
- Path: `/api/system/sync/rebuild-universe`
- Body: None

**Response:**
- Status: `200 OK` on success
- Body: Rebuild result with statistics

**Error Responses:**
- `500 Internal Server Error`: Rebuild failed

**Side Effects:**
- Rebuilds universe data
- Recalculates security scores
- Updates security relationships
- May take significant time
