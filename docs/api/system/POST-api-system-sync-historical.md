# POST /api/system/sync/historical

Sync historical price data.

**Description:**
Triggers synchronization of historical price data for securities. Fetches and stores historical price records for analysis and charting.

**Request:**
- Method: `POST`
- Path: `/api/system/sync/historical`
- Body: None

**Response:**
- Status: `200 OK` on success
- Body:
  ```json
  {
    "status": "success",
    "message": "Historical data sync completed",
    "processed": 50,
    "errors": 0
  }
  ```
  - `processed` (integer): Number of securities processed
  - `errors` (integer): Number of errors encountered

**Error Responses:**
- `500 Internal Server Error`: Sync failed

**Side Effects:**
- Fetches historical price data
- Updates historical database
- May take significant time for large datasets
