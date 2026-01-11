# GET /api/currency/conversion-path/{from}/{to}

Get currency conversion path.

**Description:**
Returns the conversion path between two currencies, which may involve intermediate currencies if direct conversion is not available.

**Request:**
- Method: `GET`
- Path: `/api/currency/conversion-path/{from}/{to}`
- Path Parameters:
  - `from` (string, required): Source currency code (e.g., "USD")
  - `to` (string, required): Target currency code (e.g., "EUR")

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "from_currency": "USD",
      "to_currency": "EUR",
      "path": ["USD", "EUR"],
      "steps": 1
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```
  - `path` (array): Conversion path as array of currency codes
  - `steps` (integer): Number of conversion steps required

**Error Responses:**
- `400 Bad Request`: Missing currency parameters
- `500 Internal Server Error`: Service error
