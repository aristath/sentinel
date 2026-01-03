# Python to Go Migration - Remaining Work

**Updated:** 2026-01-03
**Status:** ~80% Complete

---

## Priority 1: Critical Jobs (2 files)

**`app/jobs/event_based_trading.py`** (714 lines)
- Main autonomous trading loop
- Monitors planning completion, executes trades
- **Complexity:** High (event-driven workflow)

**`app/modules/planning/jobs/planner_batch.py`** (619 lines)
- Incremental planning batch processor
- Self-triggering for continuation
- **Complexity:** High (state machine + planning integration)

---

## Priority 2: Services (3 files)

**General Rebalancing Workflow**
- `CalculateRebalanceTrades()` - planning integration
- `ExecuteRebalancing()` - orchestration
- Note: Emergency rebalancing is DONE (716 lines)

**Trade Execution - Full Safety Validation**
- Current: Simplified 176-line version
- Missing: 7-layer validation (frequency, market hours, cooldowns, etc.)
- Note: Methods exist in safety_service.go, need integration

**Cash Flow Sync Orchestration**
- Main `SyncFromTradernet()` is stub
- Note: DepositProcessor + DividendCreator are complete

---

## Priority 3: Smaller Jobs (3 files)

1. **Metrics Calculation** (400 lines) - Technical indicators (RSI, EMA, Bollinger, etc.)
2. **Securities Data Sync** - Exists as service, needs job wrapper
3. **Historical Data Sync** - Exists as service, needs job wrapper

---

## Can Stay Python

- `auto_deploy.py` - Deployment pipeline
- `pypfopt` microservice - Portfolio optimization
- `tradernet` microservice - Broker API gateway

---

## Estimated Effort

**Critical (P1-P2):** 3-4 weeks
**Total (P1-P3):** 4-5 weeks
