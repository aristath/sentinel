# POST /api/securities/{isin}/refresh

Refresh score for a security.

**Description:**
Quick refresh that recalculates only the score for a specific security without fetching new data. Faster than refresh-data but doesn't update security metadata.

**Request:**
- Method: `POST`
- Path: `/api/securities/{isin}/refresh`
- Path Parameters:
  - `isin` (string, required): ISIN of the security to refresh

**Response:**
- Status: `200 OK` on success
- Body:
  ```json
  {
    "symbol": "AAPL.US",
    "total_score": 75.5,
    "quality": 80.0,
    "opportunity": 70.0,
    "analyst": 75.0,
    "allocation_fit": 72.0,
    "volatility": 25.0,
    "cagr_score": 78.0,
    "consistency_score": 76.0,
    "history_years": 5
  }
  ```

**Error Responses:**
- `400 Bad Request`: Invalid ISIN format
- `404 Not Found`: Security not found
- `500 Internal Server Error`: Score calculation failed

**Side Effects:**
- Recalculates security score
- Updates score database
- Does not fetch new data from external sources
