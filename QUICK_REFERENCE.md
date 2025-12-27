# Quick Reference Guide

## Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
uvicorn app.main:app --reload

# Or with specific host/port
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Running Tests

```bash
# Run all tests
pytest

# Run only integration tests
pytest tests/integration/

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/integration/test_transactions.py
```

## Key Endpoints

### Health & Status
- `GET /health` - Health check with service status
- `GET /api/status/jobs` - Job health monitoring

### Portfolio
- `GET /api/portfolio/summary` - Portfolio summary
- `GET /api/portfolio/history` - Portfolio history
- `GET /api/portfolio/cash` - Cash balance

### Trades
- `POST /api/trades` - Execute manual trade
- `POST /api/trades/rebalance/preview` - Preview rebalance
- `POST /api/trades/rebalance/execute` - Execute rebalance

### Stocks
- `GET /api/stocks` - List all stocks
- `POST /api/stocks` - Add new stock
- `PUT /api/stocks/{symbol}` - Update stock

## Configuration

### Required Environment Variables
```bash
TRADERNET_API_KEY=your_api_key
TRADERNET_API_SECRET=your_api_secret
DATABASE_PATH=data/trader.db
```

### Optional Configuration
```bash
# Price Fetch Retry
PRICE_FETCH_MAX_RETRIES=3
PRICE_FETCH_RETRY_DELAY_BASE=1.0

# Rate Limiting
RATE_LIMIT_MAX_REQUESTS=60
RATE_LIMIT_WINDOW_SECONDS=60
RATE_LIMIT_TRADE_MAX=10
RATE_LIMIT_TRADE_WINDOW=60

# Job Failure Tracking
JOB_FAILURE_THRESHOLD=5
JOB_FAILURE_WINDOW_HOURS=1

# Debug Mode
DEBUG=false
```

## Key Features

### Transaction Management
```python
from app.database import transaction

async with transaction(db):
    # All operations here are atomic
    await repo.create(item, auto_commit=False)
    await repo.update(item, auto_commit=False)
    # Automatically commits or rolls back
```

### File Locking
```python
from app.infrastructure.locking import file_lock

async with file_lock("operation_name", timeout=60.0):
    # Critical operation here
    await critical_operation()
```

### Repository Usage
```python
# With auto-commit (default)
await repo.create(item)

# Without auto-commit (for transactions)
await repo.create(item, auto_commit=False)
```

## Common Issues & Solutions

### Issue: Lock timeout error
**Solution**: Another operation is in progress. Wait for it to complete or check for stuck lock files in `data/locks/`

### Issue: Rate limit exceeded
**Solution**: Wait for the rate limit window to reset, or adjust limits in configuration

### Issue: Transaction rollback
**Solution**: Check logs for the specific error. Transaction ensures data consistency.

### Issue: Price fetch failures
**Solution**: Check Yahoo Finance API availability. Retry logic will attempt multiple times.

## Monitoring

### Health Check
```bash
curl http://localhost:8000/health
```

### Job Status
```bash
curl http://localhost:8000/api/status/jobs
```

### Logs
Check application logs for:
- Correlation IDs (for request tracing)
- Job execution status
- Error messages with context

## Database

### Location
- Default: `data/trader.db`
- Configurable via `DATABASE_PATH` environment variable

### Schema Version
- Tracked in `schema_version` table
- Automatically created on startup

### Backup
```bash
# Simple backup
cp data/trader.db data/trader.db.backup

# With timestamp
cp data/trader.db "data/trader.db.$(date +%Y%m%d_%H%M%S).backup"
```

## Development

### Code Quality Checks
```bash
# Run linting (if configured)
flake8 app/

# Run type checking (if configured)
mypy app/

# Run all tests
pytest
```

### Adding New Features
1. Follow existing patterns (repository, service, API layers)
2. Add integration tests for critical paths
3. Update documentation
4. Ensure backward compatibility

## Troubleshooting

### Application won't start
1. Check required environment variables are set
2. Verify database path is writable
3. Check port is not already in use
4. Review startup logs for errors

### Jobs not running
1. Check scheduler is initialized in `app/main.py`
2. Verify job functions are registered
3. Check job logs for errors
4. Review `/api/status/jobs` endpoint

### API errors
1. Check rate limiting (429 errors)
2. Verify input validation (422 errors)
3. Review correlation ID in logs
4. Check health endpoint for service status

## Support Files

- `BUG_FIXES_SUMMARY.md` - Detailed bug fixes
- `IMPLEMENTATION_COMPLETE.md` - Implementation overview
- `COMPLETE_IMPLEMENTATION_SUMMARY.md` - Complete summary
- `tests/integration/README.md` - Test documentation


