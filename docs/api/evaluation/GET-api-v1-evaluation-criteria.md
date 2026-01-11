# GET /api/v1/evaluation/criteria

Get evaluation criteria and weights.

**Description:**
Returns the evaluation criteria, scoring weights, and formulas used by the evaluation system. Useful for understanding how sequences are scored and how to optimize sequences for better scores.

**Request:**
- Method: `GET`
- Path: `/api/v1/evaluation/criteria`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "base_weights": {
        "geographic_fit": 0.25,
        "industry_fit": 0.25,
        "quality_score_fit": 0.15,
        "optimizer_fit": 0.35
      },
      "cost_impact": {
        "penalty_factor": "Configurable (default: 1.0)",
        "description": "Transaction costs reduce final score"
      },
      "feasibility": {
        "min_score": "Must be > 0",
        "cash_sufficiency": "Must have enough cash for all trades",
        "description": "Infeasible sequences get score of 0"
      },
      "allocation_fit_formula": "Weighted sum of geographic, industry, quality, and optimizer alignment",
      "final_score_formula": "allocation_fit - (transaction_costs * penalty_factor)",
      "notes": "Higher scores indicate better portfolio alignment"
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```
  - `data` (object): Evaluation criteria configuration
    - `base_weights` (object): Base weights for different fit components (geographic, industry, quality, optimizer)
    - `cost_impact` (object): Transaction cost impact configuration
    - `feasibility` (object): Feasibility requirements and scoring rules
    - `allocation_fit_formula` (string): Description of allocation fit calculation
    - `final_score_formula` (string): Description of final score calculation
    - `notes` (string): Additional notes about scoring
  - `metadata` (object): Response metadata with timestamp

**Error Responses:**
- None (always returns 200 OK)
