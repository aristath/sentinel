# GET /api/historical/prices/latest/{isin}

Get the latest price for a security.

**Description:**
Returns the most recent daily price for a security. Equivalent to getting daily prices with limit=1.

**Request:**
- Method: `GET`
- Path: `/api/historical/prices/latest/{isin}`
- Path Parameters:
  - `isin` (string, required): Security ISIN
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "isin": "US0378331005",
      "price": {
        "date": "2024-01-15",
        "close": 150.25
      }
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```

**Error Responses:**
- `500 Internal Server Error`: Database error
