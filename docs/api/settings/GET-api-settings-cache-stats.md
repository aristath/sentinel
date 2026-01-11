# GET /api/settings/cache-stats

Get cache statistics.

**Description:**
Returns statistics about cached data including entry counts for simple cache and calculations database cache. Currently returns stub data as full implementation requires cache infrastructure integration.

**Request:**
- Method: `GET`
- Path: `/api/settings/cache-stats`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "simple_cache": {
      "entries": 0
    },
    "calculations_db": {
      "entries": 0,
      "expired_cleaned": 0
    }
  }
  ```
  - `simple_cache.entries` (integer): Number of entries in simple cache
  - `calculations_db.entries` (integer): Number of entries in calculations database cache
  - `calculations_db.expired_cleaned` (integer): Number of expired entries cleaned

**Note:** Currently returns stub data. Full implementation requires cache infrastructure integration.
