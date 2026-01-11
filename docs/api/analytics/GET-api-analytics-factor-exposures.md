# GET /api/analytics/factor-exposures

Get portfolio factor exposures.

**Description:**
Calculates and returns portfolio factor exposures for value, quality, momentum, and size factors. Shows how the portfolio is tilted toward different investment factors.

**Request:**
- Method: `GET`
- Path: `/api/analytics/factor-exposures`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "value": 0.25,
    "quality": 0.45,
    "momentum": 0.30,
    "size": 0.20,
    "contributions": {
      "value": {
        "AAPL.US": 0.05,
        "MSFT.US": 0.08
      },
      "quality": {
        "AAPL.US": 0.10,
        "MSFT.US": 0.12
      },
      "momentum": {
        "AAPL.US": 0.06,
        "MSFT.US": 0.09
      },
      "size": {
        "AAPL.US": 0.04,
        "MSFT.US": 0.05
      }
    }
  }
  ```
  - Factor exposure values range from -1.0 to +1.0
  - Positive values indicate tilt toward the factor
  - Contributions show individual security contributions

**Error Responses:**
- `500 Internal Server Error`: Service error, insufficient data
