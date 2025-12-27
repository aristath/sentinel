# Planner Implementation Analysis

## Executive Summary

**✅ UNIFIED ARCHITECTURE**: The codebase now uses a **single unified recommendations system** powered by the holistic planner. All recommendations (single-step and multi-step) come from the same source.

**Key Changes**:
- Single API endpoint: `GET /api/trades/recommendations` - returns optimal sequence
- Single execution endpoint: `POST /api/trades/recommendations/execute` - always executes first step
- Removed separate buy/sell/multi-step endpoints
- Removed "strategies" concept (merged into holistic planner)
- Simplified execution model: always execute step 1, then recalculate

---

## Unified Architecture

### Single Recommendations System

**Location**: `app/api/recommendations.py`

**Status**: ✅ **ACTIVE** - Single source of truth for all recommendations

**What it does**:
- Uses holistic planner to generate optimal sequence (1-5 steps)
- Returns sequence with portfolio state at each step
- Always executes the first step when requested
- System recalculates after each execution

**Endpoints**:
- `GET /api/trades/recommendations` - Get optimal sequence
- `POST /api/trades/recommendations/execute` - Execute first step

**Service Method**:
- `RebalancingService.get_recommendations()` - Returns `List[MultiStepRecommendation]`

**Flow**:
1. Portfolio optimizer calculates target weights (MV + HRP blend)
2. Holistic planner identifies opportunities from weight gaps
3. Planner generates action sequences at all depths (1-5)
4. Planner evaluates each sequence's end-state score
5. Returns optimal sequence (may be 1 step or multi-step)

---

## Holistic Planner

**Location**: `app/domain/planning/holistic_planner.py`

**Status**: ✅ **ACTIVE** - Core planning engine for all recommendations

**What it does**:
- Evaluates action **SEQUENCES** (1-5 steps), not individual trades
- Scores the **END STATE** of the portfolio after all actions
- Uses windfall detection for smart profit-taking
- Generates narratives explaining the "why" behind each action
- Automatically tests all depths (1-5) and selects optimal sequence

**Key Functions**:
- `create_holistic_plan()` - Main entry point
- `identify_opportunities()` - Heuristic-based opportunity identification
- `identify_opportunities_from_weights()` - Optimizer-driven opportunity identification
- `generate_action_sequences()` - Generates candidate sequences at all depths
- `simulate_sequence()` - Simulates execution and returns end state

**Where it's used**:
- ✅ `RebalancingService.get_recommendations()` - **ONLY USAGE**
- ✅ `app/api/recommendations.py` - Unified API endpoint
- ✅ `app/jobs/sync_cycle.py` - Gets first step from sequence
- ✅ `app/jobs/cash_rebalance.py` - Gets first step from sequence

---

## Execution Model

### Simplified Execution

The system uses a **continuous re-evaluation model**:

1. **Get optimal sequence**: `GET /api/trades/recommendations`
   - Returns sequence of 1-5 steps from holistic planner
   - Sequence is cached for 5 minutes

2. **Execute first step**: `POST /api/trades/recommendations/execute`
   - Always executes step 1 (no `step_number` parameter)
   - After execution, cache is invalidated

3. **Recalculate**: On next request, system recalculates optimal sequence
   - Takes into account the executed trade
   - May return different sequence (could be 1 step or multi-step)
   - Always executes step 1 of the NEW sequence

**Benefits**:
- Simpler API (no step_number needed)
- Always acts on current optimal action
- Adapts to changing portfolio state
- No need for "execute-all" endpoint

---

## Removed Systems

### Old Separate Endpoints (Removed)

- ❌ `GET /api/trades/recommendations` (old buy recommendations)
- ❌ `GET /api/trades/recommendations/sell` (old sell recommendations)
- ❌ `GET /api/trades/multi-step-recommendations` (old multi-step endpoint)
- ❌ `POST /api/trades/multi-step-recommendations/execute-step/{step_number}`
- ❌ `POST /api/trades/multi-step-recommendations/execute-all`
- ❌ `GET /api/trades/multi-step-recommendations/strategies`
- ❌ `GET /api/trades/multi-step-recommendations/all`

### Old Service Methods (Removed)

- ❌ `RebalancingService.get_recommendations(limit=...)` (old buy method)
- ❌ `RebalancingService.get_recommendations_debug()`
- ❌ `RebalancingService.calculate_sell_recommendations()`

### Old Concepts (Removed)

- ❌ "Strategies" concept (merged into holistic planner)
- ❌ Separate buy/sell recommendation systems
- ❌ `step_number` parameter in execution
- ❌ "Execute-all" functionality

---

## Cache Keys

### Unified Cache Pattern

All recommendations use the same cache key pattern:
- `recommendations:{portfolio_hash}` - Portfolio-aware cache key

**Removed patterns**:
- ❌ `multi_step_recommendations:{portfolio_hash}`
- ❌ `recommendations:{limit}` (old buy recommendations)
- ❌ `sell_recommendations:{limit}` (old sell recommendations)

---

## Background Jobs

### sync_cycle.py

**Function**: `_get_holistic_recommendation()`

**What it does**:
- Gets unified recommendations from cache or service
- Extracts first step from sequence
- Returns as `Recommendation` object

**Cache key**: `recommendations:{portfolio_hash}`

### cash_rebalance.py

**Functions**:
- `_get_next_holistic_action()` - Gets first step from unified recommendations
- `_refresh_recommendation_cache()` - Caches unified recommendations and extracts buy/sell for LED ticker

**Cache keys**:
- `recommendations:{portfolio_hash}` - Main cache
- `recommendations:3` - LED ticker buy cache (extracted from unified)
- `sell_recommendations:3` - LED ticker sell cache (extracted from unified)

---

## Frontend

### Unified API Client

**File**: `static/js/api.js`

**Methods**:
- `fetchRecommendations()` - Gets unified recommendations
- `executeRecommendation()` - Executes first step

**Removed methods**:
- ❌ `fetchSellRecommendations()`
- ❌ `fetchMultiStepRecommendations()`
- ❌ `fetchAllStrategyRecommendations()`
- ❌ `executeMultiStepStep(stepNumber)`
- ❌ `executeAllMultiStep()`

### Unified Store

**File**: `static/js/store.js`

**State**:
- `recommendations` - Unified recommendations object: `{depth, steps, total_score_improvement, final_available_cash}`

**Removed state**:
- ❌ `sellRecommendations`
- ❌ `multiStepRecommendations`
- ❌ `allStrategyRecommendations`

### Unified Component

**File**: `static/components/next-actions-card.js`

**What it shows**:
- Optimal sequence from unified recommendations
- All steps in the sequence
- Execute button for first step only

---

## Testing

### Unified Test File

**File**: `tests/unit/api/test_recommendations.py`

**Tests**:
- `TestGetRecommendations` - Tests unified GET endpoint
- `TestExecuteRecommendation` - Tests unified POST endpoint (no step_number)
- `TestRemovedEndpoints` - Verifies old endpoints don't exist

**Removed test files**:
- ❌ `test_multi_step_recommendations.py`
- ❌ Old `test_recommendations.py` (for buy/sell endpoints)

---

## Summary

The codebase now has a **clean, unified architecture**:

1. **Single planner**: Holistic planner evaluates all sequences (1-5 steps)
2. **Single endpoint**: `/api/trades/recommendations` returns optimal sequence
3. **Simple execution**: Always execute step 1, then recalculate
4. **No strategies**: Merged into holistic planner
5. **No step numbers**: Always execute first step of current sequence

This architecture is:
- ✅ Simpler to understand
- ✅ Easier to maintain
- ✅ More flexible (adapts to portfolio state)
- ✅ More consistent (single scoring method)
