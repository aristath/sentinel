# Trades

Base path: `/api/trades`

---

## `GET /api/trades`

Returns paginated trade history with optional filters.

**Query params**

| Param | Type | Default | Description |
|---|---|---|---|
| `symbol` | string | — | Filter by security symbol |
| `side` | string | — | `BUY` or `SELL` |
| `start_date` | string | — | Inclusive start date (`YYYY-MM-DD`) |
| `end_date` | string | — | Inclusive end date (`YYYY-MM-DD`) |
| `limit` | int | `100` | Page size |
| `offset` | int | `0` | Pagination offset |

**Response**
```json
{
  "trades": [
    {
      "id": 42,
      "broker_trade_id": "TN-98765",
      "symbol": "AAPL.US",
      "side": "BUY",
      "quantity": 2,
      "price": 182.00,
      "commission": 2.0,
      "commission_currency": "EUR",
      "executed_at": "2026-03-15T09:31:00",
      "raw_data": "{...}"
    }
  ],
  "count": 1,
  "total": 47
}
```

| Field | Description |
|---|---|
| `id` | Internal database ID |
| `broker_trade_id` | Broker-assigned trade identifier |
| `commission` | Trading fee amount |
| `commission_currency` | Currency of the commission |
| `executed_at` | Execution timestamp |
| `raw_data` | Raw JSON payload from the broker |
| `count` | Number of trades in this response |
| `total` | Total trades matching the filters (for pagination) |

---

## `POST /api/trades/sync`

Triggers a manual sync of trade history from the broker (`sync:trades` job).

**Response**
```json
{ "status": "ok", "job_type": "sync:trades" }
```
