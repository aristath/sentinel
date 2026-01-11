# GET /api/historical/prices/daily/{isin}

Get daily price history for a security.

**Description:**
Returns daily closing prices for a security. Useful for charting and analysis.

**Request:**
- Method: `GET`
- Path: `/api/historical/prices/daily/{isin}`
- Path Parameters:
  - `isin` (string, required): Security ISIN
- Query Parameters:
  - `limit` (optional, integer): Maximum number of daily prices to return (default: 100)

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "isin": "US0378331005",
      "prices": [
        {
          "date": "2024-01-15",
          "close": 150.25,
          "open": 149.50,
          "high": 151.00,
          "low": 149.00,
          "volume": 50000000
        }
      ],
      "count": 100
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```

**Error Responses:**
- `500 Internal Server Error`: Database error, ISIN not found
