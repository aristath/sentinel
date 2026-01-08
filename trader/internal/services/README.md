# Service Layer Architecture

This document describes the service layer architecture of the Sentinel trading system, explaining service boundaries, design decisions, and usage patterns.

## Overview

The Sentinel codebase uses a **two-tier service architecture**:

1. **Shared Services** (`internal/services/`) - Core business services used across multiple modules
2. **Module Services** (`internal/modules/*/service.go`) - Domain-specific services within each module

This separation ensures:
- **Reusability**: Common functionality is shared across modules
- **Cohesion**: Domain-specific logic stays within its module
- **Maintainability**: Clear boundaries make the codebase easier to understand and modify
- **Testability**: Services can be tested independently with clear dependencies

## Service Categories

### Shared Services (`internal/services/`)

Shared services provide **cross-cutting business functionality** that multiple modules depend on. They handle operations that don't belong to a specific domain but are essential for the system to function.

#### Current Shared Services

##### 1. `CurrencyExchangeService`

**Purpose**: Handles currency conversion operations via Tradernet FX pairs.

**Responsibilities**:
- Finding conversion paths between currencies (direct or multi-step)
- Getting current exchange rates
- Executing currency exchanges
- Ensuring minimum balances in target currencies

**Key Features**:
- Supports direct conversions: EUR↔USD, EUR↔GBP, GBP↔USD, EUR↔HKD, USD↔HKD
- Routes GBP↔HKD via EUR (no direct pair available)
- Provides rate lookup and conversion execution
- Handles balance validation before conversions

**Usage Example**:
```go
service := services.NewCurrencyExchangeService(tradernetClient, log)

// Get exchange rate
rate, err := service.GetRate("USD", "EUR")

// Execute exchange
err := service.Exchange("USD", "EUR", 1000.0)

// Ensure minimum balance
hasBalance, err := service.EnsureBalance("EUR", 100.0, "USD")
```

**Design Decisions**:
- Uses interface `domain.CurrencyExchangeServiceInterface` to break circular dependencies
- Handles multi-step conversions transparently
- Provides fallback logic for autonomous operation when rates unavailable

##### 2. `TradeExecutionService`

**Purpose**: Executes trade recommendations with validation and recording.

**Responsibilities**:
- Validating trade requests (cash balance, connection status)
- Executing trades via Tradernet client
- Recording trades in database
- Emitting trade execution events
- Calculating commissions

**Key Features**:
- Pre-trade validation (cash balance checks)
- Commission calculation (fixed + variable)
- Trade recording with full audit trail
- Event emission for downstream processing

**Usage Example**:
```go
service := services.NewTradeExecutionService(
    tradernetClient,
    tradeRepo,
    positionRepo,
    cashManager,
    exchangeService,
    eventManager,
    log,
)

recommendations := []services.TradeRecommendation{
    {Symbol: "AAPL", Side: "BUY", Quantity: 10, ...},
}

results := service.ExecuteTrades(recommendations)
```

**Design Decisions**:
- Simplified version for emergency rebalancing (full validation can be added later)
- Uses domain interfaces to break circular dependencies
- Returns execution results for all trades (success/blocked/error)

### Module Services (`internal/modules/*/service.go`)

Module services encapsulate **domain-specific business logic** within their respective modules. Each module owns its service and defines its interface.

#### Service Pattern

Each module service:
- Operates on domain entities within its module
- Coordinates between repositories, external clients, and other services
- Provides business logic that isn't purely CRUD (which repositories handle)
- Uses dependency injection for testability

#### Examples

##### `PortfolioService` (`internal/modules/portfolio/service.go`)

**Purpose**: Orchestrates portfolio operations and calculations.

**Responsibilities**:
- Calculating portfolio summaries (allocation vs targets)
- Aggregating position values by country/industry
- Converting currencies for portfolio totals
- Providing portfolio state queries

**Key Methods**:
- `GetPortfolioSummary()` - Current allocation vs targets
- `aggregatePositionValues()` - Internal aggregation logic

**Dependencies**:
- `PositionRepositoryInterface` - Position data
- `domain.AllocationTargetProvider` - Target allocations
- `domain.CashManager` - Cash balances
- `domain.CurrencyExchangeServiceInterface` - Currency conversion (uses shared service!)

##### `UniverseService` (`internal/modules/universe/service.go`)

**Purpose**: Manages security (universe) operations.

**Responsibilities**:
- Activating/deactivating securities
- Synchronizing prices
- Coordinating cleanup operations

**Key Methods**:
- `DeactivateSecurity()` - Mark security inactive
- `ReactivateSecurity()` - Mark security active
- `SyncPrices()` - Update current prices

**Dependencies**:
- `SecurityRepositoryInterface` - Security data
- `SyncServiceInterface` - Price synchronization

##### `TradingService` (`internal/modules/trading/service.go`)

**Purpose**: Handles trade-related business logic.

**Responsibilities**:
- Trade history queries
- Trade safety validation
- Trade event coordination

**Key Methods**:
- `GetHistory()` - Retrieve trade history
- Safety checks via `TradeSafetyService`

**Dependencies**:
- `TradeRepositoryInterface` - Trade data
- `domain.TradernetClientInterface` - Order placement
- `TradeSafetyService` - Safety validation

## Service Boundaries

### When to Use Shared Services

Use shared services (`internal/services/`) when:

1. **Cross-Module Functionality**: The service is used by multiple modules
   - Example: `CurrencyExchangeService` used by portfolio, trading, and cash flows modules

2. **Infrastructure Concerns**: The service handles infrastructure-level operations
   - Example: `TradeExecutionService` coordinates with external APIs and event system

3. **Reusable Business Logic**: The logic is domain-agnostic and reusable
   - Example: Currency conversion paths don't depend on portfolio or trading logic

### When to Use Module Services

Use module services (`internal/modules/*/service.go`) when:

1. **Domain-Specific Logic**: The service operates on a specific domain
   - Example: `PortfolioService` calculates portfolio-specific metrics

2. **Module Cohesion**: The service keeps related functionality together
   - Example: `UniverseService` manages all security-related operations

3. **Encapsulation**: The service hides implementation details from other modules
   - Example: `PlanningService` orchestrates complex planning workflows

## Dependency Injection

All services use **constructor injection** for dependencies:

```go
// Shared service
func NewCurrencyExchangeService(
    client *tradernet.Client,
    log zerolog.Logger,
) *CurrencyExchangeService {
    // ...
}

// Module service
func NewPortfolioService(
    positionRepo PositionRepositoryInterface,
    allocRepo domain.AllocationTargetProvider,
    cashManager domain.CashManager,
    // ... more dependencies
) *PortfolioService {
    // ...
}
```

**Benefits**:
- Testability: Easy to inject mocks
- Flexibility: Dependencies can be swapped
- Clarity: Explicit dependencies in constructor

## Interface Usage

Services use **interfaces** to break circular dependencies and improve testability:

### Domain Interfaces (`internal/domain/interfaces.go`)

Common interfaces are defined in the domain package:

- `domain.CashManager`
- `domain.TradernetClientInterface`
- `domain.CurrencyExchangeServiceInterface`
- `domain.AllocationTargetProvider`
- `domain.PortfolioSummaryProvider`

### Module Interfaces (`internal/modules/*/interfaces.go`)

Each module defines its own repository interfaces:

- `portfolio.PositionRepositoryInterface`
- `universe.SecurityRepositoryInterface`
- `trading.TradeRepositoryInterface`

**Design Pattern**: Services depend on interfaces, not concrete types, allowing:
- Mock injection in tests
- Implementation swapping
- Circular dependency prevention

## Error Handling

All services follow consistent error handling patterns:

1. **Error Wrapping**: Use `fmt.Errorf` with `%w` to wrap errors with context
   ```go
   if err != nil {
       return fmt.Errorf("failed to get portfolio summary: %w", err)
   }
   ```

2. **Error Context**: Include relevant information in error messages
   ```go
   return fmt.Errorf("failed to get rate for %s/%s: %w", fromCurrency, toCurrency, err)
   ```

3. **Logging**: Log errors before returning them
   ```go
   s.log.Error().Err(err).Str("symbol", symbol).Msg("Failed to deactivate security")
   return fmt.Errorf("failed to deactivate security: %w", err)
   ```

## Testing

Services are tested with:

1. **Unit Tests**: Test business logic with mocked dependencies
   ```go
   mockRepo := &MockPositionRepository{}
   service := NewPortfolioService(mockRepo, ...)
   ```

2. **Integration Tests**: Test with real dependencies where appropriate
   ```go
   db := testing.NewTestDB()
   repo := portfolio.NewPositionRepository(db)
   service := NewPortfolioService(repo, ...)
   ```

3. **Test Utilities**: Use `internal/testing` package for common test setup
   - `testing.NewTestDB()` - In-memory SQLite for testing
   - `testing.MockPositionRepository` - Pre-built mocks

## Best Practices

### ✅ Do

- Use shared services for cross-cutting concerns
- Keep module services focused on their domain
- Use dependency injection for all dependencies
- Define interfaces for external dependencies
- Wrap errors with context
- Log errors before returning them

### ❌ Don't

- Create shared services for single-module use cases
- Put domain logic in shared services
- Access repositories directly from handlers (use services)
- Create circular dependencies between services
- Return unwrapped database errors
- Skip error logging

## Future Enhancements

Potential improvements to the service layer:

1. **Service Interface Definitions**: Define interfaces for all services to improve testability
2. **Service Middleware**: Add middleware for cross-cutting concerns (logging, metrics, retries)
3. **Service Discovery**: Implement service discovery for distributed deployments
4. **Event-Driven Architecture**: Expand event-driven communication between services
5. **Transaction Management**: Add transaction coordination for multi-service operations

## Related Documentation

- [Repository Pattern](../database/repositories/README.md) - Data access layer
- [Module Structure](../modules/README.md) - Module organization
- [Testing Guide](../testing/README.md) - Testing utilities and patterns
- [Domain Interfaces](../domain/interfaces.go) - Shared interfaces

