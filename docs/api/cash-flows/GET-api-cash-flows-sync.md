# GET /api/cash-flows/sync

Sync cash flows from broker.

**Description:**
Triggers synchronization of cash flow data from the broker (Tradernet). Fetches recent cash movements (up to 1000 records) and updates the local database.

**Request:**
- Method: `GET`
- Path: `/api/cash-flows/sync`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Sync result with count of records synced:
  ```json
  {
    "message": "Synced 5 new cash flows",
    "synced": 5,
    "total_from_api": 100
  }
  ```
  - `message` (string): Success message
  - `synced` (integer): Number of new records synced
  - `total_from_api` (integer): Total records fetched from broker API

**Error Responses:**
- `503 Service Unavailable`: Tradernet service not connected
- `500 Internal Server Error`: Broker API error, database error

**Side Effects:**
- Fetches cash flows from broker (up to 1000 records)
- Syncs new records to local database
- Updates cash balances automatically
