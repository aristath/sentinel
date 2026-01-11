# GET /api/scoring/formulas/active

Get active scoring formula.

**Description:**
Returns information about the currently active scoring formula, including formula components, weights, and description.

**Request:**
- Method: `GET`
- Path: `/api/scoring/formulas/active`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "formula": "default",
      "components": [
        "fundamental_score",
        "dividend_score",
        "technical_score",
        "quality_score",
        "valuation_score"
      ],
      "weights": {
        "fundamental": 0.25,
        "dividend": 0.20,
        "technical": 0.25,
        "quality": 0.15,
        "valuation": 0.15
      },
      "description": "Default weighted composite score",
      "note": "Symbolic regression can discover alternative formulas"
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```
  - `formula` (string): Formula identifier
  - `components` (array): List of score component names
  - `weights` (object): Weight mapping for each component
  - `description` (string): Formula description
  - `note` (string): Additional notes

**Error Responses:**
- `500 Internal Server Error`: Service error
