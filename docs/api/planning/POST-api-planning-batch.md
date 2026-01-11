# POST /api/planning/batch

Trigger batch plan generation.

**Description:**
Triggers batch generation of trade plans asynchronously. This endpoint starts a batch generation job that creates multiple trade sequences and evaluates them to find the best plan. The job runs in the background.

**Request:**
- Method: `POST`
- Path: `/api/planning/batch`
- Body (JSON):
  ```json
  {
    "opportunity_context": {
      "profit_taking": [...],
      "averaging_down": [...],
      "rebalance_buys": [...]
    },
    "config_id": 1,
    "config_name": "default",
    "force": false,
    "batch_size": 100
  }
  ```
  - `opportunity_context` (object, required): Opportunities by category
  - `config_id` (integer, optional): Configuration ID to use
  - `config_name` (string, optional): Configuration name to use (defaults to default config if neither ID nor name provided)
  - `force` (boolean, optional): Force regeneration even if plan exists
  - `batch_size` (integer, optional): Number of sequences to generate (defaults to system default)

**Response:**
- Status: `202 Accepted` (async processing)
- Body:
  ```json
  {
    "success": true,
    "message": "Batch generation initiated",
    "job_id": "batch_1705320600",
    "portfolio_hash": "",
    "sequences_total": 0
  }
  ```
  - `job_id` (string): Unique job identifier for tracking
  - `portfolio_hash` (string): Portfolio hash (computed from context)
  - `sequences_total` (integer): Total sequences generated (0 until completion)

**Error Responses:**
- `400 Bad Request`: Missing opportunity_context, invalid request body
- `500 Internal Server Error`: Failed to load configuration, generation failed

**Side Effects:**
- Starts asynchronous batch generation job
- Job runs in background and generates sequences
- Best plan is stored when generation completes
- Events are broadcast during generation
