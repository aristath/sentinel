# Multi-Bucket Portfolio System

## Overview

A multi-bucket portfolio management system with dynamic allocation:

- **Core Bucket (~70-85%)**: Long-term retirement-focused, conservative strategy
- **Satellite Buckets (~15-30% combined)**: Multiple satellites with different strategies, dynamically allocated based on performance

Each satellite operates in virtual isolation with its own universe, strategy, and cash tracking. A meta-allocator evaluates performance periodically and shifts funds toward winning strategies.

---

## Core Concepts

### Multi-Bucket Architecture

| Aspect | Core | Satellites |
|--------|------|------------|
| Allocation | 70-85% | 15-30% combined |
| Count | Always 1 | Multiple (user-defined) |
| Strategy | Long-term, conservative | Configurable per satellite |
| Hold duration | Months to years | Varies by strategy |
| Universe | Blue chips, stable | Assigned per satellite |
| Risk tolerance | Low | Configurable per satellite |

### Default State

**No satellites by default.** Users create satellites when ready to experiment.

### Global Satellite Budget

A single slider controls total allocation to all satellites combined:

```
[==========|--------------------] 15%
 Satellites          Core (85%)
```

- User adjusts as satellites are added/removed
- With 1 satellite: maybe 10%
- With 2 satellites: maybe 12-15%
- With conservative experiments: could go higher
- Core always gets the remainder

### Example Configurations

**Aggressive hunting:**
```
Satellite budget: 10%
    Satellite A: 10%  (US Tech Momentum)
Core: 90%
```

**Multiple experiments:**
```
Satellite budget: 18%
    Satellite A: 8%   (Momentum hunter)
    Satellite B: 5%   (Japan market test)
    Satellite C: 5%   (Dividend strategy experiment)
Core: 82%
```

### Satellites as Staging Ground

Satellites aren't just aggressive hunters. They can be:

- **Market experiments**: Test Japanese/emerging markets before committing to core
- **Strategy experiments**: Try dividend capture before adding to main strategy
- **Conservative tests**: Low-risk exploration of new territory
- **Research mode**: Gather data before permanent allocation

**Promotion path (ALWAYS MANUAL - never automatic):**
```
Satellite proves itself → User decides:
    1. Promote to core: Manually move securities to core universe, retire satellite
    2. Keep as satellite: Permanent allocation with proven track record
    3. Retire: Didn't work out, move cash back to core
```

**Important:** The system will NEVER automatically promote securities or satellites. Moving securities to core is a significant decision that affects the retirement fund - only the user can make that call.

Allocations within satellite budget are dynamic - adjusted quarterly based on performance.

### Universe Separation

Each security belongs to exactly one bucket. No overlap.

```sql
ALTER TABLE stocks ADD COLUMN bucket_id TEXT REFERENCES buckets(id) DEFAULT 'core';
```

Benefits:
- Clear position attribution
- No "which bucket owns this?" ambiguity
- Simple filtering: `WHERE bucket_id = 'satellite_a'`

---

## Database Schema

### Bucket Definitions

```sql
CREATE TABLE buckets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,                    -- 'core' or 'satellite'
    target_pct REAL,                       -- Current target allocation
    min_pct REAL,                          -- Hibernation threshold
    max_pct REAL,                          -- Maximum allowed
    strategy_config TEXT,                  -- JSON blob of slider values
    consecutive_losses INTEGER DEFAULT 0,
    max_consecutive_losses INTEGER DEFAULT 5,
    high_water_mark REAL DEFAULT 0,
    high_water_mark_date TEXT,
    loss_streak_paused_at TEXT,
    status TEXT DEFAULT 'active',          -- 'accumulating', 'active', 'hibernating', 'paused', 'retired'
    created_at TEXT NOT NULL
);
```

### Virtual Cash Tracking

```sql
CREATE TABLE bucket_balances (
    bucket_id TEXT NOT NULL,
    currency TEXT NOT NULL,
    balance REAL NOT NULL DEFAULT 0,
    last_updated TEXT NOT NULL,
    PRIMARY KEY (bucket_id, currency),
    FOREIGN KEY (bucket_id) REFERENCES buckets(id)
);
```

### Transaction Audit Trail

```sql
CREATE TABLE bucket_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bucket_id TEXT NOT NULL,
    type TEXT NOT NULL,                    -- 'deposit', 'reallocation', 'trade_buy', 'trade_sell', 'dividend'
    amount REAL NOT NULL,
    currency TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (bucket_id) REFERENCES buckets(id)
);
```

### Allocation Settings

```sql
CREATE TABLE allocation_settings (
    key TEXT PRIMARY KEY,
    value REAL NOT NULL,
    description TEXT
);

INSERT INTO allocation_settings VALUES
    ('satellite_budget_pct', 0.00, 'Total budget for all satellites combined (user adjustable)'),
    ('satellite_min_pct', 0.02, 'Minimum viable allocation for any single satellite'),
    ('satellite_max_pct', 0.15, 'Maximum any single satellite can reach'),
    ('evaluation_months', 3, 'Months between reallocation cycles'),
    ('reallocation_dampening', 0.5, 'Dampening factor for allocation changes');

-- Note: Core allocation = 1.0 - satellite_budget_pct
-- satellite_budget_pct starts at 0 (no satellites) and user increases as needed
```

### Critical Invariant

```
SUM(bucket_balances for currency X) == Actual brokerage balance for currency X
```

Always reconcile. Any drift indicates a bug.

---

## Meta-Allocator (Dynamic Allocation)

### Overview

The meta-allocator evaluates satellite performance periodically and adjusts allocations. Successful strategies get more capital; underperforming ones get less.

### Evaluation Cycle

- **Frequency**: Quarterly (every 3 months)
- **Metrics evaluated**: Risk-adjusted returns
- **Reallocation**: Gradual (dampened to prevent whiplash)

### Performance Metrics

| Metric | What it measures |
|--------|------------------|
| Sharpe ratio | Return per unit of total risk |
| Sortino ratio | Return per unit of downside risk |
| Max drawdown | Worst peak-to-trough decline |
| Win rate | Percentage of profitable trades |
| Profit factor | Gross profit / gross loss |

### Allocation Algorithm

```python
def calculate_new_allocations(satellites, evaluation_period_months=3):
    scores = {}
    for sat in satellites:
        returns = sat.get_returns(months=evaluation_period_months)
        scores[sat.id] = calculate_sharpe_ratio(returns)

    # Normalize scores to allocation percentages
    total_score = sum(max(s, 0) for s in scores.values())
    satellite_budget = 1.0 - CORE_MIN_PCT

    new_allocations = {}
    for sat_id, score in scores.items():
        if total_score > 0:
            new_allocations[sat_id] = (max(score, 0) / total_score) * satellite_budget
        else:
            # Equal split if all negative
            new_allocations[sat_id] = satellite_budget / len(satellites)

    return new_allocations
```

### Dampened Reallocation

```python
dampening = 0.5
new_allocation = current + (target - current) * dampening
```

Move only 50% toward target each cycle to prevent whiplash.

### Safety Rails

| Rule | Value | Rationale |
|------|-------|-----------|
| Satellite budget | User-controlled slider | User decides total satellite allocation |
| Single satellite max | 15% | No single satellite dominates |
| Single satellite min | 2% | Below this, can't trade effectively |
| Below minimum | Hibernation | Wait, don't kill |

Note: Core always gets `100% - satellite_budget`. The user controls the slider, so they decide the risk/experimentation level.

---

## Strategy Configuration (UI-Based)

### Philosophy

Users configure satellite "personality" via sliders and toggles - not technical parameters.

### Sliders

| Slider | Left | Right |
|--------|------|-------|
| Risk appetite | Conservative | Aggressive |
| Hold duration | Quick flips | Patient holds |
| Entry style | Buy dips | Buy breakouts |
| Position spread | Concentrated | Diversified |
| Profit taking | Let winners run | Take profits early |

### Toggles

- [ ] Use trailing stops
- [ ] Follow market regime
- [ ] Auto-harvest gains to core
- [ ] Pause during high volatility

### Behind the Scenes

Each slider maps to technical parameters:

```python
# "Risk appetite" slider at 70% maps to:
position_size_max = 0.15 + (0.25 * 0.7)  # 15-40% range
stop_loss_pct = 0.05 + (0.15 * 0.7)      # 5-20% range
```

User sees: "Risk appetite: Aggressive"
System sees: `position_size_max=0.325, stop_loss_pct=0.155`

### Strategy Presets

Starting points for new satellites:

- **"Momentum Hunter"** - aggressive, quick flips, buy breakouts
- **"Steady Eddy"** - conservative, patient, diversified
- **"Dip Buyer"** - moderate risk, buy dips, patient holds
- **"Dividend Catcher"** - buy before ex-div, sell after

User picks preset, then tweaks sliders to taste.

### Schema for Strategy Config

```sql
-- Stored as JSON in buckets.strategy_config
{
    "preset": "momentum_hunter",
    "sliders": {
        "risk_appetite": 0.7,
        "hold_duration": 0.3,
        "entry_style": 0.8,
        "position_spread": 0.4,
        "profit_taking": 0.6
    },
    "toggles": {
        "trailing_stops": true,
        "follow_regime": true,
        "auto_harvest": false,
        "pause_high_volatility": false
    }
}
```

---

## Satellite Lifecycle

### States

```
accumulating → active → hibernating → active (recovered)
                  ↓
               paused (manual)
                  ↓
               retired
```

### Creation

1. User creates new satellite via UI
2. Selects preset or configures from scratch
3. Assigns securities to its universe
4. Satellite starts in "accumulating" state
5. Funded from new deposits (equal split among satellites)
6. Once at minimum threshold (2%), becomes "active"

### New Satellite Onboarding

- Starts with 0% allocation
- Funded only from new deposits
- Gets a "probation period" (2 quarters)
- If passes evaluation: joins normal reallocation pool
- If fails: hibernates, waits for better conditions

### Retirement

When user retires a satellite:

1. User reassigns positions to other universes (via UI)
2. Cash transferred to core bucket
3. Satellite marked as "retired"
4. Historical data preserved for reporting

### Manual Overrides

| Action | Duration | Effect |
|--------|----------|--------|
| Boost | 1 week / 1 month | Increase aggression temporarily |
| Pause | Until resumed | Stop all trading, hold positions |
| Resume | Immediate | Return to normal operation |
| Transfer cash | Immediate | Move cash from one bucket to another |

### Manual Cash Transfers

Users can manually move cash between buckets at any time.

**Use cases:**
- Jumpstart a new satellite instead of waiting months
- React to news/events the app doesn't know about
- Rebalance faster than quarterly evaluation cycle
- Fund a satellite you believe in despite poor recent performance

**UI:**
- Select source bucket
- Select destination bucket
- Enter amount
- Confirm transfer

**Constraints:**
- Cannot transfer more than available cash in source bucket
- Core bucket cannot go below its minimum (70%)
- Transaction logged in audit trail

**Example:**
```
User sees: Satellite A has 1%, needs 2% to activate
User action: Transfer €500 from Core to Satellite A
Result: Satellite A now at 2.5%, becomes active immediately
```

---

## Dynamic Aggression System

### Percentage-Based Aggression

| Bucket % of Total | Aggression Level | Behavior |
|-------------------|------------------|----------|
| At target | Full | All opportunities, full position sizes |
| 80% of target | High | Slightly reduced sizes |
| 60% of target | Moderate | Only higher-conviction trades |
| 40% of target | Low | Minimal new positions |
| Below 40% | Hibernation | Hold only, no new trades |

### Drawdown-Based Aggression

Track high water mark (peak bucket value):

```
drawdown = (high_water_mark - current_value) / high_water_mark
```

| Drawdown from Peak | Effect |
|-------------------|--------|
| 0-15% | Full aggression allowed |
| 15-25% | Reduced position sizes |
| 25-35% | High-conviction only |
| 35%+ | Hibernation |

### Combined Aggression

```python
aggression = min(
    aggression_from_percentage(bucket_pct),
    aggression_from_drawdown(drawdown)
)
```

Both conditions must allow trading. Either can trigger hibernation.

---

## Safety Mechanisms

### Consecutive Losses Circuit Breaker

After 5 consecutive losing trades, pause trading.

**What counts as a loss:**
- Closed position where `sell_price < buy_price - threshold`
- Threshold accounts for fees/spreads (e.g., -1%)

**On pause:**
- Stop opening new positions
- Hold existing positions (don't panic sell)
- Log event for review

**Reset conditions:**
- Any winning trade resets counter to 0
- Held position recovers and closes at profit
- Time-based: 30 days allows one small "test" trade
- Manual override after review

### Win Cooldown

After exceptional performance (+20% in a month), temporarily reduce aggression.

Rationale:
- Prevents overconfidence
- Locks in gains
- Mean reversion: hot streaks often precede cold ones

### Trailing Stops

For satellite positions, implement trailing stops:

```
if position_gain > 15%:
    set trailing_stop at 10% below peak
```

Lets winners run while locking in minimum profit.

### Graduated Re-awakening

When exiting hibernation:

```
Hibernation → First trade: 25% normal size
            → Win? Second trade: 50% normal size
            → Win? Third trade: 75% normal size
            → Win? Resume normal sizing
```

Satellite must prove it can make money before getting full capital back.

---

## Startup Process

### Bootstrap (Simple Approach)

1. All satellites start at 0%
2. New deposits split equally among all buckets below target
3. Satellites accumulate cash passively
4. Once at minimum threshold (2%), satellite becomes active
5. No complex logic - cash sitting idle is acceptable

### Timeline Example

```
Month 1: Deposit €1000
    Core (below 70%): gets €700
    Satellite A: gets €100
    Satellite B: gets €100
    Satellite C: gets €100

Month 2-6: Continue accumulating

Month 7: Satellite A reaches 2%, becomes active
Month 8: Satellite B reaches 2%, becomes active
Month 9: Satellite C reaches 2%, becomes active
```

---

## Reconciliation

### Continuous Checks

On every operation:
```python
assert sum(bucket_balances[currency]) == actual_brokerage_balance[currency]
```

### Periodic Full Reconciliation

Daily job to:
1. Fetch actual balances from brokerage
2. Calculate expected balances from bucket_balances
3. If mismatch:
   - Log discrepancy
   - Auto-correct small drifts (< €1)
   - Alert for large drifts

---

## UI Considerations

### Unified View with Visual Distinction

- Single stock list with badge/color per bucket
- Single recommendations list, tagged by bucket
- Dashboard shows combined + per-bucket breakdown
- Filter toggle to focus on one bucket

### Satellite Management Panel

- List of all satellites with status indicators
- Create new satellite wizard
- Retire satellite with position reassignment
- Slider/toggle configuration per satellite
- Manual override buttons (boost/pause)

### Bucket Health Display

Show per satellite:
- Current allocation %
- Target allocation %
- Drawdown from peak
- Aggression level
- Consecutive losses count
- Status (Accumulating / Active / Hibernating / Paused)

---

## Implementation Phases

### Phase 1: Foundation
- Add `bucket_id` column to stocks
- Create bucket tables
- Implement virtual cash tracking
- Reconciliation system

### Phase 2: Multi-Bucket Basics
- Deposit splitting logic
- Per-bucket transaction tracking
- Basic UI for bucket management

### Phase 3: Strategy Configuration
- Slider/toggle UI components
- Strategy preset definitions
- Parameter mapping from sliders

### Phase 4: Satellite Planners
- Parameterized planner by strategy config
- Per-satellite recommendation generation
- Aggression-based position sizing

### Phase 5: Meta-Allocator
- Performance metric calculation
- Quarterly evaluation job
- Dampened reallocation logic

### Phase 6: Safety Systems
- Drawdown tracking
- Consecutive loss tracking
- Graduated re-awakening
- Win cooldown

### Phase 7: Lifecycle Management
- Satellite creation wizard
- Retirement flow with position reassignment
- Manual override controls

---

## Open Questions

1. **Initial satellites**: What satellites to offer by default? Or start with just core?

2. **Preset refinement**: What exact slider values for each preset?

3. **Evaluation weighting**: How to weight recent vs long-term performance?

4. **Cold start**: How to allocate to satellites with no track record?

5. **Reporting depth**: What reports/charts to show per-satellite performance?

---

## Risks

1. **Complexity**: Significantly more code = more potential bugs

2. **Strategy risk**: User-configured strategies might perform poorly

3. **Over-optimization**: Users might tweak sliders too frequently

4. **Correlation risk**: Multiple satellites might move together in market stress

---

## Success Metrics

- Satellites contribute positive risk-adjusted returns over 12-month periods
- Meta-allocator successfully shifts to winning strategies
- System correctly hibernates underperforming satellites
- Virtual cash always reconciles with actual brokerage balance
- Users can create/configure satellites without confusion
