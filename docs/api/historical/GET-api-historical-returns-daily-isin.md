# GET /api/historical/returns/daily/{isin}

Get daily returns for a security.

**Description:**
Calculates and returns daily percentage returns based on price changes. Requires at least 2 price points.

**Request:**
- Method: `GET`
- Path: `/api/historical/returns/daily/{isin}`
- Path Parameters:
  - `isin` (string, required): Security ISIN
- Query Parameters:
  - `limit` (optional, integer): Maximum number of returns to return (default: 100)

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "isin": "US0378331005",
      "returns": [
        {
          "date": "2024-01-15",
          "return": 0.015
        }
      ],
      "count": 99
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```

**Error Responses:**
- `500 Internal Server Error`: Database error, insufficient price data
