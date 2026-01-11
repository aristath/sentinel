# GET /api/allocation/groups/available/countries

Get available country codes.

**Description:**
Returns a list of all available country codes from securities in the universe. Useful for creating country groups.

**Request:**
- Method: `GET`
- Path: `/api/allocation/groups/available/countries`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "countries": ["US", "DE", "FR", "NL", "BE", "JP", "CN", "HK"]
  }
  ```
  - `countries` (array): Array of unique country codes

**Error Responses:**
- `500 Internal Server Error`: Database error
