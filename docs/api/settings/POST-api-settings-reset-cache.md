# POST /api/settings/reset-cache

Clear all cached data.

**Description:**
Clears all cached data including price caches, exchange rate caches, and other temporary data. Useful for forcing refresh of stale data.

**Request:**
- Method: `POST`
- Path: `/api/settings/reset-cache`
- Body: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "status": "ok",
    "message": "Cache reset acknowledged (simplified implementation)"
  }
  ```

**Note:** Currently returns acknowledgment only. Full implementation requires cache infrastructure integration.
