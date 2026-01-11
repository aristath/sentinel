# POST /api/sequences/generate/combinatorial

Generate sequences using multiple patterns.

**Description:**
Generates trade sequences using a combination of multiple patterns. All specified patterns are enabled simultaneously.

**Request:**
- Method: `POST`
- Path: `/api/sequences/generate/combinatorial`
- Body (JSON):
  ```json
  {
    "pattern_types": ["profit_taking", "rebalancing"],
    "opportunities": {...},
    "config": {...}
  }
  ```
  - `pattern_types` (array of strings, required): Pattern names to combine
  - `opportunities` (object, required): Opportunities by category
  - `config` (object, optional): Planner configuration

**Response:**
- Status: `200 OK`
- Body: Sequences generated from combined patterns

**Error Responses:**
- `400 Bad Request`: Missing or empty pattern_types
- `500 Internal Server Error`: Generation failed
