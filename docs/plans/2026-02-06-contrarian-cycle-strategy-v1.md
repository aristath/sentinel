# Contrarian Cycle Strategy V1 - Complete End-to-End Plan

Date: 2026-02-06
Status: Draft (execution-ready)
Owner: Sentinel

## Objective
Replace ML/wavelet-driven decisioning with a deterministic, auditable, lot-aware contrarian strategy that remains fully invested and is suitable for a small-to-mid portfolio with coarse lot constraints.

## Ground Rules
- Fully invested: no idle cash reserve target.
- Universe curation is the primary quality filter.
- Structural-break handling is user-driven (manual sell/remove/disable).
- Strategy decisions must be deterministic and explainable.
- Remove components we do not use in production decisioning.

## Delivery Constraints (Non-Negotiable)
- TDD-first: write/adjust failing tests before implementation changes, then make them pass, then refactor.
- No backward compatibility work: remove/replace old behavior directly.
- No deprecations, no legacy fallbacks, no temporary stubs, no TODO deferrals.
- Clean and lean architecture over incremental patching.
- Everything in scope is implemented fully now, fully wired, and fully tested before completion.
- Done criteria are binary: all tests pass, all wiring complete, no dead code paths, no deferred items.

## Strategy Specification

### 1. Signal Inputs
Per symbol, compute:
- `dd252 = close / rolling_max_252 - 1`
- `rsi14`
- `mom20 = close / close_20 - 1`
- `mom60 = close / close_60 - 1`
- `mom120 = close / close_120 - 1`
- `vol20 = stdev(log_returns_20)`
- `vol_ratio = vol20 / vol120`

### 2. Opportunity Score
- `dip = clip((abs(dd252) - 0.12) / 0.23, 0, 1)`
- `cap = clip((30 - rsi14) / 20, 0, 1)`
- `turn = 1 if mom20 > mom60 and mom20 > -0.02 else 0`
- `block = 1 if mom20 < -0.12 and vol_ratio > 1.5 else 0`
- `opp = 0.5*dip + 0.3*cap + 0.2*turn`
- If `block == 1`, force `opp = 0`

### 3. Portfolio Construction
- Core sleeve target: `70%`
- Opportunity sleeve target: `30%`
- Normalize to exactly `100%` invested.

Core ranking score:
- `core_rank = mom120 - 0.5*vol20`

Opportunity eligibility:
- Include symbols where `opp >= 0.55`
- Weight by `opp / max(vol20, vol_floor)`

### 4. Lot-Aware Sizing (Small Portfolio Safe)
For each symbol:
- `min_ticket = lot_size * price * fx + fees`
- `ticket_pct = min_ticket / portfolio_value`

Classification:
- `standard` if `ticket_pct <= 8%`
- `coarse` if `8% < ticket_pct <= 30%`
- `jumbo` if `ticket_pct > 30%`

Rules:
- `standard`: normal tactical entries/exits.
- `coarse`: max `1 lot` net new per rebalance cycle unless `opp >= 0.8` and concentration caps allow.
- `jumbo`: no new entries; only hold/trim existing positions.

### 5. Position Caps/Floors
- Hard symbol cap for small portfolios: default `35%`.
- Core floor for designated core holdings: default `max(5%, 1 lot if currently held)`.
- Do not trim core holdings below floor unless user explicitly permits.

### 6. Entry Tranches
Opportunity entries by drawdown:
- T1 at `dd252 <= -12%`
- T2 at `dd252 <= -20%`
- T3 at `dd252 <= -28%`

For `coarse` symbols:
- one lot per cycle max (no same-cycle stacking).

### 7. Exit/Rotation
Primarily opportunity sleeve:
- Scale out 30% at `+10%` from weighted entry.
- Scale out 30% at `+18%`.
- Exit remainder on momentum rollover (`mom20 < mom60`) after recovery.
- Time-stop rotation after `90` days if thesis does not progress.

Core sleeve:
- only trim above cap/floor boundaries and for funding better opportunities.

### 8. Funding Rule (No Idle Cash)
Buys funded in order:
1. Available cash
2. Trims from lowest-ranked opportunity positions
3. Trims from overweight core positions above floor

No explicit cash reserve target.

### 9. Safety Rails
- Keep stale/anomaly quote blockers.
- Enforce `allow_buy` / `allow_sell` gates.
- Enforce geography/industry concentration limits.
- Opportunity sleeve cooloff default `7` days.
- Core sleeve cooloff default `21` days.

## Implementation Plan (Single Pass)

### 10. Backend Strategy Engine
- Add deterministic strategy module:
  - `sentinel/strategy/contrarian.py`
- Responsibilities:
  - signal computation
  - lot classification
  - sleeve target generation
  - tranche state transitions

### 11. Planner Integration
- Replace score/ML/wavelet sourcing in:
  - `sentinel/planner/allocation.py`
  - `sentinel/planner/rebalance.py`
- Keep existing fee, lot rounding, and cash-constraint mechanics where valid.
- Introduce core-floor and lot-class guards in recommendation generation.

### 12. Database Changes
- Add strategy state table in `sentinel/database/main.py` for:
  - symbol
  - sleeve (`core`/`opportunity`)
  - tranche stage (`0..3`)
  - last entry metadata
  - last rotation metadata
- Add new settings keys for all thresholds/caps.

### 13. API Changes
- Expose deterministic diagnostics in API payloads:
  - `opp_score`, `dip_score`, `capitulation_score`, `cycle_turn`, `freefall_block`
  - `ticket_pct`, `lot_class`, `sleeve`, `core_floor_active`
- Remove ML/wavelet fields from decision-critical responses.

### 14. Frontend Changes
- Remove ML tuning controls from decision workflow.
- Show deterministic strategy diagnostics where recommendations are shown.
- Keep UI explanation-first: every recommendation must include a reason code path.

## Aggressive Cleanup Plan (Remove Unused Components)

### 15. Remove ML/Wavelet Runtime Paths
- Remove ML/wavelet decision references in:
  - `sentinel/planner/allocation.py`
  - `sentinel/planner/rebalance.py`
  - `sentinel/api/routers/securities.py`
  - `sentinel/api/routers/portfolio.py`

### 16. Remove ML Service + Scripts
- Remove `sentinel_ml/` package once planner no longer depends on it.
- Remove obsolete scripts under `scripts/` that train/backfill ML or regimes.

### 17. Remove Wavelet Analyzer Dependency
- Remove wavelet analyzer code used for decisions.
- Remove `pywt` and any unused ML/wavelet dependencies from `pyproject.toml`.

### 18. Remove Dead Settings/Schema
- Remove obsolete settings keys:
  - `ml_weight_*`, `ml_prediction_horizon_days`, `ml_training_lookback_years`, `use_regime_adjustment`, etc.
- Remove obsolete security columns if no longer used:
  - `ml_enabled`, `ml_blend_ratio`.

### 19. Frontend/Tests/Docs Cleanup
- Delete ML/wavelet UI components/hooks/utils no longer used.
- Delete ML/wavelet tests and replace with deterministic strategy tests.
- Update docs to strategy-v1 as source of truth.

## Validation and Cutover

### 20. Test Matrix
- Unit tests: signals, blockers, lot classes, tranches.
- Planner tests: fully-invested invariant, core floor protection, coarse lot behavior.
- Integration tests: recommendation reasons and payload diagnostics.

### 21. Walk-Forward Validation
- Run walk-forward backtests over available broker history.
- Compare to previous behavior on:
  - turnover
  - max drawdown
  - recovery capture
  - missed opportunity rate

### 22. Acceptance Gates
- No decision path references ML/wavelet.
- Fully invested invariant holds.
- No forbidden jumbo entries.
- Core floor protections hold.
- Grep cleanliness check:
  - `rg -n "ml_|wavelet|xgboost|ridge|rf|svr|regime_hmm"`
  - only allowed hits are archived docs kept intentionally.

### 23. Deployment Path
- Research/shadow mode first with live data.
- Promote to live only after acceptance gates pass.

## Operational Loop
- Weekly: review top and bottom decisions by reason codes.
- Monthly: bounded parameter retune (small ranges only; no open-ended optimization).
- Ongoing: maintain curated universe quality.
