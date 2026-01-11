# POST /api/trades/execute

Execute a manual trade.

**Description:**
Executes a trade order through the broker. Includes 7-layer safety validation before execution. Trades are blocked if the system is in research mode. Uses market orders (immediate execution at current market price).

**Request:**
- Method: `POST`
- Path: `/api/trades/execute`
- Body (JSON):
  ```json
  {
    "symbol": "AAPL.US",
    "side": "BUY",
    "quantity": 10.0
  }
  ```
  - `symbol` (string, required): Security symbol
  - `side` (string, required): "BUY" or "SELL"
  - `quantity` (float, required): Number of shares/units to trade

**Response:**
- Status: `200 OK` on success
- Body:
  ```json
  {
    "status": "success",
    "order_id": "ORD-12345",
    "symbol": "AAPL.US",
    "side": "BUY",
    "quantity": 10.0,
    "price": 150.25
  }
  ```
  - `status` (string): "success"
  - `order_id` (string): Broker-assigned order ID
  - `symbol` (string): Executed symbol
  - `side` (string): Executed side
  - `quantity` (float): Executed quantity
  - `price` (float): Execution price

**Error Responses:**
- `400 Bad Request`: Invalid request body, trade validation failed
- `403 Forbidden`: Trading disabled in research mode
- `500 Internal Server Error`: Failed to place order, broker error

**Safety Validation:**
The endpoint performs 7-layer safety validation including:
- Trading mode checks
- Security eligibility
- Cash sufficiency
- Position limits
- Risk checks
- And more (see TradeSafetyService)

**Side Effects:**
- Trade is recorded in the database
- TRADE_EXECUTED event is emitted
- Portfolio positions are updated (via sync)
