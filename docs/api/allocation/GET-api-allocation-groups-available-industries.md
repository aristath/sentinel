# GET /api/allocation/groups/available/industries

Get available industry names.

**Description:**
Returns a list of all available industry names from securities in the universe. Useful for creating industry groups.

**Request:**
- Method: `GET`
- Path: `/api/allocation/groups/available/industries`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "industries": ["Technology", "Software", "Banking", "Insurance"]
  }
  ```
  - `industries` (array): Array of unique industry names

**Error Responses:**
- `500 Internal Server Error`: Database error
