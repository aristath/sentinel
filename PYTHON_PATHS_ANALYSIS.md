# Python Workflow Paths Analysis

## Configuration

The Python service URL is configured in `trader/internal/config/config.go`:

```go
PythonServiceURL: getEnv("PYTHON_SERVICE_URL", "http://localhost:8000")
```

**Default:** `http://localhost:8000`

## Current Status

Based on code analysis, the Python service URL is configured but **NOT actively used** in the current Go implementation:

### 1. Universe Handlers (`trader/internal/modules/universe/handlers.go`)
- Has a `proxyToPython()` function defined (lines 980-1039)
- **But this function is NEVER called** - no handlers use it
- The `pythonURL` field is stored but unused in practice

### 2. Allocation Handlers (`trader/internal/modules/allocation/handlers.go`)
- Has a `pythonURL` field (line 22) marked as "temporary during migration"
- **NOT used anywhere** - all endpoints are implemented in Go
- This appears to be legacy code from migration

### 3. Portfolio Handlers (`trader/internal/modules/portfolio/handlers.go`)
- Has a `pythonURL` field (line 21) for "analytics endpoint"
- But `HandleGetAnalytics()` (line 186) is **implemented in Go**, not proxied
- The analytics endpoint was migrated to Go

## Conclusion

**The Python service URL configuration appears to be legacy/unused code from the migration from Python to Go.**

All functionality that was previously in Python has been migrated to Go:
- Analytics: ✅ Migrated to Go (`PortfolioService.GetAnalytics()`)
- Allocation: ✅ Fully implemented in Go
- Universe/Securities: ✅ Fully implemented in Go

## Recommendation

1. **If Python service is no longer needed:** Remove the `PythonServiceURL` configuration and all related `pythonURL` fields
2. **If Python service is still needed:** Identify which endpoints should proxy to Python and implement the proxy calls
3. **Current state:** The configuration exists but serves no functional purpose

## Environment Variable

- `PYTHON_SERVICE_URL` - defaults to `http://localhost:8000` but is not used
