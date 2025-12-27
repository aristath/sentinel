# Arduino Trader - Architecture Overview

## Quick Start

This project follows **Clean Architecture** principles with clear separation of concerns.

### Project Structure

```
app/
├── domain/              # Pure business logic (no infrastructure dependencies)
│   ├── repositories/    # Repository interfaces (contracts)
│   ├── services/       # Domain services (PriorityCalculator)
│   ├── utils/          # Shared utilities (priority_helpers)
│   └── exceptions.py   # Domain exceptions
│
├── infrastructure/      # External concerns
│   ├── database/       # SQLite repository implementations
│   ├── hardware/       # LED display
│   └── dependencies.py # FastAPI dependency injection
│
├── application/         # Orchestration layer
│   └── services/       # Application services
│       ├── PortfolioService
│       ├── RebalancingService
│       ├── ScoringService
│       └── TradeExecutionService
│
└── api/                 # Thin controllers (delegation only)
    ├── stocks.py
    ├── portfolio.py
    ├── trades.py
    ├── allocation.py
    └── status.py
```

## Key Principles

### 1. Repository Pattern
All database access goes through repository interfaces:

```python
# Domain layer defines interface
class StockRepository(ABC):
    @abstractmethod
    async def get_by_symbol(self, symbol: str) -> Optional[Stock]:
        pass

# Infrastructure implements it
class SQLiteStockRepository(StockRepository):
    async def get_by_symbol(self, symbol: str) -> Optional[Stock]:
        # SQLite implementation
        pass

# API uses it via dependency injection
@router.get("/stocks/{symbol}")
async def get_stock(
    stock_repo: StockRepository = Depends(get_stock_repository)
):
    return await stock_repo.get_by_symbol(symbol)
```

### 2. Dependency Injection
FastAPI dependencies provide repository instances:

```python
# infrastructure/dependencies.py
def get_stock_repository(
    db: aiosqlite.Connection = Depends(get_db)
) -> StockRepository:
    return SQLiteStockRepository(db)

# Usage in API
@router.get("/stocks")
async def get_stocks(
    stock_repo: StockRepository = Depends(get_stock_repository)
):
    return await stock_repo.get_all_active()
```

### 3. Application Services
Orchestrate domain services and repositories:

```python
class PortfolioService:
    def __init__(
        self,
        portfolio_repo: PortfolioRepository,
        position_repo: PositionRepository,
        allocation_repo: AllocationRepository,
    ):
        self._portfolio_repo = portfolio_repo
        self._position_repo = position_repo
        self._allocation_repo = allocation_repo

    async def get_portfolio_summary(self) -> PortfolioSummary:
        # Orchestrates multiple repositories
        positions = await self._position_repo.get_all()
        latest = await self._portfolio_repo.get_latest()
        # ... business logic ...
        return summary
```

### 4. Domain Services
Pure business logic with no infrastructure dependencies:

```python
class PriorityCalculator:
    @staticmethod
    def calculate_priority(
        input: PriorityInput,
        geo_weights: Dict[str, float],
        industry_weights: Dict[str, float],
    ) -> PriorityResult:
        # Pure business logic - no database, no I/O
        quality_score = input.stock_score * 0.4
        # ... calculations ...
        return PriorityResult(...)
```

## Usage Examples

### Adding a New Repository

1. **Define interface** in `domain/repositories/`:
```python
class NewRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: int) -> Optional[NewEntity]:
        pass
```

2. **Implement** in `infrastructure/database/repositories/`:
```python
class SQLiteNewRepository(NewRepository):
    async def get_by_id(self, id: int) -> Optional[NewEntity]:
        # SQLite implementation
        pass
```

3. **Add dependency** in `infrastructure/dependencies.py`:
```python
def get_new_repository(
    db: aiosqlite.Connection = Depends(get_db)
) -> NewRepository:
    return SQLiteNewRepository(db)
```

4. **Use in API**:
```python
@router.get("/new/{id}")
async def get_new(
    new_repo: NewRepository = Depends(get_new_repository)
):
    return await new_repo.get_by_id(id)
```

### Creating an Application Service

```python
# application/services/new_service.py
class NewService:
    def __init__(
        self,
        new_repo: NewRepository,
        other_repo: OtherRepository,
    ):
        self._new_repo = new_repo
        self._other_repo = other_repo

    async def do_something(self, id: int) -> Result:
        # Orchestrate repositories and domain services
        entity = await self._new_repo.get_by_id(id)
        # ... business logic ...
        return result
```

## Testing

### Unit Tests (Domain Logic)
Test domain services without database:

```python
def test_priority_calculator():
    input = PriorityInput(stock_score=80, ...)
    result = PriorityCalculator.calculate_priority(input, {}, {})
    assert result.combined_priority > 0
```

### Integration Tests (Repositories)
Test repository implementations with test database:

```python
@pytest.mark.asyncio
async def test_stock_repository(stock_repo):
    stock = await stock_repo.get_by_symbol("AAPL")
    assert stock is not None
```

## Benefits

✅ **Testable** - Domain logic testable without database  
✅ **Maintainable** - Clear separation of concerns  
✅ **Flexible** - Easy to swap implementations  
✅ **Scalable** - Easy to add new features  
✅ **Clean** - No code duplication  
✅ **Type-safe** - Full type hints throughout  

## Migration Notes

See `MIGRATION_NOTES.md` for details on migrating existing code to use the new architecture.

## Documentation

- `ARCHITECTURE.md` - Detailed architecture documentation
- `REFACTORING_SUMMARY.md` - What was changed and why
- `MIGRATION_NOTES.md` - How to migrate existing code
- `ARCHITECTURE_COMPLETE.md` - Completion status


