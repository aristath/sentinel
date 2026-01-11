# DELETE /api/planning/config

Delete planner configuration.

**Description:**
Deletes the current planner configuration.

**Request:**
- Method: `DELETE`
- Path: `/api/planning/config`
- Body: None

**Response:**
- Status: `204 No Content` on success

**Error Responses:**
- `404 Not Found`: No configuration exists
- `500 Internal Server Error`: Service error
