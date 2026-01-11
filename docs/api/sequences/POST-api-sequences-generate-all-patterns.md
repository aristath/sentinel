# POST /api/sequences/generate/all-patterns

Generate sequences from all patterns.

**Description:**
Generates trade sequences using all 13 available patterns simultaneously. This produces the most comprehensive set of sequences.

**Request:**
- Method: `POST`
- Path: `/api/sequences/generate/all-patterns`
- Body (JSON):
  ```json
  {
    "opportunities": {...},
    "config": {...}
  }
  ```
  - `opportunities` (object, required): Opportunities by category
  - `config` (object, optional): Planner configuration (all patterns enabled)

**Response:**
- Status: `200 OK`
- Body: Sequences from all patterns (may be large)

**Error Responses:**
- `400 Bad Request`: Invalid request body
- `500 Internal Server Error`: Generation failed
