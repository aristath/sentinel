# GET /api/symbolic-regression/formulas

Get all discovered formulas.

**Description:**
Returns all formulas discovered by symbolic regression for expected returns and scoring. Formulas are organized by type and regime ranges.

**Request:**
- Method: `GET`
- Path: `/api/symbolic-regression/formulas`
- Query Parameters:
  - `formula_type` (optional, string): Filter by formula type ("expected_return" or "scoring")
  - `security_type` (optional, string): Filter by security type ("stock" or "etf")
  - `limit` (optional, integer): Maximum number of formulas to return

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "formulas": [
        {
          "id": 1,
          "formula_type": "expected_return",
          "security_type": "stock",
          "regime_range_min": -1.0,
          "regime_range_max": 1.0,
          "formula_expression": "0.05 * pe_ratio + 0.03 * dividend_yield",
          "validation_metrics": {
            "fitness": 0.85,
            "r_squared": 0.80
          },
          "discovered_at": "2024-01-15T10:00:00Z"
        }
      ],
      "count": 10
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```

**Error Responses:**
- `500 Internal Server Error`: Database error
