# Unified View

Base path: `/api/unified`

Returns a single merged view of all active securities, combining position data, price history, contrarian signals, allocations, and trade recommendations. This is the primary data source for the main dashboard.

---

## `GET /api/unified`

**Query params**
- `period` (string, default `1Y`) — Price history window: `1M`, `1Y`, `5Y`, `10Y`
- `as_of` (string, optional) — Historical date (`YYYY-MM-DD`). When set, uses historical prices and positions as of that date instead of live data.

**Response** — Array, one object per security:

```json
[
  {
    "symbol": "AAPL.US",
    "name": "Apple Inc",
    "currency": "USD",
    "geography": "US",
    "industry": "Technology",
    "min_lot": 1,
    "active": 1,
    "allow_buy": 1,
    "allow_sell": 1,
    "user_multiplier": 0.5,
    "user_multiplier_age_weeks": 0.0,
    "user_multiplier_source": "clara",
    "user_multiplier_analysis": "Long-term strategic fit remains neutral.",
    "aliases": null,

    "has_position": true,
    "quantity": 10,
    "avg_cost": 160.00,
    "current_price": 185.50,
    "value_local": 1855.00,
    "value_eur": 1720.00,
    "profit_pct": 15.94,
    "profit_value": 255.00,
    "profit_value_eur": 236.40,
    "price_warning": null,

    "current_allocation": 3.82,
    "post_plan_allocation": 4.10,
    "ideal_allocation": 4.50,
    "allocation_sleeve": "core",
    "baseline_target_pct": 0.00,
    "clara_target_pct": 4.50,
    "opportunity_target_pct": 0.00,
    "final_target_pct": 4.50,

    "contrarian_score": 0.61,
    "opp_score": 0.63,
    "opp_score_raw": 0.61,
    "dip_score": 0.45,
    "capitulation_score": 0.21,
    "cycle_turn": false,
    "freefall_block": false,
    "ticket_pct": 0.06,
    "lot_class": "standard",
    "sleeve": "core",

    "prices": [
      { "date": "2025-04-27", "close": 185.50 }
    ],

    "recommendation": {
      "action": "buy",
      "quantity": 2,
      "value_delta_eur": 344.00,
      "reason": "Opportunity 0.61; Clara 0.90; dip 0.45; adding standard lot",
      "reason_code": "rebalance_buy",
      "execution_rank": 1,
      "contrarian_score": 0.61,
      "target_gap_ratio": 0.62,
      "timing_eligible": true,
      "is_fallback": false,
      "priority": 0.72
    }
  }
]
```

### Field notes

**Security metadata**

| Field | Description |
|---|---|
| `user_multiplier` | Stored strategic preference, 0 avoid, 0.5 neutral, 1 prefer. The weekly `decay:user_multipliers` job nudges this value back toward 0.5 over ~52 weeks of no touch. |
| `user_multiplier_age_weeks` | Age of the per-security preference timestamp (resets when the slider is touched OR the decay job runs) |
| `user_multiplier_source` | Preference source, usually `clara`, `manual`, or `migration` |
| `user_multiplier_analysis` | Human-readable rationale for the stored preference |
| `aliases` | Alternative names/tickers for companion apps |

**Position**

| Field | Description |
|---|---|
| `has_position` | `true` if quantity > 0 |
| `value_local` | Position value in the security's native currency |
| `value_eur` | Position value converted to EUR |
| `price_warning` | Non-null string if the live price looks anomalous vs historical data |

**Allocations** (all in percent)

| Field | Description |
|---|---|
| `current_allocation` | Current position as % of total portfolio |
| `post_plan_allocation` | Allocation after applying all recommendations |
| `ideal_allocation` | Target allocation from the Planner |
| `allocation_sleeve` | Timing classification, `core` or `opportunity`; it does not change the long-term weight |
| `baseline_target_pct` | Compatibility field; currently `0` because targets are Clara-defined |
| `clara_target_pct` | Clara-defined long-term target after normalization and position caps |
| `opportunity_target_pct` | Compatibility field; currently `0` because opportunity affects timing, not destination |
| `final_target_pct` | Final long-term security target after normalization and position caps |

**Contrarian signals**

| Field | Description |
|---|---|
| `contrarian_score` | Tactical opportunity score used for display and opportunity rules |
| `opp_score` | Effective opportunity score after recent-dip memory (0–1) |
| `opp_score_raw` | Raw opportunity score before recent-dip memory is applied |
| `dip_score` | Dip detection score |
| `capitulation_score` | Capitulation/oversold score |
| `cycle_turn` | `true` if a cyclical turn signal is detected |
| `freefall_block` | `true` if buying is blocked due to freefall pattern |
| `ticket_pct` | Lot cost as fraction of portfolio value |
| `lot_class` | `standard` or `coarse` |
| `sleeve` | `core` or `opportunity` |

**Prices**

Ordered oldest-first within the requested `period`. Each entry: `{ "date": "YYYY-MM-DD", "close": float }`.

**Recommendation**

`null` if no trade is recommended. When present:

| Field | Description |
|---|---|
| `action` | `buy` or `sell` |
| `quantity` | Shares/units to trade |
| `value_delta_eur` | EUR value impact (positive = buy, negative = sell) |
| `reason` | Human-readable explanation |
| `reason_code` | Machine-readable reason such as `entry_t1` or `convergence_fallback` |
| `execution_rank` | Order in the complete executable recommendation set |
| `contrarian_score` | Opportunity score used to rank buy timing |
| `target_gap_ratio` | Fraction of the twelve-month target value still missing |
| `timing_eligible` | Whether the buy meets its normal opportunity timing gate |
| `is_fallback` | `true` only for a convergence buy released after the patience window |
| `priority` | Legacy numeric urgency value; execution order is authoritative |
