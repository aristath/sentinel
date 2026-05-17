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
    "effective_user_multiplier": 0.5,
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
    "baseline_target_pct": 1.10,
    "clara_target_pct": 3.40,
    "opportunity_target_pct": 0.00,
    "final_target_pct": 4.50,
    "clara_freshness": 1.0,

    "contrarian_score": 0.61,
    "opp_score": 0.63,
    "dip_score": 0.45,
    "capitulation_score": 0.21,
    "cycle_turn": false,
    "freefall_block": false,
    "ticket_pct": 0.06,
    "lot_class": "standard",
    "sleeve": "core",
    "core_floor_active": false,

    "prices": [
      { "date": "2025-04-27", "close": 185.50 }
    ],

    "recommendation": {
      "action": "buy",
      "quantity": 2,
      "value_delta_eur": 344.00,
      "reason": "Underweight core position — adding standard lot",
      "reason_code": "CORE_UNDERWEIGHT",
      "priority": 0.72
    }
  }
]
```

### Field notes

**Security metadata**

| Field | Description |
|---|---|
| `user_multiplier` | Stored Clara strategic preference, 0 avoid, 0.5 neutral, 1 prefer |
| `effective_user_multiplier` | Preference after temporal fade toward neutral |
| `user_multiplier_age_weeks` | Age of the per-security preference timestamp |
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
| `allocation_sleeve` | Primary sleeve for the target, `core` or `opportunity` |
| `baseline_target_pct` | Baseline deterministic core target contribution |
| `clara_target_pct` | Clara strategic preference target contribution |
| `opportunity_target_pct` | Tactical contrarian opportunity target contribution |
| `final_target_pct` | Final target after normalization and position caps |
| `clara_freshness` | Global Clara freshness coefficient after temporal fade |

**Contrarian signals**

| Field | Description |
|---|---|
| `contrarian_score` | Tactical opportunity score used for display and opportunity rules |
| `opp_score` | Raw opportunity score (0–1) |
| `dip_score` | Dip detection score |
| `capitulation_score` | Capitulation/oversold score |
| `cycle_turn` | `true` if a cyclical turn signal is detected |
| `freefall_block` | `true` if buying is blocked due to freefall pattern |
| `ticket_pct` | Lot cost as fraction of portfolio value |
| `lot_class` | `standard` or `coarse` |
| `sleeve` | `core` or `opportunity` |
| `core_floor_active` | `true` if position is at or below the core floor threshold |

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
| `reason_code` | Machine-readable code (e.g. `CORE_UNDERWEIGHT`) |
| `priority` | Higher = more urgent (used for ordering) |
