# GET /api/portfolio/cost-basis

Get cost basis analysis.

**Description:**
Returns cost basis information for all positions, showing average purchase prices and total cost basis.

**Request:**
- Method: `GET`
- Path: `/api/portfolio/cost-basis`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Cost basis analysis object

**Error Responses:**
- `500 Internal Server Error`: Service error
