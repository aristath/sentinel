# POST /api/securities/refresh-all

Refresh scores for all active securities.

**Description:**
Recalculates scores for all active securities in the universe. This is a batch operation that updates industry information if missing, then recalculates and saves scores for all securities.

**Request:**
- Method: `POST`
- Path: `/api/securities/refresh-all`
- Body: None

**Response:**
- Status: `200 OK` on success
- Body:
  ```json
  {
    "message": "Refreshed scores for 50 stocks",
    "scores": [
      {
        "isin": "US0378331005",
        "symbol": "AAPL.US",
        "total_score": 75.5
      }
    ]
  }
  ```
  - `scores` (array): Array of score results with ISIN, symbol, and total_score

**Error Responses:**
- `500 Internal Server Error`: Failed to fetch securities, scoring error

**Side Effects:**
- Updates missing industry information for securities
- Recalculates scores for all active securities
- Updates score database
- May take significant time for large universes
