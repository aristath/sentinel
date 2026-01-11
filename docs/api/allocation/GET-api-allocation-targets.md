# GET /api/allocation/targets

Get allocation targets for country and industry groups.

**Description:**
Returns allocation target percentages for all country and industry groups. Groups without explicit targets default to 0.0.

**Request:**
- Method: `GET`
- Path: `/api/allocation/targets`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "country": {
      "EU": 45.0,
      "ASIA": 30.0,
      "US": 25.0
    },
    "industry": {
      "Technology": 20.0,
      "Healthcare": 15.0,
      "Financial": 10.0
    }
  }
  ```
  - `country` (object): Country group targets (percentages)
  - `industry` (object): Industry group targets (percentages)

**Error Responses:**
- `500 Internal Server Error`: Database error
