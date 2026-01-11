# POST /api/scoring/score

Calculate security score.

**Description:**
Calculates and returns the comprehensive score for a security based on multiple factors including quality, opportunity, fundamentals, and technical indicators. Requires detailed input data including price history and financial metrics.

**Request:**
- Method: `POST`
- Path: `/api/scoring/score`
- Body (JSON):
  ```json
  {
    "symbol": "AAPL.US",
    "product_type": "EQUITY",
    "daily_prices": [150.0, 151.0, 152.0],
    "monthly_prices": [
      {"date": "2024-01", "price": 150.0, "return": 0.05}
    ],
    "pe_ratio": 28.5,
    "forward_pe": 25.0,
    "dividend_yield": 0.015,
    "five_year_avg_div_yield": 0.012,
    "profit_margin": 0.25,
    "debt_to_equity": 1.5,
    "current_ratio": 1.2,
    "payout_ratio": 0.20,
    "analyst_recommendation": 4.5,
    "upside_pct": 0.10,
    "sortino_ratio": 1.5,
    "max_drawdown": 0.15,
    "market_avg_pe": 25.0,
    "target_annual_return": 0.08
  }
  ```
  - `symbol` (string, required): Security symbol
  - `product_type` (string, optional): Product type (EQUITY, ETF, MUTUALFUND, ETC, UNKNOWN)
  - `daily_prices` (array of floats, required): Array of daily closing prices
  - `monthly_prices` (array of MonthlyPrice objects, optional): Monthly price history
  - `pe_ratio` (float, optional): Price-to-earnings ratio
  - `forward_pe` (float, optional): Forward P/E ratio
  - `dividend_yield` (float, optional): Current dividend yield
  - `five_year_avg_div_yield` (float, optional): Five-year average dividend yield
  - `profit_margin` (float, optional): Profit margin
  - `debt_to_equity` (float, optional): Debt-to-equity ratio
  - `current_ratio` (float, optional): Current ratio
  - `payout_ratio` (float, optional): Dividend payout ratio
  - `analyst_recommendation` (float, optional): Analyst recommendation score
  - `upside_pct` (float, optional): Upside percentage
  - `sortino_ratio` (float, optional): Sortino ratio
  - `max_drawdown` (float, optional): Maximum drawdown
  - `market_avg_pe` (float, optional): Market average P/E ratio
  - `target_annual_return` (float, optional): Target annual return

**Response:**
- Status: `200 OK`
- Body: Score result object:
  ```json
  {
    "score": {
      "total_score": 0.85,
      "quality_score": 0.90,
      "opportunity_score": 0.75,
      "fundamental_score": 0.88,
      "technical_score": 0.70,
      "cagr_score": 0.80,
      "allocation_fit_score": 0.65
    }
  }
  ```
  or on error:
  ```json
  {
    "error": "Error message"
  }
  ```

**Error Responses:**
- `400 Bad Request`: Missing symbol, missing daily_prices, invalid data
- `500 Internal Server Error`: Scoring service error
