# Holistic Planner Modularization Plan

## Objective
Transform the monolithic holistic planner (3,822 lines) into a fully modular, registry-based architecture that supports:
- Multiple independent planner instances (one per bucket)
- Complete configurability via parameters (no hardcoded strategies)
- User-customizable strategies via UI sliders
- All features available to all buckets through configuration

## Success Criteria
1. ✅ **Complete feature parity** - Core preset produces identical results to current planner
2. ✅ **Full modularity** - Every calculator, pattern, generator, filter is pluggable
3. ✅ **Zero regression** - All existing tests pass
4. ✅ **Clean architecture** - Domain stays pure, no circular dependencies
5. ✅ **Multi-bucket ready** - Factory can create independent instances per bucket

---

## Architecture Overview

```
app/modules/planning/
├── domain/
│   ├── models.py                          # Dataclasses (ActionCandidate, HolisticPlan, etc.)
│   │
│   ├── calculations/
│   │   ├── __init__.py
│   │   ├── base.py                        # Base interfaces + registries
│   │   ├── opportunities/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                    # OpportunityCalculator ABC + Registry
│   │   │   ├── profit_taking.py           # ProfitTakingCalculator
│   │   │   ├── averaging_down.py          # AveragingDownCalculator
│   │   │   ├── rebalance_sells.py         # RebalanceSellsCalculator
│   │   │   ├── rebalance_buys.py          # RebalanceBuysCalculator
│   │   │   ├── opportunity_buys.py        # OpportunityBuysCalculator
│   │   │   └── weight_based.py            # WeightBasedCalculator (from optimizer)
│   │   │
│   │   ├── patterns/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                    # PatternGenerator ABC + Registry
│   │   │   ├── direct_buy.py              # DirectBuyPattern
│   │   │   ├── profit_taking.py           # ProfitTakingPattern
│   │   │   ├── rebalance.py               # RebalancePattern
│   │   │   ├── averaging_down.py          # AveragingDownPattern
│   │   │   ├── single_best.py             # SingleBestPattern
│   │   │   ├── multi_sell.py              # MultiSellPattern
│   │   │   ├── mixed_strategy.py          # MixedStrategyPattern
│   │   │   ├── opportunity_first.py       # OpportunityFirstPattern
│   │   │   ├── deep_rebalance.py          # DeepRebalancePattern
│   │   │   ├── cash_generation.py         # CashGenerationPattern
│   │   │   ├── cost_optimized.py          # CostOptimizedPattern
│   │   │   ├── adaptive.py                # AdaptivePatternGenerator (9 variants)
│   │   │   └── market_regime.py           # MarketRegimePatternGenerator
│   │   │
│   │   ├── generators/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                    # SequenceGenerator ABC + Registry
│   │   │   ├── combinatorial.py           # CombinatorialGenerator (enhanced + basic)
│   │   │   ├── partial_execution.py       # PartialExecutionGenerator
│   │   │   └── constraint_relaxation.py   # ConstraintRelaxationGenerator
│   │   │
│   │   ├── filters/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                    # SequenceFilter ABC + Registry
│   │   │   ├── correlation_aware.py       # CorrelationAwareFilter
│   │   │   ├── diversity.py               # DiversitySelectionFilter
│   │   │   ├── eligibility.py             # EligibilityFilter
│   │   │   └── recently_traded.py         # RecentlyTradedFilter
│   │   │
│   │   ├── simulation.py                  # Portfolio simulation
│   │   ├── evaluation.py                  # Sequence evaluation (scoring)
│   │   └── utils.py                       # Shared utilities (cost calc, hashing, etc.)
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── planner_config.py              # PlannerConfiguration dataclass
│   │   ├── presets.py                     # Configuration presets (core, momentum, etc.)
│   │   ├── parameter_mapper.py            # Map sliders → technical parameters
│   │   └── validator.py                   # Validate config, check dependencies
│   │
│   └── planner.py                         # HolisticPlanner (orchestrator)
│
└── services/
    └── planner_factory.py                 # Create configured instances per bucket
```

---

## Phase 1: Extract Calculation Modules

**Goal**: Extract all calculation logic into reusable, testable modules with registries.

### 1.1 Create Base Interfaces and Registries

**Files to create:**
- `calculations/base.py`

```python
# calculations/base.py
from abc import ABC, abstractmethod
from typing import Dict, List, Any, TypeVar, Generic

T = TypeVar('T')

class CalculationModule(ABC):
    """Base class for all calculation modules."""
    name: str  # Unique identifier

    @abstractmethod
    def default_params(self) -> dict:
        """Return default parameters for this module."""
        pass

class Registry(Generic[T]):
    """Generic registry for calculation modules."""

    def __init__(self):
        self._modules: Dict[str, T] = {}

    def register(self, module: T) -> T:
        """Register a module."""
        self._modules[module.name] = module
        return module

    def get(self, name: str) -> T | None:
        """Get module by name."""
        return self._modules.get(name)

    def get_all(self) -> Dict[str, T]:
        """Get all registered modules."""
        return self._modules.copy()

    def list_names(self) -> List[str]:
        """List all registered module names."""
        return list(self._modules.keys())
```

### 1.2 Extract Opportunity Calculators

**Status**: 5/6 already extracted, need to:
1. Add base class and registry to existing calculators
2. Extract weight-based calculator from main file
3. Ensure all use consistent interfaces

**Files to create/modify:**
- `calculations/opportunities/base.py` - Base class + registry
- `calculations/opportunities/weight_based.py` - Extract from `identify_opportunities_from_weights()`

**Example structure:**
```python
# calculations/opportunities/base.py
from app.modules.planning.domain.calculations.base import CalculationModule, Registry
from app.modules.planning.domain.models import ActionCandidate
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class OpportunityContext:
    """Context for opportunity calculation."""
    portfolio_context: 'PortfolioContext'
    positions: List['Position']
    securities: List['Security']
    available_cash: float
    exchange_rate_service: Any
    # Additional context as needed

class OpportunityCalculator(CalculationModule):
    """Base class for opportunity calculators."""

    async def calculate(
        self,
        context: OpportunityContext,
        params: dict
    ) -> List[ActionCandidate]:
        """Calculate opportunities with given parameters."""
        pass

# Global registry
opportunity_registry = Registry[OpportunityCalculator]()
```

**Migration steps:**
1. Create base class
2. Update existing 5 calculators to inherit from base
3. Add `default_params()` method to each
4. Register on import: `opportunity_registry.register(ProfitTakingCalculator())`
5. Extract weight-based calculator
6. Test each calculator independently

### 1.3 Extract Utility Functions

**Files to create:**
- `calculations/utils.py`

**Functions to extract:**
- `_calculate_transaction_cost()` → `calculate_transaction_cost()`
- `_hash_sequence()` → `hash_sequence()`
- `_calculate_weight_gaps()` → `calculate_weight_gaps()`
- `_is_trade_worthwhile()` → `is_trade_worthwhile()`
- `_compute_ineligible_symbols()` → `compute_ineligible_symbols()`
- `_process_buy_opportunity()` → `process_buy_opportunity()`
- `_process_sell_opportunity()` → `process_sell_opportunity()`

**Make them:**
- Pure functions (no side effects)
- Fully parameterized (no settings_repo calls inside)
- Well-documented
- Unit tested

### 1.4 Extract Simulation and Evaluation

**Files to create:**
- `calculations/simulation.py`
- `calculations/evaluation.py`

**simulation.py:**
```python
async def simulate_sequence(
    sequence: List[ActionCandidate],
    portfolio_context: PortfolioContext,
    available_cash: float,
    securities: List[Security],
    price_adjustments: Optional[Dict[str, float]] = None,
) -> Tuple[PortfolioContext, float]:
    """Simulate executing a sequence."""
    # Extract from holistic_planner.py:2260
```

**evaluation.py:**
```python
@dataclass
class EvaluationContext:
    """Context for sequence evaluation."""
    portfolio_context: PortfolioContext
    available_cash: float
    securities: List[Security]
    transaction_cost_fixed: float
    transaction_cost_percent: float
    cost_penalty_factor: float = 0.1

async def evaluate_sequence(
    sequence: List[ActionCandidate],
    context: EvaluationContext,
    evaluation_mode: str = 'single_objective',  # 'single', 'multi', 'stochastic', 'monte_carlo'
    mode_params: dict = None,
) -> SequenceEvaluation:
    """Evaluate a sequence using specified mode."""
    # Extract evaluation logic
```

---

## Phase 2: Create Registry System

**Goal**: Build the registry infrastructure that allows dynamic module loading.

### 2.1 Pattern Generator Registry

**Files to create:**
- `calculations/patterns/base.py`

```python
from app.modules.planning.domain.calculations.base import CalculationModule, Registry

class PatternGenerator(CalculationModule):
    """Base class for pattern generators."""

    def generate(
        self,
        opportunities: Dict[str, List[ActionCandidate]],
        params: dict,
    ) -> List[List[ActionCandidate]]:
        """Generate patterns from opportunities."""
        pass

# Global registry
pattern_registry = Registry[PatternGenerator]()
```

### 2.2 Sequence Generator Registry

**Files to create:**
- `calculations/generators/base.py`

```python
class SequenceGenerator(CalculationModule):
    """Base class for advanced sequence generators."""

    async def generate(
        self,
        opportunities: Dict[str, List[ActionCandidate]],
        existing_sequences: List[List[ActionCandidate]],
        params: dict,
    ) -> List[List[ActionCandidate]]:
        """Generate additional sequences."""
        pass

# Global registry
generator_registry = Registry[SequenceGenerator]()
```

### 2.3 Filter Registry

**Files to create:**
- `calculations/filters/base.py`

```python
class SequenceFilter(CalculationModule):
    """Base class for sequence filters."""

    async def filter(
        self,
        sequences: List[List[ActionCandidate]],
        params: dict,
    ) -> List[List[ActionCandidate]]:
        """Filter sequences based on criteria."""
        pass

# Global registry
filter_registry = Registry[SequenceFilter]()
```

---

## Phase 3: Extract Pattern Generators

**Goal**: Convert all 13 pattern generators into pluggable modules.

### 3.1 Basic Patterns (11 patterns)

**For each pattern:**
1. Create new file in `calculations/patterns/`
2. Extract logic from `holistic_planner.py`
3. Inherit from `PatternGenerator`
4. Implement `generate()` and `default_params()`
5. Register on import
6. Unit test

**Pattern files to create:**
- `direct_buy.py` - Extract from `_generate_direct_buy_pattern:752`
- `profit_taking.py` - Extract from `_generate_profit_taking_pattern:773`
- `rebalance.py` - Extract from `_generate_rebalance_pattern:796`
- `averaging_down.py` - Extract from `_generate_averaging_down_pattern:820`
- `single_best.py` - Extract from `_generate_single_best_pattern:845`
- `multi_sell.py` - Extract from `_generate_multi_sell_pattern:878`
- `mixed_strategy.py` - Extract from `_generate_mixed_strategy_pattern:912`
- `opportunity_first.py` - Extract from `_generate_opportunity_first_pattern:947`
- `deep_rebalance.py` - Extract from `_generate_deep_rebalance_pattern:976`
- `cash_generation.py` - Extract from `_generate_cash_generation_pattern:1005`
- `cost_optimized.py` - Extract from `_generate_cost_optimized_pattern:1039`

### 3.2 Advanced Patterns (2 patterns)

**adaptive.py:**
```python
class AdaptivePatternGenerator(PatternGenerator):
    """
    Generates 9 different pattern variants based on portfolio state.

    Extracted from _generate_adaptive_patterns:1091
    """
    name = "adaptive"

    def default_params(self) -> dict:
        return {
            'min_large_gap': 0.02,
            'min_medium_gap': 0.01,
        }

    def generate(
        self,
        opportunities: Dict[str, List[ActionCandidate]],
        params: dict,
    ) -> List[List[ActionCandidate]]:
        # Generate 9 pattern variants
        ...
```

**market_regime.py:**
```python
class MarketRegimePatternGenerator(PatternGenerator):
    """
    Generates patterns adapted to current market regime.

    Extracted from _generate_market_regime_patterns:1234
    """
    name = "market_regime"

    def default_params(self) -> dict:
        return {
            'regime': 'bull',  # or 'bear', 'sideways', 'high_volatility'
        }
```

---

## Phase 4: Extract Advanced Generators and Filters

### 4.1 Sequence Generators

**combinatorial.py:**
```python
class CombinatorialGenerator(SequenceGenerator):
    """
    Generates combinatorial sequences.

    Includes both enhanced and basic combinatorial generation.
    Extracted from _generate_enhanced_combinations:1696 and _generate_combinations:1878
    """
    name = "combinatorial"

    def default_params(self) -> dict:
        return {
            'mode': 'enhanced',  # or 'basic'
            'max_sells': 4,
            'max_buys': 4,
            'max_combinations': 50,
            'max_candidates': 12,
            'priority_threshold': 0.3,
        }
```

**partial_execution.py:**
```python
class PartialExecutionGenerator(SequenceGenerator):
    """
    Generates partial execution scenarios (50%, 75%, 100% fills).

    Extracted from _generate_partial_execution_scenarios:1464
    """
    name = "partial_execution"

    def default_params(self) -> dict:
        return {
            'fill_percentages': [0.5, 0.75, 1.0],
        }
```

**constraint_relaxation.py:**
```python
class ConstraintRelaxationGenerator(SequenceGenerator):
    """
    Generates sequences with relaxed constraints.

    Extracted from _generate_constraint_relaxation_scenarios:1504
    """
    name = "constraint_relaxation"

    def default_params(self) -> dict:
        return {
            'relax_allow_sell': True,
            'relax_min_lot': True,
        }
```

### 4.2 Sequence Filters

**correlation_aware.py:**
```python
class CorrelationAwareFilter(SequenceFilter):
    """
    Filters sequences with high correlation.

    Extracted from _filter_correlation_aware_sequences:1354
    """
    name = "correlation_aware"

    def default_params(self) -> dict:
        return {
            'correlation_threshold': 0.7,
        }
```

**diversity.py:**
```python
class DiversitySelectionFilter(SequenceFilter):
    """
    Selects diverse opportunities using clustering.

    Extracted from _select_diverse_opportunities:1581
    """
    name = "diversity"

    def default_params(self) -> dict:
        return {
            'diversity_weight': 0.3,
        }
```

**eligibility.py:**
```python
class EligibilityFilter(SequenceFilter):
    """
    Filters based on eligibility rules (min_hold, cooldown, max_loss).
    """
    name = "eligibility"

    def default_params(self) -> dict:
        return {
            'min_hold_days': 90,
            'sell_cooldown_days': 180,
            'max_loss_threshold': -0.20,
        }
```

**recently_traded.py:**
```python
class RecentlyTradedFilter(SequenceFilter):
    """
    Filters based on buy/sell cooldown periods.
    """
    name = "recently_traded"

    def default_params(self) -> dict:
        return {
            'buy_cooldown_days': 30,
            'sell_cooldown_days': 180,
        }
```

---

## Phase 5: Create Configuration System

**Goal**: Build the configuration infrastructure that controls planner behavior.

### 5.1 Configuration System with TOML

**Format**: TOML (Tom's Obvious Minimal Language)
- Simple key=value syntax
- Comments support
- Sections/grouping
- Built-in Python parsing (tomllib)
- User-editable in plain textarea

**Files to create:**
- `config/planner_config.py` - PlannerConfiguration dataclass + TOML parser
- `config/templates.py` - TOML templates for presets

```python
# config/planner_config.py
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import tomllib  # Python 3.11+ (or tomli for earlier versions)

@dataclass
class PlannerConfiguration:
    """
    Complete configuration for a planner instance.

    Loaded from TOML configuration string.
    """

    # === Module Selection ===
    enabled_opportunity_calculators: List[str] = field(default_factory=list)
    enabled_pattern_generators: List[str] = field(default_factory=list)
    enabled_sequence_generators: List[str] = field(default_factory=list)
    enabled_filters: List[str] = field(default_factory=list)

    # === Per-Module Parameters ===
    opportunity_params: Dict[str, dict] = field(default_factory=dict)
    pattern_params: Dict[str, dict] = field(default_factory=dict)
    generator_params: Dict[str, dict] = field(default_factory=dict)
    filter_params: Dict[str, dict] = field(default_factory=dict)

    # === Global Planning Parameters ===
    max_plan_depth: int = 5
    max_opportunities_per_category: int = 5
    batch_size: int = 100
    priority_threshold: float = 0.3

    # === Transaction Costs ===
    transaction_cost_fixed: float = 2.0
    transaction_cost_percent: float = 0.002

    # === Evaluation Settings ===
    evaluation_mode: str = 'single_objective'
    beam_width: int = 10
    cost_penalty_factor: float = 0.1

    # === Stochastic/Monte Carlo Settings ===
    stochastic_price_shifts: List[float] = field(
        default_factory=lambda: [-0.10, -0.05, 0.0, 0.05, 0.10]
    )
    monte_carlo_path_count: int = 100

    # === Hardcoded Constants (now configurable) ===
    min_weight_gap: float = 0.005
    trade_cost_multiplier: float = 2.0

    # === Metadata ===
    template_name: Optional[str] = None
    bucket_id: Optional[str] = None


def parse_toml_config(toml_string: str) -> PlannerConfiguration:
    """
    Parse TOML configuration string into PlannerConfiguration.

    Args:
        toml_string: TOML configuration text

    Returns:
        PlannerConfiguration instance
    """
    config_dict = tomllib.loads(toml_string)

    # Extract enabled modules from boolean flags
    enabled_calculators = [
        name for name, enabled
        in config_dict.get('opportunity_calculators', {}).items()
        if enabled is True
    ]

    enabled_patterns = [
        name for name, enabled
        in config_dict.get('pattern_generators', {}).items()
        if enabled is True
    ]

    enabled_generators = [
        name for name, enabled
        in config_dict.get('sequence_generators', {}).items()
        if enabled is True
    ]

    enabled_filters = [
        name for name, enabled
        in config_dict.get('filters', {}).items()
        if enabled is True
    ]

    # Extract module parameters (nested sections)
    calc_params = {}
    for name, value in config_dict.get('opportunity_calculators', {}).items():
        if isinstance(value, dict):
            calc_params[name] = value

    pattern_params = {}
    for name, value in config_dict.get('pattern_generators', {}).items():
        if isinstance(value, dict):
            pattern_params[name] = value

    gen_params = {}
    for name, value in config_dict.get('sequence_generators', {}).items():
        if isinstance(value, dict):
            gen_params[name] = value

    filter_params = {}
    for name, value in config_dict.get('filters', {}).items():
        if isinstance(value, dict):
            filter_params[name] = value

    return PlannerConfiguration(
        # Module selection
        enabled_opportunity_calculators=enabled_calculators,
        enabled_pattern_generators=enabled_patterns,
        enabled_sequence_generators=enabled_generators,
        enabled_filters=enabled_filters,

        # Module parameters
        opportunity_params=calc_params,
        pattern_params=pattern_params,
        generator_params=gen_params,
        filter_params=filter_params,

        # Global settings
        max_plan_depth=config_dict.get('max_plan_depth', 5),
        max_opportunities_per_category=config_dict.get('max_opportunities_per_category', 5),
        batch_size=config_dict.get('batch_size', 100),
        priority_threshold=config_dict.get('priority_threshold', 0.3),

        # Transaction costs
        transaction_cost_fixed=config_dict.get('transaction_cost_fixed', 2.0),
        transaction_cost_percent=config_dict.get('transaction_cost_percent', 0.002),

        # Evaluation
        evaluation_mode=config_dict.get('evaluation_mode', 'single_objective'),
        beam_width=config_dict.get('beam_width', 10),
        cost_penalty_factor=config_dict.get('cost_penalty_factor', 0.1),

        # Stochastic/Monte Carlo
        stochastic_price_shifts=config_dict.get('stochastic_price_shifts', [-0.10, -0.05, 0.0, 0.05, 0.10]),
        monte_carlo_path_count=config_dict.get('monte_carlo_path_count', 100),

        # Constants
        min_weight_gap=config_dict.get('min_weight_gap', 0.005),
        trade_cost_multiplier=config_dict.get('trade_cost_multiplier', 2.0),
    )
```

### 5.2 TOML Configuration Templates

**Files to create:**
- `config/templates.py` - TOML template strings for each preset

```python
# config/templates.py

class ConfigurationTemplates:
    """TOML configuration templates for common strategies."""

    @staticmethod
    def core() -> str:
        """
        Core bucket configuration template.

        All features enabled, conservative parameters.
        This matches current planner behavior.
        """
        return """\
# ============================================================================
# Core Planner Configuration
# All features enabled, conservative parameters for long-term retirement fund
# ============================================================================

# ──────────────────────────────────────────────────────────────────────────
# CORE PARAMETERS
# ──────────────────────────────────────────────────────────────────────────

# Maximum plan depth (1-10)
# Controls how many sequential actions to consider in a plan.
# - Lower (1-3): Faster, simpler plans (good for aggressive strategies)
# - Medium (4-6): Balanced complexity and quality
# - Higher (7-10): More thorough but slower (may timeout on Arduino)
# RECOMMENDATION: Start with 5, reduce to 3 if planning takes >60 seconds
max_plan_depth = 5

# Maximum opportunities per category (1-20)
# Limits how many buy/sell candidates to consider from each calculator.
# - Lower (1-3): Faster, more focused
# - Higher (10-20): More comprehensive, slower
# Set to 0 to disable limiting (use all opportunities)
max_opportunities_per_category = 5

# Batch size for incremental processing (10-500)
# Number of sequences to evaluate per batch when using incremental mode.
# - Smaller batches: More responsive, can stop early
# - Larger batches: Better optimization, slower feedback
# Only relevant if using database-backed incremental planning
batch_size = 100

# Priority threshold for combinations (0.0-1.0)
# Minimum priority score required for an action to be included in combinations.
# - Lower (0.1-0.3): More combinations, slower
# - Higher (0.4-0.7): Fewer but higher-quality combinations
# Set to 0.0 to disable filtering
priority_threshold = 0.3

# ──────────────────────────────────────────────────────────────────────────
# TRANSACTION COSTS
# ──────────────────────────────────────────────────────────────────────────

# Fixed cost per trade in EUR
# Typical values: 0 (free trading), 1-5 (discount broker), 10+ (full-service)
transaction_cost_fixed = 2.0

# Variable cost as percentage of trade value (0.0-0.01)
# Typical values: 0.001 (0.1%), 0.002 (0.2%), 0.005 (0.5%)
transaction_cost_percent = 0.002

# ──────────────────────────────────────────────────────────────────────────
# EVALUATION MODE
# ──────────────────────────────────────────────────────────────────────────

# Choose ONE evaluation mode:
#   - "single_objective": Fast, maximizes end_state_score only
#   - "multi_objective": Slower, considers multiple objectives (score, risk, diversity)
#   - "stochastic": Test sequences under price variations (±10%, ±5%)
#   - "monte_carlo": Simulate random price paths (most thorough, slowest)
#
# ⚠️  MUTUAL EXCLUSIVITY: stochastic and monte_carlo cannot both be active
#     If you want robustness testing, choose ONE:
evaluation_mode = "single_objective"

# Advanced evaluation selector (only if you want stochastic OR monte_carlo)
# Uncomment and set to "stochastic" or "monte_carlo" to override evaluation_mode
# stochastic_or_monte = "stochastic"  # Options: "stochastic", "monte_carlo", or comment out

# Beam search width (1-50)
# Only used with multi_objective or stochastic/monte_carlo modes.
# Keeps top N sequences at each depth level.
# - Lower (5-10): Faster, less diverse
# - Higher (20-50): More diverse solutions, slower
# Set to 0 to disable beam search (evaluate all sequences)
beam_width = 10

# Cost penalty factor (0.0-1.0)
# Penalizes plans with high transaction costs.
# - 0.0: Ignore costs completely
# - 0.1: Slight penalty (default)
# - 0.5+: Strong penalty, prefer fewer trades
cost_penalty_factor = 0.1

# Monte Carlo simulation parameters (only if evaluation_mode = "monte_carlo")
# Number of random price paths to simulate (10-1000)
# More paths = more accurate but much slower
# Set to 0 to disable Monte Carlo (use evaluation_mode instead)
monte_carlo_path_count = 0

# Stochastic price shift scenarios (only if evaluation_mode = "stochastic")
# Price variations to test: [-0.10, -0.05, 0.0, 0.05, 0.10] = ±10%, ±5%, base
# Sequences are tested against each scenario and scored on average performance
# Leave empty [] to disable stochastic testing
stochastic_price_shifts = []

# ============================================================================
# OPPORTUNITY CALCULATORS
# Enable/disable different types of opportunity identification
# ============================================================================

[opportunity_calculators]
# Each calculator finds a different type of trading opportunity:

# profit_taking: Identifies positions with windfall gains to sell
# - Finds stocks that have exceeded expected returns
# - Sells partial positions to lock in profits
# - Use when you want to harvest gains systematically
profit_taking = true

# averaging_down: Finds quality positions that dipped to buy more
# - Identifies strong holdings trading below your cost basis
# - Only considers high-quality securities (good fundamentals)
# - Use when you want to "buy the dip" on winners
averaging_down = true

# rebalance_sells: Finds overweight positions to trim
# - Identifies holdings that exceed target country/industry allocation
# - Helps maintain diversification
# - Use when portfolio concentration becomes risky
rebalance_sells = true

# rebalance_buys: Finds underweight areas to increase
# - Identifies under-allocated countries/industries
# - Suggests securities to increase exposure
# - Use when you want to maintain target allocations
rebalance_buys = true

# opportunity_buys: Finds high-quality opportunities based on scores
# - Uses fundamental + technical + analyst scoring
# - Filters by 52-week highs, EMA, RSI, etc.
# - Primary source of new investment ideas
opportunity_buys = true

# weight_based: Uses portfolio optimizer target weights
# - Requires portfolio optimizer to be active
# - Calculates optimal weights using mean-variance optimization
# - More sophisticated than simple rebalancing
# ⚠️  Only enable if you have optimizer configured and historical data
weight_based = false

# ──────────────────────────────────────────────────────────────────────────
# OPPORTUNITY CALCULATOR PARAMETERS
# ──────────────────────────────────────────────────────────────────────────

[opportunity_calculators.profit_taking]
# Windfall threshold (0.10-1.0)
# Minimum "excess gain" to trigger profit-taking.
# If position gained 30%+ above expected return = windfall
# - Lower (0.15-0.25): Take profits earlier, more frequently
# - Higher (0.35-0.50): More patient, wait for bigger wins
windfall_threshold = 0.30

# Priority weight multiplier (0.5-2.0)
# Adjusts priority of profit-taking opportunities.
# - >1.0: Prioritize selling windfalls (default: 1.2)
# - <1.0: Deprioritize selling, let winners run
# - 1.0: Neutral priority
priority_weight = 1.2

[opportunity_calculators.averaging_down]
# Maximum drawdown to consider (-0.05 to -0.30)
# Only average down if position is down this much or less.
# - Shallow (-0.05 to -0.10): Very selective, only small dips
# - Medium (-0.10 to -0.20): Balanced approach (default: -0.15)
# - Deep (-0.20 to -0.30): Buy significant dips
# ⚠️  Don't catch falling knives - only quality positions!
max_drawdown = -0.15

# Priority weight multiplier (0.5-2.0)
# Adjusts priority of averaging down opportunities.
# - >1.0: Actively buy dips
# - <1.0: Conservative, prefer other opportunities (default: 0.9)
priority_weight = 0.9

# ============================================================================
# PATTERN GENERATORS
# Different trading patterns/strategies to generate action sequences
# ============================================================================

[pattern_generators]
# Each pattern creates a different type of action sequence:

# direct_buy: Simple buy using available cash
direct_buy = true

# profit_taking: Sell windfalls, reinvest proceeds
profit_taking = true

# rebalance: Sell overweight, buy underweight
rebalance = true

# averaging_down: Buy quality dips only
averaging_down = true

# single_best: Single highest-priority action
single_best = true

# multi_sell: Multiple sells, no buys
multi_sell = true

# mixed_strategy: 1-2 sells + 1-2 buys
mixed_strategy = true

# opportunity_first: Prioritize opportunity buys
opportunity_first = true

# deep_rebalance: Multiple rebalancing actions
deep_rebalance = true

# cash_generation: Focus on generating cash
cash_generation = true

# cost_optimized: Minimize transaction costs
cost_optimized = true

# adaptive: Adapt patterns based on portfolio state (9 sub-patterns)
adaptive = true

# market_regime: Adapt based on market conditions (bull/bear/sideways)
# ⚠️  Experimental - requires additional market data
market_regime = false

# ============================================================================
# ADVANCED SEQUENCE GENERATORS
# More sophisticated sequence generation methods
# ============================================================================

[sequence_generators]
# combinatorial: Smart combinatorial sequence generation
# Creates combinations of high-priority actions (can be slow)
# Set to false to disable, or configure parameters below
combinatorial = true

# partial_execution: Simulate partial fills (50%, 75%, 100%)
# ⚠️  Experimental - adds significant sequences
partial_execution = false

# constraint_relaxation: "What if" scenarios by relaxing constraints
# ⚠️  Experimental - use only for research buckets
constraint_relaxation = false

# ──────────────────────────────────────────────────────────────────────────
# COMBINATORIAL GENERATOR PARAMETERS
# ──────────────────────────────────────────────────────────────────────────

[sequence_generators.combinatorial]
# Mode: "enhanced" (diversity-aware) or "basic" (faster)
mode = "enhanced"

# Maximum combinations per depth (10-200)
# Set to 0 to disable limiting (may generate thousands!)
max_combinations = 50

# Maximum sell/buy actions in a combination (1-10)
# Set to 0 for no limit (not recommended)
max_sells = 4
max_buys = 4

# Maximum candidates for combinations (5-30)
# Only consider top N opportunities
# Set to 0 to use all (can be extremely slow!)
max_candidates = 12

# ============================================================================
# FILTERS
# Post-processing filters for sequences
# ============================================================================

[filters]
# correlation_aware: Filter highly correlated sequences
# Removes sequences that buy/sell correlated securities
# ⚠️  Requires securities correlation data
correlation_aware = false

# diversity: Balance priority vs diversity
# Clusters by country/industry, selects diverse opportunities
diversity = true

# eligibility: Filter ineligible sells
# Enforces min hold days, sell cooldown, max loss threshold
eligibility = true

# recently_traded: Filter recently traded symbols
# Prevents buying/selling same symbol too frequently
recently_traded = true

# ──────────────────────────────────────────────────────────────────────────
# FILTER PARAMETERS
# ──────────────────────────────────────────────────────────────────────────

[filters.diversity]
# Diversity weight (0.0-1.0)
# Balance between priority (0.0) and diversity (1.0)
# - 0.0: Pure priority, ignore diversity
# - 0.3: Slight diversity preference (default)
# - 0.7+: Strong diversity preference
diversity_weight = 0.3

[filters.eligibility]
# Minimum hold days (0-365)
# Don't sell positions held less than this
# Set to 0 to disable minimum hold requirement
min_hold_days = 90

# Sell cooldown days (0-365)
# Days between sells of same symbol
# Set to 0 to disable cooldown
sell_cooldown_days = 180

# Maximum loss threshold (-1.0 to 0.0)
# Never sell if down more than this percentage
# e.g., -0.20 = never sell if down >20%
# Set to 0.0 to disable (allow selling at any loss)
max_loss_threshold = -0.20

[filters.recently_traded]
# Buy cooldown days (0-90)
# Days between buys of same symbol
# Set to 0 to disable buy cooldown
buy_cooldown_days = 30

# Sell cooldown days (0-365)
# Days between sells of same symbol
# Set to 0 to disable sell cooldown
sell_cooldown_days = 180
"""

    @staticmethod
    def momentum_hunter() -> str:
        """Momentum hunter satellite template."""
        return """\
# ============================================================================
# Momentum Hunter Configuration
# Aggressive, breakout-focused strategy
# ============================================================================

max_plan_depth = 3
max_opportunities_per_category = 3
batch_size = 50
priority_threshold = 0.4  # Higher threshold = more selective

transaction_cost_fixed = 2.0
transaction_cost_percent = 0.002

evaluation_mode = "single_objective"

# ============================================================================
# Opportunity Calculators (Selective)
# ============================================================================

[opportunity_calculators]
profit_taking = true
opportunity_buys = true
# Disabled: averaging_down, rebalance (not momentum-focused)

[opportunity_calculators.profit_taking]
windfall_threshold = 0.15  # Take profits earlier
priority_weight = 1.5

[opportunity_calculators.opportunity_buys]
momentum_threshold = 0.8  # High momentum required

# ============================================================================
# Pattern Generators (Selective)
# ============================================================================

[pattern_generators]
single_best = true
opportunity_first = true
cash_generation = true
# Disabled: rebalance, averaging_down, deep_rebalance

# ============================================================================
# Advanced Generators
# ============================================================================

[sequence_generators]
combinatorial = true

[sequence_generators.combinatorial]
mode = "basic"  # Simpler combinations
max_combinations = 25
priority_threshold = 0.4

# ============================================================================
# Filters (Minimal)
# ============================================================================

[filters]
eligibility = true
# Disabled: correlation_aware, diversity (speed over diversity)

[filters.eligibility]
min_hold_days = 30  # Shorter holds
sell_cooldown_days = 90
max_loss_threshold = -0.15  # Stop losses tighter
"""

    @staticmethod
    def dip_buyer() -> str:
        """Dip buyer satellite template."""
        return """\
# ============================================================================
# Dip Buyer Configuration
# Patient, averaging-down focused strategy
# ============================================================================

max_plan_depth = 4
max_opportunities_per_category = 5
batch_size = 75
priority_threshold = 0.3

transaction_cost_fixed = 2.0
transaction_cost_percent = 0.002

# ============================================================================
# Opportunity Calculators
# ============================================================================

[opportunity_calculators]
averaging_down = true  # Primary focus
rebalance_buys = true
profit_taking = true

[opportunity_calculators.averaging_down]
max_drawdown = -0.25  # Tolerate deeper dips
priority_weight = 1.5

[opportunity_calculators.profit_taking]
windfall_threshold = 0.40  # Patient with profits

# ============================================================================
# Pattern Generators
# ============================================================================

[pattern_generators]
averaging_down = true
rebalance = true
single_best = true
# Focus on buying dips, not aggressive patterns

# ============================================================================
# Advanced Generators
# ============================================================================

[sequence_generators]
combinatorial = true

[sequence_generators.combinatorial]
mode = "enhanced"
max_combinations = 40

# ============================================================================
# Filters
# ============================================================================

[filters]
eligibility = true
diversity = true

[filters.diversity]
diversity_weight = 0.4  # More diversity

[filters.eligibility]
min_hold_days = 120  # Patient approach
sell_cooldown_days = 180
max_loss_threshold = -0.25  # Allow deeper losses before stopping
"""

    @staticmethod
    def steady_eddy() -> str:
        """Steady, conservative satellite template."""
        return """\
# ============================================================================
# Steady Eddy Configuration
# Very conservative, balanced approach
# ============================================================================

max_plan_depth = 4
max_opportunities_per_category = 5
batch_size = 100
priority_threshold = 0.35

transaction_cost_fixed = 2.0
transaction_cost_percent = 0.002

# ============================================================================
# Opportunity Calculators
# ============================================================================

[opportunity_calculators]
profit_taking = true
rebalance_sells = true
rebalance_buys = true
opportunity_buys = true

[opportunity_calculators.profit_taking]
windfall_threshold = 0.35

# ============================================================================
# Pattern Generators
# ============================================================================

[pattern_generators]
direct_buy = true
rebalance = true
single_best = true
deep_rebalance = true

# ============================================================================
# Advanced Generators
# ============================================================================

[sequence_generators]
combinatorial = true

# ============================================================================
# Filters
# ============================================================================

[filters]
eligibility = true
diversity = true

[filters.diversity]
diversity_weight = 0.4

[filters.eligibility]
min_hold_days = 90
sell_cooldown_days = 180
max_loss_threshold = -0.20
"""
```

**Usage:**
```python
from app.modules.planning.domain.config.templates import ConfigurationTemplates
from app.modules.planning.domain.config.planner_config import parse_toml_config

# Load template
toml_str = ConfigurationTemplates.core()

# Parse into configuration
config = parse_toml_config(toml_str)

# User can edit TOML string before parsing
# Store edited TOML in bucket.strategy_config
```

### 5.3 Configuration Validator

**Files to create:**
- `config/validator.py`

```python
class ConfigurationValidator:
    """Validates TOML configurations before parsing."""

    @staticmethod
    def validate_toml_syntax(toml_string: str) -> Tuple[bool, List[str]]:
        """
        Validate TOML syntax.

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        try:
            import tomllib
            tomllib.loads(toml_string)
            return (True, [])
        except Exception as e:
            errors.append(f"TOML syntax error: {str(e)}")
            return (False, errors)

    @staticmethod
    def validate_config(config: PlannerConfiguration) -> List[str]:
            # Enable ALL calculators
            enabled_opportunity_calculators=[
                'profit_taking',
                'averaging_down',
                'rebalance_sells',
                'rebalance_buys',
                'opportunity_buys',
                'weight_based',
            ],

            # Enable ALL patterns
            enabled_pattern_generators=[
                'direct_buy',
                'profit_taking',
                'rebalance',
                'averaging_down',
                'single_best',
                'multi_sell',
                'mixed_strategy',
                'opportunity_first',
                'deep_rebalance',
                'cash_generation',
                'cost_optimized',
                'adaptive',
                'market_regime',
            ],

            # Enable advanced generators
            enabled_sequence_generators=[
                'combinatorial',
                'partial_execution',
                'constraint_relaxation',
            ],

            # Enable filters
            enabled_filters=[
                'correlation_aware',
                'diversity',
                'eligibility',
                'recently_traded',
            ],

            # Module-specific parameters
            opportunity_params={
                'profit_taking': {
                    'windfall_threshold': 0.30,
                    'priority_weight': 1.2,
                },
                'averaging_down': {
                    'max_drawdown': -0.15,
                    'priority_weight': 0.9,
                },
            },

            generator_params={
                'combinatorial': {
                    'mode': 'enhanced',
                    'max_combinations': 50,
                    'max_sells': 4,
                    'max_buys': 4,
                    'max_candidates': 12,
                    'priority_threshold': 0.3,
                },
            },

            filter_params={
                'correlation_aware': {
                    'correlation_threshold': 0.7,
                },
                'diversity': {
                    'diversity_weight': 0.3,
                },
                'eligibility': {
                    'min_hold_days': 90,
                    'sell_cooldown_days': 180,
                    'max_loss_threshold': -0.20,
                },
                'recently_traded': {
                    'buy_cooldown_days': 30,
                    'sell_cooldown_days': 180,
                },
            },

            # Global settings
            max_plan_depth=5,
            max_opportunities_per_category=5,
            batch_size=100,
            priority_threshold=0.3,

            # Transaction costs
            transaction_cost_fixed=2.0,
            transaction_cost_percent=0.002,

            # Evaluation
            evaluation_mode='single_objective',
            beam_width=10,
            cost_penalty_factor=0.1,

            # Sliders (conservative)
            risk_appetite=0.2,
            hold_duration=0.9,
            entry_style=0.3,  # Slight dip preference
            position_spread=0.9,  # Highly diversified
            profit_taking=0.4,

            # Toggles
            use_trailing_stops=False,
            follow_market_regime=False,
            auto_harvest_gains=False,
            pause_high_volatility=False,

            # Metadata
            preset_name='core',
        )

    @staticmethod
    def momentum_hunter() -> PlannerConfiguration:
        """Momentum hunter satellite configuration."""
        return PlannerConfiguration(
            # Selective calculators
            enabled_opportunity_calculators=[
                'profit_taking',
                'opportunity_buys',
            ],

            # Selective patterns
            enabled_pattern_generators=[
                'single_best',
                'opportunity_first',
                'cash_generation',
            ],

            # Basic generators
            enabled_sequence_generators=[
                'combinatorial',
            ],

            # Minimal filters
            enabled_filters=[
                'eligibility',
            ],

            # Aggressive parameters
            opportunity_params={
                'profit_taking': {
                    'windfall_threshold': 0.15,
                    'priority_weight': 1.5,
                },
                'opportunity_buys': {
                    'momentum_threshold': 0.8,
                },
            },

            generator_params={
                'combinatorial': {
                    'mode': 'basic',
                    'max_combinations': 25,
                    'priority_threshold': 0.4,
                },
            },

            # Aggressive settings
            max_plan_depth=3,
            max_opportunities_per_category=3,
            batch_size=50,

            # Sliders (aggressive)
            risk_appetite=0.8,
            hold_duration=0.2,
            entry_style=0.9,  # Strong breakout preference
            position_spread=0.4,  # More concentrated
            profit_taking=0.7,  # Take profits quickly

            # Toggles
            use_trailing_stops=True,
            follow_market_regime=True,

            preset_name='momentum_hunter',
        )

    @staticmethod
    def dip_buyer() -> PlannerConfiguration:
        """Dip buyer satellite configuration."""
        return PlannerConfiguration(
            enabled_opportunity_calculators=[
                'averaging_down',
                'rebalance_buys',
                'profit_taking',
            ],

            enabled_pattern_generators=[
                'averaging_down',
                'rebalance',
                'single_best',
            ],

            enabled_sequence_generators=[
                'combinatorial',
            ],

            enabled_filters=[
                'eligibility',
                'diversity',
            ],

            opportunity_params={
                'averaging_down': {
                    'max_drawdown': -0.25,
                    'priority_weight': 1.5,
                },
                'profit_taking': {
                    'windfall_threshold': 0.40,  # Patient
                },
            },

            # Moderate settings
            max_plan_depth=4,

            # Sliders (dip focus)
            risk_appetite=0.5,
            hold_duration=0.7,
            entry_style=0.1,  # Strong dip preference
            position_spread=0.6,
            profit_taking=0.3,

            preset_name='dip_buyer',
        )

    @staticmethod
    def steady_eddy() -> PlannerConfiguration:
        """Steady, conservative satellite configuration."""
        return PlannerConfiguration(
            enabled_opportunity_calculators=[
                'profit_taking',
                'rebalance_sells',
                'rebalance_buys',
                'opportunity_buys',
            ],

            enabled_pattern_generators=[
                'direct_buy',
                'rebalance',
                'single_best',
                'deep_rebalance',
            ],

            enabled_sequence_generators=[
                'combinatorial',
            ],

            enabled_filters=[
                'eligibility',
                'diversity',
            ],

            # Conservative settings
            max_plan_depth=4,

            # Sliders (very conservative)
            risk_appetite=0.3,
            hold_duration=0.8,
            entry_style=0.4,
            position_spread=0.8,
            profit_taking=0.2,

            preset_name='steady_eddy',
        )
```

### 5.3 Parameter Mapper (Sliders → Technical Parameters)

**Files to create:**
- `config/parameter_mapper.py`

```python
class ParameterMapper:
    """
    Maps UI slider values (0.0-1.0) to technical parameters.

    This is where the "magic" happens - user-friendly sliders
    get translated into concrete calculation parameters.
    """

    @staticmethod
    def map_risk_appetite(value: float) -> dict:
        """
        Map risk appetite slider to parameters.

        Args:
            value: 0.0 (conservative) to 1.0 (aggressive)

        Returns:
            Dict of risk-related parameters
        """
        return {
            'priority_threshold': 0.5 - (value * 0.3),  # 0.5→0.2
            'cost_penalty_factor': 0.2 - (value * 0.15),  # 0.2→0.05
            'max_position_concentration': 0.10 + (value * 0.10),  # 10%→20%
        }

    @staticmethod
    def map_hold_duration(value: float) -> dict:
        """
        Map hold duration slider to parameters.

        Args:
            value: 0.0 (quick flips) to 1.0 (patient holds)

        Returns:
            Dict of time-related parameters
        """
        return {
            'min_hold_days': int(30 + (value * 150)),  # 30→180 days
            'profit_taking_threshold': 0.10 + (value * 0.30),  # 10%→40%
        }

    @staticmethod
    def map_entry_style(value: float) -> dict:
        """
        Map entry style slider to parameters.

        Args:
            value: 0.0 (buy dips) to 1.0 (buy breakouts)

        Returns:
            Dict of entry-related parameters
        """
        return {
            'dip_weight': (1.0 - value),
            'breakout_weight': value,
            'momentum_threshold': 0.3 + (value * 0.6),  # 0.3→0.9
        }

    @staticmethod
    def map_position_spread(value: float) -> dict:
        """
        Map position spread slider to parameters.

        Args:
            value: 0.0 (concentrated) to 1.0 (diversified)

        Returns:
            Dict of diversification-related parameters
        """
        return {
            'max_opportunities_per_category': int(2 + (value * 8)),  # 2→10
            'diversity_weight': value * 0.5,  # 0.0→0.5
            'max_position_size': 0.20 - (value * 0.10),  # 20%→10%
        }

    @staticmethod
    def map_profit_taking(value: float) -> dict:
        """
        Map profit taking slider to parameters.

        Args:
            value: 0.0 (let winners run) to 1.0 (take profits early)

        Returns:
            Dict of profit-taking parameters
        """
        return {
            'windfall_threshold': 0.40 - (value * 0.25),  # 40%→15%
            'windfall_sell_pct': 0.20 + (value * 0.30),  # 20%→50%
            'trailing_stop_distance': 0.15 - (value * 0.10),  # 15%→5%
        }

    @staticmethod
    def apply_sliders_to_config(config: PlannerConfiguration) -> PlannerConfiguration:
        """
        Apply slider values to configuration by updating module parameters.

        This is called when config is created from sliders to ensure
        all technical parameters reflect the slider positions.
        """
        # Map each slider
        risk_params = ParameterMapper.map_risk_appetite(config.risk_appetite)
        hold_params = ParameterMapper.map_hold_duration(config.hold_duration)
        entry_params = ParameterMapper.map_entry_style(config.entry_style)
        spread_params = ParameterMapper.map_position_spread(config.position_spread)
        profit_params = ParameterMapper.map_profit_taking(config.profit_taking)

        # Apply to global settings
        config.priority_threshold = risk_params['priority_threshold']
        config.cost_penalty_factor = risk_params['cost_penalty_factor']
        config.max_opportunities_per_category = spread_params['max_opportunities_per_category']

        # Apply to module params
        if 'profit_taking' in config.opportunity_params:
            config.opportunity_params['profit_taking'].update({
                'windfall_threshold': profit_params['windfall_threshold'],
                'windfall_sell_pct': profit_params['windfall_sell_pct'],
            })

        if 'eligibility' in config.filter_params:
            config.filter_params['eligibility'].update({
                'min_hold_days': hold_params['min_hold_days'],
            })

        if 'diversity' in config.filter_params:
            config.filter_params['diversity'].update({
                'diversity_weight': spread_params['diversity_weight'],
            })

        return config
```

### 5.4 Configuration Validator

**Files to create:**
- `config/validator.py`

```python
class ConfigurationValidator:
    """Validates planner configurations and checks for issues."""

    @staticmethod
    def validate(config: PlannerConfiguration) -> List[str]:
        """
        Validate configuration and return list of issues.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check module existence
        from app.modules.planning.domain.calculations.opportunities.base import opportunity_registry
        from app.modules.planning.domain.calculations.patterns.base import pattern_registry
        # ... other registries

        for calc_name in config.enabled_opportunity_calculators:
            if not opportunity_registry.get(calc_name):
                errors.append(f"Unknown opportunity calculator: {calc_name}")

        for pattern_name in config.enabled_pattern_generators:
            if not pattern_registry.get(pattern_name):
                errors.append(f"Unknown pattern generator: {pattern_name}")

        # Check parameter validity
        if config.max_plan_depth < 1:
            errors.append("max_plan_depth must be >= 1")

        if not 0.0 <= config.priority_threshold <= 1.0:
            errors.append("priority_threshold must be between 0.0 and 1.0")

        # Check slider ranges
        for slider_name in ['risk_appetite', 'hold_duration', 'entry_style', 'position_spread', 'profit_taking']:
            value = getattr(config, slider_name)
            if not 0.0 <= value <= 1.0:
                errors.append(f"{slider_name} must be between 0.0 and 1.0")

        return errors

    @staticmethod
    def check_dependencies(config: PlannerConfiguration) -> List[str]:
        """
        Check for module dependency issues.

        Returns:
            List of warnings about missing dependencies
        """
        warnings = []

        # Example: combinatorial generator needs certain patterns
        if 'combinatorial' in config.enabled_sequence_generators:
            if len(config.enabled_pattern_generators) < 2:
                warnings.append(
                    "Combinatorial generator works best with multiple patterns enabled"
                )

        # Correlation filter needs securities data
        if 'correlation_aware' in config.enabled_filters:
            warnings.append(
                "Correlation-aware filter requires securities with country/industry data"
            )

        return warnings
```

---

## Phase 6: Refactor Planner to Use Modules

**Goal**: Rewrite the main planner to be a module orchestrator.

### 6.1 New Planner Structure

**Files to modify:**
- `domain/planner.py`

```python
from typing import Optional, List, Dict
from app.modules.planning.domain.config.planner_config import PlannerConfiguration
from app.modules.planning.domain.calculations.opportunities.base import opportunity_registry
from app.modules.planning.domain.calculations.patterns.base import pattern_registry
from app.modules.planning.domain.calculations.generators.base import generator_registry
from app.modules.planning.domain.calculations.filters.base import filter_registry
from app.modules.planning.domain.models import HolisticPlan, ActionCandidate

class HolisticPlanner:
    """
    Unified holistic planner that composes modules based on configuration.

    No hardcoded logic - all behavior is configuration-driven.
    Core and satellite planners use the same code with different configs.
    """

    def __init__(
        self,
        config: PlannerConfiguration,
        bucket_id: str = 'core',
    ):
        self.config = config
        self.bucket_id = bucket_id

        # Load enabled modules from registries
        self.opportunity_calculators = self._load_opportunity_calculators()
        self.pattern_generators = self._load_pattern_generators()
        self.sequence_generators = self._load_sequence_generators()
        self.filters = self._load_filters()

    def _load_opportunity_calculators(self):
        """Load enabled opportunity calculators from registry."""
        calculators = []
        for name in self.config.enabled_opportunity_calculators:
            calc = opportunity_registry.get(name)
            if calc:
                calculators.append(calc)
            else:
                logger.warning(f"Opportunity calculator '{name}' not found in registry")
        return calculators

    def _load_pattern_generators(self):
        """Load enabled pattern generators from registry."""
        patterns = []
        for name in self.config.enabled_pattern_generators:
            pattern = pattern_registry.get(name)
            if pattern:
                patterns.append(pattern)
            else:
                logger.warning(f"Pattern generator '{name}' not found in registry")
        return patterns

    def _load_sequence_generators(self):
        """Load enabled sequence generators from registry."""
        generators = []
        for name in self.config.enabled_sequence_generators:
            gen = generator_registry.get(name)
            if gen:
                generators.append(gen)
            else:
                logger.warning(f"Sequence generator '{name}' not found in registry")
        return generators

    def _load_filters(self):
        """Load enabled filters from registry."""
        filters = []
        for name in self.config.enabled_filters:
            filt = filter_registry.get(name)
            if filt:
                filters.append(filt)
            else:
                logger.warning(f"Filter '{name}' not found in registry")
        return filters

    async def identify_opportunities(
        self,
        context: 'OpportunityContext',
    ) -> Dict[str, List[ActionCandidate]]:
        """
        Identify opportunities using configured calculators.

        No hardcoded logic - runs all enabled calculators with their parameters.
        """
        opportunities: Dict[str, List[ActionCandidate]] = {}

        for calculator in self.opportunity_calculators:
            # Get calculator-specific parameters from config
            params = self.config.opportunity_params.get(
                calculator.name,
                calculator.default_params()
            )

            # Run calculator
            candidates = await calculator.calculate(context, params)

            # Store by calculator name
            opportunities[calculator.name] = candidates

        return opportunities

    async def generate_sequences(
        self,
        opportunities: Dict[str, List[ActionCandidate]],
        max_depth: Optional[int] = None,
    ) -> List[List[ActionCandidate]]:
        """
        Generate sequences using configured patterns and generators.

        Process:
        1. Generate base sequences from patterns
        2. Apply advanced generators
        3. Apply filters
        """
        sequences = []
        max_depth = max_depth or self.config.max_plan_depth

        # Step 1: Generate sequences from basic patterns at each depth
        for depth in range(1, max_depth + 1):
            for pattern in self.pattern_generators:
                params = self.config.pattern_params.get(
                    pattern.name,
                    pattern.default_params()
                )
                # Add depth constraint to params
                params['max_depth'] = depth

                pattern_sequences = pattern.generate(opportunities, params)
                sequences.extend(pattern_sequences)

        # Step 2: Apply advanced generators
        for generator in self.sequence_generators:
            params = self.config.generator_params.get(
                generator.name,
                generator.default_params()
            )

            additional = await generator.generate(opportunities, sequences, params)
            sequences.extend(additional)

        # Step 3: Apply filters
        for filter_module in self.filters:
            params = self.config.filter_params.get(
                filter_module.name,
                filter_module.default_params()
            )

            sequences = await filter_module.filter(sequences, params)

        return sequences

    async def evaluate_sequences(
        self,
        sequences: List[List[ActionCandidate]],
        context: 'EvaluationContext',
    ) -> List['SequenceEvaluation']:
        """Evaluate all sequences using configured evaluation mode."""
        from app.modules.planning.domain.calculations.evaluation import evaluate_sequence

        evaluations = []

        mode = self.config.evaluation_mode
        mode_params = {
            'beam_width': self.config.beam_width,
            'monte_carlo_paths': self.config.monte_carlo_path_count,
            'stochastic_shifts': self.config.stochastic_price_shifts,
        }

        for sequence in sequences:
            eval_result = await evaluate_sequence(
                sequence,
                context,
                evaluation_mode=mode,
                mode_params=mode_params,
            )
            evaluations.append(eval_result)

        return evaluations

    async def select_best(
        self,
        evaluations: List['SequenceEvaluation'],
    ) -> Optional['SequenceEvaluation']:
        """Select best evaluation based on configuration."""
        if not evaluations:
            return None

        if self.config.evaluation_mode == 'multi_objective':
            # Pareto frontier selection
            non_dominated = [
                e for e in evaluations
                if not any(other.is_dominated_by(e) for other in evaluations if other != e)
            ]
            # Pick best from non-dominated (highest end_score)
            return max(non_dominated, key=lambda e: e.end_score)
        else:
            # Simple: highest end_score
            return max(evaluations, key=lambda e: e.end_score)

    async def plan(
        self,
        context: 'PlannerContext',
    ) -> Optional[HolisticPlan]:
        """
        Create plan using configured modules.

        Identical logic for core and satellites - only config differs.
        """
        # Step 1: Identify opportunities
        opportunities = await self.identify_opportunities(context.opportunity_context)

        # Step 2: Generate sequences
        sequences = await self.generate_sequences(opportunities)

        # Step 3: Evaluate sequences
        evaluations = await self.evaluate_sequences(sequences, context.evaluation_context)

        # Step 4: Select best
        best_eval = await self.select_best(evaluations)

        if not best_eval:
            return None

        # Step 5: Convert to HolisticPlan
        plan = self._evaluation_to_plan(best_eval, context)

        return plan

    def _evaluation_to_plan(
        self,
        evaluation: 'SequenceEvaluation',
        context: 'PlannerContext',
    ) -> HolisticPlan:
        """Convert SequenceEvaluation to HolisticPlan."""
        # Generate steps, narrative, etc.
        # (Similar to existing logic but extracted)
        ...
```

### 6.2 Incremental Processing Support

The planner needs to support incremental batch processing for the database-backed workflow:

```python
class HolisticPlanner:
    # ... previous methods ...

    async def plan_incremental(
        self,
        context: 'PlannerContext',
        batch_size: Optional[int] = None,
    ) -> Optional[HolisticPlan]:
        """
        Incremental planning mode.

        Process:
        1. Check if sequences exist in DB
        2. If not, generate all sequences and store
        3. Get next batch from DB
        4. Evaluate batch
        5. Update best result
        6. Return best so far
        """
        from app.modules.planning.database.planner_repository import PlannerRepository

        batch_size = batch_size or self.config.batch_size
        repo = PlannerRepository()

        # Generate portfolio hash for cache key
        portfolio_hash = self._generate_portfolio_hash(context)

        # Step 1: Check if sequences exist
        has_sequences = await repo.has_sequences(portfolio_hash)

        if not has_sequences:
            # Generate all sequences
            opportunities = await self.identify_opportunities(context.opportunity_context)
            sequences = await self.generate_sequences(opportunities)

            # Store in DB
            await repo.ensure_sequences_generated(portfolio_hash, sequences)

        # Step 2: Get next batch
        next_batch = await repo.get_next_sequences(portfolio_hash, limit=batch_size)

        if not next_batch:
            # All sequences processed
            best = await repo.get_best_result(portfolio_hash)
            if best:
                # Load and return best plan
                sequence = await repo.get_best_sequence_from_hash(
                    portfolio_hash, best['best_sequence_hash']
                )
                # Reconstruct plan
                ...
            return None

        # Step 3: Evaluate batch
        from datetime import datetime
        now = datetime.now().isoformat()

        for seq_data in next_batch:
            sequence = self._deserialize_sequence(seq_data['sequence_json'])

            # Check if already evaluated
            if await repo.has_evaluation(seq_data['sequence_hash'], portfolio_hash):
                await repo.mark_sequence_completed(
                    seq_data['sequence_hash'], portfolio_hash, now
                )
                continue

            # Evaluate
            eval_result = await self.evaluate_sequences([sequence], context.evaluation_context)
            if eval_result:
                evaluation = eval_result[0]

                # Store evaluation
                await repo.insert_evaluation(
                    seq_data['sequence_hash'],
                    portfolio_hash,
                    evaluation.end_score,
                    evaluation.breakdown,
                    context.final_cash,  # from simulation
                    context.final_positions,  # from simulation
                    evaluation.diversification_score,
                    context.total_value,
                )

                # Update best if better
                best = await repo.get_best_result(portfolio_hash)
                if not best or evaluation.end_score > best['best_score']:
                    await repo.update_best_result(
                        portfolio_hash,
                        seq_data['sequence_hash'],
                        evaluation.end_score,
                    )

                # Mark completed
                await repo.mark_sequence_completed(
                    seq_data['sequence_hash'], portfolio_hash, now
                )

        # Step 4: Return current best
        best = await repo.get_best_result(portfolio_hash)
        if best:
            sequence = await repo.get_best_sequence_from_hash(
                portfolio_hash, best['best_sequence_hash']
            )
            # Reconstruct and return plan
            ...

        return None
```

---

## Phase 7: Create Factory and Integration

**Goal**: Build the factory that creates planner instances and integrate with the rest of the system.

### 7.1 Planner Factory

**Files to create:**
- `services/planner_factory.py`

```python
import json
from typing import Optional
from app.modules.planning.domain.planner import HolisticPlanner
from app.modules.planning.domain.config.planner_config import PlannerConfiguration
from app.modules.planning.domain.config.presets import ConfigurationPresets
from app.modules.planning.domain.config.parameter_mapper import ParameterMapper
from app.modules.planning.domain.config.validator import ConfigurationValidator

def create_planner_for_bucket(bucket: 'Bucket') -> HolisticPlanner:
    """
    Create planner instance for a bucket.

    Args:
        bucket: Bucket instance with strategy_config

    Returns:
        Configured HolisticPlanner instance
    """
    # Load configuration
    if bucket.strategy_config:
        config = _load_config_from_bucket(bucket)
    else:
        # Default: core for core bucket, steady for satellites
        if bucket.type == 'core':
            config = ConfigurationPresets.core()
        else:
            config = ConfigurationPresets.steady_eddy()

    # Set bucket ID
    config.bucket_id = bucket.id

    # Validate configuration
    errors = ConfigurationValidator.validate(config)
    if errors:
        raise ValueError(f"Invalid configuration for bucket {bucket.id}: {errors}")

    # Check for warnings
    warnings = ConfigurationValidator.check_dependencies(config)
    if warnings:
        logger.warning(f"Configuration warnings for bucket {bucket.id}: {warnings}")

    # Create planner
    return HolisticPlanner(config=config, bucket_id=bucket.id)

def _load_config_from_bucket(bucket: 'Bucket') -> PlannerConfiguration:
    """Load configuration from bucket's strategy_config JSON."""
    config_dict = json.loads(bucket.strategy_config)

    # Check if user started from preset
    if 'preset' in config_dict and config_dict['preset']:
        preset_name = config_dict['preset']

        # Get preset base config
        if hasattr(ConfigurationPresets, preset_name):
            config = getattr(ConfigurationPresets, preset_name)()
        else:
            raise ValueError(f"Unknown preset: {preset_name}")

        # Apply user overrides
        if 'sliders' in config_dict:
            for key, value in config_dict['sliders'].items():
                if hasattr(config, key):
                    setattr(config, key, value)

        if 'toggles' in config_dict:
            for key, value in config_dict['toggles'].items():
                toggle_key = f'use_{key}' if not key.startswith('use_') else key
                if hasattr(config, toggle_key):
                    setattr(config, toggle_key, value)

        # Apply module overrides
        if 'enabled_calculators' in config_dict:
            config.enabled_opportunity_calculators = config_dict['enabled_calculators']
        if 'enabled_patterns' in config_dict:
            config.enabled_pattern_generators = config_dict['enabled_patterns']
        # ... etc

        # Apply slider mappings
        config = ParameterMapper.apply_sliders_to_config(config)
    else:
        # Build config from scratch
        config = PlannerConfiguration(**config_dict)

    return config

def create_planner_for_core() -> HolisticPlanner:
    """
    Create planner instance for core bucket with all features.

    Convenience function for backwards compatibility.
    """
    config = ConfigurationPresets.core()
    return HolisticPlanner(config=config, bucket_id='core')
```

### 7.2 Update Planner Batch Job

**Files to modify:**
- `jobs/planner_batch.py`

```python
async def process_planner_batch_job(
    max_depth: int = 0,
    portfolio_hash: Optional[str] = None,
    bucket_id: str = 'core',  # NEW: bucket ID
):
    """
    Process next batch of sequences for holistic planner.

    Now bucket-aware: creates planner instance for specified bucket.
    """
    try:
        # Get bucket configuration
        from app.modules.satellites.database.satellites_repository import SatellitesRepository

        if bucket_id == 'core':
            # Use factory for core
            from app.modules.planning.services.planner_factory import create_planner_for_core
            planner = create_planner_for_core()
        else:
            # Load satellite configuration
            satellite_repo = SatellitesRepository()
            satellite = await satellite_repo.get(bucket_id)

            if not satellite:
                logger.error(f"Satellite {bucket_id} not found")
                return

            # Create planner for satellite
            from app.modules.planning.services.planner_factory import create_planner_for_bucket
            planner = create_planner_for_bucket(satellite)

        # Build context (same as before, but bucket-aware)
        # ...

        # Run planner (incremental mode)
        plan = await planner.plan_incremental(
            context=context,
            batch_size=planner.config.batch_size,
        )

        # Emit events, etc.
        # ...

    except Exception as e:
        logger.error(f"Error in planner batch job for bucket {bucket_id}: {e}", exc_info=True)
```

---

## Phase 8: Testing and Validation

**Goal**: Ensure complete feature parity and no regressions.

### 8.1 Unit Tests

**For each extracted module:**
1. Test with default parameters
2. Test with various parameter combinations
3. Test edge cases
4. Test error handling

**Example test structure:**
```python
# tests/unit/domain/planning/calculations/opportunities/test_profit_taking.py
import pytest
from app.modules.planning.domain.calculations.opportunities.profit_taking import ProfitTakingCalculator

@pytest.mark.asyncio
async def test_profit_taking_calculator_default_params():
    """Test profit taking with default parameters."""
    calc = ProfitTakingCalculator()
    params = calc.default_params()

    # Setup context
    context = ...

    # Run
    candidates = await calc.calculate(context, params)

    # Assert
    assert len(candidates) >= 0
    # ... assertions

@pytest.mark.asyncio
async def test_profit_taking_calculator_aggressive_params():
    """Test profit taking with aggressive threshold."""
    calc = ProfitTakingCalculator()
    params = calc.default_params()
    params['windfall_threshold'] = 0.15  # Lower threshold

    # Run
    candidates = await calc.calculate(context, params)

    # Should find more opportunities
    # ... assertions
```

### 8.2 Integration Tests

**Test complete planner workflow:**
```python
# tests/integration/planning/test_planner_equivalence.py
import pytest
from app.modules.planning.domain.config.presets import ConfigurationPresets
from app.modules.planning.services.planner_factory import create_planner_for_core

@pytest.mark.asyncio
async def test_core_preset_matches_original():
    """
    Test that core preset produces same results as original planner.

    This is the CRITICAL test - ensures no regression.
    """
    # Create planner with core preset
    planner = create_planner_for_core()

    # Run on same inputs as original
    context = ...  # Use fixed test data

    new_plan = await planner.plan(context)

    # Compare with stored original results
    # (Generated before refactoring and saved)
    original_plan = load_original_plan_results()

    # Assert equivalence
    assert new_plan.end_state_score == pytest.approx(original_plan.end_state_score, abs=0.001)
    assert len(new_plan.steps) == len(original_plan.steps)
    # ... detailed assertions
```

### 8.3 Regression Test Suite

**Create comprehensive regression tests:**
1. Save outputs from current planner on various scenarios
2. Run new planner on same scenarios
3. Compare outputs (should be identical for core preset)
4. Test all presets (momentum, dip_buyer, etc.)
5. Test slider variations

### 8.4 Performance Tests

```python
# tests/performance/test_planner_performance.py
import pytest
import time

@pytest.mark.asyncio
async def test_planner_performance():
    """Ensure refactored planner is not significantly slower."""
    planner = create_planner_for_core()
    context = ...

    start = time.time()
    await planner.plan(context)
    elapsed = time.time() - start

    # Should complete within reasonable time
    # (Original takes ~X seconds, allow some overhead)
    assert elapsed < ORIGINAL_TIME * 1.2  # Max 20% slower
```

---

## Migration Strategy

### Approach: Parallel Development

1. **Keep original planner working** - Don't break existing functionality
2. **Build new structure alongside** - New modules don't interfere
3. **Test incrementally** - Each module tested as extracted
4. **Switch over when ready** - Feature flag or direct replacement
5. **Remove old code** - After validation period

### Rollout Phases

**Phase 1-3: Build Foundation (Non-breaking)**
- Extract modules, create registries
- Original planner still in use
- New modules tested independently

**Phase 4-5: Configuration System (Non-breaking)**
- Build config system
- Create presets
- Not yet used by production

**Phase 6: Parallel Operation**
- New planner exists alongside old
- Feature flag: `use_modular_planner`
- Both run, compare results
- Log any differences

**Phase 7: Switchover**
- After validation period, switch default to new planner
- Keep old planner for 1 release as fallback
- Monitor metrics

**Phase 8: Cleanup**
- Remove old planner code
- Remove feature flag
- Archive regression test data

---

## Risk Mitigation

### Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Regression in results** | High | Comprehensive regression tests, parallel operation |
| **Performance degradation** | Medium | Performance tests, profiling, optimization |
| **Breaking existing integrations** | High | Keep interfaces stable, version APIs |
| **Incomplete feature extraction** | High | Detailed audit (done), checklist validation |
| **Configuration complexity** | Medium | Good defaults, presets, validation |
| **Registry initialization issues** | Low | Explicit registration, tests |

### Validation Checklist

Before declaring migration complete:
- [ ] All 100+ configuration points accounted for
- [ ] All 6 opportunity calculators working
- [ ] All 13 pattern generators working
- [ ] All 4 advanced generators working
- [ ] All 4 filters working
- [ ] Core preset produces identical results to original
- [ ] All existing tests passing
- [ ] New unit tests for all modules
- [ ] Integration tests for complete workflow
- [ ] Performance within acceptable range
- [ ] Documentation updated
- [ ] Example configurations for satellites
- [ ] Factory tested with multiple buckets

---

## Timeline Estimate

**Assuming one developer working full-time:**

| Phase | Estimated Duration | Dependencies |
|-------|-------------------|--------------|
| Phase 1: Extract calculations | 1-2 weeks | None |
| Phase 2: Create registries | 3-5 days | Phase 1 |
| Phase 3: Extract patterns | 2-3 weeks | Phase 2 |
| Phase 4: Extract generators/filters | 1-2 weeks | Phase 2 |
| Phase 5: Configuration system | 1 week | None (parallel) |
| Phase 6: Refactor planner | 1-2 weeks | Phases 1-5 |
| Phase 7: Factory & integration | 3-5 days | Phase 6 |
| Phase 8: Testing & validation | 1-2 weeks | Phase 6 |

**Total: 8-12 weeks**

**With parallel work or multiple developers: 5-8 weeks**

---

## Success Metrics

### Technical Metrics
- [ ] Zero regression in planner output (core preset)
- [ ] <20% performance overhead vs original
- [ ] 100% test coverage for new modules
- [ ] Zero circular dependencies
- [ ] All feature flags working

### Architecture Metrics
- [ ] Can create planner for any bucket in <50ms
- [ ] Can swap configurations at runtime
- [ ] Can add new calculator without touching planner
- [ ] Can add new pattern without touching planner
- [ ] Configuration validated before use

### Multi-Bucket Readiness
- [ ] Factory works with bucket database
- [ ] Independent planners don't interfere
- [ ] Batch jobs can run per-bucket
- [ ] Each bucket tracks own sequences
- [ ] Presets cover common strategies

---

## Next Steps

1. **Get approval for this plan**
2. **Set up development branch**
3. **Start Phase 1: Extract calculation modules**
4. **Create test fixtures from current planner outputs**
5. **Begin incremental extraction and testing**

---

## Questions for Discussion

1. **Timing**: Is 8-12 weeks acceptable for this refactoring?
2. **Approach**: Agree with parallel development vs direct replacement?
3. **Testing**: Need more regression test scenarios?
4. **Presets**: Are the 4 presets (core, momentum, dip_buyer, steady) sufficient to start?
5. **Parameter mapping**: Should sliders be more granular or is 5 sliders enough?
