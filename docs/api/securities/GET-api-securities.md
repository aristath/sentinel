# GET /api/securities

Get all securities with scores and priority rankings.

**Description:**
Returns a list of all securities in the universe with their scores, priority rankings, position information, and metadata. Securities are sorted by priority score (descending). This endpoint combines data from multiple sources: security metadata, scores, and current positions.

**Request:**
- Method: `GET`
- Path: `/api/securities`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Array of security objects with extensive metadata:
  ```json
  [
    {
      "symbol": "AAPL.US",
      "name": "Apple Inc.",
      "isin": "US0378331005",
      "yahoo_symbol": "AAPL",
      "product_type": "EQUITY",
      "country": "US",
      "fullExchangeName": "NASDAQ",
      "industry": "Technology",
      "priority_multiplier": 1.0,
      "min_lot": 1,
      "active": true,
      "allow_buy": true,
      "allow_sell": true,
      "currency": "USD",
      "last_synced": "2024-01-15T10:30:00Z",
      "min_portfolio_target": 0.0,
      "max_portfolio_target": 10.0,
      "quality_score": 0.85,
      "opportunity_score": 0.72,
      "analyst_score": 0.80,
      "allocation_fit_score": 0.65,
      "total_score": 0.78,
      "cagr_score": 0.75,
      "consistency_score": 0.82,
      "history_years": 5.0,
      "volatility": 0.25,
      "technical_score": 0.70,
      "fundamental_score": 0.85,
      "position_value": 1500.00,
      "position_quantity": 10.0,
      "current_price": 150.25,
      "priority_score": 0.78,
      "tags": ["high_quality", "dividend_payer"]
    }
  ]
  ```

**Error Responses:**
- `500 Internal Server Error`: Database error or service failure
