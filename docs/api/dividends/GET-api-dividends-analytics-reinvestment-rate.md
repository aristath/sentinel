# GET /api/dividends/analytics/reinvestment-rate

Get overall dividend reinvestment rate.

**Description:**
Returns the overall reinvestment rate, calculated as the percentage of dividends that have been reinvested vs. total dividends received.

**Request:**
- Method: `GET`
- Path: `/api/dividends/analytics/reinvestment-rate`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "rate": 0.85
  }
  ```
  - `rate` (float): Reinvestment rate as a decimal (e.g., 0.85 = 85%)

**Error Responses:**
- `500 Internal Server Error`: Database error
