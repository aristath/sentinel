# Backtest

Base path: `/api/backtest`

Runs historical simulations using the actual Planner and trading logic in an isolated in-memory database. The real database is never modified.

---

## `GET /api/backtest/run`

Run a backtest simulation. Returns a **Server-Sent Events (SSE)** stream — connect with `EventSource` or an SSE-capable HTTP client.

**Query params**

| Param | Type | Default | Description |
|---|---|---|---|
| `start_date` | string | required | Start date (`YYYY-MM-DD`) |
| `end_date` | string | required | End date (`YYYY-MM-DD`) |
| `initial_capital` | float | `10000.0` | Starting capital in EUR |
| `monthly_deposit` | float | `0.0` | Monthly cash injection in EUR |
| `rebalance_frequency` | string | `weekly` | `daily` or `weekly` |
| `use_existing_universe` | bool | `true` | Use the current security universe |
| `pick_random` | bool | `true` | Pick a random subset of the universe |
| `random_count` | int | `10` | Number of securities to pick randomly |
| `symbols` | string | `""` | Comma-separated list of specific symbols (overrides random pick) |

**Response headers**
```
Content-Type: text/event-stream
Cache-Control: no-cache
```

### SSE event: `progress`

Emitted periodically as the simulation advances through time.

```json
{
  "current_date": "2023-06-15",
  "progress_pct": 42.5,
  "portfolio_value": 12350.00,
  "status": "running",
  "message": "Rebalancing...",
  "phase": "rebalance",
  "current_item": "AAPL.US",
  "items_done": 4,
  "items_total": 10
}
```

`status` can be `running`, `error`, or `cancelled`. The stream ends after an `error` or `cancelled` status.

### SSE event: `result`

Emitted once when the simulation completes successfully.

```json
{
  "config": {
    "start_date": "2020-01-01",
    "end_date": "2024-12-31",
    "initial_capital": 10000.0,
    "monthly_deposit": 500.0,
    "rebalance_frequency": "weekly",
    "use_existing_universe": true,
    "pick_random": true,
    "random_count": 10,
    "symbols": []
  },
  "snapshots": [
    {
      "date": "2020-01-06",
      "total_value": 10050.00,
      "cash": 500.00,
      "positions_value": 9550.00
    }
  ],
  "trades": [
    {
      "date": "2020-01-06",
      "symbol": "AAPL.US",
      "action": "buy",
      "quantity": 5,
      "price": 76.20,
      "value": 381.00
    }
  ],
  "initial_value": 10000.00,
  "final_value": 18430.00,
  "total_deposits": 13000.00,
  "total_return": 5430.00,
  "total_return_pct": 41.8,
  "cagr": 7.2,
  "max_drawdown": -18.5,
  "sharpe_ratio": 0.82,
  "security_performance": [
    {
      "symbol": "AAPL.US",
      "name": "Apple Inc",
      "total_invested": 3200.00,
      "total_sold": 1800.00,
      "final_value": 2100.00,
      "total_return": 700.00,
      "return_pct": 21.9,
      "num_buys": 8,
      "num_sells": 3
    }
  ]
}
```

### SSE event: `error`

Emitted on failure.

```json
{ "message": "Insufficient price data for universe" }
```

---

## `POST /api/backtest/cancel`

Cancel a running backtest. No-op if no backtest is active.

**Response**
```json
{ "status": "ok", "message": "Backtest cancellation requested" }
```
