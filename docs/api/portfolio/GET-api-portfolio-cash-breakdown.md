# GET /api/portfolio/cash-breakdown

Get cash balance breakdown by currency.

**Description:**
Returns detailed cash balances for each currency in the portfolio. Shows available cash in EUR, USD, and other currencies.

**Request:**
- Method: `GET`
- Path: `/api/portfolio/cash-breakdown`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Object mapping currency codes to balances:
  ```json
  {
    "EUR": 2500.00,
    "USD": 1000.00,
    "GBP": 500.00
  }
  ```

**Error Responses:**
- `500 Internal Server Error`: Failed to retrieve cash balances
