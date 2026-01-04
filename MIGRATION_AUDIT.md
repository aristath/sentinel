# Database Architecture Migration - Complete Audit

## Current Database Structure (As-Is)

### Databases Currently Opened in main.go

1. **config.db** (`cfg.DatabasePath`)
   - Used by: SecurityRepository, AllocationRepository, PlannerConfigRepository, RecommendationRepository
   - Contains: securities, allocation_targets, groups, settings, recommendations, planner_configs

2. **state.db** (`../data/state.db`)
   - Used by: PositionRepository, ScoreRepository
   - Contains: positions, scores

3. **snapshots.db** (`../data/snapshots.db`)
   - Used by: PortfolioRepository, TurnoverTracker
   - Contains: portfolio_snapshots

4. **ledger.db** (`../data/ledger.db`)
   - Used by: TradeRepository, TurnoverTracker, AttributionCalculator
   - Contains: trades, cash_flows

5. **dividends.db** (`../data/dividends.db`)
   - Used by: DividendRepository
   - Contains: dividend_history, drip_tracking

6. **satellites.db** (`../data/satellites.db`)
   - Used by: BucketRepository, BalanceRepository
   - Contains: buckets, bucket_balances, bucket_transactions, satellite_settings

### Databases NOT Currently Opened (But Exist)

7. **planner.db** - Planning sequences and configs (accessed where?)
8. **cache.db** - Ephemeral cache data
9. **calculations.db** - Calculated metrics (accessed where?)
10. **history/{SYMBOL}.db** - Per-security price history (accessed via history_db.go)

## New Database Structure (To-Be)

### 8 Databases

1. **universe.db** (NEW - split from config.db)
   - Tables: securities, country_groups, industry_groups
   - Repositories: SecurityRepository

2. **config.db** (REDUCED)
   - Tables: settings, allocation_targets
   - Repositories: AllocationRepository, SettingsRepository

3. **ledger.db** (EXPANDED - merge dividends.db)
   - Tables: trades, cash_flows, dividend_history
   - Repositories: TradeRepository, DividendRepository, TurnoverTracker

4. **portfolio.db** (NEW - merge state.db + calculations.db + snapshots.db)
   - Tables: positions, scores, calculated_metrics, portfolio_snapshots
   - Repositories: PositionRepository, ScoreRepository, PortfolioRepository

5. **satellites.db** (UPDATED schema)
   - Tables: buckets (add agent_id column), bucket_balances, bucket_transactions, satellite_settings
   - Repositories: BucketRepository, BalanceRepository

6. **agents.db** (RENAMED from planner.db)
   - Tables: agent_configs (rename from planner_configs), config_history, sequences, evaluations, best_result
   - Repositories: PlannerConfigRepository, PlannerRepository, RecommendationRepository

7. **history.db** (NEW - consolidate all history/*.db)
   - Tables: daily_prices, exchange_rates, symbol_removals, cleanup_log
   - Repositories: HistoryRepository (NEW)

8. **cache.db** (for recommendations moved from config.db)
   - Tables: recommendations, cache_data
   - Repositories: RecommendationRepository (moved)

## All Files That Touch Databases (40 files)

### Core Database Infrastructure
1. `/trader/internal/database/db.go` - Database wrapper
2. `/trader/internal/database/repositories/base.go` - Base repository

### Repositories (19 files)
3. `/trader/internal/modules/universe/security_repository.go` - config.db → universe.db
4. `/trader/internal/modules/universe/score_repository.go` - state.db → portfolio.db
5. `/trader/internal/modules/portfolio/position_repository.go` - state.db → portfolio.db
6. `/trader/internal/modules/portfolio/portfolio_repository.go` - snapshots.db → portfolio.db
7. `/trader/internal/modules/portfolio/history_repository.go` - history/*.db → history.db
8. `/trader/internal/modules/trading/trade_repository.go` - ledger.db (keep)
9. `/trader/internal/modules/dividends/dividend_repository.go` - dividends.db → ledger.db
10. `/trader/internal/modules/cash_flows/repository.go` - ledger.db (keep)
11. `/trader/internal/modules/satellites/bucket_repository.go` - satellites.db (update schema)
12. `/trader/internal/modules/satellites/balance_repository.go` - satellites.db (keep)
13. `/trader/internal/modules/allocation/repository.go` - config.db (keep)
14. `/trader/internal/modules/allocation/grouping_repository.go` - config.db → universe.db
15. `/trader/internal/modules/settings/repository.go` - config.db (keep)
16. `/trader/internal/modules/planning/repository/planner_repository.go` - planner.db → agents.db
17. `/trader/internal/modules/planning/repository/config_repository.go` - config.db → agents.db
18. `/trader/internal/modules/planning/recommendation_repository.go` - config.db → cache.db
19. `/trader/internal/modules/cash_flows/repository_test.go` - Test file
20. `/trader/internal/modules/satellites/bucket_repository_test.go` - Test file
21. `/trader/internal/modules/satellites/balance_repository_test.go` - Test file

### Services (11 files)
22. `/trader/internal/modules/portfolio/service.go` - Uses multiple repos
23. `/trader/internal/modules/universe/sync_service.go` - Uses SecurityRepository
24. `/trader/internal/modules/satellites/balance_service.go` - Uses BalanceRepository
25. `/trader/internal/modules/allocation/service.go` - Uses AllocationRepository
26. `/trader/internal/modules/charts/service.go` - Uses various repos
27. `/trader/internal/modules/optimization/handlers.go` - Uses various repos
28. `/trader/internal/modules/optimization/returns.go` - Uses history data
29. `/trader/internal/modules/optimization/risk.go` - Uses history data
30. `/trader/internal/modules/portfolio/turnover.go` - Uses ledger + snapshots
31. `/trader/internal/modules/portfolio/attribution.go` - Uses trades + history
32. `/trader/internal/modules/scoring/cache/technical.go` - Uses cache db

### Handlers (2 files)
33. `/trader/internal/modules/universe/handlers.go` - HTTP handlers

### Display (3 files)
34. `/trader/internal/modules/display/portfolio_display_calculator.go`
35. `/trader/internal/modules/display/security_performance.go`
36. `/trader/internal/modules/display/portfolio_performance.go`

### Scheduler (1 file)
37. `/trader/internal/scheduler/health_check.go` - Health checks

### Schema (2 files)
38. `/trader/internal/modules/satellites/schema.go` - Table schemas
39. `/trader/internal/modules/cash_flows/schema.go` - Table schemas

### Other (2 files)
40. `/trader/internal/modules/universe/history_db.go` - History database access
41. `/trader/internal/modules/scoring/cache/technical_test.go` - Test file

## Migration Changes Required

### main.go Changes
**Current:** Opens 6 databases (config, state, snapshots, ledger, dividends, satellites)
**New:** Opens 8 databases (universe, config, ledger, portfolio, satellites, agents, history, cache)

```go
// OLD
configDB, err := database.New(cfg.DatabasePath)
stateDB, err := database.New("../data/state.db")
snapshotsDB, err := database.New("../data/snapshots.db")
ledgerDB, err := database.New("../data/ledger.db")
dividendsDB, err := database.New("../data/dividends.db")
satellitesDB, err := database.New("../data/satellites.db")

// NEW
universeDB, err := database.New("../data/universe.db")
configDB, err := database.New("../data/config.db")
ledgerDB, err := database.New("../data/ledger.db")
portfolioDB, err := database.New("../data/portfolio.db")
satellitesDB, err := database.New("../data/satellites.db")
agentsDB, err := database.New("../data/agents.db")
historyDB, err := database.New("../data/history.db")
cacheDB, err := database.New("../data/cache.db")
```

### Repository Constructor Changes

**Example - SecurityRepository:**
```go
// OLD
NewSecurityRepository(configDB.Conn(), log)

// NEW
NewSecurityRepository(universeDB.Conn(), log)
```

**Example - PositionRepository:**
```go
// OLD
NewPositionRepository(stateDB.Conn(), configDB.Conn(), log)

// NEW
NewPositionRepository(portfolioDB.Conn(), universeDB.Conn(), log)
```

**Example - DividendRepository:**
```go
// OLD
NewDividendRepository(dividendsDB.Conn(), log)

// NEW
NewDividendRepository(ledgerDB.Conn(), log)
```

## Priority Order for Migration

### Phase 1: Core Infrastructure
1. Update `/trader/internal/database/db.go` with PRAGMA configurations
2. Create all 10 migration SQL files
3. Add `_database_health` tables to each database

### Phase 2: Update main.go
1. Open all 8 new databases
2. Update server.Config to pass new databases
3. Update all repository constructors

### Phase 3: Update Each Repository (19 files)
**Critical path - must update ALL:**
1. SecurityRepository → universe.db
2. ScoreRepository → portfolio.db
3. PositionRepository → portfolio.db
4. PortfolioRepository → portfolio.db
5. HistoryRepository → history.db (NEW implementation)
6. TradeRepository → ledger.db (no change)
7. DividendRepository → ledger.db (was dividends.db)
8. CashFlowsRepository → ledger.db (no change)
9. BucketRepository → satellites.db (update schema for agent_id)
10. BalanceRepository → satellites.db (no change)
11. AllocationRepository → config.db (no change)
12. GroupingRepository → universe.db (was config.db)
13. SettingsRepository → config.db (no change)
14. PlannerRepository → agents.db (was planner.db)
15. ConfigRepository → agents.db (was config.db)
16. RecommendationRepository → cache.db (was config.db)
17. + Any test files

### Phase 4: Update Services (11 files)
Review and update all service files to use correct repositories

### Phase 5: Create New Infrastructure
1. UniverseService (coordination layer)
2. DatabaseHealthService (auto-recovery)
3. MaintenanceJobs (daily/weekly/monthly)
4. BackupService (tiered backups)
5. MonitoringService (metrics + alerts)

### Phase 6: Testing
1. Unit tests for each repository
2. Integration tests
3. Data migration verification
4. 10-year growth simulation

## Success Criteria

- [ ] All 40 files reviewed and updated
- [ ] All 19 repositories migrated to new databases
- [ ] main.go opens correct 8 databases
- [ ] All tests passing
- [ ] Data migrated with integrity checks
- [ ] No database calls to old structure remain
- [ ] Reliability infrastructure in place
