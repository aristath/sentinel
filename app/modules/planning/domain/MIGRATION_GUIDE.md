# Migration Guide: Monolithic → Modular Planner

This guide provides a step-by-step approach to migrating from the monolithic `holistic_planner.py` to the modular planner system.

## Migration Strategy

We use a **gradual migration** approach with an adapter pattern, allowing both systems to coexist during the transition.

### Phase 1: Parallel Operation (Current)

```
┌─────────────────────────────────────┐
│   Existing Holistic Planner         │
│   (holistic_planner.py - 3,822 lines)│
└─────────────────────────────────────┘
              ↓
         [Production]

┌─────────────────────────────────────┐
│   Modular Planner System            │
│   (42 modules, 4,900 lines)         │
└─────────────────────────────────────┘
              ↓
    [Testing/Validation]
```

### Phase 2: Gradual Integration (Next)

```
┌─────────────────────────────────────┐
│   Holistic Planner (Hybrid)         │
│   ┌──────────────────────────────┐  │
│   │ Monolithic Code (decreasing) │  │
│   └──────────────────────────────┘  │
│   ┌──────────────────────────────┐  │
│   │ ModularPlannerAdapter        │  │
│   │ (uses modular system)        │  │
│   └──────────────────────────────┘  │
└─────────────────────────────────────┘
```

### Phase 3: Complete Migration (Future)

```
┌─────────────────────────────────────┐
│   Modular Planner                   │
│   (Pure modular architecture)       │
└─────────────────────────────────────┘
```

## Step-by-Step Migration

### Step 1: Use Adapter in Existing Code

The `ModularPlannerAdapter` provides the same interface as the monolithic functions.

**Before (Monolithic):**
```python
# In holistic_planner.py
def identify_opportunities(...):
    # 300 lines of hardcoded logic
    profit_taking_candidates = []
    averaging_down_candidates = []
    rebalance_sells = []
    # ... more hardcoded calculators
    return {
        "profit_taking": profit_taking_candidates,
        "averaging_down": averaging_down_candidates,
        # ...
    }
```

**After (Modular via Adapter):**
```python
# In holistic_planner.py
from app.modules.planning.domain.modular_adapter import ModularPlannerAdapter

# Load configuration once at module level or in function
adapter = ModularPlannerAdapter.from_config_file(
    Path("config/planner/default.toml")
)

async def identify_opportunities(...):
    # All calculator logic is now in separate modules
    opportunities = await adapter.calculate_opportunities(
        positions=positions,
        securities=securities,
        stocks_by_symbol=stocks_by_symbol,
        available_cash_eur=available_cash,
        total_portfolio_value_eur=total_value,
        security_scores=security_scores,
    )
    return opportunities
```

### Step 2: Replace Pattern Generation

**Before (Monolithic):**
```python
def _generate_patterns_at_depth(...):
    sequences = []

    # Hardcoded pattern 1
    pattern1 = _generate_direct_buy_pattern(...)
    if pattern1:
        sequences.append(pattern1)

    # Hardcoded pattern 2
    pattern2 = _generate_profit_taking_pattern(...)
    if pattern2:
        sequences.append(pattern2)

    # ... 11 more hardcoded patterns
    return sequences
```

**After (Modular via Adapter):**
```python
def _generate_patterns_at_depth(...):
    # All patterns loaded from config
    sequences = adapter.generate_patterns(
        opportunities=opportunities,
        available_cash=available_cash,
        max_depth=max_depth,
    )
    return sequences
```

### Step 3: Replace Combinatorial Generation

**Before (Monolithic):**
```python
if enable_combinatorial:
    # 150 lines of complex combinatorial logic
    combo_sequences = _generate_enhanced_combinations(...)
    sequences.extend(combo_sequences)
```

**After (Modular via Adapter):**
```python
if enable_combinatorial:
    # Generator enabled in config
    combo_sequences = adapter.generate_combinatorial_sequences(
        opportunities=all_opportunities,
        available_cash=available_cash,
        max_depth=max_depth,
    )
    sequences.extend(combo_sequences)
```

### Step 4: Replace Filtering

**Before (Monolithic):**
```python
# Hardcoded correlation filtering
filtered = await _filter_correlation_aware_sequences(
    sequences, securities, max_steps
)
```

**After (Modular via Adapter):**
```python
# Filter enabled in config
filtered = await adapter.filter_sequences(sequences, securities)
```

## Complete Example: Refactored create_holistic_plan()

### Before (Monolithic)

```python
async def create_holistic_plan(
    positions: List[Position],
    securities: List[Security],
    # ... many parameters
) -> Optional[HolisticPlan]:
    # 500+ lines of monolithic code
    opportunities = identify_opportunities(...)  # 300 lines
    sequences = generate_action_sequences(...)   # 200 lines
    filtered = await _filter_sequences(...)      # 100 lines
    best = select_best_sequence(...)             # 100 lines
    return best
```

### After (Modular with Adapter)

```python
async def create_holistic_plan(
    positions: List[Position],
    securities: List[Security],
    # ... many parameters
    planner_config_path: Path = Path("config/planner/default.toml"),
) -> Optional[HolisticPlan]:
    # Load modular planner
    adapter = ModularPlannerAdapter.from_config_file(planner_config_path)

    # Log configuration being used
    config_summary = adapter.get_configuration_summary()
    logger.info(f"Using planner config: {config_summary['name']}")
    logger.info(f"Enabled modules: {config_summary['total_modules']}")

    # Step 1: Calculate opportunities (replaces identify_opportunities)
    opportunities = await adapter.calculate_opportunities(
        positions=positions,
        securities=securities,
        stocks_by_symbol=stocks_by_symbol,
        available_cash_eur=available_cash,
        total_portfolio_value_eur=total_value,
        country_allocations=country_allocations,
        country_to_group=country_to_group,
        country_weights=country_weights,
        target_weights=target_weights,
        security_scores=security_scores,
    )

    # Step 2: Generate sequences (replaces generate_action_sequences)
    sequences = []
    for depth in range(1, adapter.config.max_depth + 1):
        depth_sequences = adapter.generate_patterns(
            opportunities=opportunities,
            available_cash=available_cash,
            max_depth=depth,
        )
        sequences.extend(depth_sequences)

    # Optional: Combinatorial generation (if enabled in config)
    if adapter.config.get_enabled_generators():
        all_opportunities = []
        for opps in opportunities.values():
            all_opportunities.extend(opps)

        combo_sequences = adapter.generate_combinatorial_sequences(
            opportunities=all_opportunities,
            available_cash=available_cash,
            max_depth=adapter.config.max_depth,
        )
        sequences.extend(combo_sequences)

    # Step 3: Filter sequences (replaces _filter_sequences)
    if adapter.config.get_enabled_filters():
        sequences = await adapter.filter_sequences(sequences, securities)

    # Step 4: Evaluate and select (keep existing logic)
    best_sequence = select_best_sequence(sequences, ...)

    return best_sequence
```

## Multi-Bucket Integration

The modular system enables per-bucket configurations:

```python
# In the main planning service
class PlanningService:
    def __init__(self):
        # Load different configs for each bucket
        self.stable_planner = ModularPlannerAdapter.from_config_file(
            Path("config/planner/stable_bucket.toml")
        )
        self.growth_planner = ModularPlannerAdapter.from_config_file(
            Path("config/planner/growth_bucket.toml")
        )
        self.speculative_planner = ModularPlannerAdapter.from_config_file(
            Path("config/planner/speculative_bucket.toml")
        )

    async def create_plan_for_bucket(
        self, bucket_type: str, positions: List[Position], ...
    ) -> Optional[HolisticPlan]:
        # Select adapter based on bucket
        if bucket_type == "stable":
            adapter = self.stable_planner
        elif bucket_type == "growth":
            adapter = self.growth_planner
        else:
            adapter = self.speculative_planner

        # Use adapter for planning
        opportunities = await adapter.calculate_opportunities(...)
        sequences = adapter.generate_patterns(...)
        # ... rest of planning logic

        return plan
```

## Configuration Per Bucket

### Stable Bucket (Conservative)

```toml
# config/planner/stable_bucket.toml
[planner]
name = "stable_bucket"
description = "Conservative strategy for stable income"
max_depth = 2
priority_threshold = 0.6

[pattern_generators.single_best]
enabled = true  # Only single best action

[pattern_generators.direct_buy]
enabled = true
[pattern_generators.direct_buy.params]
max_depth = 2
```

### Growth Bucket (Balanced)

```toml
# config/planner/growth_bucket.toml
[planner]
name = "growth_bucket"
description = "Balanced growth strategy"
max_depth = 5
priority_threshold = 0.3

# More patterns enabled
[pattern_generators.profit_taking]
enabled = true

[pattern_generators.rebalance]
enabled = true
```

### Speculative Bucket (Aggressive)

```toml
# config/planner/speculative_bucket.toml
[planner]
name = "speculative_bucket"
description = "Aggressive trading strategy"
max_depth = 7
priority_threshold = 0.2

# All patterns enabled
[sequence_generators.enhanced_combinatorial]
enabled = true
[sequence_generators.enhanced_combinatorial.params]
max_combinations = 100
```

## Testing Strategy

### 1. Unit Tests (Already Complete)

49 tests covering configuration system ✅

### 2. Integration Tests (Next)

```python
# tests/integration/planning/test_modular_adapter.py
async def test_adapter_with_real_portfolio():
    """Test adapter with real portfolio data."""
    adapter = ModularPlannerAdapter.from_config_file(
        Path("config/planner/default.toml")
    )

    # Load test portfolio
    positions, securities = load_test_portfolio()

    # Test opportunity calculation
    opportunities = await adapter.calculate_opportunities(
        positions=positions,
        securities=securities,
        ...
    )

    assert "profit_taking" in opportunities
    assert len(opportunities["profit_taking"]) >= 0

    # Test pattern generation
    sequences = adapter.generate_patterns(
        opportunities=opportunities,
        available_cash=1000.0,
        max_depth=5,
    )

    assert len(sequences) >= 0
```

### 3. Comparison Tests

```python
async def test_modular_matches_monolithic():
    """Verify modular system produces same results as monolithic."""
    # Run monolithic planner
    monolithic_result = await create_holistic_plan_monolithic(...)

    # Run modular planner
    adapter = ModularPlannerAdapter.from_config_file(...)
    modular_result = await create_holistic_plan_modular(adapter, ...)

    # Compare results
    assert len(modular_result.opportunities) == len(monolithic_result.opportunities)
    # ... more assertions
```

## Rollout Plan

### Week 1-2: Testing & Validation
- [ ] Run modular system in parallel (no production impact)
- [ ] Compare outputs with monolithic system
- [ ] Validate all 22 modules work correctly
- [ ] Performance testing

### Week 3-4: Gradual Rollout
- [ ] Deploy to one bucket (e.g., stable bucket)
- [ ] Monitor for 1 week
- [ ] If successful, deploy to growth bucket
- [ ] Monitor for 1 week

### Week 5-6: Complete Migration
- [ ] Deploy to all buckets
- [ ] Remove monolithic code paths
- [ ] Update documentation
- [ ] Archive old code

## Rollback Plan

If issues are encountered:

1. **Immediate:** Switch config back to monolithic
2. **Short-term:** Fix module issues, redeploy
3. **Long-term:** Improve testing, add safeguards

The adapter pattern allows instant rollback by simply not using it.

## Benefits Realized

After migration:

✅ **Per-Bucket Configuration** - Each bucket has optimal strategy
✅ **Easier Testing** - Each module tested independently
✅ **Faster Iteration** - Change config without code changes
✅ **Better Maintainability** - 22 focused modules vs 1 monolith
✅ **Type Safety** - Full mypy compliance
✅ **Cleaner Architecture** - Proper separation of concerns

## Support

- **Documentation:** `app/modules/planning/domain/MODULAR_PLANNER.md`
- **Examples:** `examples/modular_planner/`
- **Tests:** `tests/unit/planning/domain/config/`
- **Configuration:** `config/planner/*.toml`
