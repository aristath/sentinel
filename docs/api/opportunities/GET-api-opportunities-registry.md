# GET /api/opportunities/registry

Get opportunity registry.

**Description:**
Returns the complete opportunity registry showing all identified opportunities with their metadata and classification.

**Request:**
- Method: `GET`
- Path: `/api/opportunities/registry`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Opportunity registry object with all opportunities organized by type

**Error Responses:**
- `500 Internal Server Error`: Service error
