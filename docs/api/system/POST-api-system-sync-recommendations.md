# POST /api/system/sync/recommendations

Sync recommendations cache.

**Description:**
Triggers synchronization of trading recommendations, updating the recommendation cache with latest data.

**Request:**
- Method: `POST`
- Path: `/api/system/sync/recommendations`
- Body: None

**Response:**
- Status: `200 OK` on success
- Body: Sync result

**Error Responses:**
- `500 Internal Server Error`: Sync failed

**Side Effects:**
- Updates recommendation cache
- Refreshes recommendation data
