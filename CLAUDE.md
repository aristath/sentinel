# Arduino Trader

## What This Is

This is an autonomous portfolio management system that manages my retirement fund. It runs on an Arduino Uno Q, handles monthly deposits, and allocates funds according to scoring algorithms and allocation targets.

**This is not a toy.** It manages real money for my future. Every line of code matters. Every decision has consequences.

## Philosophy

### Clean and Lean
- No legacy code, no deprecations, no dead code
- No backwards compatibility - single user, single device
- If code isn't used, delete it
- Every file, function, and line earns its place

### Autonomous Operation
- Must run without human intervention
- Handle monthly deposits automatically
- Recover gracefully from failures
- Operate intelligently when APIs are unavailable

### Proper Solutions
- Fix root causes, not symptoms
- Understand the full impact before changes
- If a fix seems too simple, investigate deeper
- Ask before making architectural changes

## Architecture

### Clean Architecture - Strictly Enforced
- **Domain layer is pure**: No imports from infrastructure, repositories, or external APIs
- **Dependency flows inward**: API → Application → Domain
- **Repository pattern**: All data access through interfaces
- **Dependency injection**: FastAPI `Depends()` for dependencies

### When Touching Existing Violations
The codebase has documented violations in the README.md Architecture section. Before fixing or extending them, ask.

## Code Style

### Types
```python
# Use Optional[T]
def get_security(symbol: str) -> Optional[Security]:
```

### I/O
All I/O operations are async.

### Imports
- Explicit only, no wildcards
- isort with black profile

### Naming
- Clarity over brevity
- `calculate_portfolio_allocation` not `calc_alloc`

## Error Handling

- Use `ServiceResult` / `CalculationResult` for operations that can fail
- Raise domain exceptions, catch at API layer
- Log with context
- Degrade gracefully - partial results over total failure

## Testing

- Unit tests for domain logic (no DB, no network)
- Integration tests for APIs
- Tests before implementation for new features
- Never decrease coverage

## Deployment

Runs on Arduino Uno Q:
- Limited resources - optimize accordingly
- Network may fail - handle gracefully
- LED display shows status - keep it informative

## Commands

```bash
pytest                 # Run tests
make format           # Black + isort
make lint             # Flake8 + mypy
make check            # All checks
```
