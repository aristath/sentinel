# Sentinel Agent Guide

## Project Overview

Sentinel is a long-term autonomous portfolio management system built with Python/FastAPI backend and React frontend. It integrates with TraderNet API for live trading and supports automated portfolio rebalancing with a deterministic contrarian strategy.

## Essential Commands

### Development & Testing
**IMPORTANT**: Always activate virtual environment first:
```bash
# Activate venv (Python 3.13 on target device)
source .venv/bin/activate  # Linux/macOS
# or .venv\\Scripts\\activate  # Windows

# Run web server only
python main.py

# Run web server + scheduler
python main.py --all

# Run specific test
pytest tests/test_database.py -v

# Run all tests
pytest

# Lint code
ruff check .

# Format code
ruff format .

# Type check
pyright
```

### Frontend
```bash
cd web/
npm install
npm run dev      # Dev server on http://localhost:5173
npm run build    # Build for production
```

## Code Organization

### Backend Structure
- `sentinel/` - Main application package
  - `api/` - FastAPI routers and endpoints
  - `database/` - Database operations using aiosqlite
  - `jobs/` - APScheduler-based task scheduling
  - `strategy/` - Deterministic portfolio signal and lot-aware sizing logic
  - `services/` - Business logic services
  - `utils/` - Utility functions and decorators
  - `planner/` - Portfolio planning and rebalancing logic
  - `led/` - LED indicator controller (optional hardware)

### Key Architecture Patterns

1. **Singleton Pattern**: Uses `@singleton` decorator for database, settings, and other shared resources
2. **Database Access**: All database operations go through `Database` class in `sentinel/database/main.py`
3. **Settings Management**: All configuration stored in database, editable via web UI
4. **Async/Await**: Entire codebase uses async patterns with FastAPI and aiosqlite

## Important Conventions

### Database Pattern
- Never use raw SQL - use Database class methods
- All database calls are async
- Database file: `sentinel/data/sentinel.db`
- Settings stored in `settings` table, accessible via `Settings` class

### API Structure
- All API routes under `/api/` prefix
- Response format: standardized JSON with consistent error handling
- CORS enabled for development

### Strategy Components
- Deterministic contrarian scoring in `sentinel/strategy/contrarian.py`
- Portfolio allocation logic in `sentinel/planner/allocation.py`
- Trade recommendation engine in `sentinel/planner/rebalance.py`

### Configuration
- No hardcoded values - all settings go through Settings class
- Trading mode: 'research' (no real trades) or 'live' (real trading)
- Default settings defined in `sentinel/settings.py`

## Testing Approach

### Test Organization
- `tests/` - Main test directory
- `tests/jobs/` - Job scheduling specific tests
- Test files follow pattern `test_*.py`

### Test Commands
```bash
uv run pytest                    # All tests
uv run pytest tests/test_database.py -v  # Specific file
uv run pytest -k "test_settings" -v     # Pattern matching
```

## Critical Gotchas

### Database
- Database is singleton per path - one connection per unique database file
- Always async operations - use `await` with all DB calls
- Auto-seeds default values on first connection

### Settings
- Settings are cached in memory
- Changes via UI update both DB and memory cache
- Default values only applied on empty database

### Trading
- Mode set via settings: 'research' vs 'live'
- Research mode prevents actual trades
- Fee structure configurable via settings

### Scheduler
- APScheduler-based with database persistence
- Jobs stored in database schedules
- Market hours checking via BrokerMarketChecker

### Frontend
- Vite dev server proxies `/api` to port 8000
- Production build served via FastAPI static files
- Build output goes to `web/dist/`

## Security Considerations

The app runs on a local network and is not publicly accessible. Security is not a concern for this internal system.

## Deployment Notes

- Auto-deploys to main branch - no manual deployment scripts needed
- Designed for Docker deployment on Arduino UNO Q
- Docker compose setup in `docker-compose.yml`
- Systemd service files for auto-start in `systemd/`
- LED controller optional - checks settings before initializing

## Environment Setup

This project uses Python 3.13 target with virtual environment:
- Always activate venv before running commands
- Package dependencies in `pyproject.toml`
- Lock file: `uv.lock`
- Never use `uv run` prefix - always use activated venv

## Common Tasks

### Adding New API Endpoint
1. Create router in `sentinel/api/routers/`
2. Import in `sentinel/app.py`
3. Include router with appropriate prefix
4. Add tests in `tests/test_api_*.py`

### Modifying Database Schema
1. Update schema in `sentinel/database/base.py`
2. Add migration logic in Database class
3. Update all affected database methods

### Modifying Strategy Logic
1. Update deterministic signals in `sentinel/strategy/contrarian.py`
2. Update sleeve or weighting behavior in `sentinel/planner/allocation.py`
3. Update trade generation constraints in `sentinel/planner/rebalance.py`
4. Add/adjust tests in `tests/test_strategy_contrarian.py` and planner tests

## Error Handling

- All API errors return JSON with consistent structure
- Database operations wrapped with proper error handling
- Logging via standard Python logging module
- Critical errors logged with full stack traces

## Code Style

- Ruff configured with 120 character line length
- Target Python version: 3.13
- Async/await throughout - no sync blocking
- Type hints encouraged but not strictly required
