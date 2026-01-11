# POST /api/securities/add-by-identifier

Add security by symbol or ISIN with automatic setup.

**Description:**
Automatically adds a security to the universe by symbol or ISIN. This endpoint fetches the ISIN from the broker if not provided, then performs full security setup including data fetching from Yahoo Finance and initial scoring.

**Request:**
- Method: `POST`
- Path: `/api/securities/add-by-identifier`
- Body (JSON):
  ```json
  {
    "identifier": "AAPL.US",
    "min_lot": 1,
    "allow_buy": true,
    "allow_sell": true
  }
  ```
  - `identifier` (string, required): Symbol or ISIN
  - `min_lot` (integer, optional): Minimum lot size (default: 1)
  - `allow_buy` (boolean, optional): Allow buying (default: true)
  - `allow_sell` (boolean, optional): Allow selling (default: true)

**Response:**
- Status: `200 OK` on success
- Body: Created security object with all fetched data

**Error Responses:**
- `400 Bad Request`: Invalid identifier, security already exists
- `500 Internal Server Error`: Failed to fetch ISIN, setup failed

**Side Effects:**
- Fetches ISIN from broker if not provided
- Fetches security data from Yahoo Finance
- Triggers initial security scoring
- Creates security record in database
