# POST /api/planning/execute

Execute a step in a trade plan.

**Description:**
Executes a specific step in the best trade plan for a portfolio. Retrieves the plan from the database, validates the step number, and executes the trade via the trading service.

**Request:**
- Method: `POST`
- Path: `/api/planning/execute`
- Body (JSON):
  ```json
  {
    "portfolio_hash": "abc123def456",
    "step_number": 1
  }
  ```
  - `portfolio_hash` (string, required): Portfolio hash identifying the plan
  - `step_number` (integer, required): Step number to execute (1-based, must be within plan bounds)

**Response:**
- Status: `200 OK` on success
- Body (success):
  ```json
  {
    "success": true,
    "message": "Step executed successfully",
    "step_number": 1,
    "next_step": 2,
    "execution_details": "Executed step 1: BUY AAPL.US (quantity: 10, price: $150.25, value: $1502.50 USD)"
  }
  ```
  - `step_number` (integer): Step that was executed
  - `next_step` (integer): Next step number (0 if this was the last step)
  - `execution_details` (string): Human-readable execution summary

- Body (failure):
  ```json
  {
    "success": false,
    "message": "Trade execution failed: insufficient funds",
    "step_number": 1,
    "execution_details": "Failed to execute BUY AAPL.US"
  }
  ```

**Error Responses:**
- `400 Bad Request`: Invalid step number (out of bounds)
- `404 Not Found`: Plan not found for portfolio_hash, no plan available
- `500 Internal Server Error`: Trade execution failed

**Side Effects:**
- Executes the trade via trading service
- Trade is recorded in ledger
- Portfolio state is updated
- Events are emitted for execution
