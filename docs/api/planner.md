# Planner

Base path: `/api/planner`

The planner separates destination from timing. Clara scores define long-term target weights, subject to qualification and position-risk limits. Contrarian opportunity signals decide which under-target securities are timely to buy today. In live execution the plan is valid only for the current configured trading window; the next cycle syncs broker state and replans.

---

## `GET /api/planner/recommendations`

Returns today's trade recommendations, the fresh twelve-month destination behind them, and a fee-adjusted cash summary. The plan is a terminal target snapshot, not a schedule of future orders.

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
      "reason": "Opportunity 0.61; Clara 0.90; dip 0.25; adding standard lot",
      "reason_code": "rebalance_buy",
      "timing_eligible": true,
      "target_gap_ratio": 0.62,
      "is_fallback": false,
      "execution_rank": 1
    }
  ],
  "plan": {
    "as_of_date": "2026-07-16",
    "horizon_end_date": "2027-07-16",
    "horizon_months": 12,
    "current_total_value_eur": 30000.00,
    "avg_monthly_net_deposit_eur": 1000.00,
    "expected_contributions_eur": 12000.00,
    "terminal_portfolio_value_eur": 42000.00,
    "current_cash_eur": 2500.00,
    "target_cash_allocation_pct": 5.00,
    "target_cash_value_eur": 2100.00,
    "cash_gap_eur": -400.00,
    "targets": [
      {
        "symbol": "AAPL.US",
        "clara_score": 0.90,
        "opportunity_score": 0.61,
        "target_allocation_pct": 4.50,
        "current_value_eur": 1720.00,
        "target_value_eur": 1890.00,
        "gap_eur": 170.00
      }
    ]
  },
  "summary": {
    "current_cash": 2500.00,
    "total_sell_value": 0.00,
    "total_buy_value": 305.00,
    "total_fees": 2.61,
    "cash_after_plan": 2192.39,
    "generated_at": "2026-07-16T09:20:00+00:00",
    "valid_for_minutes": 20
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
| `reason_code` | Machine-readable explanation code |
| `timing_eligible` | Whether the opportunity gate prefers this buy now; false buys are convergence fallbacks only |
| `target_gap_ratio` | Fraction of the terminal target amount still missing |
| `is_fallback` | Whether the buy was released by the persistent convergence window |
| `execution_rank` | Order within the complete executable trade set; funding sells come before their buys |

**Plan fields**

| Field | Description |
|---|---|
| `horizon_end_date` | Exact endpoint twelve months after this planner run |
| `expected_contributions_eur` | Current rolling monthly net contribution multiplied by 12 once |
| `terminal_portfolio_value_eur` | Current total plus expected contributions |
| `current_cash_eur` | Current uninvested value inferred from total value and security allocations |
| `target_cash_allocation_pct` | Explicit residual target after configured cash and position caps |
| `target_cash_value_eur` | Cash target at the terminal portfolio value |
| `cash_gap_eur` | Target cash minus current cash |
| `targets` | Every positive target plus current target-zero holdings, with terminal EUR amounts and current gaps |

Normal allocation drift does not create a standalone sell. Non-mandatory sells are selected only when needed to fund a buy that is executable in the current market and cash context. If no normally timed buy is executable, the planner waits `strategy_fallback_wait_days` before allowing one convergence fallback.

**Summary fields**

| Field | Description |
|---|---|
| `cash_after_plan` | Projected cash after executing all recommendations |
| `total_fees` | Combined buy + sell transaction fees |
| `generated_at` | UTC time this advisory plan was produced |
| `valid_for_minutes` | Current `trading:execute` market-open interval, when configured |

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
  "rebalance_threshold_pct": 5,
  "needs_rebalance": true,
  "status": "needs_rebalance"
}
```

| Field | Description |
|---|---|
| `total_deviation` | Sum of absolute allocation deviations across all securities |
| `max_deviation` | Largest single-security deviation |
| `average_deviation` | Mean deviation per security |
| `rebalance_threshold_pct` | Configured deviation threshold used for the status |
| `needs_rebalance` | Boolean convenience field for scheduler/UI consumers |
| `status` | `aligned`, `minor_drift`, or `needs_rebalance` |
