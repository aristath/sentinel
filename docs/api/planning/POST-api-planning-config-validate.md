# POST /api/planning/config/validate

Validate planner configuration.

**Description:**
Validates a planner configuration without saving it. Useful for checking configuration before applying it.

**Request:**
- Method: `POST`
- Path: `/api/planning/config/validate`
- Body (JSON): Planner configuration object to validate

**Response:**
- Status: `200 OK` if valid
- Body: Validation result:
  ```json
  {
    "valid": true,
    "errors": []
  }
  ```
  or
  ```json
  {
    "valid": false,
    "errors": ["Error message 1", "Error message 2"]
  }
  ```

**Error Responses:**
- `400 Bad Request`: Invalid request body
