# Integration Tests

This directory contains integration tests for critical system paths.

## Test Files

### `test_transactions.py`
Tests transaction management and rollback scenarios:
- Transaction rollback on error
- Transaction commit on success
- Multiple repository operations in transaction
- Nested transactions (savepoints)
- Auto-commit behavior

### `test_concurrent_jobs.py`
Tests concurrent job execution and locking:
- File lock prevents concurrent execution
- File lock timeout handling
- Concurrent position updates with locking
- Concurrent trade execution atomicity

### `test_error_recovery.py`
Tests error recovery paths:
- Trade execution rollback on database error
- Trade execution handles external API failures
- Position sync recovery after partial failure
- Price fetch retry logic
- Allocation target validation errors

### `test_external_api_failures.py`
Tests external API failure handling:
- Yahoo Finance API failures
- Tradernet API connection failures
- Exchange rate cache fallback
- Portfolio sync with API failures
- Health check with degraded services

## Running Tests

```bash
# Run all integration tests
pytest tests/integration/

# Run specific test file
pytest tests/integration/test_transactions.py

# Run with verbose output
pytest tests/integration/ -v

# Run with coverage
pytest tests/integration/ --cov=app --cov-report=html
```

## Test Coverage

These tests cover:
- ✅ Concurrent job execution
- ✅ Transaction rollback scenarios
- ✅ Error recovery paths
- ✅ External API failure handling

## Dependencies

Tests require:
- `pytest>=7.4.0`
- `pytest-asyncio>=0.21.0`
- Test database fixtures (from `conftest.py`)


