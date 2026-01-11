# GET /api/system/database/stats

Get database statistics.

**Description:**
Returns statistics about all databases including sizes, table counts, and row counts for the 7-database architecture.

**Request:**
- Method: `GET`
- Path: `/api/system/database/stats`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "core_databases": [
      {
        "name": "universe",
        "path": "/data/universe.db",
        "size_mb": 50.5,
        "table_count": 10,
        "row_count": 5000
      }
    ],
    "history_dbs": 1,
    "total_size_mb": 250.0,
    "last_checked": "2024-01-15T10:30:00Z"
  }
  ```
  - `core_databases` (array): Information about core databases (universe, config, ledger, portfolio, agents, cache)
  - `history_dbs` (integer): Number of history databases
  - `total_size_mb` (float): Total database size in megabytes
  - `last_checked` (string): Last check timestamp

**Error Responses:**
- `500 Internal Server Error`: Database error
