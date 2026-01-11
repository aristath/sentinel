# POST /api/securities

Create a new security in the universe.

**Description:**
Creates a new security record. Requires ISIN as the primary key. Tags are ignored (auto-assigned internally). This endpoint triggers security setup including initial data fetching.

**Request:**
- Method: `POST`
- Path: `/api/securities`
- Body (JSON):
  ```json
  {
    "symbol": "AAPL.US",
    "name": "Apple Inc.",
    "isin": "US0378331005",
    "yahoo_symbol": "AAPL",
    "product_type": "EQUITY",
    "country": "US",
    "fullExchangeName": "NASDAQ",
    "industry": "Technology",
    "min_lot": 1,
    "allow_buy": true,
    "allow_sell": true,
    "currency": "USD",
    "min_portfolio_target": 0.0,
    "max_portfolio_target": 10.0
  }
  ```
  - `symbol` (string, required): Security symbol
  - `name` (string, required): Security name
  - `isin` (string, required): ISIN identifier (PRIMARY KEY)
  - `yahoo_symbol` (string, optional): Yahoo Finance symbol
  - `product_type` (string, optional): Product type (EQUITY, ETF, etc.)
  - `country` (string, optional): Country code
  - `fullExchangeName` (string, optional): Exchange name
  - `industry` (string, optional): Industry classification
  - `min_lot` (integer, optional): Minimum lot size (default: 1)
  - `allow_buy` (boolean, optional): Allow buying this security
  - `allow_sell` (boolean, optional): Allow selling this security
  - `currency` (string, optional): Trading currency
  - `min_portfolio_target` (float, optional): Minimum portfolio target percentage
  - `max_portfolio_target` (float, optional): Maximum portfolio target percentage

**Response:**
- Status: `200 OK` on success
- Body: Created security object

**Error Responses:**
- `400 Bad Request`: Missing required fields (symbol, name, ISIN), invalid ISIN format
- `500 Internal Server Error`: Security setup failed, database error

**Note:** For automatic ISIN resolution, use `/api/securities/add-by-identifier` endpoint instead.
