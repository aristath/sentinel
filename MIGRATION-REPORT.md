# Python to Go Migration Report

**Generated:** 2026-01-03
**Status:** 196 Python files remaining (excluding `__init__.py`)
**Goal:** 100% migration to Go (except pypfopt and tradernet microservices)

---

## Executive Summary

### Current State
- **Original Python files:** ~600
- **Deleted this session:** 10 fully migrated files
- **Remaining:** 196 files (275 including `__init__.py`)
- **Go implementation:** 241 Go files

### Migration Progress
- **Fully Migrated Modules:** allocation, cash_flows, dividends, optimization (API/domain)
- **Partially Migrated:** planning, portfolio, rebalancing, satellites, scoring, trading, universe
- **Not Migrated:** analytics (actively used), jobs (8 files), core infrastructure

### Blocking Issues
1. **Portfolio hash generation** - Critical, referenced in Go but not implemented
2. **Analytics module** - Actively used by scoring and rebalancing
3. **Trade execution workflow** - 851 lines of safety logic missing
4. **Rebalancing service** - 853 lines of planning integration missing
5. **Database repositories** - All 7 Python repositories still active
6. **Job schedulers** - 8 jobs not migrated, 4 partially migrated

---

## Category 1: Job Schedulers (14 files)

### 1.1 NOT MIGRATED - Critical Jobs (8 files)

#### `app/jobs/auto_deploy.py`
- **Purpose:** Automated deployment from GitHub (code/sketch/evaluator)
- **Lines:** ~300
- **Go Equivalent:** None
- **Dependencies:**
  - Git operations (GitHub API)
  - Virtual environment management
  - Systemd service control
  - File system operations
  - Arduino sketch compilation
- **What's Missing:**
  - Entire deployment pipeline
  - GitHub webhook integration
  - Deployment rollback logic
  - Service restart coordination
- **Migration Priority:** LOW - Can remain Python
- **Action Items:**
  - Decision: Keep as Python or create Go deployment service
  - If migrating: Implement git operations, systemd control, venv management in Go

#### `app/jobs/event_based_trading.py`
- **Purpose:** Main event-driven trading loop with planning integration
- **Lines:** 714
- **Go Equivalent:** None
- **Dependencies:**
  - Holistic planner orchestration
  - Portfolio monitoring
  - Planning completion detection
  - Trade execution coordination
  - Event bus integration
- **What's Missing:**
  - Entire event-driven trading workflow
  - Planning state machine
  - Multi-phase portfolio analysis
  - Trade execution trigger logic
- **Migration Priority:** CRITICAL
- **Action Items:**
  - Implement event-driven scheduler in Go
  - Integrate with Go planning module
  - Port planning state machine logic
  - Implement portfolio monitoring

#### `app/jobs/historical_data_sync.py`
- **Purpose:** Syncs historical prices from Yahoo Finance
- **Lines:** ~250
- **Go Equivalent:** None
- **Dependencies:**
  - Yahoo Finance client
  - Per-symbol database management
  - Monthly aggregation logic
  - Price history validation
- **What's Missing:**
  - Yahoo Finance integration for historical data
  - Database schema for price history
  - Aggregation to monthly prices
- **Migration Priority:** MEDIUM
- **Action Items:**
  - Implement Yahoo Finance client in Go
  - Create history database repositories
  - Port aggregation logic

#### `app/jobs/maintenance.py`
- **Purpose:** Database backup, WAL checkpoint, cleanup tasks
- **Lines:** ~300
- **Go Equivalent:** Partial (HealthCheckJob only)
- **Dependencies:**
  - SQLite backup API (Python sqlite3 module)
  - WAL checkpoint operations
  - Database integrity checks
  - Scheduled cleanup (prices, snapshots, caches)
- **What's Missing:**
  - SQLite backup using BACKUP API
  - Cleanup task scheduler
  - Database optimization (VACUUM, ANALYZE)
- **Migration Priority:** HIGH
- **Action Items:**
  - Implement SQLite backup using Go database/sql
  - Create cleanup scheduler
  - Port database maintenance operations

#### `app/jobs/metrics_calculation.py`
- **Purpose:** Batch calculates technical indicators (RSI, EMA, Bollinger, etc.)
- **Lines:** ~400
- **Go Equivalent:** None
- **Dependencies:**
  - NumPy array operations
  - Technical analysis formulas (RSI, EMA, Bollinger Bands, Sharpe, CAGR)
  - Price history database
  - Batch processing coordination
- **What's Missing:**
  - Technical indicator calculation engine
  - Batch processing framework
  - Caching layer for expensive calculations
- **Migration Priority:** MEDIUM
- **Action Items:**
  - Port technical indicator formulas to Go
  - Create batch calculation framework
  - Implement caching strategy

#### `app/jobs/scheduler.py`
- **Purpose:** Python APScheduler wrapper
- **Lines:** ~200
- **Go Equivalent:** `trader/internal/scheduler/scheduler.go` (different architecture)
- **Dependencies:**
  - APScheduler library
  - Job registration
  - Cron scheduling
- **What's Missing:**
  - N/A - Go uses cron-based scheduler (architectural difference)
- **Migration Priority:** N/A
- **Action Items:**
  - None - keep Python scheduler or fully migrate to Go cron scheduler

#### `app/jobs/securities_data_sync.py`
- **Purpose:** Hourly security data processing (prices, country/exchange/industry detection, metrics, score refresh)
- **Lines:** ~350
- **Go Equivalent:** Partial (`universe_service.SyncPrices()`)
- **Dependencies:**
  - Yahoo Finance integration
  - Country detection logic
  - Exchange detection logic
  - Industry classification
  - Metrics calculation
  - Score refresh trigger
- **What's Missing:**
  - Country/exchange detection pipeline
  - Industry classification logic
  - Integrated metrics calculation
  - Score refresh integration
- **Migration Priority:** HIGH
- **Action Items:**
  - Complete `UniverseService` with detection pipelines
  - Implement country/exchange detection
  - Add industry classification
  - Integrate with scoring service

#### `app/modules/planning/jobs/planner_batch.py`
- **Purpose:** Holistic planner batch processing - incremental sequence generation
- **Lines:** 619
- **Go Equivalent:** None
- **Dependencies:**
  - Planner API client
  - Incremental sequence generation
  - Batch state management
  - Database caching for sequences
- **What's Missing:**
  - Entire incremental planning workflow
  - Batch execution API
  - State persistence
- **Migration Priority:** CRITICAL
- **Action Items:**
  - Implement incremental planner in Go
  - Create batch execution API
  - Port state management logic

### 1.2 PARTIALLY MIGRATED - Needs Completion (4 files)

#### `app/jobs/cash_flow_sync.py` + `app/modules/cash_flows/jobs/cash_flow_sync.py`
- **Purpose:** Syncs cash flows from Tradernet, creates dividend records, processes deposits
- **Lines:** ~250 (duplicated)
- **Go Equivalent:** `SyncCycleJob.syncCashFlows()` calls `CashFlowsService.SyncFromTradernet()`
- **Dependencies:**
  - Tradernet transaction API
  - Dividend record creation
  - Deposit allocation logic for buckets
  - Cash flow categorization
- **What's Missing in Go:**
  - Dividend record creation in cash flows table
  - Deposit allocation to buckets
  - Transaction categorization logic
- **Migration Priority:** HIGH
- **Action Items:**
  - Complete `CashFlowsService.SyncFromTradernet()` implementation
  - Add dividend record creation
  - Implement deposit allocation workflow

#### `app/jobs/daily_sync.py`
- **Purpose:** Daily portfolio sync (positions, cash, snapshots, prices, universe updates)
- **Lines:** ~350
- **Go Equivalent:** Partial via `SyncCycleJob` and `portfolio_service`
- **Dependencies:**
  - Portfolio position sync from Tradernet
  - Cash balance conversion (multi-currency)
  - Portfolio snapshot creation
  - Price sync coordination
  - Security universe updates
- **What's Missing in Go:**
  - Portfolio snapshot creation and storage
  - Universe security addition logic
  - Multi-currency cash balance handling
- **Migration Priority:** HIGH
- **Action Items:**
  - Implement portfolio snapshot creation in Go
  - Add universe auto-population logic
  - Complete multi-currency support

#### `app/jobs/sync_cycle.py`
- **Purpose:** Unified 5-minute sync orchestrator (trades, cash flows, portfolio, prices, display)
- **Lines:** ~200
- **Go Equivalent:** `SyncCycleJob` in `trader/internal/scheduler/sync_cycle.go`
- **Dependencies:**
  - Trade sync coordination
  - Cash flow sync coordination
  - Portfolio sync coordination
  - Price sync (market hours aware)
  - Display update coordination
- **What's Missing in Go:**
  - Some sync steps marked as TODO
  - Portfolio sync incomplete
- **Migration Priority:** HIGH
- **Action Items:**
  - Complete all TODO items in Go `SyncCycleJob`
  - Verify all sync steps are functional
  - Test integrated workflow

#### `app/modules/rebalancing/jobs/emergency_rebalance.py`
- **Purpose:** Immediate negative balance rebalancing with emergency trade execution
- **Lines:** ~150
- **Go Equivalent:** Callback exists in `SyncCycleJob.emergencyRebalance()` but not implemented
- **Dependencies:**
  - Negative balance detection
  - Emergency trade calculation
  - Immediate execution (bypasses normal cooldowns)
  - Balance restoration logic
- **What's Missing in Go:**
  - `checkNegativeBalances()` implementation
  - Emergency rebalance calculation
  - Immediate execution workflow
- **Migration Priority:** HIGH
- **Action Items:**
  - Implement negative balance detection
  - Create emergency rebalancing logic
  - Add immediate execution bypass

### 1.3 REFERENCE ONLY (2 files)

#### `app/modules/scoring/jobs/score_refresh.py`
- **Purpose:** Periodic score refresh for all securities
- **Lines:** ~100
- **Go Equivalent:** None (Python-specific scoring orchestration)
- **Dependencies:**
  - Scoring service
  - 8-group scoring system
  - Batch processing
- **Migration Priority:** LOW - Depends on scoring service migration
- **Action Items:**
  - Wait for scoring service migration
  - Create Go batch scoring scheduler

---

## Category 2: Domain Layer (26 files)

### 2.1 CRITICAL - Not Migrated (1 file)

#### `app/domain/portfolio_hash.py`
- **Purpose:** Portfolio state hashing for recommendation caching and change detection
- **Lines:** ~200
- **Functions:**
  - `generate_portfolio_hash()` - Hash positions, securities, cash, pending orders
  - `generate_settings_hash()` - Hash settings affecting recommendations
  - `generate_allocations_hash()` - Hash allocation targets
  - `generate_recommendation_cache_key()` - Combined hash for cache invalidation
  - `apply_pending_orders_to_portfolio()` - Apply pending orders to portfolio state
- **Go Equivalent:** Portfolio hash strings used but NO hash generation functions
- **Dependencies:**
  - Position data access
  - Settings access
  - Allocation targets access
  - Cryptographic hashing
- **What's Missing in Go:**
  - ALL hash generation logic
  - Cache key generation
  - Portfolio state change detection
- **Migration Priority:** CRITICAL - Blocking recommendation caching
- **Action Items:**
  - Implement all 5 hash generation functions in Go
  - Add to planning module
  - Wire into recommendation repository

### 2.2 Event System (5 files)

#### `app/domain/events/base.py`
- **Purpose:** Event bus and base DomainEvent class
- **Lines:** ~150
- **Go Equivalent:** `trader/internal/events/manager.go` (simpler implementation)
- **Dependencies:**
  - Event subscriber pattern
  - Async event dispatch
  - Event type registry
- **What's Missing in Go:**
  - Rich typed domain events
  - Pub/sub event bus pattern
  - Event subscriber registration
- **Migration Priority:** MEDIUM - Architectural difference
- **Action Items:**
  - Decision: Accept Go's simpler event system or port full DDD events
  - If porting: Implement event bus pattern in Go
  - Update all event publishers/subscribers

#### `app/domain/events/trade_events.py`
- **Purpose:** TradeExecutedEvent
- **Lines:** ~30
- **Go Equivalent:** String-based event types in Go
- **Migration Priority:** LOW - Part of event system decision

#### `app/domain/events/recommendation_events.py`
- **Purpose:** RecommendationCreatedEvent
- **Lines:** ~30
- **Go Equivalent:** String-based event types in Go
- **Migration Priority:** LOW - Part of event system decision

#### `app/domain/events/position_events.py`
- **Purpose:** PositionUpdatedEvent
- **Lines:** ~30
- **Go Equivalent:** String-based event types in Go
- **Migration Priority:** LOW - Part of event system decision

#### `app/domain/events/security_events.py`
- **Purpose:** SecurityAddedEvent
- **Lines:** ~30
- **Go Equivalent:** String-based event types in Go
- **Migration Priority:** LOW - Part of event system decision

### 2.3 Factory Pattern (2 files)

#### `app/domain/factories/recommendation_factory.py`
- **Purpose:** Creates buy/sell recommendation data structures
- **Lines:** ~150
- **Go Equivalent:** None (Go creates structs directly)
- **Dependencies:**
  - Recommendation model
  - Data validation
  - Enum conversions
- **What's Missing in Go:**
  - Factory pattern (architectural difference)
  - Validation logic embedded in factory
- **Migration Priority:** MEDIUM
- **Action Items:**
  - Decision: Accept direct struct creation or implement factory pattern
  - If keeping: Port validation logic to Go constructors

#### `app/domain/factories/trade_factory.py`
- **Purpose:** Creates Trade objects from execution results and sync data
- **Lines:** ~200
- **Go Equivalent:** None (Go creates structs directly)
- **Dependencies:**
  - Trade model
  - Data transformation
  - Currency conversions
  - DateTime parsing
- **What's Missing in Go:**
  - Factory creation methods
  - Data transformation logic
  - Validation embedded in factory
- **Migration Priority:** MEDIUM
- **Action Items:**
  - Port creation logic to Go constructors
  - Implement validation in struct methods

### 2.4 Response Types (4 files)

#### `app/domain/responses/service.py`
- **Purpose:** ServiceResult[T] generic with success/error handling
- **Lines:** ~100
- **Go Equivalent:** None (Go uses (value, error) tuples)
- **Migration Priority:** LOW - Architectural difference
- **Action Items:** None - Python Result pattern vs Go error handling

#### `app/domain/responses/calculation.py`
- **Purpose:** CalculationResult for numerical calculations
- **Lines:** ~50
- **Migration Priority:** LOW - Architectural difference

#### `app/domain/responses/list.py`
- **Purpose:** ListResult[T] for list operations with pagination
- **Lines:** ~80
- **Migration Priority:** LOW - Architectural difference

#### `app/domain/responses/score.py`
- **Purpose:** ScoreResult for scoring functions
- **Lines:** ~60
- **Migration Priority:** LOW - Architectural difference

### 2.5 Domain Services (1 file)

#### `app/domain/services/allocation_calculator.py`
- **Purpose:** Risk parity position sizing, rebalancing bands
- **Lines:** ~250
- **Functions:**
  - `is_outside_rebalance_band()`
  - `calculate_position_size()`
  - `calculate_target_volatility()`
- **Go Equivalent:** Logic inline in opportunities calculators (not centralized)
- **Dependencies:**
  - Target allocation percentages
  - Portfolio volatility targets
  - Rebalancing band thresholds
- **What's Missing in Go:**
  - Centralized allocation calculation service
  - Rebalancing band check functions
  - Position sizing with volatility targeting
- **Migration Priority:** HIGH
- **Action Items:**
  - Create AllocationCalculator service in Go
  - Port rebalancing band logic
  - Integrate with opportunities module

### 2.6 Other Domain Files (3 files)

#### `app/domain/models.py`
- **Purpose:** Core domain models (Security, Trade, SecurityScore, Recommendation, etc.)
- **Lines:** ~800
- **Go Equivalent:** `trader/internal/domain/models.go` (basic models only)
- **Models in Python:**
  - Security, Position, Trade, Money (in Go)
  - SecurityScore, Recommendation, AllocationStatus (NOT in Go)
  - PortfolioSummary, SecurityPriority (NOT in Go)
  - MultiStepRecommendation, DividendRecord (NOT in Go)
- **Migration Priority:** MEDIUM
- **Action Items:**
  - Migrate missing models to appropriate Go modules
  - Verify model field compatibility

#### `app/domain/exceptions.py`
- **Purpose:** Domain-specific exceptions (DomainError, ValidationError)
- **Lines:** ~100
- **Go Equivalent:** None (Go uses error returns)
- **Migration Priority:** LOW - Architectural difference
- **Action Items:** None - exception-based vs error-based handling

#### `app/domain/repositories/protocols.py`
- **Purpose:** Repository interface protocols for dependency injection
- **Lines:** ~200
- **Protocols:**
  - ISecurityRepository
  - IPositionRepository
  - ITradeRepository
  - ISettingsRepository
  - IAllocationRepository
- **Go Equivalent:** None (Go uses concrete repository types)
- **Migration Priority:** LOW - Needed for Python DI
- **Action Items:** Keep until Python modules fully migrated

---

## Category 3: Analytics Module (16 files)

**⚠️ BLOCKING:** Actively used by scoring and rebalancing services

### 3.1 ACTIVELY USED - Cannot Delete Yet (3 files)

#### `app/modules/analytics/domain/market_regime.py`
- **Purpose:** Detect market regime (bull/bear/sideways) using SPY/QQQ 200-day MA
- **Lines:** ~150
- **Go Equivalent:** `trader/internal/modules/portfolio/market_regime.go` (DIFFERENT LOGIC)
- **Used By:**
  - `app/modules/rebalancing/services/rebalancing_service.py` (line 503) - Cash reserve adjustment
  - `app/modules/planning/domain/holistic_planner.py` (line 3267) - Market-aware planning
- **Difference:**
  - Python: SPY/QQQ 200-day moving average from Tradernet
  - Go: Portfolio-based heuristics (return trend, volatility, drawdown)
- **Migration Priority:** CRITICAL - Different algorithms
- **Action Items:**
  - Decision: Keep Python SPY/QQQ approach or switch to Go portfolio approach
  - Update rebalancing service to use Go version
  - Update planning service to use Go version
  - Verify regime detection accuracy in both approaches

#### `app/modules/analytics/domain/position/drawdown.py`
- **Purpose:** Calculate position drawdown for individual positions
- **Lines:** ~100
- **Function:** `get_position_drawdown(symbol, start_date, end_date)`
- **Used By:**
  - `app/modules/scoring/domain/sell.py` (line 57) - Drawdown score for sell decisions
- **Go Equivalent:** Functionality exists in evaluation service
- **Migration Priority:** HIGH
- **Action Items:**
  - Verify Go evaluation service has equivalent function
  - Update sell scoring to use Go equivalent
  - Test drawdown calculation consistency

#### `app/modules/analytics/domain/position/risk.py`
- **Purpose:** Calculate position risk metrics
- **Lines:** ~120
- **Function:** `get_position_risk_metrics(symbol, returns)`
- **Used By:**
  - Sell scoring system (via analytics wrapper)
- **Go Equivalent:** Functionality in evaluation service
- **Migration Priority:** HIGH
- **Action Items:**
  - Port to Go if not already present
  - Update sell scoring integration

### 3.2 Migrated but Dependencies Not Updated (13 files)

#### `app/modules/analytics/domain/attribution/performance.py`
- **Purpose:** Performance attribution by category (country, industry, sector)
- **Lines:** ~250
- **Go Equivalent:** `trader/internal/modules/portfolio/attribution.go` (FULLY MIGRATED)
- **Migration Priority:** MEDIUM - Update imports
- **Action Items:** Update any Python code importing this to use Go API

#### `app/modules/analytics/domain/attribution/factors.py`
- **Purpose:** Factor attribution analysis
- **Lines:** ~150
- **Go Equivalent:** Included in `portfolio/attribution.go`
- **Migration Priority:** MEDIUM - Update imports

#### `app/modules/analytics/domain/metrics/portfolio.py`
- **Purpose:** Portfolio metrics (Sharpe, Sortino, Calmar, volatility, max drawdown)
- **Lines:** ~200
- **Go Equivalent:** `trader/internal/modules/portfolio/service.go` (lines 393-454)
- **Migration Priority:** MEDIUM - Update imports

#### `app/modules/analytics/domain/metrics/returns.py`
- **Purpose:** Portfolio returns calculation
- **Lines:** ~100
- **Go Equivalent:** `trader/pkg/formulas/` (risk metrics)
- **Migration Priority:** MEDIUM - Update imports

#### `app/modules/analytics/domain/reconstruction/cash.py`
#### `app/modules/analytics/domain/reconstruction/positions.py`
#### `app/modules/analytics/domain/reconstruction/values.py`
- **Purpose:** Historical portfolio reconstruction from trades
- **Lines:** ~150 each
- **Go Equivalent:** Portfolio snapshots stored in database, `GetPositionHistory()` in Go
- **Migration Priority:** LOW - Replaced by snapshot approach

#### All `__init__.py` wrapper files (6 files)
- Re-export wrappers only, no unique functionality
- Safe to delete after dependencies removed

---

## Category 4: Services (10 files)

### 4.1 NOT MIGRATED (2 files)

#### `app/modules/planning/services/planner_initializer.py`
- **Purpose:** Seeds database with default planner configs from TOML files
- **Lines:** 189
- **Methods:**
  - `seed_default_configs()` - Reads TOML files and creates database records
  - `ensure_core_config()` - Ensures core bucket has configuration
- **Go Equivalent:** None
- **Dependencies:**
  - TOML config parsing
  - Planner config repository
  - Default configuration files
- **What's Missing in Go:**
  - Database seeding workflow
  - TOML config loading
  - Default config management
- **Migration Priority:** MEDIUM
- **Action Items:**
  - Implement config seeding in Go
  - Port TOML parsing logic
  - Create initialization service

#### `app/modules/trading/services/trade_frequency_service.py`
- **Purpose:** Check frequency limits (min time, daily, weekly)
- **Lines:** 146
- **Methods:**
  - `can_execute_trade(symbol, side)` - Validates against all limits
  - `get_frequency_status(symbol)` - Current frequency status
- **Go Equivalent:** None
- **Dependencies:**
  - Trade repository
  - Frequency limit constants
  - Time-based validation
- **What's Missing in Go:**
  - Entire frequency limiting service
  - Trade frequency validation
  - Cooldown period checking
- **Migration Priority:** CRITICAL - Required for safe trading
- **Action Items:**
  - Implement TradeFrequencyService in Go
  - Add to trade execution workflow
  - Port all frequency limit logic

### 4.2 PARTIALLY MIGRATED (6 files)

#### `app/modules/planning/services/planner_factory.py`
- **Purpose:** Creates planner instances for core and satellite buckets
- **Lines:** 293
- **Methods:**
  - `create_for_core_bucket()` - From TOML config
  - `create_for_satellite_bucket()` - From slider settings
  - `_create_config_from_sliders()` - Maps satellite settings to planner config
  - `_apply_slider_overrides()` - Applies slider overrides to preset configs
- **Go Equivalent:** Partial in `planner_loader.go`
- **Dependencies:**
  - TOML config loading
  - ParameterMapper for slider-to-config translation
  - Satellite settings integration
- **What's Missing in Go:**
  - Satellite bucket planner creation
  - Slider-based configuration
  - ParameterMapper integration
- **Migration Priority:** HIGH
- **Action Items:**
  - Complete planner factory in Go
  - Implement satellite config creation
  - Port ParameterMapper logic

#### `app/modules/rebalancing/services/rebalancing_service.py`
- **Purpose:** Calculate optimal rebalancing trades using holistic planner
- **Lines:** 853 (LARGEST SERVICE FILE)
- **Methods:**
  - `calculate_rebalance_trades()` - Full planning integration
  - `get_recommendations()` - Optimizer + planner workflow
  - `calculate_min_trade_amount()` - Minimum economical trade size
- **Go Equivalent:** Minimal (only helper functions)
- **Dependencies:**
  - Holistic planner integration
  - Portfolio optimizer
  - Market regime detection
  - Pending orders adjustment
  - Incremental planner database caching
- **What's Missing in Go:**
  - Full planning module integration
  - Optimizer integration
  - Recommendation sequence generation
  - Market-aware cash reserve adjustment
- **Migration Priority:** CRITICAL
- **Action Items:**
  - Implement full rebalancing workflow in Go
  - Integrate with planning module
  - Port optimizer integration
  - Add market regime integration

#### `app/modules/satellites/services/performance_metrics.py`
- **Purpose:** Calculate bucket performance metrics
- **Lines:** 373
- **Methods:**
  - `calculate_bucket_performance()` - Comprehensive metrics (90-day default)
  - Sharpe, Sortino, Calmar, max drawdown, win rate, profit factor
- **Go Equivalent:** `trader/internal/modules/satellites/performance_metrics.go`
- **Dependencies:**
  - Trade repository integration (MISSING in Go)
  - Position history
  - Return calculations
- **What's Missing in Go:**
  - `calculate_bucket_performance()` marked as TODO
  - Trade repository integration
  - Data fetching for calculations
- **Migration Priority:** MEDIUM
- **Action Items:**
  - Complete TODO in Go performance_metrics
  - Integrate with trade repository
  - Test calculation accuracy

#### `app/modules/scoring/services/scoring_service.py`
- **Purpose:** Application-level scoring orchestration
- **Lines:** 185
- **Methods:**
  - `calculate_and_save_score()` - Calculate and persist
  - `score_all_securities()` - Batch scoring
  - `_get_price_data()` - Fetch historical prices
- **Go Equivalent:** Calculation logic in `evaluation/scoring.go`
- **Dependencies:**
  - 8-group scoring system
  - Price data access
  - Database persistence
- **What's Missing in Go:**
  - Service orchestration layer
  - Database persistence of scores
  - Batch processing coordination
- **Migration Priority:** HIGH
- **Action Items:**
  - Create ScoringService in Go
  - Add score persistence
  - Implement batch processing

#### `app/modules/trading/services/trade_execution_service.py`
- **Purpose:** Execute trade recommendations via Tradernet
- **Lines:** 851 (LARGEST SERVICE FILE)
- **Methods:**
  - `execute_trades()` - Full execution workflow
  - Multiple validation helpers (cooldown, currency, sell validation, pending orders, market hours)
  - Currency conversion integration
  - Balance service integration
- **Go Equivalent:** Minimal (`TradingService.SyncFromTradernet()` only)
- **Dependencies:**
  - Tradernet order placement API
  - Safety checks (cooldown, min hold, frequency limits)
  - Market hours checking
  - Currency conversion
  - Balance tracking
- **What's Missing in Go:**
  - Full trade execution workflow
  - All safety checks and validations
  - Order placement integration
  - Balance service updates
- **Migration Priority:** CRITICAL
- **Action Items:**
  - Implement full execution service in Go
  - Port all safety checks
  - Integrate with Tradernet API
  - Add balance service integration

#### `app/application/services/turnover_tracker.py`
- **Purpose:** Calculate annual portfolio turnover rate
- **Lines:** ~150
- **Go Equivalent:** `trader/internal/modules/portfolio/turnover.go` (FULLY MIGRATED)
- **Used By:** `app/jobs/daily_sync.py` (line 200-206)
- **Migration Priority:** MEDIUM
- **Action Items:**
  - Update daily_sync.py to call Go API
  - Delete Python version after migration

### 4.3 REFERENCE ONLY (2 files)

#### `app/modules/portfolio/services/portfolio_service.py`
#### `app/modules/universe/services/security_setup_service.py`
- Both have Go equivalents but with minor TODOs
- Can be deleted after testing Go versions

---

## Category 5: Database Repositories (7 files)

**⚠️ ALL ACTIVELY USED - Cannot delete until Go repositories are created**

#### `app/modules/planning/database/planner_repository.py`
- **Purpose:** Manage planner sequences, evaluations, and results
- **Lines:** 450
- **Database:** planner.db
- **Tables:** sequences, evaluations, best_result
- **Methods:**
  - `ensure_sequences_generated()`
  - `get_next_sequences()`
  - `insert_evaluation()`
  - `get_best_result()`
  - `update_best_result()`
  - `mark_sequence_completed()`
- **Go Equivalent:** None
- **Migration Priority:** CRITICAL
- **Action Items:**
  - Create PlannerRepository in Go
  - Migrate all query logic
  - Wire into planning module

#### `app/modules/planning/database/planner_config_repository.py`
- **Purpose:** CRUD for planner configurations with version history
- **Lines:** 247
- **Database:** planner.db
- **Tables:** planner_configs, planner_config_history
- **Methods:**
  - `get_all()`, `get_by_id()`, `get_by_bucket()`
  - `create()`, `update()`, `delete()`
  - `get_history()`
- **Go Equivalent:** None
- **Migration Priority:** CRITICAL
- **Action Items:**
  - Create PlannerConfigRepository in Go
  - Implement CRUD operations
  - Add version history tracking

#### `app/modules/portfolio/database/history_repository.py`
- **Purpose:** Daily and monthly price history per security
- **Lines:** 245
- **Database:** Per-symbol databases (history/*.db)
- **Tables:** daily_prices, monthly_prices
- **Methods:**
  - `get_daily_prices()`, `get_daily_range()`
  - `get_latest_price()`
  - `upsert_daily()`
  - `aggregate_to_monthly()`
  - `get_52_week_high()`, `get_52_week_low()`
- **Used By:** metrics_calculation.py
- **Go Equivalent:** None
- **Migration Priority:** HIGH
- **Action Items:**
  - Create HistoryRepository in Go
  - Implement per-symbol database access
  - Port aggregation logic

#### `app/modules/satellites/database/balance_repository.py`
- **Purpose:** Virtual cash balance tracking per bucket/currency
- **Lines:** 304
- **Database:** satellites.db
- **Tables:** bucket_balances, bucket_transactions, allocation_settings
- **Methods:**
  - `get_balance()`, `get_total_by_currency()`
  - `set_balance()`, `adjust_balance()`
  - `record_transaction()`, `get_transactions()`
- **Go Equivalent:** None
- **Migration Priority:** HIGH
- **Action Items:**
  - Create BalanceRepository in Go
  - Migrate transaction tracking
  - Wire into satellites module

#### `app/modules/satellites/database/bucket_repository.py`
- **Purpose:** Bucket/satellite CRUD operations
- **Lines:** 320
- **Database:** satellites.db
- **Tables:** buckets, satellite_settings
- **Methods:**
  - `get_by_id()`, `get_all()`, `get_active()`
  - `get_by_type()`, `get_by_status()`
  - `create()`, `update()`, `update_status()`
  - `increment_consecutive_losses()`
  - `get_settings()`, `save_settings()`
- **Go Equivalent:** None
- **Migration Priority:** HIGH
- **Action Items:**
  - Create BucketRepository in Go
  - Implement CRUD operations
  - Add settings management

#### `app/modules/satellites/database/schemas.py`
- **Purpose:** Database schema definition for satellites.db
- **Lines:** 178
- **Tables:**
  - buckets
  - satellite_settings
  - bucket_balances
  - bucket_transactions
  - allocation_settings
  - satellite_regime_performance
- **Function:** `init_satellites_schema()`
- **Go Equivalent:** None
- **Migration Priority:** HIGH
- **Action Items:**
  - Create schema definitions in Go
  - Implement schema initialization
  - Add migration support

#### `app/modules/universe/database/security_repository.py`
- **Purpose:** Security/stock universe CRUD operations
- **Lines:** 324
- **Database:** config.db
- **Tables:** securities
- **Methods:**
  - `get_by_symbol()`, `get_by_isin()`, `get_by_identifier()`
  - `get_all_active()`, `get_by_bucket()`
  - `create()`, `update()`, `delete()`
  - `get_with_scores()` - ⚠️ VIOLATES CLEAN ARCHITECTURE (accesses multiple databases)
- **Go Equivalent:** None
- **Migration Priority:** CRITICAL
- **Action Items:**
  - Create SecurityRepository in Go
  - Fix clean architecture violation in `get_with_scores()`
  - Implement CRUD operations

---

## Category 6: Infrastructure (23 files)

### 6.1 External Integrations - Keep as Python (13 files)

#### Tradernet Integration (7 files)
- `app/infrastructure/external/tradernet/client.py` (~800 lines)
- `app/infrastructure/external/tradernet/models.py`
- `app/infrastructure/external/tradernet/parsers.py`
- `app/infrastructure/external/tradernet/transactions.py`
- `app/infrastructure/external/tradernet/utils.py`
- `app/infrastructure/external/tradernet_connection.py`
- `app/infrastructure/external/tradernet/websocket.py`

**Purpose:** Broker API integration (WebSocket, REST, trading, positions, cash flows)
**Migration Priority:** LOW - Can remain as Python microservice
**Action Items:**
  - Keep as standalone Python service
  - Communicate with Go via HTTP/gRPC

#### Yahoo Finance Integration (6 files)
- `app/infrastructure/external/yahoo/data_fetchers.py`
- `app/infrastructure/external/yahoo/market_indicators.py`
- `app/infrastructure/external/yahoo/models.py`
- `app/infrastructure/external/yahoo/symbol_converter.py`
- `app/infrastructure/external/yahoo_finance.py`
- `app/infrastructure/external/yahoo/price_fetcher.py`

**Purpose:** Market data integration (prices, indicators, symbols)
**Migration Priority:** MEDIUM - Could migrate to Go
**Action Items:**
  - Decision: Keep Python or migrate to Go
  - If migrating: Implement Yahoo Finance client in Go

### 6.2 Deployment System - Keep as Python (5 files)

- `app/infrastructure/deployment/deployment_manager.py`
- `app/infrastructure/deployment/file_deployer.py`
- `app/infrastructure/deployment/git_checker.py`
- `app/infrastructure/deployment/service_manager.py`
- `app/infrastructure/deployment/sketch_deployer.py`

**Purpose:** Arduino deployment system (git, files, systemd, Arduino sketch)
**Migration Priority:** LOW - Python is fine
**Action Items:** Keep as Python

### 6.3 Core Infrastructure (5 files)

#### `app/infrastructure/cache_invalidation.py`
- **Purpose:** Cache invalidation strategies
- **Lines:** ~100
- **Go Equivalent:** Partial in various modules
- **Migration Priority:** MEDIUM
- **Action Items:** Port cache invalidation logic to Go

#### `app/infrastructure/daily_pnl.py`
- **Purpose:** Daily P&L calculation with circuit breaker
- **Lines:** ~150
- **Go Equivalent:** None
- **Migration Priority:** MEDIUM
- **Action Items:** Implement daily P&L service in Go

#### `app/infrastructure/dependencies.py`
- **Purpose:** FastAPI dependency injection setup
- **Lines:** ~300
- **Go Equivalent:** N/A (FastAPI-specific)
- **Migration Priority:** N/A
- **Action Items:** Delete when FastAPI is removed

#### `app/infrastructure/locking.py`
- **Purpose:** File-based locking for critical sections
- **Lines:** ~80
- **Go Equivalent:** None
- **Migration Priority:** MEDIUM
- **Action Items:** Implement file locking in Go

#### `app/infrastructure/market_hours.py`
- **Purpose:** Market hours checking (NYSE, NASDAQ)
- **Lines:** ~120
- **Go Equivalent:** None
- **Migration Priority:** MEDIUM
- **Action Items:** Port market hours logic to Go

#### `app/infrastructure/recommendation_cache.py`
- **Purpose:** Recommendation caching layer
- **Lines:** ~150
- **Go Equivalent:** None
- **Migration Priority:** HIGH
- **Action Items:** Implement caching in Go planning module

#### `app/infrastructure/recommendation_events.py`
- **Purpose:** Recommendation event handlers
- **Lines:** ~80
- **Go Equivalent:** Event system in Go
- **Migration Priority:** LOW
- **Action Items:** Port event handlers to Go

---

## Category 7: Core System (10 files)

### 7.1 Critical - Must Keep (7 files)

#### `app/core/database/schemas.py`
- **Purpose:** Database schema definitions for all 12 databases
- **Lines:** ~600
- **Databases:** config.db, ledger.db, state.db, cache.db, calculations.db, recommendations.db, dividends.db, rates.db, snapshots.db, planner.db, satellites.db, history/*.db
- **Go Equivalent:** None (critical for Python database access)
- **Migration Priority:** CRITICAL
- **Action Items:**
  - Port all schema definitions to Go
  - Create migration system
  - Validate schema compatibility

#### `app/core/database/manager.py`
- **Purpose:** Database connection management
- **Lines:** ~400
- **Go Equivalent:** Partial in `trader/internal/database/`
- **Migration Priority:** CRITICAL
- **Action Items:**
  - Complete Go database manager
  - Port connection pooling
  - Add transaction management

#### `app/core/database/queue.py`
- **Purpose:** Write serialization queue for SQLite
- **Lines:** ~200
- **Go Equivalent:** None
- **Migration Priority:** HIGH
- **Action Items:**
  - Implement write queue in Go
  - Add async write handling

#### `app/core/cache/cache.py`
- **Purpose:** Simple in-memory cache with TTL
- **Lines:** ~150
- **Go Equivalent:** Partial caching in various modules
- **Migration Priority:** MEDIUM
- **Action Items:**
  - Create centralized cache in Go
  - Port TTL logic

#### `app/core/events/events.py`
- **Purpose:** LED integration and system events
- **Lines:** ~100
- **Go Equivalent:** Event system in Go
- **Migration Priority:** MEDIUM
- **Action Items:**
  - Port LED integration to Go
  - Complete event system

#### `app/core/middleware/rate_limit.py`
- **Purpose:** API rate limiting
- **Lines:** ~100
- **Go Equivalent:** None
- **Migration Priority:** LOW (if FastAPI is removed)
- **Action Items:** Implement in Go HTTP server or delete with FastAPI

#### `app/core/logging/logging_context.py`
- **Purpose:** Correlation ID support for logging
- **Lines:** ~80
- **Go Equivalent:** Partial logging in Go
- **Migration Priority:** LOW
- **Action Items:** Implement correlation ID in Go logging

### 7.2 Configuration (3 files)

#### `app/config.py`
- **Purpose:** Application configuration (paths, settings, environment)
- **Lines:** ~200
- **Go Equivalent:** `trader/internal/config/`
- **Migration Priority:** MEDIUM
- **Action Items:**
  - Verify all config values ported to Go
  - Migrate environment variable handling

---

## Category 8: API Layer (2 files)

#### `app/api/errors.py`
- **Purpose:** Utility functions for API responses
- **Lines:** ~50
- **Functions:** `error_response()`, `success_response()`
- **Go Equivalent:** Similar utilities in Go HTTP handlers
- **Migration Priority:** LOW
- **Action Items:** Delete when FastAPI is removed

#### `app/modules/system/api/status.py`
- **Purpose:** System status endpoints (~20+ endpoints)
- **Lines:** ~500
- **Endpoints:**
  - Health checks
  - LED control
  - Sync triggers
  - Maintenance operations
  - Job status
  - Database statistics
  - Logs access
  - Deployment status
  - Disk usage
- **Go Equivalent:** Partial in various route files
- **Migration Priority:** HIGH
- **Action Items:**
  - Audit all endpoints for Go equivalents
  - Migrate missing endpoints
  - Delete after verification

---

## Category 9: Module-Specific Domain Files

### 9.1 Planning Module (60 files total)

**Status:** 80% migrated (48/60 files)

**Fully Migrated:**
- Core planner (7 files) ✓
- Opportunities (7 files) ✓
- Patterns (15 files) ✓
- Sequences (6 files) ✓
- Filters (6 files) ✓

**Not Migrated:**
- Incremental planning (2 files)
- Multi-timeframe evaluation (1 file)
- Utilities (4 files)
- Config management (2 files)

**Migration Priority:** MEDIUM - Core functionality complete
**Action Items:** Migrate remaining utilities and incremental planning

### 9.2 Scoring Module (37 files total)

**Status:** 97% migrated (36/37 files)

**Fully Migrated:**
- All 8 scoring groups ✓
- Calculation logic ✓
- Sell scoring ✓

**Not Migrated:**
- Caching layer with TTL configuration (1 file)

**Migration Priority:** HIGH - Almost complete
**Action Items:** Implement caching layer in Go

### 9.3 Rebalancing Module

**Files:** 4 files
- `domain/rebalancing_triggers.py` - DELETED (migrated)
- `services/rebalancing_service.py` - PARTIALLY MIGRATED
- `jobs/emergency_rebalance.py` - PARTIALLY MIGRATED
- `api/rebalancing.py` - DELETED (migrated)

**Migration Priority:** CRITICAL - Service logic incomplete

### 9.4 Satellites Module

**Files:** 12 files
- Domain files (8) - DELETED (migrated)
- Services (2) - PARTIALLY MIGRATED
- Repositories (2) - NOT MIGRATED

**Migration Priority:** HIGH - Repositories needed

### 9.5 Trading Module

**Files:** 6 files
- Domain files (1) - DELETED (migrated)
- Services (3) - PARTIALLY MIGRATED
- API (1) - DELETED (migrated)

**Migration Priority:** CRITICAL - Execution service incomplete

### 9.6 Universe Module

**Files:** 4 files
- Domain files (2) - DELETED (migrated)
- Repository (1) - NOT MIGRATED
- Service (1) - FULLY MIGRATED

**Migration Priority:** HIGH - Repository needed

### 9.7 Portfolio Module

**Files:** 4 files
- Domain files (1) - DELETED (migrated)
- Repository (1) - NOT MIGRATED
- Service (1) - FULLY MIGRATED
- API (1) - DELETED (migrated)

**Migration Priority:** HIGH - Repository needed

---

## Priority Matrix

### P0 - CRITICAL (Must migrate immediately)

1. **portfolio_hash.py** - Blocking recommendation caching
2. **trade_execution_service.py** (851 lines) - Trading safety
3. **trade_frequency_service.py** - Trading safety
4. **rebalancing_service.py** (853 lines) - Core functionality
5. **event_based_trading.py** (714 lines) - Main trading loop
6. **planner_batch.py** (619 lines) - Planning workflow
7. **Database repositories** (7 files, ~2,000 lines) - Data access

**Estimated Effort:** 3-4 weeks

### P1 - HIGH (Migrate soon)

1. **Job schedulers** (4 partial, 350-400 lines each)
2. **Analytics dependencies** (3 files actively used)
3. **Scoring service orchestration** (185 lines)
4. **Planning factories and initializer** (482 lines)
5. **Database schemas** (600 lines)
6. **Core infrastructure** (cache, locking, market hours)

**Estimated Effort:** 2-3 weeks

### P2 - MEDIUM (Migrate when possible)

1. **Domain services** (allocation_calculator.py)
2. **Metrics calculation job** (400 lines)
3. **Historical data sync** (250 lines)
4. **Maintenance job** (300 lines)
5. **Turnover tracker** (update daily_sync to use Go)
6. **Analytics module** (update imports after dependencies resolved)
7. **Domain models** (migrate missing models)

**Estimated Effort:** 1-2 weeks

### P3 - LOW (Migrate or keep as Python)

1. **External integrations** (Tradernet, Yahoo - can remain Python)
2. **Deployment system** (can remain Python)
3. **Event system** (architectural difference - decision needed)
4. **Factory pattern** (architectural difference - decision needed)
5. **Response types** (architectural difference - accept Go idioms)
6. **Auto deploy job** (can remain Python)

**Estimated Effort:** Varies or N/A

---

## Recommended Migration Sequence

### Phase 1: Critical Path (Week 1-2)
1. Portfolio hash generation (CRITICAL - blocking)
2. Database repositories (7 files) - Start with planner repositories
3. Trade frequency service (safety critical)

### Phase 2: Trading & Rebalancing (Week 3-5)
1. Trade execution service (851 lines)
2. Rebalancing service (853 lines)
3. Emergency rebalance job
4. Complete cash flow sync job

### Phase 3: Planning & Jobs (Week 6-8)
1. Event-based trading job (714 lines)
2. Planner batch job (619 lines)
3. Planner factory and initializer
4. Daily sync completion
5. Securities data sync completion

### Phase 4: Analytics & Scoring (Week 9-10)
1. Resolve analytics dependencies (market_regime, position analysis)
2. Complete scoring service orchestration
3. Scoring caching layer
4. Update all analytics imports

### Phase 5: Infrastructure & Polish (Week 11-12)
1. Database schemas migration
2. Core infrastructure (cache, locking, market hours)
3. Database manager completion
4. Historical data sync
5. Maintenance job
6. Metrics calculation

### Phase 6: Cleanup (Week 13)
1. Domain models migration
2. Update remaining imports
3. Delete Python-only files (FastAPI, dependencies)
4. Final verification and testing

---

## Migration Blockers

### Hard Blockers (Cannot proceed without)
1. ✅ Go HTTP server functional
2. ❌ Portfolio hash generation in Go
3. ❌ Database repositories in Go (7 files)
4. ❌ Trade execution safety checks in Go

### Soft Blockers (Can work around but slows migration)
1. Analytics module dependencies (3 active uses)
2. Planning module integration in rebalancing
3. Event system architectural decision
4. Factory pattern architectural decision

---

## Success Metrics

- [ ] **0 CRITICAL files remaining** (currently 10+ files)
- [ ] **0 HIGH priority files remaining** (currently 20+ files)
- [ ] **All 7 database repositories migrated to Go**
- [ ] **Trading safety checks 100% in Go**
- [ ] **Planning workflow 100% in Go**
- [ ] **Analytics dependencies resolved**
- [ ] **Python file count < 50** (currently 196)
- [ ] **Go test coverage > 80%** for migrated code

---

## Notes

- **Architectural Decisions Needed:**
  - Event system: Accept Go's simpler events or port full DDD pattern?
  - Factory pattern: Use Go constructors or implement factory pattern?
  - Response types: Accept Go error handling or implement Result types?

- **Keep as Python Services:**
  - Tradernet integration (7 files) - Complex WebSocket/REST client
  - pypfopt microservice - Python-specific optimization library

- **Delete After Migration:**
  - FastAPI infrastructure (main.py, dependencies.py, middleware)
  - Test files (187 files in tests/)
  - All `__init__.py` files when modules are empty

---

**Last Updated:** 2026-01-03
**Next Review:** After Phase 1 completion
