# Portfolio

Base path: `/api/portfolio`

---

## `GET /api/portfolio`

Returns the full current portfolio state: positions, cash balances, and aggregate values.

**Response**
```json
{
  "positions": [
    {
      "symbol": "AAPL.US",
      "name": "Apple Inc.",
      "quantity": 5.0,
      "avg_cost": 160.00,
      "current_price": 270.94,
      "currency": "USD",
      "updated_at": "now",
      "value_local": 1354.70,
      "value_eur": 1159.01,
      "invested_eur": 684.74,
      "profit_pct": 69.34
    }
  ],
  "total_value": 23917.92,
  "total_value_eur": 23917.92,
  "portfolio_return_pct": 12.5,
  "cash": {
    "EUR": 1200.00,
    "USD": 350.00
  },
  "total_cash_eur": 1499.43
}
```

**Position fields**

| Field | Description |
|---|---|
| `value_local` | Position value in the security's native currency |
| `value_eur` | Position value converted to EUR |
| `invested_eur` | Cost basis of the position in EUR (`avg_cost × quantity` converted) |
| `profit_pct` | Unrealised P&L as a percentage of invested cost |
| `updated_at` | Timestamp of last quote update (`"now"` when synced live) |

**Top-level fields**

| Field | Description |
|---|---|
| `total_value` | Total portfolio value in base currency |
| `total_value_eur` | Total portfolio value in EUR |
| `portfolio_return_pct` | Overall return percentage from inception |
| `cash` | Cash balances per currency |
| `total_cash_eur` | Sum of all cash balances converted to EUR |

---

## `POST /api/portfolio/sync`

Triggers a live sync of portfolio positions from the broker. Equivalent to running the `sync:portfolio` job manually.

**Response**
```json
{ "status": "ok" }
```

---

## `GET /api/portfolio/cagr`

Returns a lightweight CAGR from inception for ambient display. Calculated from net card deposits to current portfolio value.

**Response**
```json
{
  "cagr": 20.4,
  "years": 1.97,
  "target": 11.0
}
```

- `cagr` — Compound annual growth rate in percent
- `years` — Years since first portfolio snapshot
- `target` — Hardcoded target CAGR (11%)

---

## `GET /api/portfolio/pnl-history`

Returns daily P&L history for the past 365 days with 365-day rolling time-weighted return (TWR).

**Response**
```json
{
  "snapshots": [
    {
      "date": "2025-04-27",
      "total_value_eur": 44200.00,
      "net_deposits_eur": 40000.00,
      "pnl_eur": 4200.00,
      "pnl_pct": 10.5,
      "actual_ann_return": 9.8
    }
  ],
  "summary": {
    "start_value": 38000.00,
    "end_value": 44200.00,
    "start_net_deposits": 36000.00,
    "end_net_deposits": 40000.00,
    "pnl_absolute": 4200.00,
    "pnl_percent": 10.5,
    "target_ann_return": 11.0
  }
}
```

- `actual_ann_return` — 365-day rolling TWR annualised (null if insufficient history)
