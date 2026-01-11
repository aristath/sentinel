# GET /api/market-hours/holidays

Get market holidays.

**Description:**
Returns a list of market holidays for all exchanges, including dates and which markets are closed.

**Request:**
- Method: `GET`
- Path: `/api/market-hours/holidays`
- Query Parameters:
  - `year` (optional, integer): Filter holidays for specific year
  - `exchange` (optional, string): Filter holidays for specific exchange

**Response:**
- Status: `200 OK`
- Body: Array of holiday objects with dates and affected exchanges

**Error Responses:**
- `500 Internal Server Error`: Service error
