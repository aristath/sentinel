# Architectural Analysis & Refactoring Opportunities

**Date**: 2025-01-04
**Project**: Arduino Trader
**Purpose**: Comprehensive architectural analysis identifying refactoring opportunities

---

## Executive Summary

This analysis identifies **12 major architectural issues** and **25+ specific refactoring opportunities** across the codebase. The primary concerns are:

1. **Dependency Injection**: 840-line `main.go` with all wiring
2. **Service Duplication**: Services created in 3+ places
3. **Circular Dependencies**: Interface band-aids instead of proper design
4. **Handler Inconsistency**: Mixed patterns across modules
5. **Database Access**: Raw `.Conn()` calls, no abstraction layer
6. **Testing Gaps**: Inconsistent mocking and test coverage

**Priority**: High-impact refactoring should focus on DI extraction and dependency management first, as these enable all other improvements.

---

## 1. Dependency Injection Architecture

### Current State

**Problem**: All dependency wiring in `cmd/server/main.go` (842 lines)

```go
// main.go - 842 lines of wiring
func registerJobs(...) {
    // 500+ lines of service/repository creation
    positionRepo := portfolio.NewPositionRepository(...)
    securityRepo := universe.NewSecurityRepository(...)
    // ... 50+ more initializations
}
```

**Issues**:
- Impossible to test in isolation
- Hard to understand dependency graph
- Changes require modifying massive function
- No dependency validation
- Services created multiple times (main.go, server.go, settings_routes.go)

### Refactoring Opportunities

#### 1.1 Extract DI Package

**Create**: `internal/di/` package

**Structure**:
```
internal/di/
├── wire.go          # Main wiring function
├── databases.go     # Database initialization
├── repositories.go  # Repository wiring
├── services.go      # Service wiring
├── handlers.go      # Handler wiring
├── jobs.go          # Job registration
└── types.go         # DI container types
```

**Benefits**:
- `main.go` reduces from 842 to ~100 lines
- Single source of truth for dependencies
- Testable dependency graph
- Clear dependency relationships

**Impact**: ⭐⭐⭐⭐⭐ (Critical)

#### 1.2 Service Creation Duplication

**Problem**: Services created in:
- `cmd/server/main.go` (registerJobs function)
- `internal/server/server.go` (setup*Routes functions)
- `internal/server/settings_routes.go` (onboarding setup)

**Example**:
```go
// main.go line 367
portfolioService := portfolio.NewPortfolioService(...)

// server.go line 367 (duplicate!)
portfolioService := portfolio.NewPortfolioService(...)

// settings_routes.go line 134 (duplicate!)
portfolioService := portfolio.NewPortfolioService(...)
```

**Solution**: Single service creation in `internal/di/services.go`

**Impact**: ⭐⭐⭐⭐ (High)

---

## 2. Circular Dependencies

### Current State

**Problem**: Circular dependencies broken with interface band-aids

**Dependency Cycle**:
```
portfolio → cash_flows → trading → allocation → portfolio
```

**Band-Aid Solution**:
```go
// portfolio/service.go
type CashManager interface { ... }  // Interface to break cycle

// cash_flows/cash_security_manager.go
type CashManager struct { ... }  // Implements interface

// services/trade_execution_service.go
type CashManagerInterface interface { ... }  // Another interface!
```

**Issues**:
- Same interface defined in 3+ places
- No single source of truth
- Hard to track what implements what
- Adapter types everywhere (`qualityGatesAdapter`, etc.)

### Refactoring Opportunities

#### 2.1 Centralize Shared Interfaces

**Create**: `internal/domain/interfaces.go`

**Move all shared interfaces**:
- `CashManager` (from portfolio, cash_flows, services)
- `AllocationTargetProvider` (from portfolio)
- `PortfolioSummaryProvider` (from allocation)
- `ConcentrationAlertProvider` (from allocation)
- `TradernetClientInterface` (from portfolio, services)
- `CurrencyExchangeServiceInterface` (from portfolio, services)
- All other cross-module interfaces

**Benefits**:
- Single source of truth
- Clear dependency graph
- No duplicate definitions
- Easier to understand relationships

**Impact**: ⭐⭐⭐⭐ (High)

#### 2.2 Remove Adapter Types

**Problem**: Adapter types like `qualityGatesAdapter` in `main.go`

**Solution**: Use domain interfaces directly, no adapters needed

**Impact**: ⭐⭐⭐ (Medium)

---

## 3. Handler/Routing Architecture

### Current State

**Problem**: Inconsistent handler patterns

**Pattern 1**: Handlers in `server.go` (15+ functions)
```go
// server.go
func (s *Server) setupAllocationRoutes(r chi.Router) { ... }
func (s *Server) setupPortfolioRoutes(r chi.Router) { ... }
// ... 13 more setup*Routes functions
```

**Pattern 2**: Handlers in module with `RegisterRoutes()` (2 modules)
```go
// modules/symbolic_regression/handlers.go
func (h *Handlers) RegisterRoutes(r chi.Router) { ... }

// modules/rebalancing/handlers.go
func (h *Handlers) RegisterRoutes(r chi.Router) { ... }
```

**Pattern 3**: Handlers in module but no `RegisterRoutes()` (most modules)
```go
// modules/trading/handlers.go
type TradingHandlers struct { ... }
// No RegisterRoutes function!
```

**Issues**:
- Inconsistent patterns make code hard to navigate
- Routing logic scattered across server.go
- Some modules have handlers, some don't
- Hard to test routing in isolation

### Refactoring Opportunities

#### 3.1 Standardize Handler Pattern

**Standard**: Every module with HTTP endpoints should have:
```
modules/{module}/
├── handlers/
│   ├── handlers.go      # Handler struct and methods
│   └── routes.go        # RegisterRoutes function
```

**Modules Needing Extraction**:
1. allocation - from `setupAllocationRoutes()`
2. portfolio - from `setupPortfolioRoutes()`
3. universe - from `setupUniverseRoutes()`
4. trading - handlers exist but no routes.go
5. dividends - from `setupDividendRoutes()`
6. display - from `setupDisplayRoutes()`
7. scoring - from `setupScoringRoutes()`
8. optimization - from `setupOptimizationRoutes()`
9. cash_flows - handlers exist but no routes.go
10. charts - from `setupChartsRoutes()`
11. settings - from `setupSettingsRoutes()`
12. planning - has handlers/, ensure RegisterRoutes exists

**Benefits**:
- Consistent pattern across all modules
- Routing logic lives with module
- Easier to test
- Server becomes thin router

**Impact**: ⭐⭐⭐⭐ (High)

#### 3.2 Simplify server.go

**Current**: 1000+ lines with 15+ setup functions

**Target**: ~200 lines, just calls module RegisterRoutes

**Impact**: ⭐⭐⭐ (Medium)

---

## 4. Database Access Patterns

### Current State

**Problem**: Raw database connections passed everywhere

**Pattern**:
```go
// Everywhere in codebase
positionRepo := portfolio.NewPositionRepository(
    portfolioDB.Conn(),  // Raw *sql.DB
    universeDB.Conn(),  // Raw *sql.DB
    log,
)
```

**Issues**:
- No abstraction layer
- Hard to mock for testing
- Connection management scattered
- No transaction support
- Direct access to `*sql.DB` everywhere

### Refactoring Opportunities

#### 4.1 Database Abstraction Layer

**Option A**: Repository pattern with interfaces (Recommended)
```go
// internal/database/repository.go
type Repository interface {
    BeginTx(ctx context.Context) (*sql.Tx, error)
    Query(ctx context.Context, query string, args ...interface{}) (*sql.Rows, error)
    // ... other operations
}
```

**Option B**: Keep current pattern but add transaction support
```go
// Add transaction methods to database.DB
func (db *DB) WithTransaction(ctx context.Context, fn func(*sql.Tx) error) error
```

**Impact**: ⭐⭐⭐ (Medium)

#### 4.2 Connection Pool Management

**Current**: Connection pools configured per database, but no centralized management

**Opportunity**: Add connection pool monitoring and health checks

**Impact**: ⭐⭐ (Low)

---

## 5. Service Layer Architecture

### Current State

**Problem**: Unclear service boundaries

**Services in `internal/services/`**:
- `currency_exchange_service.go`
- `trade_execution_service.go`

**Services in modules**:
- `modules/*/service.go` (15+ services)

**Issues**:
- Unclear what goes where
- Some services are truly shared, some are domain-specific
- `trade_execution_service` is in services/ but used by trading module

### Refactoring Opportunities

#### 5.1 Clarify Service Boundaries

**Rule**:
- **Module services** (`modules/*/service.go`): Business logic for specific domain
- **Shared services** (`internal/services/`): Infrastructure services used by multiple modules
- **Client services** (`internal/clients/`): External API clients

**Decision Needed**: Should `trade_execution_service` move to `modules/trading/`?

**Impact**: ⭐⭐⭐ (Medium)

#### 5.2 Service Interface Standardization

**Problem**: Some services have interfaces, some don't

**Opportunity**: Define service interfaces for testability

**Impact**: ⭐⭐ (Low)

---

## 6. Repository Pattern

### Current State

**Problem**: Inconsistent repository patterns

**Pattern 1**: Uses `BaseRepository` (unused)
```go
// database/repositories/base.go exists but not used
```

**Pattern 2**: Direct struct with `*sql.DB` (most repositories)
```go
type PositionRepository struct {
    portfolioDB *sql.DB
    universeDB  *sql.DB
    log         zerolog.Logger
}
```

**Pattern 3**: Some repositories have interfaces, some don't

**Issues**:
- BaseRepository exists but unused
- No consistent pattern
- Hard to mock for testing
- Some repos have interfaces, some don't

### Refactoring Opportunities

#### 6.1 Standardize Repository Pattern

**Standard**: All repositories should:
1. Have interface defined
2. Accept `*sql.DB` or transaction in methods
3. Use consistent error handling
4. Follow naming: `{Entity}Repository` and `{Entity}RepositoryInterface`

**Impact**: ⭐⭐⭐ (Medium)

#### 6.2 Use BaseRepository or Remove It

**Decision**: Either use `BaseRepository` consistently or remove it

**Impact**: ⭐⭐ (Low)

---

## 7. Error Handling Patterns

### Current State

**Pattern**: Inconsistent error wrapping

**Examples**:
```go
// Good: Wrapped with context
return fmt.Errorf("failed to fetch security: %w", err)

// Bad: No context
return err

// Bad: String error
return fmt.Errorf("error occurred")
```

**Issues**:
- Some errors wrapped, some not
- Inconsistent error messages
- Some errors logged, some not
- No error categorization

### Refactoring Opportunities

#### 7.1 Standardize Error Wrapping

**Rule**: Always wrap errors with context using `fmt.Errorf("operation: %w", err)`

**Impact**: ⭐⭐⭐ (Medium)

#### 7.2 Error Categorization

**Opportunity**: Define error types for different categories
```go
type DomainError struct { ... }
type InfrastructureError struct { ... }
type ValidationError struct { ... }
```

**Impact**: ⭐⭐ (Low)

---

## 8. Testing Architecture

### Current State

**Pattern**: Inconsistent testing

**Good Examples**:
- `modules/trading/service_test.go` - Uses mocks
- `modules/universe/service_test.go` - Uses testify/mock

**Issues**:
- Some modules have tests, some don't
- Inconsistent mocking patterns
- Some tests use real DB, some use mocks
- No test utilities package

### Refactoring Opportunities

#### 8.1 Test Utilities Package

**Create**: `internal/testing/` package

**Contents**:
- Mock factories
- Test database helpers
- Common test utilities

**Impact**: ⭐⭐⭐ (Medium)

#### 8.2 Standardize Test Patterns

**Rule**:
- Unit tests: Use mocks, no real DB
- Integration tests: Use test database
- All tests: Use testify for assertions

**Impact**: ⭐⭐⭐ (Medium)

---

## 9. Configuration Management

### Current State

**Pattern**: Mixed configuration sources

**Sources**:
- Environment variables (`.env` file)
- Settings database (`config.db`)
- Hard-coded defaults

**Issues**:
- Unclear precedence
- Deprecated `.env` for credentials but still used
- Configuration scattered

### Refactoring Opportunities

#### 9.1 Centralize Configuration

**Opportunity**: Single configuration source with clear precedence

**Impact**: ⭐⭐ (Low)

---

## 10. Job/Scheduler Architecture

### Current State

**Pattern**: Jobs mixed with services

**Structure**:
- Jobs in `internal/scheduler/` (good)
- Some jobs are services (e.g., `cash_flows.SyncJob`)
- Job registration in `main.go`

**Issues**:
- Unclear separation between jobs and services
- Job dependencies wired in main.go

### Refactoring Opportunities

#### 10.1 Extract Job Wiring

**Move**: Job registration to `internal/di/jobs.go`

**Impact**: ⭐⭐⭐ (Medium)

---

## 11. Code Organization

### Current State

**Problem**: Mixed concerns in modules

**Examples**:
- `modules/portfolio/` contains market regime code (wrong domain)
- `modules/universe/` contains scoring integration (mixed concerns)
- `modules/optimization/` contains regime-aware AND non-regime-aware code

### Recent Improvements

#### 11.0 Quantum Probability Module (✅ Implemented 2025-01-27)

**New Module**: `internal/modules/quantum/`

**Structure** (follows clean architecture):
```
internal/modules/quantum/
├── calculator.go      # Core quantum probability calculator
├── bubble.go          # Bubble detection using quantum states
├── value_trap.go      # Value trap detection using superposition
├── scoring.go         # Quantum-enhanced scoring metrics
├── models.go          # Quantum state models and types
└── calculator_test.go # Comprehensive unit tests
```

**Integration Points**:
- **Tag Assigner** (`modules/universe/tag_assigner.go`): Ensemble logic combining classical + quantum bubble/value trap detection
- **Security Scorer** (`modules/scoring/scorers/security.go`): Quantum metrics added to SubScores under "quantum" group
- **Opportunity Calculators**: All three calculators updated to use ensemble tags for filtering

**Architecture Notes**:
- ✅ Clean module structure with clear separation of concerns
- ✅ No circular dependencies (quantum module is a pure calculator)
- ✅ Dependency injection via constructor (quantumCalculator field)
- ✅ Comprehensive unit tests with benchmarks
- ✅ Follows existing patterns (similar to other scoring modules)

**Impact**: ⭐⭐⭐⭐ (High) - Demonstrates good module organization

### Refactoring Opportunities

#### 11.1 Extract Market Regime

**Move**: From `modules/portfolio/` to `internal/market_regime/`

**Files to Move**:
- `market_regime.go` → `market_regime/detector.go`
- `regime_persistence.go` → `market_regime/persistence.go`
- `market_index_service.go` → `market_regime/index_service.go`

**Impact**: ⭐⭐⭐⭐ (High)

#### 11.2 Standardize Module Structure

**Standard Template**:
```
modules/{module}/
├── domain/              # Domain models (if needed)
├── repository/          # Data access
├── service/             # Business logic
├── handlers/            # HTTP handlers (if module has API)
├── models.go           # DTOs/request/response models
└── interfaces.go       # Module-specific interfaces (if needed)
```

**Impact**: ⭐⭐⭐ (Medium)

---

## 12. Type Safety Issues

### Current State

**Problem**: Use of `interface{}` and `any`

**Found**: 15+ instances of `interface{}` or `any`

**Examples**:
- `modules/opportunities/calculators/weight_based.go:49`
- `modules/symbolic_regression/storage.go:42`
- `modules/scoring/scorers/security.go:441`

**Issues**:
- Loss of type safety
- Harder to refactor
- Runtime errors instead of compile-time

### Refactoring Opportunities

#### 12.1 Replace interface{} with Specific Types

**Rule**: Use explicit types, avoid `interface{}` when possible

**Impact**: ⭐⭐⭐ (Medium)

---

## Refactoring Priority Matrix

### Critical (Do First)
1. **Extract Dependency Injection** - Enables all other refactoring
2. **Break Circular Dependencies** - Required before handler extraction
3. **Extract Market Regime** - Clean separation of concerns

### High Priority
4. **Standardize Handler Pattern** - Consistency across codebase
5. **Consolidate Service Creation** - Single source of truth
6. **Centralize Shared Interfaces** - Clear dependency graph

### Medium Priority
7. **Standardize Repository Pattern** - Consistency
8. **Standardize Module Structure** - Predictability
9. **Extract Job Wiring** - Clean separation
10. **Improve Error Handling** - Better debugging

### Low Priority
11. **Database Abstraction** - Nice to have
12. **Test Utilities** - Quality of life
13. **Configuration Centralization** - Minor improvement

---

## Implementation Strategy

### Phase 1: Foundation (Week 1-2)
1. Extract DI package
2. Break circular dependencies
3. Extract market regime

**Result**: Clean foundation for all other work

### Phase 2: Consistency (Week 3-4)
4. Standardize handlers
5. Consolidate services
6. Standardize repositories

**Result**: Consistent patterns across codebase

### Phase 3: Quality (Week 5-6)
7. Improve error handling
8. Add test utilities
9. Standardize module structure

**Result**: Higher code quality

---

## Success Metrics

- `main.go` reduced from 842 to <150 lines
- Zero circular dependencies
- All modules follow standard structure
- All handlers in module `handlers/` subdirectories
- Single source of truth for service creation
- 100% test coverage for critical paths
- All tests passing

---

## Notes

- This analysis focuses on structural issues, not business logic
- Some refactoring may require breaking changes (acceptable per project philosophy)
- Prioritize refactoring that enables other improvements
- Test after each phase to ensure no regressions

---

## Recent Additions (2025-01-27)

### Quantum Probability Module

A new `internal/modules/quantum/` module has been implemented following clean architecture principles:

**Key Features**:
- Quantum-inspired probability models for asset returns
- Ensemble approach combining classical and quantum detection methods
- Zero circular dependencies (pure calculator module)
- Comprehensive test coverage with performance benchmarks
- Clean integration with existing tag assigner, scoring, and opportunity calculator systems

**Architectural Quality**: ⭐⭐⭐⭐⭐
- Follows standard module structure
- No architectural violations
- Well-tested and documented
- Serves as a good example for future module development

**See**: `docs/QUANTUM_PROBABILITY_IMPLEMENTATION.md` for detailed technical documentation
