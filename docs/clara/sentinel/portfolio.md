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
  "cash": { "EUR": 1200.00, "USD": 350.00 },
  "total_cash_eur": 1499.43
}
```

The legacy `allocations` field (per-geography / per-industry / per-security rollups) was removed alongside the allocation-targets feature.

---

## `POST /api/portfolio/sync`

Triggers a live sync of portfolio positions from the broker.

---

## `GET /api/portfolio/cagr`

Lightweight CAGR from inception for ambient display.

---

## `GET /api/portfolio/pnl-history`

Daily P&L history with a rolling 365-day money-weighted investor return that
uses the opening value plus every dated deposit and withdrawal.

---

## Removed endpoints

- `GET /api/portfolio/allocations` — gone.
- `GET /api/allocation/current`, `GET /api/allocation/targets`, all `PUT/DELETE /api/allocation/targets/*` — gone.
- `GET /api/allocation-targets`, `PUT /api/allocation-targets/*` — gone.

Allocation targets and the planner's diversification-tilt mechanism have been retired; per-security `ai_research_multiplier` ratings are now the sole conviction signal.
