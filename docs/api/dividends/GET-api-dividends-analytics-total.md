# GET /api/dividends/analytics/total

Get total dividends by symbol.

**Description:**
Returns aggregated total dividend amounts grouped by security symbol. Useful for analyzing dividend income by security over time. Results are sorted by total amount (descending).

**Request:**
- Method: `GET`
- Path: `/api/dividends/analytics/total`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Object mapping symbols to total dividend amounts in EUR:
  ```json
  {
    "AAPL.US": 250.50,
    "MSFT.US": 180.75,
    "GOOGL.US": 95.25
  }
  ```
  - Keys are security symbols (strings)
  - Values are total dividend amounts in EUR (floats)

**Error Responses:**
- `500 Internal Server Error`: Database error
