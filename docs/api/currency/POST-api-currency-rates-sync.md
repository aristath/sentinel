# POST /api/currency/rates/sync

Sync exchange rates.

**Description:**
Triggers a manual synchronization of exchange rates from external sources. Forces refresh of cached rates to ensure up-to-date conversion rates. Note: Rate synchronization normally runs automatically via scheduled background jobs.

**Request:**
- Method: `POST`
- Path: `/api/currency/rates/sync`
- Body: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "status": "success",
      "message": "Exchange rates synchronized successfully",
      "note": "Rate synchronization normally runs automatically via scheduled background jobs"
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```

**Error Responses:**
- `500 Internal Server Error`: Cache service not initialized or sync failed

**Side Effects:**
- Refreshes cached exchange rates from external sources
- Updates exchange rate cache
