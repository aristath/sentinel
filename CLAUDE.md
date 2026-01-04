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
- **Dependency flows inward**: Handlers → Services → Repositories → Domain
- **Repository pattern**: All data access through interfaces
- **Dependency injection**: Constructor injection only

### When Touching Existing Violations
The codebase has documented violations in the README.md Architecture section. Before fixing or extending them, ask.

## Code Style

### Types
```go
// Use explicit types, avoid interface{} when possible
func GetSecurity(id int64) (*domain.Security, error) {
    // ...
}
```

### Error Handling
- Return errors, don't panic
- Wrap errors with context: `fmt.Errorf("failed to fetch security: %w", err)`
- Use structured logging with zerolog

### Imports
- Explicit only, no wildcards
- Group: stdlib, third-party, local
- Use `goimports` for formatting

### Naming
- Clarity over brevity
- `CalculatePortfolioAllocation` not `CalcAlloc`
- Use camelCase for unexported, PascalCase for exported

## Error Handling

- Return errors from functions, don't panic
- Wrap errors with context using `fmt.Errorf` with `%w` verb
- Log errors with structured logging (zerolog)
- Degrade gracefully - partial results over total failure

## Testing

- Unit tests for domain logic (no DB, no network)
- Integration tests for APIs and repositories
- Tests before implementation for new features
- Never decrease coverage
- Use `testify` for assertions

## Deployment

Runs on Arduino Uno Q:
- Limited resources - optimize accordingly
- Network may fail - handle gracefully
- LED display shows status - keep it informative

## Commands

```bash
go test ./...          # Run all tests
go test -cover ./...   # Run tests with coverage
go fmt ./...           # Format code
go vet ./...           # Run go vet
golangci-lint run      # Run linter
```
