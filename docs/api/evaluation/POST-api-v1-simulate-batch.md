# POST /api/v1/simulate/batch

Simulate multiple sequences in batch.

**Description:**
Simulates multiple trade sequences in batch, projecting future performance. Used for forward-looking analysis.

**Request:**
- Method: `POST`
- Path: `/api/v1/simulate/batch`
- Body (JSON):
  ```json
  {
    "sequences": [...],
    "evaluation_context": {
      "transaction_cost_fixed": 2.0,
      "transaction_cost_percent": 0.002
    }
  }
  ```
  - `sequences` (array, required): Sequences to simulate (max 10,000)
  - `evaluation_context` (object, required): Simulation parameters

**Response:**
- Status: `200 OK`
- Body: Simulation results for each sequence

**Error Responses:**
- `400 Bad Request`: No sequences provided, too many sequences
- `500 Internal Server Error`: Simulation failed
