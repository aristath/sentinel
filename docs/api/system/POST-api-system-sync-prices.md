# POST /api/system/sync/prices

Sync security prices.

**Description:**
Triggers synchronization of security prices from external data sources (Yahoo Finance). Updates current prices for all active securities in the universe.

**Request:**
- Method: `POST`
- Path: `/api/system/sync/prices`
- Body: None

**Response:**
- Status: `200 OK` on success
- Body:
  ```json
  {
    "status": "success",
    "message": "Price sync completed",
    "quotes": 50
  }
  ```
  - `quotes` (integer): Number of price quotes synced

**Error Responses:**
- `500 Internal Server Error`: Sync failed, data source error

**Side Effects:**
- Fetches latest prices from Yahoo Finance
- Updates price data in database
- Updates position market values
