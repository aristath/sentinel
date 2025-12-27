# Planner Implementation Analysis

## Executive Summary

After analyzing the codebase, there is **ONE planner implementation** (the holistic planner), but **THREE separate recommendation systems** that serve different purposes. The holistic planner is only used for multi-step recommendations.

**⚠️ CRITICAL INSIGHT**: There is **NO conceptual difference** between "planner" and "recommendations". The holistic planner already evaluates sequences of length 1-5, so it should handle ALL recommendations (single and multi-step). The current separation is unnecessary and should be unified.

---

## Conceptual Analysis: Why Separate "Planner" and "Recommendations"?

### The User's Question

> "Why is there a separation between 'planner' and 'recommendation'? What is the conceptual difference? If the 'holistic planner' evaluates sequences of actions and also evaluates single-action sequences, then that should cover the single buy and single sell recommendations. Correct?"

### Answer: **There is NO conceptual difference. The separation is unnecessary.**

The holistic planner:
1. ✅ Evaluates sequences of length **1-5** (already handles single actions)
2. ✅ Scores **end-states** (better than post-transaction scoring)
3. ✅ Handles both **buys and sells**
4. ✅ Can work with or without **optimizer target weights**

**Therefore**: The holistic planner should be the **single source of truth** for ALL recommendations.

### Current Unnecessary Separation

| System | Uses Holistic Planner? | Scoring Method | Why Separate? |
|--------|------------------------|----------------|---------------|
| Single Buy | ❌ No | `calculate_post_transaction_score()` | **No good reason** |
| Single Sell | ❌ No | Sell-specific scoring | **No good reason** |
| Multi-Step | ✅ Yes | `calculate_portfolio_end_state_score()` | **This is correct** |

**The Problem**:
- Post-transaction score: Only evaluates diversification impact
- End-state score: Evaluates total return, promise, stability, diversification, opinion (weighted across entire portfolio)
- **End-state scoring is superior** - why use inferior scoring for single recommendations?

**The Solution**:
- Use holistic planner for **everything**
- If optimal sequence is 1 step → return as single recommendation
- If optimal sequence is 2-5 steps → return as multi-step recommendation
- **No conceptual difference needed**

---

## Current Architecture

### 1. Holistic Planner (Single Implementation)

**Location**: `app/domain/planning/holistic_planner.py`

**Status**: ✅ **ACTIVE** - This is the unified planner implementation

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
- ✅ `RebalancingService.get_multi_step_recommendations()` - **ONLY USAGE**
- ✅ `app/api/multi_step_recommendations.py` - API endpoint
- ✅ `app/jobs/sync_cycle.py` - `_get_holistic_recommendation()`
- ✅ `app/jobs/cash_rebalance.py` - `_get_next_holistic_action()`

**Note**: The comment in `holistic_planner.py` line 4 mentions "This planner differs from the standard goal planner by:" but **no such "standard goal planner" exists** in the codebase. This appears to be legacy documentation.

---

## Three Recommendation Systems (Not Three Planners)

### System 1: Single Buy Recommendations

**Location**: `app/application/services/rebalancing_service.py::get_recommendations()`

**Status**: ✅ **ACTIVE** - Does NOT use holistic planner

**What it does**:
- Generates individual buy recommendations
- Scores each stock by POST-TRANSACTION portfolio impact
- Uses portfolio-aware scoring with allocation fit
- Respects min_lot and transaction costs
- Stores recommendations in database with UUIDs

**Flow**:
1. Build portfolio context
2. Filter stocks (cooldown, quality, price)
3. Score each candidate by portfolio improvement
4. Store top N recommendations in database
5. Return as `List[Recommendation]`

**Where it's used**:
- ✅ `app/api/recommendations.py::get_recommendations()` - API endpoint
- ✅ `app/jobs/sync_cycle.py` - (indirectly, for single-step trades)

**Key difference from holistic planner**:
- Evaluates **individual trades**, not sequences
- Uses **post-transaction scoring** (how portfolio looks after ONE trade)
- Does NOT consider multi-step sequences

---

### System 2: Single Sell Recommendations

**Location**: `app/application/services/rebalancing_service.py::calculate_sell_recommendations()`

**Status**: ✅ **ACTIVE** - Does NOT use holistic planner

**What it does**:
- Generates individual sell recommendations
- Uses sell scoring system (windfall, rebalancing, opportunity cost)
- Scores each position by sell impact
- Stores recommendations in database with UUIDs

**Flow**:
1. Get all positions
2. Calculate sell scores for each position
3. Filter and sort by score
4. Store top N recommendations in database
5. Return as `List[Recommendation]`

**Where it's used**:
- ✅ `app/api/recommendations.py::get_sell_recommendations()` - API endpoint

**Key difference from holistic planner**:
- Evaluates **individual sells**, not sequences
- Uses **sell-specific scoring** (windfall detection, rebalancing needs)
- Does NOT coordinate with buys

---

### System 3: Multi-Step Recommendations (Uses Holistic Planner)

**Location**: `app/application/services/rebalancing_service.py::get_multi_step_recommendations()`

**Status**: ✅ **ACTIVE** - **ONLY system that uses holistic planner**

**What it does**:
- Generates optimal **sequence** of actions (1-5 steps)
- Uses portfolio optimizer to calculate target weights
- Passes target weights to holistic planner
- Planner evaluates sequences and selects best end-state
- Returns as `List[MultiStepRecommendation]`

**Flow**:
1. Run portfolio optimizer (MV + HRP blend) → target weights
2. Build portfolio context
3. Call `create_holistic_plan()` with target weights
4. Planner identifies opportunities from weight gaps
5. Planner generates sequences at all depths (1-5)
6. Planner evaluates each sequence's end-state score
7. Returns optimal sequence

**Where it's used**:
- ✅ `app/api/multi_step_recommendations.py::get_multi_step_recommendations()` - API endpoint
- ✅ `app/jobs/sync_cycle.py::_get_holistic_recommendation()` - Gets first step
- ✅ `app/jobs/cash_rebalance.py::_get_next_holistic_action()` - Gets first step

**Key difference**:
- Evaluates **action sequences**, not individual trades
- Uses **end-state scoring** (how portfolio looks after ALL steps)
- Coordinates buys and sells together

---

## What Actually Runs

### In Production:

1. **Single Buy Recommendations** (`/api/trades/recommendations`)
   - Uses: `RebalancingService.get_recommendations()`
   - **Does NOT use holistic planner**
   - Used for: Individual buy decisions

2. **Single Sell Recommendations** (`/api/trades/recommendations/sell`)
   - Uses: `RebalancingService.calculate_sell_recommendations()`
   - **Does NOT use holistic planner**
   - Used for: Individual sell decisions

3. **Multi-Step Recommendations** (`/api/trades/multi-step-recommendations`)
   - Uses: `RebalancingService.get_multi_step_recommendations()`
   - **USES holistic planner** (`create_holistic_plan()`)
   - Used for: Strategic multi-step sequences

### In Background Jobs:

1. **`sync_cycle.py`** (Step 6: Get recommendation)
   - Calls: `_get_holistic_recommendation()`
   - Which calls: `RebalancingService.get_multi_step_recommendations()`
   - **USES holistic planner**
   - Gets first step from multi-step sequence

2. **`cash_rebalance.py`** (Step 3: Get recommendation)
   - Calls: `_get_next_holistic_action()`
   - Which calls: `RebalancingService.get_multi_step_recommendations()`
   - **USES holistic planner**
   - Gets first step from multi-step sequence

---

## Key Findings

### ✅ What's Unified

1. **Holistic Planner is the single planner implementation**
   - No competing planner implementations exist
   - All multi-step planning goes through `create_holistic_plan()`

2. **Opportunity identification is modular**
   - `app/domain/planning/opportunities/` contains helper functions
   - Used by holistic planner for opportunity detection
   - Clean separation of concerns

3. **Narrative generation is unified**
   - `app/domain/planning/narrative.py` generates all explanations
   - Used by holistic planner for step narratives

### ⚠️ What's NOT Unified

1. **Single buy/sell recommendations don't use holistic planner**
   - They use their own scoring systems
   - They evaluate individual trades, not sequences
   - This is intentional (different use cases)

2. **Three separate recommendation systems**
   - Buy recommendations: Individual trades
   - Sell recommendations: Individual trades
   - Multi-step recommendations: Sequences (uses holistic planner)

### 🔍 Legacy Code References

1. **Comment in `holistic_planner.py:4`**
   - Mentions "standard goal planner" that doesn't exist
   - Likely from refactoring where old planner was removed
   - Should be updated to remove reference

---

## Code Flow Diagrams

### Multi-Step Recommendations (Uses Holistic Planner)

```
API Request: GET /api/trades/multi-step-recommendations
    ↓
RebalancingService.get_multi_step_recommendations()
    ↓
PortfolioOptimizer.optimize() → target_weights
    ↓
create_holistic_plan(
    target_weights=target_weights,  # Optimizer-driven
    ...
)
    ↓
identify_opportunities_from_weights()  # Weight-based
    ↓
generate_action_sequences()  # All depths 1-5
    ↓
For each sequence:
    simulate_sequence() → end_context
    calculate_portfolio_end_state_score() → end_score
    ↓
Select sequence with best end_score
    ↓
Return List[MultiStepRecommendation]
```

### Single Buy Recommendations (Does NOT Use Holistic Planner)

```
API Request: GET /api/trades/recommendations
    ↓
RebalancingService.get_recommendations()
    ↓
Build portfolio context
    ↓
For each stock:
    calculate_post_transaction_score()  # Individual trade impact
    ↓
Sort by score improvement
    ↓
Store top N in database
    ↓
Return List[Recommendation]
```

### Single Sell Recommendations (Does NOT Use Holistic Planner)

```
API Request: GET /api/trades/recommendations/sell
    ↓
RebalancingService.calculate_sell_recommendations()
    ↓
For each position:
    calculate_all_sell_scores()  # Sell-specific scoring
    ↓
Sort by score
    ↓
Store top N in database
    ↓
Return List[Recommendation]
```

---

## Recommendations

### 1. **UNIFY EVERYTHING UNDER HOLISTIC PLANNER** ⚠️ **CRITICAL**

**The user is absolutely correct**: There is no conceptual difference between "planner" and "recommendations". The holistic planner already:
- Evaluates sequences of length 1-5
- Scores end-states (which is better than post-transaction scoring)
- Handles both buys and sells
- Can work with or without optimizer target weights

**Why the current separation exists (but shouldn't)**:
- `get_recommendations()` uses `calculate_post_transaction_score()` - simpler, faster, but less comprehensive
- `calculate_sell_recommendations()` uses sell-specific scoring - different logic
- `get_multi_step_recommendations()` uses holistic planner - more comprehensive end-state scoring

**The problem**:
- Post-transaction score only evaluates diversification impact
- End-state score evaluates: total return, promise, stability, diversification, opinion (weighted across entire portfolio)
- **End-state scoring is superior** - why use inferior scoring for single recommendations?

**The solution**:
1. **Remove `get_recommendations()` and `calculate_sell_recommendations()`**
2. **Use `get_multi_step_recommendations()` for everything**
3. **If optimal sequence is 1 step → single recommendation**
4. **If optimal sequence is 2-5 steps → multi-step recommendation**

**Benefits**:
- Single source of truth (holistic planner)
- Consistent scoring methodology
- Better recommendations (end-state scoring is more comprehensive)
- Simpler codebase (remove duplicate logic)
- No conceptual confusion

**Implementation**:
- `GET /api/trades/recommendations` → Call `get_multi_step_recommendations()`, return first step if sequence length = 1
- `GET /api/trades/recommendations/sell` → Same, filter for sells
- Keep `GET /api/trades/multi-step-recommendations` as-is (returns full sequence)

### 2. Update Documentation
- Remove reference to "standard goal planner" in `holistic_planner.py:4`
- Document that holistic planner is the single source of truth for ALL recommendations
- Remove documentation about "three recommendation systems"

### 3. Clean Up Dead Code
- Remove `calculate_post_transaction_score()` (or keep for backward compatibility during migration)
- Remove `get_recommendations()` implementation
- Remove `calculate_sell_recommendations()` implementation
- Remove sell-specific scoring if not needed by holistic planner

---

## File Inventory

### Planner Implementation
- ✅ `app/domain/planning/holistic_planner.py` - **ONLY planner implementation**
- ✅ `app/domain/planning/narrative.py` - Narrative generation
- ✅ `app/domain/planning/opportunities/` - Opportunity identification helpers

### Recommendation Systems
- ✅ `app/application/services/rebalancing_service.py::get_recommendations()` - Single buys
- ✅ `app/application/services/rebalancing_service.py::calculate_sell_recommendations()` - Single sells
- ✅ `app/application/services/rebalancing_service.py::get_multi_step_recommendations()` - Multi-step (uses planner)

### API Endpoints
- ✅ `app/api/recommendations.py` - Single buy/sell recommendations
- ✅ `app/api/multi_step_recommendations.py` - Multi-step recommendations

### Background Jobs
- ✅ `app/jobs/sync_cycle.py` - Uses holistic planner (multi-step)
- ✅ `app/jobs/cash_rebalance.py` - Uses holistic planner (multi-step)

---

## Conclusion

**There is ONE planner implementation (holistic planner) that is unified and working correctly.**

The confusion about "three competing implementations" likely refers to the **three recommendation systems** (single buy, single sell, multi-step), not three planners. The holistic planner is only used for multi-step recommendations, which is the correct architecture.

**What runs:**
- ✅ Holistic planner runs for multi-step recommendations
- ✅ Single buy/sell recommendations use their own scoring (intentional separation)

**Status: ✅ Unified and working as designed**
