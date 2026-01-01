# Modular Planner Usage Guide

## Quick Start

### For Core Bucket (Immediate Use)

The modular planner can be used as a drop-in replacement:

```python
# Option 1: Use the adapter (recommended for gradual migration)
from app.modules.planning.domain.planner_adapter import (
    create_holistic_plan_modular as create_holistic_plan
)

plan = await create_holistic_plan(
    portfolio_context=portfolio_context,
    available_cash=available_cash,
    securities=securities,
    positions=positions,
    max_plan_depth=5,
    max_opportunities_per_category=5,
)
```

```python
# Option 2: Use the planner class directly
from app.modules.planning.domain.config.models import PlannerConfiguration
from app.modules.planning.domain.planner import HolisticPlanner

config = PlannerConfiguration(
    name="my_config",
    max_depth=5,
    max_opportunities_per_category=5,
    priority_threshold=0.3,
)

planner = HolisticPlanner(config=config)
plan = await planner.create_plan(
    portfolio_context=portfolio_context,
    positions=positions,
    securities=securities,
    available_cash=available_cash,
)
```

### For Satellite Buckets (Automatic)

The planner batch job automatically uses the factory service for satellites:

```python
# In planner_batch.py or your satellite planning code
from app.modules.planning.jobs.planner_batch import process_planner_batch_job

# For a satellite bucket
await process_planner_batch_job(
    max_depth=0,
    portfolio_hash=None,
    bucket_id="satellite_momentum_1",  # Automatically uses factory service
)

# For core bucket (default)
await process_planner_batch_job()  # Uses existing implementation
```

The system will:
1. Load SatelliteSettings for the bucket
2. Convert slider values to PlannerConfiguration
3. Create a bucket-specific planner
4. Run incremental planning with bucket's configuration

## Configuration

### Using TOML Files

Create configuration files in `config/planner/`:

```toml
# config/planner/aggressive.toml
name = "aggressive"
description = "Aggressive trading strategy"

max_depth = 7
max_opportunities_per_category = 8
priority_threshold = 0.2
enable_diverse_selection = true
diversity_weight = 0.2

transaction_cost_fixed = 2.0
transaction_cost_percent = 0.002

[opportunity_calculators.profit_taking]
enabled = true

[opportunity_calculators.averaging_down]
enabled = true

[pattern_generators.adaptive]
enabled = true
```

Load it:

```python
from pathlib import Path
from app.modules.planning.domain.config.factory import ModularPlannerFactory

factory = ModularPlannerFactory.from_config_file(
    Path("config/planner/aggressive.toml")
)
planner = HolisticPlanner(
    config=factory.config,
    settings_repo=settings_repo,
    trade_repo=trade_repo,
)
```

### Using Satellite Settings

For satellite buckets, settings are converted automatically:

```python
from app.modules.satellites.domain.models import SatelliteSettings
from app.modules.planning.services.planner_factory import PlannerFactoryService

# Create satellite settings
settings = SatelliteSettings(
    satellite_id="momentum_1",
    preset="aggressive",  # Optional preset
    risk_appetite=0.8,    # 0.0 = conservative, 1.0 = aggressive
    hold_duration=0.3,    # 0.0 = quick flips, 1.0 = patient holds
    entry_style=0.6,      # 0.0 = buy dips, 1.0 = buy breakouts
    position_spread=0.4,  # 0.0 = concentrated, 1.0 = diversified
    profit_taking=0.7,    # 0.0 = let run, 1.0 = take profits early
)

# Create planner
factory = PlannerFactoryService()
planner = factory.create_for_satellite_bucket("momentum_1", settings)
```

### Programmatic Configuration

Create configurations in code:

```python
from app.modules.planning.domain.config.models import (
    PlannerConfiguration,
    ModuleConfig,
    OpportunityCalculatorsConfig,
)

# Enable specific calculators
calc_config = OpportunityCalculatorsConfig(
    profit_taking=ModuleConfig(enabled=True),
    averaging_down=ModuleConfig(enabled=True),
    opportunity_buys=ModuleConfig(enabled=True),
)

config = PlannerConfiguration(
    name="custom",
    max_depth=6,
    max_opportunities_per_category=7,
    opportunity_calculators=calc_config,
)

planner = HolisticPlanner(config=config)
```

## Advanced Features

### Incremental Processing

For large portfolios, use incremental batch processing:

```python
planner = HolisticPlanner(config=config)

# Process in batches
plan = await planner.create_plan_incremental(
    portfolio_context=portfolio_context,
    positions=positions,
    securities=securities,
    available_cash=available_cash,
    batch_size=100,  # Process 100 sequences per batch
)

# Call again to process next batch
# Progress is stored in database
plan = await planner.create_plan_incremental(
    portfolio_context=portfolio_context,
    positions=positions,
    securities=securities,
    available_cash=available_cash,
    batch_size=100,
)
```

### Using the Factory Service

The factory service provides convenient bucket-based creation:

```python
from app.modules.planning.services.planner_factory import PlannerFactoryService

factory = PlannerFactoryService()

# For core bucket
core_planner = factory.create_for_core_bucket()

# For satellite bucket
satellite_planner = factory.create_for_satellite_bucket(
    satellite_id="momentum_1",
    satellite_settings=settings,
)

# Generic creation by bucket ID
planner = factory.create_for_bucket(
    bucket_id="core",  # or satellite ID
    satellite_settings=None,  # Only needed for satellites
)
```

## Module Customization

### Available Modules

**Opportunity Calculators** (6):
- `profit_taking` - Identify windfall gains
- `averaging_down` - Find quality dips
- `opportunity_buys` - High-quality buy opportunities
- `rebalance_sells` - Overweight positions to trim
- `rebalance_buys` - Underweight areas to increase
- `weight_based` - Uses optimizer target weights

**Pattern Generators** (13):
- `direct_buy` - Simple buy with available cash
- `profit_taking` - Sell windfalls, reinvest proceeds
- `rebalance` - Sell overweight, buy underweight
- `averaging_down` - Buy quality dips only
- `single_best` - Single highest-priority action
- `multi_sell` - Multiple sells, no buys
- `mixed_strategy` - 1-2 sells + 1-2 buys
- `opportunity_first` - Prioritize opportunity buys
- `deep_rebalance` - Multiple rebalancing actions
- `cash_generation` - Focus on generating cash
- `cost_optimized` - Minimize transaction costs
- `adaptive` - 9 adaptive pattern variants
- `market_regime` - Bull/bear/sideways strategies

**Sequence Generators** (4):
- `combinatorial` - Basic combinations
- `enhanced_combinatorial` - Diversity-aware combinations
- `partial_execution` - Partial fill scenarios
- `constraint_relaxation` - "What if" scenarios

**Filters** (4):
- `correlation_aware` - Remove correlated sequences
- `diversity` - Balance priority with diversity
- `eligibility` - Enforce trading rules
- `recently_traded` - Prevent over-trading

### Enabling/Disabling Modules

In TOML:
```toml
[opportunity_calculators.profit_taking]
enabled = true

[pattern_generators.adaptive]
enabled = false
```

In code:
```python
config.opportunity_calculators.profit_taking.enabled = True
config.pattern_generators.adaptive.enabled = False
```

## Migration from Monolithic Planner

### Step 1: Test with Adapter

```python
# Before:
from app.modules.planning.domain.holistic_planner import create_holistic_plan

# After:
from app.modules.planning.domain.planner_adapter import (
    create_holistic_plan_modular as create_holistic_plan
)

# No other changes needed - same API
```

### Step 2: Validate Output

Run both planners in parallel and compare:

```python
# Original
plan_original = await create_holistic_plan_original(...)

# Modular
plan_modular = await create_holistic_plan_modular(...)

# Compare
assert plan_original.end_state_score == plan_modular.end_state_score
assert len(plan_original.steps) == len(plan_modular.steps)
```

### Step 3: Switch to Modular

Once validated, replace all imports:

```bash
# Find all usages
grep -r "from app.modules.planning.domain.holistic_planner import create_holistic_plan"

# Update imports
# Replace with modular version
```

## Troubleshooting

### Configuration Validation Errors

```python
from app.modules.planning.domain.config.validator import ConfigurationValidator

errors = ConfigurationValidator.validate(config)
if errors:
    for error in errors:
        print(f"Configuration error: {error}")
```

### Module Not Found

Check if module is registered:

```python
from app.modules.planning.domain.calculations.opportunities.base import (
    opportunity_calculator_registry
)

calculator = opportunity_calculator_registry.get("profit_taking")
if calculator is None:
    print("Calculator not registered")
```

### Performance Issues

Enable logging to see which modules are taking time:

```python
import logging
logging.getLogger("app.modules.planning").setLevel(logging.DEBUG)
```

## Best Practices

1. **Use presets for satellites** - Create TOML presets for common strategies
2. **Validate configurations** - Always validate before deployment
3. **Start with adapter** - Use backward-compatible adapter first
4. **Monitor performance** - Track execution time in production
5. **Incremental for large portfolios** - Use batch processing for >100 securities
6. **Test configurations** - Validate new configs in development first

## Examples

See `examples/modular_planner/` for:
- Basic usage example
- Custom configuration example
- Satellite integration example
- Performance comparison example
