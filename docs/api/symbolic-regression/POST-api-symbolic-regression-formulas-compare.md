# POST /api/symbolic-regression/formulas/compare

Compare multiple formulas.

**Description:**
Compares multiple formulas side-by-side, showing their validation metrics and identifying the best and worst performers.

**Request:**
- Method: `POST`
- Path: `/api/symbolic-regression/formulas/compare`
- Body (JSON):
  ```json
  {
    "formula_ids": [1, 2, 3],
    "isins": ["US0378331005", "US5949181045"]
  }
  ```
  - `formula_ids` (array of integers, required): Formula IDs to compare
  - `isins` (array of strings, optional): Test ISINs for comparison

**Response:**
- Status: `200 OK`
- Body: Comparison object with formulas, metrics, and best/worst identification

**Error Responses:**
- `400 Bad Request`: Missing formula_ids, empty array
- `500 Internal Server Error`: Comparison error
