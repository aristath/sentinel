# Holistic Planner - Complete Audit

## Overview
Comprehensive audit of all settings, calculations, parameters, and features in the current monolithic holistic planner (3,822 lines). Every item listed must be accounted for in the modular architecture.

---

## 1. Configuration Parameters (Settings)

### Core Planning Parameters
| Setting Key | Type | Default | Description |
|------------|------|---------|-------------|
| `max_plan_depth` | int | 5 | Maximum sequence depth to test |
| `max_opportunities_per_category` | int | 5 | Max opportunities per category to consider |
| `transaction_cost_fixed` | float | 2.0 | Fixed cost per trade in EUR |
| `transaction_cost_percent` | float | 0.002 | Variable cost as fraction (0.2%) |
| `priority_threshold_for_combinations` | float | 0.3 | Minimum priority for combinations |
| `batch_size` | int | 100 | Sequences to process per batch (incremental mode) |

### Combinatorial Generation Parameters
| Setting Key | Type | Default | Description |
|------------|------|---------|-------------|
| `enable_combinatorial_generation` | bool | 1.0 | Enable combinatorial sequence generation |
| `combinatorial_max_combinations_per_depth` | int | 50 | Max combinations per depth level |
| `combinatorial_max_sells` | int | 4 | Max sell actions in a combination |
| `combinatorial_max_buys` | int | 4 | Max buy actions in a combination |
| `combinatorial_max_candidates` | int | 12 | Max candidates for combinatorial generation |

### Eligibility Parameters
| Setting Key | Type | Default | Description |
|------------|------|---------|-------------|
| `min_hold_days` | int | 90 | Minimum days to hold before selling |
| `sell_cooldown_days` | int | 180 | Days between sells of same symbol |
| `max_loss_threshold` | float | -0.20 | Never sell if down more than 20% |

### Advanced Features (Toggles)
| Setting Key | Type | Default | Description |
|------------|------|---------|-------------|
| `enable_diverse_selection` | bool | 1.0 | Enable diversity-based opportunity selection |
| `diversity_weight` | float | 0.3 | Weight for diversity vs priority (0-1) |
| `enable_market_regime_scenarios` | bool | 0.0 | Enable market regime pattern generation |
| `enable_correlation_aware` | bool | 0.0 | Enable correlation-aware filtering |
| `enable_partial_execution` | bool | 0.0 | Enable partial execution scenarios |
| `enable_constraint_relaxation` | bool | 0.0 | Enable constraint relaxation scenarios |
| `enable_multi_objective` | bool | 0.0 | Enable multi-objective optimization |
| `enable_stochastic_scenarios` | bool | 0.0 | Enable stochastic price scenarios |
| `enable_monte_carlo_paths` | bool | 0.0 | Enable Monte Carlo simulation |
| `enable_multi_timeframe` | bool | 0.0 | Enable multi-timeframe analysis |

### Advanced Feature Parameters
| Setting Key | Type | Default | Description |
|------------|------|---------|-------------|
| `beam_width` | int | 10 | Beam search width for sequence selection |
| `cost_penalty_factor` | float | 0.1 | Penalty factor for transaction costs |
| `monte_carlo_path_count` | int | 100 | Number of Monte Carlo paths to simulate |
| `risk_profile` | str | null | Risk profile identifier |

---

## 2. Hardcoded Constants (from code)

### Weight Gap Thresholds
| Constant | Value | Location | Description |
|----------|-------|----------|-------------|
| Min gap threshold | 0.005 | `_calculate_weight_gaps:102` | Ignore gaps < 0.5% |
| Min gap for unowned | 0.005 | `_calculate_weight_gaps:114` | Min current weight to consider |

### Trade Worthiness
| Constant | Value | Location | Description |
|----------|-------|----------|-------------|
| Trade cost multiplier | 2.0 | `_is_trade_worthwhile:140` | Gap must be ≥ 2x trade cost |

### Rebalancing Thresholds
| Constant | Value | Location | Description |
|----------|-------|----------|-------------|
| Large gap threshold | 0.02 | `adaptive:1164` | ≥ 2% gap for adaptive patterns |
| Medium gap threshold | 0.01 | `adaptive:1174` | ≥ 1% gap for adaptive patterns |

### Correlation Filtering
| Constant | Value | Location | Description |
|----------|-------|----------|-------------|
| Correlation threshold | 0.7 | `correlation_aware:1425` | Filter if correlation > 70% |

### Diversity Scoring
| Constant | Value | Location | Description |
|----------|-------|----------|-------------|
| Overlap threshold (country) | 0.8 | `diversity:1800` | High overlap detection |
| Overlap threshold (industry) | 0.8 | `diversity:1800` | High overlap detection |
| Priority normalization | 100.0 | `diversity:1685` | Normalize priority for scoring |
| Diversity bonus factor | 0.5 | `diversity:1683` | Bonus decay per same-cluster item |

### Stochastic Scenarios
| Constant | Value | Location | Description |
|----------|-------|----------|-------------|
| Price shift scenarios | [-0.10, -0.05, 0.0, 0.05, 0.10] | `stochastic:3286` | ±10%, ±5%, base |

---

## 3. Domain Constants (from constants files)

### From app.domain.constants
| Constant | Value | Description |
|----------|-------|-------------|
| `BUY_COOLDOWN_DAYS` | 30 | Days between buys of same symbol |
| `MAX_PRICE_VS_52W_HIGH` | 0.95 | Block buys if price > 95% of 52W high |
| `MAX_POSITION_PCT` | 0.15 | Max 15% in any single position |

### From app.modules.scoring.domain.constants
| Category | Constant | Value |
|----------|----------|-------|
| **Sell Eligibility** | `DEFAULT_MIN_HOLD_DAYS` | 90 |
| | `DEFAULT_SELL_COOLDOWN_DAYS` | 180 |
| | `DEFAULT_MAX_LOSS_THRESHOLD` | -0.20 |
| | `DEFAULT_MIN_SELL_VALUE_EUR` | 100 |
| **Sell Limits** | `MIN_SELL_PCT` | 0.10 |
| | `MAX_SELL_PCT` | 0.50 |
| **Windfall Detection** | `WINDFALL_EXCESS_HIGH` | 0.50 |
| | `WINDFALL_EXCESS_MEDIUM` | 0.25 |
| | `WINDFALL_SELL_PCT_HIGH` | 0.40 |
| | `WINDFALL_SELL_PCT_MEDIUM` | 0.20 |
| | `CONSISTENT_DOUBLE_SELL_PCT` | 0.30 |

---

## 4. Opportunity Calculators

### Existing Modularized Calculators (in opportunities/)
1. **profit_taking.py** - Windfall detection and profit-taking
   - Uses `get_windfall_recommendation()`
   - Filters by `allow_sell`
   - Applies priority multiplier inversely

2. **averaging_down.py** - Quality dips to buy more of
   - Checks position exists, price below avg
   - Filters by `allow_buy`
   - Tags as "averaging_down"

3. **rebalance_sells.py** - Overweight positions to reduce
   - Checks country/industry allocations
   - Filters ineligible and recently sold
   - Uses priority multiplier inversely

4. **rebalance_buys.py** - Underweight areas to increase
   - Checks country/industry allocations
   - Filters recently bought
   - Uses priority multiplier directly

5. **opportunity_buys.py** - High-quality opportunities
   - Score-based filtering
   - Checks trade size worthwhile
   - Filters recently bought

### Weight-Based Calculator (not yet extracted)
**identify_opportunities_from_weights()**
- Uses optimizer target weights
- Calculates weight gaps
- Generates buy/sell candidates based on gaps
- Filters by trade worthiness
- Applies priority multipliers

---

## 5. Pattern Generators

### Basic Patterns (all in holistic_planner.py)
1. **Direct Buy** (`_generate_direct_buy_pattern:752`)
   - If cash available, buy top opportunities

2. **Profit Taking** (`_generate_profit_taking_pattern:773`)
   - Sell windfall, reinvest in top buys

3. **Rebalance** (`_generate_rebalance_pattern:796`)
   - Sell overweight, buy underweight

4. **Averaging Down** (`_generate_averaging_down_pattern:820`)
   - Buy quality dips only

5. **Single Best** (`_generate_single_best_pattern:845`)
   - Single highest-priority action

6. **Multi-Sell** (`_generate_multi_sell_pattern:878`)
   - Multiple sells only (no buys)

7. **Mixed Strategy** (`_generate_mixed_strategy_pattern:912`)
   - 1-2 sells + 1-2 buys

8. **Opportunity First** (`_generate_opportunity_first_pattern:947`)
   - Prioritize opportunity buys

9. **Deep Rebalance** (`_generate_deep_rebalance_pattern:976`)
   - Multiple rebalance actions

10. **Cash Generation** (`_generate_cash_generation_pattern:1005`)
    - Focus on generating cash

11. **Cost Optimized** (`_generate_cost_optimized_pattern:1039`)
    - Minimize transaction costs

### Advanced Pattern Generators
12. **Adaptive Patterns** (`_generate_adaptive_patterns:1091`)
    - Adapt based on portfolio state
    - 9 different pattern types based on conditions

13. **Market Regime Patterns** (`_generate_market_regime_patterns:1234`)
    - Adapt based on market regime
    - Different patterns for bull/bear/sideways

---

## 6. Sequence Generators (Advanced)

### Combinatorial Generation
1. **Enhanced Combinations** (`_generate_enhanced_combinations:1696`)
   - Smart combinatorial generation
   - Filters by priority threshold
   - Limits on sells/buys
   - Considers country/industry diversity

2. **Basic Combinations** (`_generate_combinations:1878`)
   - Simple combinatorial approach
   - All combinations of high-priority actions

### Scenario Generators
3. **Partial Execution** (`_generate_partial_execution_scenarios:1464`)
   - Simulate partial fills
   - Generate 50%, 75%, 100% fill scenarios

4. **Constraint Relaxation** (`_generate_constraint_relaxation_scenarios:1504`)
   - Relax constraints (allow_sell, min_lot, etc.)
   - Test "what if" scenarios

---

## 7. Sequence Filters

### Implemented Filters
1. **Correlation-Aware** (`_filter_correlation_aware_sequences:1354`)
   - Filter highly correlated sequences
   - Uses correlation threshold (0.7)
   - Requires securities data

2. **Diversity Selection** (`_select_diverse_opportunities:1581`)
   - Cluster by country/industry
   - Balance priority vs diversity
   - Configurable diversity weight

### Implicit Filters (built-in)
3. **Eligibility** (in opportunity identification)
   - Min hold days
   - Sell cooldown
   - Max loss threshold
   - allow_buy/allow_sell flags

4. **Recently Traded** (in opportunity identification)
   - Buy cooldown (30 days)
   - Sell cooldown (180 days)

---

## 8. Simulation & Evaluation

### Portfolio Simulation
**simulate_sequence()** (`holistic_planner:2260`)
- Applies sequence to portfolio state
- Tracks cash changes
- Updates positions
- Handles price adjustments (for scenarios)
- Returns final PortfolioContext + cash

### Sequence Evaluation
**Evaluation Components:**
1. **End-state scoring** - `calculate_portfolio_end_state_score()`
2. **Diversification** - `calculate_portfolio_score()`
3. **Transaction costs** - `_calculate_transaction_cost()`
4. **Risk scoring** - From multi-objective mode
5. **Cost penalty** - Applied if `cost_penalty_factor > 0`

### Multi-Objective Evaluation
**SequenceEvaluation dataclass:**
- `end_score` - Primary objective (0-1)
- `diversification_score` - Diversification (0-1)
- `risk_score` - Risk measure (0-1)
- `transaction_cost` - Total cost in EUR
- Pareto dominance checking

---

## 9. Advanced Features (Experimental)

### Stochastic Scenarios
- Price shifts: ±10%, ±5%, base
- Evaluates sequence under different price movements
- Weighted scoring across scenarios

### Monte Carlo Simulation
- Configurable path count
- Simulates random price movements
- Aggregates results across paths

### Multi-Timeframe Analysis
- Evaluates sequences across different time horizons
- Not fully implemented

### Beam Search
- Configurable beam width
- Keeps top N sequences at each depth
- Uses multi-objective or single-objective scoring

---

## 10. Incremental Processing

### Database Integration
**Tables Used:**
- `sequences` - Generated action sequences
- `evaluations` - Evaluation results
- `best_result` - Best sequence found

### Process Flow
1. **First run**: Generate all sequences, store in DB
2. **Subsequent runs**:
   - Fetch next batch (priority order)
   - Evaluate batch
   - Update best result
   - Mark sequences completed
3. **Return**: Best result from DB

### Batch Processing
- Configurable batch size (default 100)
- Priority-ordered processing
- Incremental best tracking
- Portfolio hash for cache invalidation

---

## 11. Narrative Generation (Separate Module)

**Already extracted to domain/narrative.py:**
- `generate_step_narrative()` - Per-action narrative
- `generate_plan_narrative()` - Overall plan summary
- `generate_tradeoff_explanation()` - Trade-off reasoning
- `format_action_summary()` - One-line summary

**Dependencies:**
- ActionCandidate tags
- PortfolioContext
- All opportunities (for context)

---

## 12. Data Models

### Core Dataclasses
1. **ActionCandidate**
   - side, symbol, name, quantity, price
   - value_eur, currency
   - priority, reason, tags

2. **HolisticStep**
   - step_number, side, symbol, name, quantity
   - estimated_price, estimated_value, currency
   - reason, narrative
   - is_windfall, is_averaging_down, contributes_to

3. **HolisticPlan**
   - steps, current_score, end_state_score, improvement
   - narrative_summary, score_breakdown
   - cash_required, cash_generated, feasible

4. **SequenceEvaluation**
   - sequence, end_score, diversification_score, risk_score
   - transaction_cost, breakdown
   - `is_dominated_by()` method for Pareto checking

---

## 13. Helper Functions

### Utilities
- `_calculate_transaction_cost()` - Cost calculation
- `_hash_sequence()` - Deterministic sequence hashing
- `_calculate_weight_gaps()` - Target vs current weights
- `_is_trade_worthwhile()` - Trade size validation
- `_compute_ineligible_symbols()` - Sell eligibility check
- `_process_buy_opportunity()` - Weight gap → buy candidate
- `_process_sell_opportunity()` - Weight gap → sell candidate

---

## 14. External Dependencies

### Repository Dependencies
- `SettingsRepository` - All settings
- `TradeRepository` - Recently traded symbols, last transaction dates
- `PositionRepository` - Current positions
- `SecurityRepository` - Security data
- `AllocationRepository` - Allocation targets
- `GroupingRepository` - Country/industry groupings

### Service Dependencies
- `ExchangeRateService` - Currency conversion
- `PortfolioOptimizer` - Target weights
- Yahoo Finance - Current prices
- Windfall detection - `get_windfall_recommendation()`
- Sell eligibility - `check_sell_eligibility()`
- Min trade amount - `calculate_min_trade_amount()`

### Scoring Dependencies
- `calculate_portfolio_score()` - Diversification score
- `calculate_portfolio_end_state_score()` - End-state holistic score

---

## 15. Parameter Relationships

### Interdependent Parameters
1. **Batch size vs depth**
   - Larger depth → more sequences → may need smaller batch

2. **Priority threshold vs combinatorial**
   - Lower threshold → more combinations
   - Higher threshold → fewer, higher-quality combinations

3. **Diversity weight vs max opportunities**
   - Higher diversity weight → broader selection
   - More opportunities → more room for diversity

4. **Transaction costs vs trade worthiness**
   - Higher costs → fewer small trades
   - Affects rebalance and optimization behavior

### Feature Interactions
1. **Diverse selection + combinatorial**
   - Both affect sequence diversity
   - May need coordination

2. **Multi-objective + beam search**
   - Beam keeps multiple objectives
   - Pareto frontier selection

3. **Stochastic + Monte Carlo**
   - Both add robustness testing
   - May be redundant if both enabled

---

## 16. Missing/Future Features

### Noted in Code but Not Implemented
1. Enhanced combinatorial flag check (line 2123)
   - Checks `enable_enhanced_combinatorial` but uses hardcoded True

2. Risk profile usage (line 3296)
   - Fetches but doesn't use

3. Multi-timeframe partial implementation
   - Flag exists but logic minimal

---

## Summary Statistics

- **Total Settings**: 27
- **Hardcoded Constants**: 15+
- **Domain Constants**: 30+
- **Opportunity Calculators**: 6 (5 extracted, 1 in monolith)
- **Pattern Generators**: 13
- **Sequence Generators**: 4
- **Sequence Filters**: 4 (2 implemented, 2 implicit)
- **Advanced Features**: 8 toggleable features
- **Data Models**: 4 core dataclasses
- **Helper Functions**: 7+
- **External Dependencies**: 5 repositories, 5+ services

**Total Configurable Points**: ~100+

---

## Notes for Modular Architecture

### Critical Requirements
1. **Every setting must be configurable per bucket**
2. **Every feature must be toggleable per bucket**
3. **Every calculator must be pluggable**
4. **Every pattern must be selectable**
5. **All hardcoded constants should become parameters**

### Architecture Implications
- Need registry system for calculators, patterns, generators, filters
- Need configuration schema supporting all parameters
- Need parameter validation and interdependency checking
- Need preset system for common configurations
- Need parameter mapping from sliders to technical parameters
