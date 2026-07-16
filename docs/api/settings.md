# Settings

Base path: `/api/settings`

---

## `GET /api/settings`

Returns all application settings, merging stored values with defaults. Runtime snapshots such as exchange rates and LED bridge health may also appear in the same key-value store.

**Response** (abbreviated)
```json
{
  "trading_mode": "live",
  "transaction_fee_fixed": 2.0,
  "transaction_fee_percent": 0.2,
  "max_position_pct": 25,
  "min_position_pct": 2,
  "min_trade_value": 250,
  "min_cash_buffer": 0.005,
  "target_cash_pct": 0,
  "simulated_cash_eur": null,
  "rebalance_threshold_pct": 5,
  "diversification_impact_pct": 10,
  "max_dividend_reinvestment_boost": 0.15,
  "tradernet_api_key": "...",
  "tradernet_api_secret": "...",
  "strategy_min_opp_score": 0.55,
  "strategy_ideal_qualifying_threshold": 0.65,
  "strategy_core_timing_min_score": 0.3,
  "strategy_core_timing_min_dip_score": 0.2,
  "strategy_fallback_wait_days": 30,
  "strategy_entry_t1_dd": -0.1,
  "strategy_entry_t2_dd": -0.16,
  "strategy_entry_t3_dd": -0.22,
  "strategy_entry_memory_days": 45,
  "strategy_memory_max_boost": 0.12,
  "strategy_opportunity_addon_threshold": 0.75,
  "strategy_max_opportunity_buys_per_cycle": 1,
  "strategy_max_new_opportunity_buys_per_cycle": 1,
  "strategy_lot_standard_max_pct": 0.08,
  "strategy_lot_coarse_max_pct": 0.3,
  "strategy_coarse_max_new_lots_per_cycle": 1,
  "cooldown_enabled": true,
  "strategy_opportunity_cooloff_days": 7,
  "strategy_core_cooloff_days": 21,
  "strategy_same_side_cooloff_days": 15,
  "strategy_rotation_time_stop_days": 90,
  "strategy_max_funding_sells_per_cycle": 2,
  "strategy_max_funding_turnover_pct": 0.12,
  "strategy_funding_conviction_bias": 1.0,
  "clara_preference_strength": 5.0,
  "user_multiplier_decay_factor": 0.9,
  "user_multiplier_decay_interval_days": 7,
  "led_display_enabled": true,
  "led_brightness": 200,
  "r2_account_id": "",
  "r2_access_key": "",
  "r2_secret_key": "",
  "r2_bucket_name": "",
  "r2_backup_retention_days": 30,
  "exchange_rates": {
    "EUR": 1.0,
    "USD": 0.8555,
    "GBP": 1.1558,
    "HKD": 0.1094
  },
  "led_bridge_health": {
    "bridge_ok": true,
    "consecutive_failures": 0,
    "last_attempt_ts": 1745748000,
    "last_success_ts": 1745748000,
    "last_error_ts": null,
    "last_error": null,
    "watchdog_action": null,
    "app_instance": "arduino-app/sentinel",
    "updated_at_ts": 1745748000
  }
}
```

**Notable non-obvious fields**

| Field | Description |
|---|---|
| `exchange_rates` | Current FX rates to EUR, embedded as a convenience (same data as `GET /api/exchange-rates`) |
| `led_bridge_health` | Latest bridge health snapshot (same data as `GET /api/led/bridge/health`) |
| `target_cash_pct` | Long-term cash allocation target; the remaining target weight is allocated to securities |
| `min_cash_buffer` | Cash reserve ratio kept out of buy budgets during trade sizing |
| `cooldown_enabled` | Master switch for planner cool-off checks. When false, recent-trade cooldown periods are ignored. |

---

## `PUT /api/settings/{key}`

Set a single setting value.

**Path params**
- `key` — Setting key (e.g. `trading_mode`, `transaction_fee_fixed`)

**Request body**
```json
{ "value": "live" }
```

**Response**
```json
{ "status": "ok" }
```

Planner-affecting settings such as cash targets, transaction fees, position caps, and timing thresholds invalidate planner caches when updated through this endpoint.

---

## `PUT /api/settings`

Atomically update the strategy-tuning settings shown in the Strategy tab. All keys must be present; partial updates are rejected. Other planner settings, including cash reserve and target cash, are updated individually through `PUT /api/settings/{key}`.

**Required keys**
- `strategy_min_opp_score` — Minimum score to classify a security as opportunity (0–1).
- `strategy_ideal_qualifying_threshold` — Minimum Clara score required for a positive long-term target (0–1).
- `strategy_core_timing_min_score` — Minimum opportunity score for a normally timed core buy (0–1).
- `strategy_core_timing_min_dip_score` — Minimum dip score for a normally timed core buy (0–1); a cycle turn also qualifies.
- `strategy_fallback_wait_days` — Persistent wait before one poorly timed convergence buy may execute (0–365).
- `strategy_entry_t1_dd`, `strategy_entry_t2_dd`, `strategy_entry_t3_dd` — Drawdown tranche thresholds (-0.9–0).
- `strategy_entry_memory_days` — Recent-dip memory window (1–252).
- `strategy_memory_max_boost` — Maximum recent-dip opportunity boost (0–0.5).
- `strategy_opportunity_addon_threshold` — Opportunity score required for additional accumulation (0–1).
- `strategy_max_opportunity_buys_per_cycle` — Total opportunity buys allowed per cycle (0–50).
- `strategy_max_new_opportunity_buys_per_cycle` — New opportunity positions allowed per cycle (0–50).

**Request body**
```json
{
  "values": {
    "strategy_min_opp_score": 0.55,
    "strategy_ideal_qualifying_threshold": 0.65,
    "strategy_core_timing_min_score": 0.3,
    "strategy_core_timing_min_dip_score": 0.2,
    "strategy_fallback_wait_days": 30,
    "strategy_entry_t1_dd": -0.1,
    "strategy_entry_t2_dd": -0.16,
    "strategy_entry_t3_dd": -0.22,
    "strategy_entry_memory_days": 45,
    "strategy_memory_max_boost": 0.12,
    "strategy_opportunity_addon_threshold": 0.75,
    "strategy_max_opportunity_buys_per_cycle": 1,
    "strategy_max_new_opportunity_buys_per_cycle": 1
  }
}
```

**Response**
```json
{ "status": "ok" }
```

**Errors**
- `400` — Missing keys, wrong types, or out-of-range values.
