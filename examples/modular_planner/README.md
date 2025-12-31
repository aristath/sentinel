# Modular Planner Examples

This directory contains examples demonstrating how to use the modular planner system.

## Examples

### 1. `basic_usage.py`

Demonstrates the fundamental workflow:
- Loading configuration from TOML files
- Instantiating planner factories
- Accessing enabled modules
- Retrieving module parameters
- Multi-bucket configuration

**Run:**
```bash
python examples/modular_planner/basic_usage.py
```

**Output:**
- Shows all enabled modules from default.toml
- Compares conservative vs aggressive configurations
- Explains the planning workflow

### 2. `custom_config.py`

Shows how to create configurations programmatically:
- Creating PlannerConfiguration objects in code
- Custom module enabling/disabling
- Specialized configurations (minimal, rebalancing-focused)
- No TOML files required

**Run:**
```bash
python examples/modular_planner/custom_config.py
```

**Output:**
- Creates minimal and rebalancing configurations
- Shows enabled modules for each
- Demonstrates programmatic config creation

## Integration with Existing Code

The modular planner is designed to coexist with the current monolithic planner. Here's how to integrate:

### Current Architecture (Monolithic)

```python
# In holistic_planner.py
async def create_holistic_plan(...):
    # 3,822 lines of monolithic code
    opportunities = identify_opportunities(...)
    sequences = generate_action_sequences(...)
    best_sequence = select_best_sequence(...)
    return best_sequence
```

### New Architecture (Modular)

```python
from pathlib import Path
from app.modules.planning.domain.config.factory import create_planner_from_config

# Load bucket-specific configuration
factory = create_planner_from_config(Path(f"config/planner/{bucket_name}.toml"))

# Get enabled modules
calculators = factory.get_calculators()
patterns = factory.get_patterns()
generators = factory.get_generators()
filters = factory.get_filters()

# Use modules in planning workflow
opportunities = {}
for calc in calculators:
    params = factory.get_calculator_params(calc.name)
    opps = await calc.calculate(context, params)
    opportunities[calc.name] = opps

sequences = []
for pattern in patterns:
    params = factory.get_pattern_params(pattern.name)
    seqs = pattern.generate(opportunities, params)
    sequences.extend(seqs)

# Filter sequences
for filt in filters:
    params = factory.get_filter_params(filt.name)
    sequences = await filt.filter(sequences, params)

# Evaluate and select best
best_sequence = evaluate_sequences(sequences)
```

## Configuration Files

Example configurations are in `config/planner/`:

- **default.toml** - All features enabled (standard)
- **conservative.toml** - Minimal intervention (1-2 actions max)
- **aggressive.toml** - Active trading (up to 7 actions)

Create custom configs for each bucket:

```toml
# config/planner/stable_bucket.toml
[planner]
name = "stable_bucket"
description = "Conservative strategy for stable income bucket"
max_depth = 2
priority_threshold = 0.6

[opportunity_calculators.profit_taking]
enabled = true
[opportunity_calculators.profit_taking.params]
windfall_threshold = 0.40  # Higher threshold

[pattern_generators.single_best]
enabled = true  # Only take single best action
```

## Multi-Bucket Example

```python
# Load different configs for each bucket
stable_planner = create_planner_from_config(Path("config/planner/stable_bucket.toml"))
growth_planner = create_planner_from_config(Path("config/planner/growth_bucket.toml"))
speculative_planner = create_planner_from_config(Path("config/planner/speculative_bucket.toml"))

# Each has different strategies
assert stable_planner.config.max_depth == 2      # Conservative
assert growth_planner.config.max_depth == 5      # Moderate
assert speculative_planner.config.max_depth == 7  # Aggressive

# Execute planning for each bucket independently
stable_plan = await run_planner(stable_planner, stable_portfolio)
growth_plan = await run_planner(growth_planner, growth_portfolio)
speculative_plan = await run_planner(speculative_planner, speculative_portfolio)
```

## Testing

All modules are independently testable:

```python
# Test a single calculator
from app.modules.planning.domain.calculations.opportunities.profit_taking import (
    ProfitTakingCalculator
)

calc = ProfitTakingCalculator()
params = {"windfall_threshold": 0.50, "priority_weight": 1.5}
opportunities = await calc.calculate(context, params)
```

## Documentation

See `app/modules/planning/domain/MODULAR_PLANNER.md` for complete documentation.
