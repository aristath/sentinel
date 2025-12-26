# Arduino Trader Architecture Refactoring Plan

## Current Issues Identified

1. **No Dependency Injection**: Repositories and services are instantiated directly in API endpoints (`PositionRepository()`, `RebalancingService()`)
2. **Inconsistent Service Patterns**: Some services use optional parameters with defaults, creating new instances internally
3. **Mixed Responsibilities**: `app/services/` contains both infrastructure (yahoo, tradernet) and domain logic
4. **Tight Coupling**: Services directly import infrastructure modules (`get_db_manager()`, `get_tradernet_client()`)
5. **Inconsistent Repository Pattern**: Mix of protocols and concrete classes
6. **Testing Difficulties**: Hard to mock dependencies due to direct instantiation
7. **Large Monolithic Files**: Some files are too large (e.g., `rebalancing_service.py` ~1330 lines, `trades.py` ~1228 lines) and handle multiple responsibilities

## Refactoring Strategy

### Phase 1: Dependency Injection Container

**Goal**: Create a centralized DI container using FastAPI's dependency system**Changes**:

- Create `app/infrastructure/dependencies.py` with FastAPI dependency functions for all repositories
- Create dependency functions for all application services
- Update all API endpoints to use `Depends()` instead of direct instantiation

**Files to modify**:

- Create: `app/infrastructure/dependencies.py`
- Update: All files in `app/api/` (portfolio.py, trades.py, stocks.py, etc.)
- Update: `app/main.py` (if needed)

### Phase 2: Reorganize Service Layer

**Goal**: Move infrastructure services out of `app/services/` and into `app/infrastructure/`**Changes**:

- Move `app/services/yahoo.py` → `app/infrastructure/external/yahoo_finance.py`
- Move `app/services/tradernet.py` → `app/infrastructure/external/tradernet.py`
- Move `app/services/tradernet_connection.py` → `app/infrastructure/external/tradernet_connection.py`
- Move `app/services/allocator.py` → `app/domain/services/allocation_calculator.py` (domain logic)
- Update all imports across the codebase

**Files to modify**:

- Move and refactor: `app/services/yahoo.py`
- Move and refactor: `app/services/tradernet.py`
- Move and refactor: `app/services/tradernet_connection.py`
- Move and refactor: `app/services/allocator.py`
- Update: All files importing from `app.services`
- Delete: `app/services/` directory entirely after migration

### Phase 3: Remove Optional Dependencies with Defaults

**Goal**: Make all dependencies explicit and required**Changes**:

- Update `RebalancingService.__init__()` to require all repositories (remove `Optional` with defaults)
- Update `ScoringService` if it has similar patterns
- Update any other services with optional dependencies

**Files to modify**:

- `app/application/services/rebalancing_service.py`
- `app/application/services/scoring_service.py`
- Any other services with optional dependencies

### Phase 4: Remove Direct Infrastructure Imports from Services

**Goal**: Services should receive infrastructure dependencies, not import them**Changes**:

- Remove `get_db_manager()` calls from services - pass database manager as dependency
- Remove `get_tradernet_client()` calls from services - pass client as dependency or use a factory
- Update service constructors to accept these dependencies

**Files to modify**:

- `app/application/services/rebalancing_service.py` (remove `get_db_manager()`)
- `app/application/services/scoring_service.py` (remove `get_db_manager()`)
- `app/application/services/trade_execution_service.py` (remove `get_tradernet_client()`)
- Create factory functions in `app/infrastructure/dependencies.py` for infrastructure services

### Phase 5: Standardize Internal Response Types

**Goal**: Create standardized response types so changing format in one place affects all consumers**Current Issues**:

1. **Inconsistent Return Types**: Some functions return tuples `(score, subs)`, others return `Optional[float]`, others return dicts
2. **No Standard Error Handling**: Some return `None` on error, others raise exceptions
3. **Inconsistent Data Structures**: Similar data returned in different formats
4. **Hard to Refactor**: Changing return format requires updating all consumers

**Proposed Standard Response Types**:

```python
# app/domain/responses/__init__.py

# Standard calculation result (for all calculations)
@dataclass
class CalculationResult:
    """Standard result for any calculation."""
    value: float
    sub_components: Dict[str, float]  # Breakdown of calculation
    metadata: Optional[Dict[str, Any]] = None  # Additional context
    
# Standard score result (for scoring functions)
@dataclass
class ScoreResult:
    """Standard result for scoring functions."""
    score: float  # Main score (0-1)
    sub_scores: Dict[str, float]  # Component scores
    confidence: Optional[float] = None  # How confident we are in this score
    
# Standard service result (for service operations)
@dataclass
class ServiceResult[T]:
    """Generic service result with success/error handling."""
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
# Standard list result (for operations returning lists)
@dataclass
class ListResult[T]:
    """Standard result for list operations."""
    items: List[T]
    total: int
    metadata: Optional[Dict[str, Any]] = None
```

**Benefits**:

- **Single Source of Truth**: Change format in one place, all consumers adapt
- **Type Safety**: Clear types for all responses
- **Consistency**: All functions return same structure
- **Easy to Extend**: Add fields to base type, all consumers get them
- **Easy to Refactor**: Change internal structure without breaking consumers

**Example Refactoring**:**Before** (inconsistent):

```python
# long_term.py
async def calculate_long_term_score(...) -> tuple:
    return (total_score, {"cagr": 0.8, "sharpe": 0.7})

# opportunity.py  
async def calculate_opportunity_score(...) -> tuple:
    return (total_score, {"below_52w": 0.9, "pe": 0.6})

# Some functions return None on error, others raise
```

**After** (standardized):

```python
# All scoring functions use same type
from app.domain.responses import ScoreResult

async def calculate_long_term_score(...) -> ScoreResult:
    return ScoreResult(
        score=total_score,
        sub_scores={"cagr": 0.8, "sharpe": 0.7},
        confidence=0.95
    )

async def calculate_opportunity_score(...) -> ScoreResult:
    return ScoreResult(
        score=total_score,
        sub_scores={"below_52w": 0.9, "pe": 0.6},
        confidence=0.90
    )

# All calculation functions use same type
from app.domain.responses import CalculationResult

def calculate_cagr(...) -> CalculationResult:
    return CalculationResult(
        value=cagr_value,
        sub_components={"5y": 0.11, "10y": 0.10},
        metadata={"months_used": 60}
    )
```

**Files to create**:

- `app/domain/responses/__init__.py` - All standard response types
- `app/domain/responses/calculation.py` - Calculation result types
- `app/domain/responses/score.py` - Score result types
- `app/domain/responses/service.py` - Service result types

**Files to update**:

- All scoring functions → Use `ScoreResult`
- All calculation functions → Use `CalculationResult`
- All service methods → Use `ServiceResult[T]`
- Update all consumers to use new types

**Common Patterns to Standardize**:

1. **Score Calculations** (currently return `tuple[float, Dict]`):
   ```python
      # Before
      async def calculate_long_term_score(...) -> tuple:
          return (0.85, {"cagr": 0.8, "sharpe": 0.7})
      
      # After
      async def calculate_long_term_score(...) -> ScoreResult:
          return ScoreResult(
              score=0.85,
              sub_scores={"cagr": 0.8, "sharpe": 0.7},
              confidence=0.95
          )
   ```




2. **Raw Calculations** (currently return `Optional[float]`):
   ```python
      # Before
      def calculate_cagr(...) -> Optional[float]:
          if insufficient_data:
              return None
          return 0.11
      
      # After
      def calculate_cagr(...) -> CalculationResult:
          if insufficient_data:
              return CalculationResult(
                  value=0.0,
                  sub_components={},
                  metadata={"error": "insufficient_data"}
              )
          return CalculationResult(
              value=0.11,
              sub_components={"5y": 0.11, "10y": 0.10},
              metadata={"months_used": 60}
          )
   ```




3. **Service Operations** (currently inconsistent error handling):
   ```python
      # Before
      async def get_recommendations(...) -> List[Recommendation]:
          if error:
              return []  # or raise exception
          return recommendations
      
      # After
      async def get_recommendations(...) -> ServiceResult[List[Recommendation]]:
          if error:
              return ServiceResult(
                  success=False,
                  error="Failed to fetch recommendations",
                  data=None
              )
          return ServiceResult(
              success=True,
              data=recommendations,
              metadata={"count": len(recommendations)}
          )
   ```


**Migration Strategy**:

1. Create standard types in `app/domain/responses/`
2. Update scoring functions first (most used)
3. Update calculation functions
4. Update service methods
5. Update all consumers incrementally
6. Remove old tuple/None returns

### Phase 6: Standardize Repository Pattern

**Goal**: Use consistent repository interfaces**Changes**:

- Review `app/domain/repositories/protocols.py` - ensure all repositories have protocol definitions
- Update concrete repositories in `app/repositories/` to implement protocols
- Update type hints in services to use protocols

**Files to modify**:

- `app/domain/repositories/protocols.py` (ensure completeness)
- `app/repositories/*.py` (ensure they implement protocols)
- `app/application/services/*.py` (use protocol types)

### Phase 7: Refactor Scoring System for Better Modularity

**Goal**: Improve scoring system organization by separating calculations from scoring logic and eliminating duplication**Current Issues Identified**:

1. **Code Duplication**: `calculate_cagr()` is duplicated in both `long_term.py` and `fundamentals.py`
2. **Mixed Concerns**: Calculation logic mixed with caching logic in same files
3. **Inconsistent Patterns**: Some calculations in group files, others in `technical.py`
4. **Unclear Boundaries**: Hard to know where to find a specific calculation

**Proposed Structure**:

```javascript
app/domain/scoring/
├── calculations/          # Pure calculation functions (no caching, no scoring)
│   ├── __init__.py
│   ├── cagr.py           # CAGR calculation (single source of truth)
│   ├── sharpe.py         # Sharpe ratio calculation
│   ├── sortino.py        # Sortino ratio calculation
│   ├── volatility.py     # Volatility calculation
│   ├── drawdown.py       # Max drawdown calculation
│   ├── technical_indicators.py  # EMA, RSI, Bollinger calculations
│   └── financial_metrics.py     # P/E, debt/equity, etc.
│
├── scorers/              # Scoring functions (convert metrics to 0-1 scores)
│   ├── __init__.py
│   ├── cagr_scorer.py    # CAGR → score conversion
│   ├── sharpe_scorer.py  # Sharpe → score conversion
│   ├── pe_scorer.py      # P/E → score conversion
│   └── ...               # Other scoring functions
│
├── groups/               # Score group orchestrators (combine calculations + scorers)
│   ├── __init__.py
│   ├── long_term.py      # Orchestrates CAGR, Sharpe, Sortino
│   ├── fundamentals.py   # Orchestrates financial strength, consistency
│   ├── opportunity.py    # Orchestrates 52W high, P/E
│   └── ...               # Other groups
│
├── caching/              # Caching wrappers (separate from calculations)
│   ├── __init__.py
│   └── metric_cache.py   # Cache get/set operations
│
├── stock_scorer.py       # Main orchestrator (combines all groups)
└── ...                   # Other existing files (models, constants, etc.)
```

**Benefits**:

- **Single Source of Truth**: Each calculation exists in exactly one place
- **Clear Separation**: Calculations → Scorers → Groups → Orchestrator
- **Easy to Test**: Pure calculation functions are easy to unit test
- **Easy to Find**: Know exactly where to look for any calculation
- **Easy to Modify**: Change CAGR calculation in one place, affects all users

**Example Refactoring**:**Before** (duplicated):

```python
# long_term.py
def calculate_cagr(prices, months): ...

# fundamentals.py  
def calculate_cagr(prices, months): ...  # DUPLICATE!
```

**After** (single source):

```python
# calculations/cagr.py
def calculate_cagr(prices: List[Dict], months: int) -> Optional[float]:
    """Single source of truth for CAGR calculation."""
    ...

# groups/long_term.py
from app.domain.scoring.calculations.cagr import calculate_cagr
cagr = calculate_cagr(monthly_prices, 60)

# groups/fundamentals.py
from app.domain.scoring.calculations.cagr import calculate_cagr
cagr = calculate_cagr(monthly_prices, 60)
```

**Files to refactor**:

- Extract `calculate_cagr` from `long_term.py` and `fundamentals.py` → `calculations/cagr.py`
- Extract scoring functions (e.g., `score_cagr`, `score_sharpe`) → `scorers/`
- Move group orchestrators to `groups/` directory
- Create caching layer to separate cache logic from calculations
- Update all imports

### Phase 8: Modularize Large Files

**Goal**: Split large files into smaller, single-responsibility modules with clear APIs**Principles**:

- **Single Responsibility**: Each file should have one clear purpose
- **Stable API**: Each module should have a well-defined, stable interface
- **Clear Input/Output**: Functions should have explicit, typed inputs and outputs
- **Size Limit**: Target ~200-300 lines per file (max ~500 lines)
- **Modularity**: Changes to one module should not require changes to others

**Files to split**:

1. **`app/application/services/rebalancing_service.py`** (~1330 lines)

- Split into:
- `rebalancing_service.py` - Main orchestration (public API)
- `recommendation_generator.py` - Buy recommendation generation logic
- `sell_recommendation_generator.py` - Sell recommendation generation logic
- `portfolio_context_builder.py` - Portfolio context construction
- `technical_data_calculator.py` - Technical indicator calculations
- `performance_adjustment_calculator.py` - Performance-adjusted weights

2. **`app/api/trades.py`** (~1228 lines)

- Split into:
- `trades.py` - Basic trade endpoints (GET, POST /execute)
- `recommendations.py` - Recommendation endpoints
- `multi_step_recommendations.py` - Multi-step recommendation endpoints
- Note: Funding functionality removed (holistic recommendations handle this)

3. **`app/services/yahoo.py`** (~419 lines)

- Split into:
- `yahoo_finance_client.py` - Core API client
- `symbol_converter.py` - Symbol format conversion
- `analyst_data_fetcher.py` - Analyst data fetching
- `fundamental_data_fetcher.py` - Fundamental data fetching
- `price_fetcher.py` - Price data fetching

4. **`app/application/services/trade_execution_service.py`** (~365 lines)

- Split into:
- `trade_execution_service.py` - Main orchestration
- `trade_recorder.py` - Trade recording logic
- `currency_converter.py` - Currency conversion handling
- `trade_validator.py` - Trade validation logic

**Files to modify**:

- Split large files as identified above
- Update all imports
- Ensure each new file has clear docstrings explaining its responsibility
- Add type hints to all public APIs

### Phase 9: Clean Up Dead Code and Legacy Patterns

**Goal**: Remove all legacy code, unused imports, and deprecated patterns**Changes**:

- Search for and remove any unused imports
- Delete any functions/classes that are no longer referenced
- Remove any `# TODO` or `# FIXME` comments related to old architecture
- Clean up any duplicate code patterns
- Remove any workarounds or hacks that are no longer needed

**Files to review**:

- All files in `app/` directory
- Check for unused imports with tools like `ruff` or `pylint`
- Remove any commented-out code blocks

### Phase 9: Update Tests

**Goal**: Ensure tests work with new dependency injection pattern**Changes**:

- Update test fixtures to use dependency injection
- Create mock repositories that can be injected
- Update integration tests to use DI container
- Remove any tests for deprecated patterns

**Files to modify**:

- `tests/conftest.py` (add DI fixtures)
- All test files in `tests/unit/` and `tests/integration/`

## Implementation Strategy: Atomic Tasks

**Key Principles**:

- **One task = One focused change** (max 3-5 files per task)
- **Each task is testable** (can verify it works before moving on)
- **Tasks are independent** (can be done in any order within a phase)
- **Incremental progress** (each task builds on previous)
- **Run tests after each task** (catch issues early)

## Phase 0: Test Foundation (TDD Preparation)

**Goal**: Ensure all existing tests pass before starting refactoring**Task 0.1**: Run all existing tests and document failures

- Run `pytest` or `composer test` to get baseline
- Document any failing tests
- **Files**: 0 (just running tests)
- **Test**: Tests run successfully (may fail, that's expected)

**Task 0.2**: Fix failing unit tests

- Fix any unit test failures
- **Files**: Test files that need fixing
- **Test**: All unit tests pass

**Task 0.3**: Fix failing integration tests

- Fix any integration test failures
- **Files**: Integration test files that need fixing
- **Test**: All integration tests pass

**Task 0.4**: Verify test coverage baseline

- Run coverage report to understand current coverage
- Document coverage metrics
- **Files**: 0 (just running coverage)
- **Test**: Coverage report generated

**Task 0.5**: Add missing tests for critical paths (if needed)

- Identify critical paths without tests
- Add basic tests for those paths
- **Files**: New test files
- **Test**: New tests pass

## Task Breakdown by Phase

### Phase 1: Dependency Injection Container (Foundation)

**Task 1.1**: Create dependencies.py with repository dependencies

- Create `app/infrastructure/dependencies.py`
- Add dependency functions for: StockRepository, PositionRepository, TradeRepository
- **Files**: 1 new file
- **Test**: Import and verify functions work

**Task 1.2**: Add more repository dependencies

- Add: PortfolioRepository, AllocationRepository, ScoreRepository, SettingsRepository
- **Files**: 1 file (dependencies.py)
- **Test**: Import and verify

**Task 1.3**: Add application service dependencies

- Add: PortfolioService, ScoringService dependencies
- **Files**: 1 file (dependencies.py)
- **Test**: Import and verify

**Task 1.4**: Update portfolio.py API to use DI

- **TDD Step 1 (RED)**: Update API tests to use DI pattern
- Update tests in `tests/integration/test_api_portfolio.py` (or create if missing)
- Mock dependencies using FastAPI's TestClient
- Verify endpoints work with injected dependencies
- Run tests - may fail if tests don't exist yet
- **TDD Step 2 (GREEN)**: Replace direct instantiation with `Depends()`
- Update `get_portfolio()` endpoint to use `Depends(get_position_repository)`
- Update `get_portfolio_summary()` endpoint to use `Depends(get_portfolio_service)`
- Make tests pass
- **TDD Step 3 (VERIFY)**: Run all tests - `pytest tests/ -v`
- All API tests pass
- All existing tests still pass
- **Files**: 1 file (app/api/portfolio.py) + test updates
- **Test Command**: `pytest tests/integration/ -k portfolio -v`

**Task 1.5**: Update stocks.py API to use DI

- Replace direct instantiation with `Depends()`
- **Files**: 1 file (app/api/stocks.py)
- **Test**: Run API endpoint, verify it works

**Task 1.6**: Update trades.py API to use DI (part 1 - basic endpoints)

- Update `get_trades()` and `execute_trade()` endpoints
- **Files**: 1 file (app/api/trades.py)
- **Test**: Run API endpoints, verify they work

**Task 1.7**: Update trades.py API to use DI (part 2 - recommendation endpoints)

- Update recommendation-related endpoints
- **Files**: 1 file (app/api/trades.py)
- **Test**: Run API endpoints, verify they work

**Task 1.8**: Update remaining API files to use DI

- Update: allocation.py, cash_flows.py, charts.py, settings.py, status.py
- **Files**: 5 files
- **Test**: Run each API endpoint, verify they work

### Phase 2: Service Reorganization (Move Files)

**Task 2.1**: Move yahoo.py to infrastructure/external

- Move file and update imports in 1-2 key files first
- **Files**: 1 move + 2-3 import updates
- **Test**: Import works, basic function call works

**Task 2.2**: Update all yahoo.py imports across codebase

- Find and update all `from app.services.yahoo import` statements
- **Files**: ~10-15 files (grep to find all)
- **Test**: Run tests, verify no import errors

**Task 2.3**: Move tradernet.py to infrastructure/external

- Move file and update imports in 1-2 key files first
- **Files**: 1 move + 2-3 import updates
- **Test**: Import works, basic function call works

**Task 2.4**: Update all tradernet.py imports

- Find and update all imports
- **Files**: ~10-15 files
- **Test**: Run tests, verify no import errors

**Task 2.5**: Move tradernet_connection.py

- Move file and update imports
- **Files**: 1 move + ~5 import updates
- **Test**: Run tests, verify no import errors

**Task 2.6**: Move allocator.py to domain/services

- Move file and update imports
- **Files**: 1 move + ~5 import updates
- **Test**: Run tests, verify no import errors

**Task 2.7**: Delete app/services/ directory

- Remove directory after verifying all imports updated
- **Files**: Delete directory
- **Test**: Run full test suite, verify everything works

### Phase 3: Remove Optional Dependencies

**Task 3.1**: Update RebalancingService constructor

- Remove `Optional` with defaults, make all required
- **Files**: 1 file (rebalancing_service.py)
- **Test**: Import fails (expected), will fix in next task

**Task 3.2**: Update RebalancingService callers

- Update all places that create RebalancingService to pass all dependencies
- **Files**: ~5-10 files (grep for `RebalancingService()`)
- **Test**: Import works, service can be instantiated

**Task 3.3**: Update ScoringService if needed

- Check if it has optional dependencies, fix if needed
- **Files**: 1-2 files
- **Test**: Service works

### Phase 4: Remove Direct Infrastructure Imports

**Task 4.1**: Add database manager dependency to dependencies.py

- Create dependency function for database manager
- **Files**: 1 file (dependencies.py)
- **Test**: Import works

**Task 4.2**: Update RebalancingService to accept db_manager

- Remove `get_db_manager()` call, accept as parameter
- **Files**: 1 file (rebalancing_service.py)
- **Test**: Service works with injected db_manager

**Task 4.3**: Update RebalancingService callers to pass db_manager

- Update all places that create RebalancingService
- **Files**: ~5 files
- **Test**: Service works

**Task 4.4**: Update ScoringService to accept db_manager

- Remove `get_db_manager()` call, accept as parameter
- **Files**: 1 file (scoring_service.py)
- **Test**: Service works

**Task 4.5**: Update ScoringService callers

- Update all places that create ScoringService
- **Files**: ~3-5 files
- **Test**: Service works

**Task 4.6**: Update TradeExecutionService to accept tradernet_client

- Remove `get_tradernet_client()` call, accept as parameter
- **Files**: 1 file (trade_execution_service.py)
- **Test**: Service works

**Task 4.7**: Update TradeExecutionService callers

- Update all places that create TradeExecutionService
- **Files**: ~5 files
- **Test**: Service works

### Phase 5: Standardize Internal Response Types

**Task 5.1**: Create response types module

- Create `app/domain/responses/__init__.py` with base types
- **Files**: 1 new file
- **Test**: Import works, can create instances

**Task 5.2**: Update one scoring function as proof of concept

- Update `calculate_long_term_score()` to return `ScoreResult`
- **Files**: 1 file (long_term.py)
- **Test**: Function works, returns ScoreResult

**Task 5.3**: Update long_term.py consumer

- Update code that calls `calculate_long_term_score()` to use new format
- **Files**: 1 file (stock_scorer.py)
- **Test**: Scoring still works

**Task 5.4**: Update remaining scoring functions (part 1)

- Update: fundamentals.py, opportunity.py
- **Files**: 2 files
- **Test**: Each function works

**Task 5.5**: Update remaining scoring functions (part 2)

- Update: dividends.py, short_term.py, technicals.py
- **Files**: 3 files
- **Test**: Each function works

**Task 5.6**: Update remaining scoring functions (part 3)

- Update: opinion.py, diversification.py
- **Files**: 2 files
- **Test**: Each function works

**Task 5.7**: Update stock_scorer.py to use all new ScoreResult types

- Update orchestrator to handle all ScoreResult returns
- **Files**: 1 file (stock_scorer.py)
- **Test**: Full scoring pipeline works

**Task 5.8**: Update calculation functions (CAGR first)

- Extract `calculate_cagr` to use `CalculationResult`
- **Files**: 1 file (create calculations/cagr.py)
- **Test**: Function works

**Task 5.9**: Update CAGR consumers

- Update long_term.py and fundamentals.py to use new CAGR
- **Files**: 2 files
- **Test**: Scoring still works

**Task 5.10**: Update more calculation functions

- Update: Sharpe, Sortino, volatility calculations
- **Files**: 3-4 files
- **Test**: Each works

### Phase 6: Standardize Repositories

**Task 6.1**: Review and complete protocols.py

- Ensure all repositories have protocol definitions
- **Files**: 1 file (protocols.py)
- **Test**: All protocols defined

**Task 6.2**: Update one repository to implement protocol

- Update StockRepository to explicitly implement IStockRepository
- **Files**: 1 file (repositories/stock.py)
- **Test**: Repository works, type checks pass

**Task 6.3**: Update remaining repositories

- Update all other repositories to implement protocols
- **Files**: ~7 files
- **Test**: Each repository works

**Task 6.4**: Update service type hints

- Update services to use protocol types instead of concrete
- **Files**: ~5 files
- **Test**: Type checks pass, services work

### Phase 7: Refactor Scoring System

**Task 7.1**: Extract CAGR calculation to separate file

- Create `calculations/cagr.py`, move function there
- **Files**: 1 new file + 2 updates (remove from long_term.py and fundamentals.py)
- **Test**: CAGR calculation works

**Task 7.2**: Extract Sharpe calculation

- Create `calculations/sharpe.py` or add to risk_metrics.py
- **Files**: 1 new file + 1 update
- **Test**: Calculation works

**Task 7.3**: Extract Sortino calculation

- Add to risk_metrics.py
- **Files**: 1 file
- **Test**: Calculation works

**Task 7.4**: Create scorers directory and move scoring functions

- Create `scorers/cagr_scorer.py`, move `score_cagr()` there
- **Files**: 1 new file + 1 update
- **Test**: Scoring works

**Task 7.5**: Move more scoring functions

- Move: score_sharpe, score_sortino, score_pe_ratio
- **Files**: 3 new files + 3 updates
- **Test**: Each scorer works

**Task 7.6**: Create groups directory and move group orchestrators

- Move long_term.py, fundamentals.py to groups/
- **Files**: 2 moves + update imports
- **Test**: Groups work

**Task 7.7**: Move remaining groups

- Move: opportunity.py, dividends.py, etc. to groups/
- **Files**: 5 moves + update imports
- **Test**: All groups work

**Task 7.8**: Create caching layer

- Create `caching/metric_cache.py` for cache operations
- **Files**: 1 new file
- **Test**: Caching works

**Task 7.9**: Update groups to use caching layer

- Refactor groups to use new caching module
- **Files**: ~7 files
- **Test**: Caching works, groups work

### Phase 8: Modularize Large Files

**Task 8.1**: Extract buy recommendation generator from RebalancingService

- **TDD Step 1 (RED)**: Write tests for buy recommendation generator
- Test that it generates buy recommendations correctly
- Test filtering logic (cooldown, allow_buy, etc.)
- **TDD Step 2 (GREEN)**: Create `recommendation_generator_buy.py`, move buy recommendation logic
- Extract `get_recommendations()` logic from RebalancingService
- Make tests pass
- **TDD Step 3 (VERIFY)**: Run all tests - `pytest tests/ -v`
- **Files**: 1 new file + 1 update (rebalancing_service.py) + 1 test file
- **Test Command**: `pytest tests/ -k recommendation -v`

**Task 8.2**: Extract sell recommendation generator

- **TDD Step 1 (RED)**: Write tests for sell recommendation generator
- Test that it generates sell recommendations correctly
- Test filtering logic (eligibility, band checks, etc.)
- **TDD Step 2 (GREEN)**: Create `recommendation_generator_sell.py`
- Extract `calculate_sell_recommendations()` logic from RebalancingService
- Make tests pass
- **TDD Step 3 (VERIFY)**: Run all tests - `pytest tests/ -v`
- **Files**: 1 new file + 1 update + 1 test file
- **Test Command**: `pytest tests/ -k sell -v`

**Task 8.3**: Extract portfolio context builder

- Create `portfolio_context_builder.py`
- **Files**: 1 new file + 1 update
- **Test**: Context building works

**Task 8.4**: Extract technical data calculator

- Create `technical_data_calculator.py`
- **Files**: 1 new file + 1 update
- **Test**: Technical data works

**Task 8.5**: Extract performance adjustment calculator

- Create `performance_adjustment_calculator.py`
- **Files**: 1 new file + 1 update
- **Test**: Performance adjustment works

**Task 8.6**: Split trades.py API (part 1 - basic trades)

- **TDD Step 1 (RED)**: Write/update tests for basic trade endpoints
- Test `GET /api/trades` and `POST /api/trades/execute`
- **TDD Step 2 (GREEN)**: Create `trades.py` with basic trade endpoints
- Move `get_trades()` and `execute_trade()` endpoints
- Update imports in main.py
- **TDD Step 3 (VERIFY)**: Run all tests - `pytest tests/ -v`
- **Files**: 1 new file + 1 update (remove from old trades.py) + test updates
- **Test Command**: `pytest tests/integration/ -k trades -v`

**Task 8.7**: Split trades.py API (part 2 - recommendations)

- **TDD Step 1 (RED)**: Write/update tests for recommendation endpoints
- Test `GET /api/trades/recommendations` and related endpoints
- **TDD Step 2 (GREEN)**: Create `recommendations.py` with recommendation endpoints
- Move recommendation-related endpoints
- Update imports in main.py
- **TDD Step 3 (VERIFY)**: Run all tests - `pytest tests/ -v`
- **Files**: 1 new file + 1 update + test updates
- **Test Command**: `pytest tests/integration/ -k recommendation -v`

**Task 8.8**: Split trades.py API (part 3 - multi-step)

- **TDD Step 1 (RED)**: Write/update tests for multi-step endpoints
- Test multi-step recommendation endpoints
- **TDD Step 2 (GREEN)**: Create `multi_step_recommendations.py`
- Move multi-step recommendation endpoints
- Update imports in main.py
- **TDD Step 3 (VERIFY)**: Run all tests - `pytest tests/ -v`
- **Files**: 1 new file + 1 update + test updates
- **Test Command**: `pytest tests/integration/ -k multi_step -v`

**Task 8.9**: Remove funding functionality

- **TDD Step 1 (RED)**: Remove/update tests for funding endpoints
- Remove tests for funding endpoints
- Update any tests that depend on funding
- Run tests - may fail if tests reference funding
- **TDD Step 2 (GREEN)**: Remove funding endpoints and service
- Remove funding endpoints from `trades.py`:
    - `GET /api/trades/recommendations/{symbol}/funding-options`
    - `POST /api/trades/recommendations/{symbol}/execute-funding`
    - Remove `FundingSellRequest` and `ExecuteFundingRequest` models
- Delete `app/application/services/funding_service.py`
- Remove funding-related imports from trades.py
- **TDD Step 3 (GREEN)**: Remove frontend funding functionality
- Remove `showFundingModal` state from `static/js/store.js`
- Remove `openFundingModal()` and `closeFundingModal()` methods from store.js
- Remove funding button from `static/components/next-actions-card.js`
- Delete `static/components/funding-modal.js`
- Remove `<funding-modal>` element and script tag from `static/index.html`
- **TDD Step 4 (VERIFY)**: Run all tests - `pytest tests/ -v`
- All tests pass
- No references to funding remain in backend
- Verify frontend still works (funding modal removed, no broken references)
- **Files**: 
- Remove from: `app/api/trades.py` (2 endpoints + 2 models)
- Delete: `app/application/services/funding_service.py`
- Remove from: `static/js/store.js` (funding modal state/methods)
- Remove from: `static/components/next-actions-card.js` (funding button)
- Delete: `static/components/funding-modal.js`
- Remove from: `static/index.html` (funding modal element/script)
- **Test Command**: `pytest tests/ -v`
- **Note**: Holistic recommendations already handle funding scenarios optimally

**Task 8.10**: Split yahoo service (part 1 - client)

- Create `yahoo_finance_client.py` with core client
- **Files**: 1 new file + 1 update
- **Test**: Client works

**Task 8.11**: Split yahoo service (part 2 - data fetchers)

- Create separate fetchers for analyst, fundamental, price data
- **Files**: 3 new files + 1 update
- **Test**: Each fetcher works

**Task 8.12**: Split trade execution service

- Extract: recorder, validator, currency_converter
- **Files**: 3 new files + 1 update
- **Test**: Each component works

### Phase 9: Clean Up Dead Code

**Task 9.1**: Remove unused imports (automated)

- Run ruff/pylint to find unused imports, remove them
- **Files**: All files
- **Test**: Code still works

**Task 9.2**: Remove commented-out code

- Find and remove all commented code blocks
- **Files**: All files
- **Test**: Code still works

**Task 9.3**: Remove duplicate functions

- Find and remove any duplicate function definitions
- **Files**: Various
- **Test**: Code still works

### Phase 10: Update Tests

**Task 10.1**: Update test fixtures for DI

- Update conftest.py with DI fixtures
- **Files**: 1 file (tests/conftest.py)
- **Test**: Tests can import fixtures

**Task 10.2**: Update unit tests for new response types

- Update scoring tests to use ScoreResult
- **Files**: ~5 test files
- **Test**: Tests pass

**Task 10.3**: Update integration tests

- Update integration tests for new structure
- **Files**: ~3 test files
- **Test**: Tests pass

## TDD Execution Guidelines

**Before Starting Any Refactoring (Phase 0)**:

1. **Run all tests** - `pytest tests/ -v`
2. **Document failures** - List any failing tests
3. **Fix all failures** - Complete Phase 0 first
4. **Verify green baseline** - All tests must pass before refactoring
5. **Check coverage** - Run `pytest --cov=app --cov-report=term` to see baseline

**For Each Refactoring Task (TDD Cycle - Red-Green-Refactor)**:

1. **RED: Write/Update Tests First**

- Write tests that describe the desired behavior
- Or update existing tests if behavior changes
- Run tests - they should pass (if updating) or fail (if new behavior)
- **Goal**: Tests exist and describe what we want

2. **GREEN: Make Minimal Change**

- Make the smallest change to make tests pass
- Focus only on that task
- Don't add extra features or "improvements"
- **Goal**: All tests pass

3. **VERIFY: Run All Tests**

- Run all tests: `pytest tests/ -v`
- Verify no regressions
- If tests fail, fix before moving on
- **Goal**: All tests pass, no regressions

4. **REFACTOR: Clean Up (Optional)**

- Clean up code while keeping tests green
- Improve structure without changing behavior
- **Goal**: Better code, same behavior, all tests still pass

5. **COMMIT: Save Progress**

- Commit after tests pass
- Clear commit message: "Task X.Y: [description]"
- **Goal**: Safe checkpoint

6. **CONTINUE: Move to Next**

- Only proceed if current task is complete and all tests pass
- **Goal**: Incremental, safe progress

**Test Requirements**:

- ✅ **All existing tests must pass** before starting a task
- ✅ **All tests must pass** after completing a task
- ✅ **Add tests** for new functionality
- ✅ **Update tests** when behavior changes
- ✅ **No test should be skipped** unless absolutely necessary
- ✅ **Run full test suite** after each task, not just new tests

**If a Task Fails**:

- **STOP** - Don't continue to next task
- **CHECK TESTS** - Are tests failing? Fix them first
- **DEBUG** - Fix the issue
- **TEST** - Run all tests: `pytest tests/ -v`
- **VERIFY** - All tests pass
- **THEN CONTINUE** - Only proceed when current task is solid and all tests pass

**Test-First Checklist for Each Task**:

- [ ] All existing tests pass before starting (`pytest tests/ -v`)
- [ ] Tests written/updated for new behavior
- [ ] Implementation makes tests pass
- [ ] All tests pass after implementation (`pytest tests/ -v`)
- [ ] No test regressions introduced
- [ ] Code is clean and follows patterns

**Task Size Guidelines**:

- **Small**: 1-3 files changed (preferred)
- **Medium**: 4-6 files changed (acceptable)
- **Large**: 7+ files changed (split into smaller tasks)

**Running Tests**:

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=term

# Run specific test file
pytest tests/unit/domain/test_priority_calculator.py -v

# Run tests matching pattern
pytest tests/ -k "test_cagr" -v
```



## Design Decision: API Endpoint Granularity

### Question: Should each calculation have its own API endpoint?

**Answer: No - Keep calculations internal, expose business operationsWhy NOT expose every calculation as an API endpoint**:

1. **Performance Overhead**: HTTP calls are slower than direct function calls

- Internal code calling `/api/calculations/cagr` adds latency
- Serialization/deserialization overhead
- Network latency even for localhost

2. **Tight Coupling**: Internal code would depend on HTTP API

- Changes to API affect internal code
- Harder to refactor
- Testing becomes more complex (need to mock HTTP)

3. **Security Concerns**: Exposing internal calculations

- Unnecessary attack surface
- Rate limiting becomes critical
- Need to secure endpoints that shouldn't be public

4. **Maintenance Burden**: More endpoints = more code to maintain

- More tests needed
- More documentation
- More versioning concerns

5. **Breaking Changes**: API changes break internal code

- Can't refactor calculations without API versioning
- Internal refactoring becomes harder

**Recommended Approach: Business-Focused APIsExpose high-level business operations, not implementation details**:

```python
# ✅ GOOD - Business operations
GET /api/stocks/{symbol}              # Get stock with full score
GET /api/stocks/{symbol}/score         # Get complete stock score (all components)
GET /api/portfolio/analytics           # Get portfolio analytics
GET /api/trades/recommendations        # Get trade recommendations

# ❌ BAD - Implementation details
GET /api/calculations/cagr?symbol=AAPL
GET /api/calculations/sharpe?symbol=AAPL
GET /api/currency/convert?from=USD&to=EUR&amount=100
```

**Exception: Debug/Admin Endpoints** (if needed):

```python
# Debug endpoints (clearly marked, admin-only)
GET /api/debug/calculations/cagr?symbol=AAPL
GET /api/debug/calculations/sharpe?symbol=AAPL
GET /api/admin/currency/convert?from=USD&to=EUR&amount=100
```

**Benefits of This Approach**:

- **Performance**: Internal code uses fast function calls
- **Flexibility**: Can refactor calculations without breaking API
- **Security**: Minimal attack surface
- **Maintainability**: Less code to maintain
- **Clear Boundaries**: API reflects business operations, not implementation

**For Currency Conversion**:

- If only used internally → Keep it internal
- If frontend needs it → Expose as `/api/currency/convert` (business operation)
- Don't expose just for consistency

**Current API Structure** (already good):

- `/api/portfolio/*` - Portfolio operations
- `/api/stocks/*` - Stock operations  
- `/api/trades/*` - Trade operations
- `/api/charts/*` - Chart data
- `/api/settings/*` - Settings

**Keep it this way** - these reflect business operations, not implementation details.**When to Expose Something as an API Endpoint**:

1. **Frontend/External Consumer Needs It**

- If the frontend needs currency conversion for a calculator → Expose it
- If external systems need to query stock scores → Expose it
- But expose as business operation, not raw calculation

2. **It's a Business Operation**

- "Get stock score" is a business operation → Expose it
- "Calculate CAGR" is an implementation detail → Keep it internal
- "Convert currency" could be either → Expose if frontend needs it

3. **It's Useful for Debugging**

- Debug endpoints are fine, but mark them clearly
- Use `/api/debug/*` or `/api/admin/*` prefix
- Require authentication/authorization

**Example: Currency Conversion Decision**:

```python
# Scenario 1: Only used internally for trade execution
# → Keep it internal (current state)
# Internal code: exchange_service.convert(100, "USD", "EUR")

# Scenario 2: Frontend needs currency calculator
# → Expose as business operation
# GET /api/currency/convert?from=USD&to=EUR&amount=100
# This is a business operation (user wants to convert money)

# Scenario 3: Need to debug exchange rates
# → Expose as debug endpoint
# GET /api/debug/currency/rate?from=USD&to=EUR
# This is for debugging, not normal operation
```

**Key Principle**:

- **API = Business Interface** (what users/clients need)
- **Internal Functions = Implementation** (how we do it)
- Don't expose implementation details just for consistency

## Design Decision: Calculation Granularity

### Question: Separate file per calculation vs. single get_stock_scores?

**Answer: Hybrid approach - Group by domain, not by individual calculationWhy NOT one file per calculation**:

- Too many small files (50+ files for all calculations)
- Hard to see relationships between related calculations
- Difficult to maintain consistency across related metrics
- Overhead of managing many imports

**Why NOT one giant get_stock_scores file**:

- Too large, hard to navigate
- Multiple responsibilities in one file
- Hard to test individual components
- Changes affect too much code

**Recommended Approach** (already partially implemented):

```javascript
calculations/
├── cagr.py              # All CAGR-related (5y, 10y, different periods)
├── risk_metrics.py      # Sharpe, Sortino, volatility (related risk metrics)
├── technical_indicators.py  # EMA, RSI, Bollinger (all technical indicators)
├── financial_metrics.py    # P/E, debt/equity, margins (all fundamental metrics)
└── price_metrics.py        # 52W high/low, drawdown (all price-based metrics)
```

**Benefits**:

- **Related calculations together**: Easy to see how they relate
- **Manageable file count**: ~5-10 calculation files, not 50+
- **Clear boundaries**: Each file has a clear domain (risk, technical, fundamental)
- **Easy to find**: Know which file to look in based on metric type
- **Stable API**: Each file exposes a consistent interface

**Example**:

```python
# calculations/cagr.py - All CAGR calculations
def calculate_cagr_5y(prices): ...
def calculate_cagr_10y(prices): ...
def calculate_cagr_custom(prices, months): ...

# Usage in groups/long_term.py
from app.domain.scoring.calculations.cagr import calculate_cagr_5y
cagr = calculate_cagr_5y(monthly_prices)
```

**For get_stock_scores()**:

- Keep the orchestrator function (`calculate_stock_score()`)
- It calls individual group calculators
- Each group uses calculation modules
- Clear separation: Orchestrator → Groups → Calculations

## File Organization Principles

### Single Responsibility Principle

- Each file should have **one clear purpose**
- If a file does multiple things, split it into multiple files
- Each module should be independently testable

### Stable API Design

- Each module should expose a **well-defined, stable interface**
- Public functions should have clear docstrings
- Use type hints for all inputs and outputs
- Avoid exposing internal implementation details

### Size Guidelines

- **Target**: 200-300 lines per file
- **Maximum**: ~500 lines (if larger, split it)
- **Minimum**: No artificial minimum, but ensure files have a clear purpose

### Modularity

- Changes to one module should **not require changes to others**
- Use dependency injection to avoid tight coupling
- Prefer composition over large monolithic classes

### Clear Input/Output

- All public functions should have:
- Explicit type hints for parameters
- Explicit return type hints
- Docstrings explaining purpose, parameters, and return values
- Clear error handling

## Benefits

- **Testability**: Easy to inject mocks for testing
- **Maintainability**: Clear dependencies, easier to understand
- **Flexibility**: Easy to swap implementations (e.g., different database)
- **Consistency**: Uniform patterns throughout codebase
- **Separation of Concerns**: Clear boundaries between layers
- **Modularity**: Small, focused files that are easy to understand and modify
- **Refactorability**: Changes isolated to single files, reducing risk

## Clean Refactoring Strategy

- **No backward compatibility** - Remove old patterns immediately
- **Delete deprecated code** - Remove any dead code, unused imports, or legacy patterns found
- **Clean break** - Update all imports at once when moving files
- **Remove unused code** - Delete any functions/classes that are no longer used
- **No deprecation warnings** - Remove old code entirely, don't mark as deprecated
- Run tests after each phase to ensure everything works
- **No backward compatibility** - Remove old patterns immediately
- **Delete deprecated code** - Remove any dead code, unused imports, or legacy patterns found
- **Clean break** - Update all imports at once when moving files
- **Remove unused code** - Delete any functions/classes that are no longer used
- **No deprecation warnings** - Remove old code entirely, don't mark as deprecated