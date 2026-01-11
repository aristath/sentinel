# GET /api/historical/prices/range

Get price data for multiple securities.

**Description:**
Returns daily prices for multiple securities in a single request. ISINs are specified as a comma-separated list.

**Request:**
- Method: `GET`
- Path: `/api/historical/prices/range`
- Query Parameters:
  - `isins` (string, required): Comma-separated list of ISINs (e.g., "US0378331005,US5949181045")
  - `limit` (optional, integer): Maximum number of daily prices per security (default: 100)

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "prices": {
        "US0378331005": [
          {"date": "2024-01-15", "close": 150.25}
        ],
        "US5949181045": [
          {"date": "2024-01-15", "close": 350.50}
        ]
      }
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```

**Error Responses:**
- `400 Bad Request`: Missing isins parameter
- `500 Internal Server Error`: Database error (errors for individual ISINs are logged but don't fail the request)
