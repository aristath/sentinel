# GET /api/risk/securities/{isin}/beta

Get security beta.

**Description:**
Calculates the beta of a security relative to the portfolio or market. Beta measures sensitivity to market movements.

**Request:**
- Method: `GET`
- Path: `/api/risk/securities/{isin}/beta`
- Path Parameters:
  - `isin` (string, required): Security ISIN

**Response:**
- Status: `200 OK`
- Body: Beta value and calculation details

**Error Responses:**
- `404 Not Found`: Security not found
- `500 Internal Server Error`: Database error
