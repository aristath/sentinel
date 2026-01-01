# Modular Planner Architecture

## Overview

The modular planner system provides a flexible, registry-based architecture for portfolio planning. Each bucket can have its own planner instance with different enabled modules and parameters configured via TOML files.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     TOML Configuration                          │
│          (default.toml, conservative.toml, etc.)                │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  PlannerConfiguration                           │
│         (Dataclass with all module configs)                     │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                 ModularPlannerFactory                           │
│        (Instantiates modules from registries)                   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Module Registries                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ OpportunityCalculator Registry                           │  │
│  │  - profit_taking, averaging_down, opportunity_buys, ...  │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ PatternGenerator Registry                                │  │
│  │  - direct_buy, rebalance, single_best, adaptive, ...     │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ SequenceGenerator Registry                               │  │
│  │  - combinatorial, enhanced_combinatorial                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ SequenceFilter Registry                                  │  │
│  │  - correlation_aware                                     │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Module Types

### 1. Opportunity Calculators (`calculations/opportunities/`)

Calculate different types of trading opportunities from portfolio state.

**Available:**
- `profit_taking` - Detect windfall gains (>30% profit)
- `averaging_down` - Identify quality dips worth buying
- `opportunity_buys` - High-quality buying opportunities
- `rebalance_sells` - Trim overweight positions
- `rebalance_buys` - Increase underweight areas
- `weight_based` - Optimizer-driven rebalancing

**Interface:**
```python
class OpportunityCalculator(ABC):
    @property
    def name(self) -> str: ...

    def default_params(self) -> Dict[str, Any]: ...

    async def calculate(
        self, context: OpportunityContext, params: Dict[str, Any]
    ) -> List[ActionCandidate]: ...
```

### 2. Pattern Generators (`calculations/patterns/`)

Generate action sequences from opportunities using different strategies.

**Available:**
- **Basic:** `direct_buy`, `profit_taking`, `rebalance`, `averaging_down`, `single_best`
- **Advanced:** `multi_sell`, `mixed_strategy`, `opportunity_first`, `deep_rebalance`
- **Strategic:** `cash_generation`, `cost_optimized`
- **Complex:** `adaptive`, `market_regime`

**Interface:**
```python
class PatternGenerator(ABC):
    @property
    def name(self) -> str: ...

    def default_params(self) -> Dict[str, Any]: ...

    def generate(
        self,
        opportunities: Dict[str, List[ActionCandidate]],
        params: Dict[str, Any],
    ) -> List[List[ActionCandidate]]: ...
```

### 3. Sequence Generators (`calculations/sequences/`)

Combine opportunities into sequences using combinatorial strategies.

**Available:**
- `combinatorial` - All valid combinations (expensive)
- `enhanced_combinatorial` - Weighted sampling with diversity constraints

**Interface:**
```python
class SequenceGenerator(ABC):
    @property
    def name(self) -> str: ...

    def default_params(self) -> Dict[str, Any]: ...

    def generate(
        self,
        opportunities: List[ActionCandidate],
        params: Dict[str, Any],
    ) -> List[List[ActionCandidate]]: ...
```

### 4. Sequence Filters (`calculations/filters/`)

Filter and refine generated sequences based on criteria.

**Available:**
- `correlation_aware` - Remove highly correlated positions (>0.7 correlation)

**Interface:**
```python
class SequenceFilter(ABC):
    @property
    def name(self) -> str: ...

    def default_params(self) -> Dict[str, Any]: ...

    async def filter(
        self,
        sequences: List[List[ActionCandidate]],
        params: Dict[str, Any],
    ) -> List[List[ActionCandidate]]: ...
```

## Usage

### 1. Basic Usage

```python
from pathlib import Path
from app.modules.planning.domain.config.factory import create_planner_from_config

# Load configuration and instantiate modules
factory = create_planner_from_config(Path("config/planner/default.toml"))

# Get enabled modules
calculators = factory.get_calculators()
patterns = factory.get_patterns()
generators = factory.get_generators()
filters = factory.get_filters()

# Get module parameters
profit_taking_params = factory.get_calculator_params("profit_taking")
# {'windfall_threshold': 0.30, 'priority_weight': 1.2}
```

### 2. Multi-Bucket Configuration

```python
# Each bucket gets its own planner
growth_bucket = create_planner_from_config(Path("config/planner/aggressive.toml"))
stable_bucket = create_planner_from_config(Path("config/planner/conservative.toml"))

# Different modules enabled for each
assert len(growth_bucket.get_patterns()) > len(stable_bucket.get_patterns())
```

### 3. Custom Configuration

```python
from app.modules.planning.domain.config.parser import load_planner_config_from_string

config_toml = """
[planner]
name = "custom"
max_depth = 3

[opportunity_calculators.profit_taking]
enabled = true
[opportunity_calculators.profit_taking.params]
windfall_threshold = 0.50

[pattern_generators.single_best]
enabled = true
"""

config = load_planner_config_from_string(config_toml)
factory = ModularPlannerFactory.from_config(config)
```

## Configuration Files

### Location

Configuration files are stored in `config/planner/`:
- `default.toml` - All features enabled
- `conservative.toml` - Minimal intervention (1-2 actions)
- `aggressive.toml` - Active trading (up to 7 actions)

### Structure

```toml
[planner]
name = "my_strategy"
description = "Custom strategy"
max_depth = 5
priority_threshold = 0.3

[opportunity_calculators.profit_taking]
enabled = true
[opportunity_calculators.profit_taking.params]
windfall_threshold = 0.30
priority_weight = 1.2

[pattern_generators.single_best]
enabled = true
[pattern_generators.single_best.params]
max_depth = 1

[filters.correlation_aware]
enabled = true
[filters.correlation_aware.params]
correlation_threshold = 0.7
```

## Adding New Modules

### 1. Create Module Class

```python
# app/modules/planning/domain/calculations/opportunities/my_calculator.py
from app.modules.planning.domain.calculations.opportunities.base import (
    OpportunityCalculator,
    opportunity_calculator_registry,
)

class MyCalculator(OpportunityCalculator):
    @property
    def name(self) -> str:
        return "my_calculator"

    def default_params(self) -> Dict[str, Any]:
        return {"threshold": 0.5}

    async def calculate(self, context, params):
        # Implementation
        pass

# Auto-register
_my_calculator = MyCalculator()
opportunity_calculator_registry.register(_my_calculator.name, _my_calculator)
```

### 2. Import Module

Ensure the module is imported so it auto-registers:

```python
# app/modules/planning/domain/calculations/opportunities/__init__.py
from . import my_calculator  # noqa: F401
```

### 3. Add to Configuration Model

```python
# app/modules/planning/domain/config/models.py
@dataclass
class OpportunityCalculatorsConfig:
    my_calculator: ModuleConfig = field(default_factory=ModuleConfig)
    # ... other calculators
```

### 4. Update Parser

```python
# app/modules/planning/domain/config/parser.py
def _parse_calculators_config(config_dict):
    return OpportunityCalculatorsConfig(
        my_calculator=_parse_module_config(config_dict.get("my_calculator")),
        # ... other calculators
    )
```

### 5. Use in Configuration

```toml
[opportunity_calculators.my_calculator]
enabled = true
[opportunity_calculators.my_calculator.params]
threshold = 0.5
```

## Registry Pattern

All modules use auto-registration:

```python
# Module registers itself on import
_pattern = MyPattern()
pattern_generator_registry.register(_pattern.name, _pattern)

# Factory retrieves from registry
pattern = pattern_generator_registry.get("my_pattern")
```

## Benefits

1. **Configurability** - Each bucket can have different strategies
2. **Modularity** - Add/remove features without changing code
3. **Testability** - Each module is independently testable
4. **Type Safety** - Full mypy compliance
5. **Clean Architecture** - Clear separation of concerns
6. **No Legacy Code** - Single user, no backwards compatibility needed

## Migration Path

The modular system is parallel to the monolithic planner:

1. ✅ **Phase 1-5**: Extract all modules and configuration (COMPLETE)
2. 🔄 **Phase 6**: Refactor `holistic_planner.py` to use modules
3. 🔄 **Phase 7**: Factory integration in production code
4. 🔄 **Phase 8**: Testing and validation
5. 🔜 **Phase 9**: Remove monolithic code

## Performance Considerations

- **Registry lookups**: O(1) dictionary lookups
- **Configuration**: Loaded once at startup
- **Auto-registration**: Happens on import (startup only)
- **Module reuse**: Same instances used across invocations

## Future Enhancements

- [ ] Add `selector` modules for diverse opportunity selection
- [ ] Add `transformer` modules for sequence modifications
- [ ] Add `validator` modules for sequence validation
- [ ] Support hot-reloading of configurations
- [ ] Add module dependency graph validation
- [ ] Support module composition (pipelines)
