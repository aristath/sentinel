# PUT /api/planning/config

Update planner configuration.

**Description:**
Updates the planner configuration. The configuration is validated before being saved.

**Request:**
- Method: `PUT`
- Path: `/api/planning/config`
- Body (JSON): Planner configuration object (structure depends on configuration schema)

**Response:**
- Status: `200 OK` on success
- Body: Updated configuration object

**Error Responses:**
- `400 Bad Request`: Invalid configuration, validation error
- `500 Internal Server Error`: Service error
