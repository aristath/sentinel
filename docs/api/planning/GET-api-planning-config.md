# GET /api/planning/config

Get planner configuration.

**Description:**
Returns the current planner configuration including all planning parameters, constraints, and strategy settings.

**Request:**
- Method: `GET`
- Path: `/api/planning/config`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Planner configuration object (structure varies based on configuration schema)

**Error Responses:**
- `404 Not Found`: No configuration set
- `500 Internal Server Error`: Service error
