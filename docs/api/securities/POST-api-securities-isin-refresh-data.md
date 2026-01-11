# POST /api/securities/{isin}/refresh-data

Refresh all data for a security.

**Description:**
Triggers a full data refresh for a specific security including fetching latest data from Yahoo Finance and recalculating scores. This is a comprehensive refresh operation.

**Request:**
- Method: `POST`
- Path: `/api/securities/{isin}/refresh-data`
- Path Parameters:
  - `isin` (string, required): ISIN of the security to refresh

**Response:**
- Status: `200 OK` on success
- Body:
  ```json
  {
    "status": "success",
    "symbol": "AAPL.US",
    "message": "Full data refresh completed for AAPL.US"
  }
  ```

**Error Responses:**
- `400 Bad Request`: Invalid ISIN format
- `404 Not Found`: Security not found
- `500 Internal Server Error`: Refresh failed, data source error

**Side Effects:**
- Fetches latest security data from Yahoo Finance
- Updates security metadata
- Recalculates scores
- Updates database
- Emits SECURITY_SYNCED event
