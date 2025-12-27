# Arduino Trader Architecture

## Overview

The project follows a **Clean Architecture** pattern with clear separation between domain logic, infrastructure, and application layers.

## Architecture Layers

```
app/
├── domain/              # Pure business logic (no dependencies on infrastructure)
│   ├── models/          # Domain entities (Stock, Position, etc.)
│   ├── services/        # Domain services (PriorityCalculator)
│   ├── utils/           # Shared utilities (priority_helpers)
│   ├── repositories/    # Repository interfaces (abstract contracts)
│   └── exceptions.py    # Domain-specific exceptions
│
├── infrastructure/      # External concerns
│   ├── database/        # Repository implementations (SQLite)
│   ├── external/        # API clients (can move Tradernet/Yahoo here)
│   ├── hardware/        # LED display
│   └── dependencies.py  # FastAPI dependency injection
│
├── application/         # Application services (orchestration)
│   ├── services/        # Use cases (PortfolioService, RebalancingService, ScoringService)
│   └── dto/            # Data transfer objects (if needed)
│
├── api/                 # FastAPI routes (thin controllers)
├── services/            # Legacy services (allocator, scorer, tradernet, yahoo)
└── jobs/               # Background jobs
```

## Key Principles

### 1. Domain Layer (Pure Business Logic)
- **No dependencies** on infrastructure (database, APIs, hardware)
- Contains core business rules and calculations
- Fully testable without mocks
- Examples:
  - `domain/services/priority_calculator.py` - Priority calculation logic
  - `domain/utils/priority_helpers.py` - Shared utility functions

### 2. Repository Pattern
- **Interfaces** defined in `domain/repositories/`
- **Implementations** in `infrastructure/database/repositories/`
- All database access goes through repositories
- Easy to swap implementations (e.g., PostgreSQL instead of SQLite)

### 3. Dependency Injection
- FastAPI dependencies in `infrastructure/dependencies.py`
- Repositories injected via `Depends()`
- Makes testing easier (can inject mocks)

### 4. Application Services
- Orchestrate domain services and repositories
- Handle transactions and coordination
- **No business logic** (that's in domain layer)
- Examples:
  - `PortfolioService` - Portfolio operations
  - `RebalancingService` - Rebalancing use cases
  - `ScoringService` - Stock scoring orchestration

### 5. API Layer (Thin Controllers)
- API endpoints are thin - just request/response handling
- Delegate to application services
- No business logic in API layer

## Migration Status

### ✅ Completed
- Domain layer structure created
- Repository interfaces and implementations
- Dependency injection setup
- Priority calculation extracted to domain service
- LED display moved to infrastructure
- Application services created
- API endpoints refactored (stocks, portfolio, trades, allocation)
- Test infrastructure set up
- Unit and integration tests written

### 🔄 Remaining (Can be done incrementally)
- Jobs still use old `allocator.py` functions (backward compatible)
- External API clients (Tradernet, Yahoo) still in `services/` (can move to `infrastructure/external/`)
- Some legacy functions in `allocator.py` still used by jobs

## Benefits

1. **Testability**: Domain logic can be tested without database
2. **Maintainability**: Clear separation of concerns
3. **Flexibility**: Easy to swap implementations (e.g., different database)
4. **No Duplication**: Shared utilities centralized
5. **Scalability**: Architecture supports growth

## Testing

- **Unit Tests**: `tests/unit/domain/` - Test domain logic in isolation
- **Integration Tests**: `tests/integration/` - Test repository implementations
- Run tests: `pytest`

## Usage Examples

### Using Repositories

```python
from app.infrastructure.dependencies import get_stock_repository

@router.get("/stocks")
async def get_stocks(
    stock_repo: StockRepository = Depends(get_stock_repository)
):
    stocks = await stock_repo.get_all_active()
    return stocks
```

### Using Application Services

```python
from app.application.services.portfolio_service import PortfolioService

portfolio_service = PortfolioService(
    portfolio_repo,
    position_repo,
    allocation_repo,
)
summary = await portfolio_service.get_portfolio_summary()
```

### Using Domain Services

```python
from app.domain.services.priority_calculator import PriorityCalculator

results = PriorityCalculator.calculate_priorities(
    priority_inputs,
    geo_weights,
    industry_weights,
)
```


