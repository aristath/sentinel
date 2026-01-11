# DELETE /api/securities/{isin}

Delete a security (soft delete).

**Description:**
Performs a soft delete on a security by setting its `active` flag to false. The security record remains in the database but is no longer included in active listings.

**Request:**
- Method: `DELETE`
- Path: `/api/securities/{isin}`
- Path Parameters:
  - `isin` (string, required): ISIN of the security to delete

**Response:**
- Status: `200 OK` on success
- Body:
  ```json
  {
    "message": "Security AAPL.US removed from universe"
  }
  ```

**Error Responses:**
- `400 Bad Request`: Invalid ISIN format
- `404 Not Found`: Security not found
- `500 Internal Server Error`: Delete failed

**Side Effects:**
- Sets security `active` flag to false (soft delete)
- Security is no longer included in active listings
- Existing positions and historical data are preserved
