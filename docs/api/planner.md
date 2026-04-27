# Planner

Base path: `/api/planner`

The planner computes a deterministic ideal portfolio allocation from the contrarian strategy and generates trade recommendations to move the current portfolio toward it.

---

## `GET /api/planner/recommendations`

Returns trade recommendations to move the portfolio toward its ideal allocation, along with a fee-adjusted cash summary.

**Query params**
- `min_value` (float, optional) — Minimum trade value in EUR. Defaults to the `min_trade_value` setting.

**Response**
```json
{
  "recommendations": [
    {
      "symbol": "AAPL.US",
      "action": "buy",
      "current_allocation_pct": 3.82,
      "target_allocation_pct": 4.50,
      "allocation_delta_pct": 0.68,
      "current_value_eur": 1720.00,
      "target_value_eur": 2025.00,
      "value_delta_eur": 305.00,
      "quantity": 2,
      "price": 185.50,
      "currency": "USD",
      "lot_size": 1,
      "contrarian_score": 0.61,
      "priority": 0.72,
      "reason": "Underweight core position — adding standard lot"
    }
  ],
  "summary": {
    "current_cash": 2500.00,
    "total_sell_value": 0.00,
    "total_buy_value": 305.00,
    "total_fees": 2.61,
    "cash_after_plan": 2192.39
  }
}
```

**Recommendation fields**

| Field | Description |
|---|---|
| `action` | `buy` or `sell` |
| `allocation_delta_pct` | Target minus current (positive = underweight) |
| `value_delta_eur` | EUR amount to buy (positive) or sell (negative) |
| `quantity` | Shares/units rounded to lot size |
| `contrarian_score` | Deterministic signal strength |
| `priority` | Higher = more urgent to act on |
| `reason` | Human-readable explanation |

**Summary fields**

| Field | Description |
|---|---|
| `cash_after_plan` | Projected cash after executing all recommendations |
| `total_fees` | Combined buy + sell transaction fees |

---

## `GET /api/planner/ideal`

Returns the calculated ideal portfolio allocation vs current, as percentages.

**Response**
```json
{
  "ideal": { "AAPL.US": 4.50, "MSFT.US": 5.00 },
  "current": { "AAPL.US": 3.82, "MSFT.US": 6.20 }
}
```

---

## `GET /api/planner/summary`

Returns a high-level summary of how well the portfolio is aligned with its ideal allocation.

**Response**
```json
{
  "total_securities": 41,
  "aligned_count": 34,
  "needs_adjustment_count": 7,
  "total_deviation": 1.39,
  "max_deviation": 0.29,
  "average_deviation": 0.034,
  "status": "needs_rebalance"
}
```

| Field | Description |
|---|---|
| `total_deviation` | Sum of absolute allocation deviations across all securities |
| `max_deviation` | Largest single-security deviation |
| `average_deviation` | Mean deviation per security |
| `status` | `aligned` or `needs_rebalance` |
