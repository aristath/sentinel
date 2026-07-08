# Sentinel Agent Guide

## Project Overview

Sentinel is a long-term autonomous portfolio management system built with Python/FastAPI backend and React frontend. It integrates with TraderNet API for live trading and supports automated portfolio rebalancing with a deterministic contrarian strategy.

## Essential Commands

### Development & Testing

**IMPORTANT**: Always activate virtual environment first:

```bash
# Activate venv (Python 3.13+ on target device)
source .venv/bin/activate  # Linux/macOS
# or .venv\Scripts\activate  # Windows

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
  - `app.py` - FastAPI application entry point with lifespan management (scheduler, LED, DB connections)
  - `broker.py` - Singleton Tradernet API wrapper (`Broker` class)
  - `portfolio.py` - Portfolio-level operations and sync (`Portfolio` class)
  - `portfolio_composition.py` - Portfolio analytics: country/industry breakdowns, risk/return metrics, radar chart data (41KB)
  - `security.py` - Single-security operations (`Security` class)
  - `settings.py` - All app configuration via DB (`Settings` class + `DEFAULTS`)
  - `cache.py` - In-memory TTL cache for expensive computations (`Cache` class)
  - `currency.py` - Exchange rate management via Tradernet (`Currency` class)
  - `currency_exchange.py` - Currency conversion utilities
  - `universe.py` - Freedom24 universe reconciliation and security import management
  - `aggregates.py` - Equal-weighted aggregate price series for country/industry groups
  - `backtester.py` - Historical simulation in an isolated in-memory DB (`Backtester`)
  - `price_validator.py` - Price spike/crash detection and interpolation (`PriceValidator`)
  - `snapshot_service.py` - Portfolio snapshot reconstruction and backfill
  - `paths.py` - Data directory path resolution (respects `SENTINEL_DATA_DIR` env var)
  - `version.py` - Application version string
  - `research/` - Research notebooks and analysis scripts
  - `api/` - FastAPI routers and endpoints
  - `config/` - Static configuration (supported categories, currencies)
  - `database/` - Database operations using aiosqlite
  - `jobs/` - APScheduler-based task scheduling
  - `led/` - LED indicator controller (optional hardware, Arduino UNO Q bridge)
  - `planner/` - Portfolio planning and rebalancing logic
  - `strategy/` - Deterministic contrarian scoring and lot classification
  - `utils/` - Utility functions and decorators

### API Routers (`sentinel/api/routers/`)

Each file provides one or more routers mounted under `/api`:

| File | Routers |
|---|---|
| `settings.py` | `settings_router`, `led_router` |
| `portfolio.py` | `portfolio_router`, `allocation_router`, `targets_router` |
| `securities.py` | `securities_router`, `prices_router`, `unified_router` |
| `trading.py` | `trading_router`, `cashflows_router`, `trading_actions_router` |
| `planner.py` | `planner_router` |
| `jobs.py` | `jobs_router` |
| `backup.py` | `backup_router` |
| `system.py` | `system_router`, `cache_router`, `backtest_router`, `exchange_rates_router`, `markets_router`, `meta_router`, `pulse_router` |

### Planner Package (`sentinel/planner/`)

- `planner.py` - Facade class (`Planner`) delegating to the components below
- `allocation.py` - Ideal portfolio computation (`AllocationCalculator`)
- `analyzer.py` - Current portfolio state queries (`PortfolioAnalyzer`)
- `rebalance.py` - Trade recommendation generation (`RebalanceEngine`)
- `rebalance_cash.py` - Cash constraint and deficit-sell logic
- `rebalance_rules.py` - Priority calculation, tranche stages, trade reasons
- `preferences.py` - Clara preference handling and fade logic
- `deposit_history.py` - Rolling 6-month deposit average helper (`DepositHistoryHelper`)
- `models.py` - Data classes: `TradeRecommendation`, `RebalanceSummary`

### Scheduled Job Tasks (`sentinel/jobs/tasks.py`)

Plain async functions executed by APScheduler:

| Task | Purpose |
|---|---|
| `sync_portfolio` | Sync positions from broker |
| `sync_prices` | Fetch 20-year historical prices for all securities |
| `sync_quotes` | Refresh live quote data |
| `sync_metadata` | Sync security metadata from broker (country, industry, lot size) |
| `sync_benchmarks` | Sync benchmark indices roster and prices |
| `sync_exchange_rates` | Fetch current FX rates |
| `sync_trades` | Sync trade history |
| `sync_cashflows` | Sync cashflow history |
| `sync_dividends` | Sync dividend records |
| `snapshot_backfill` | Reconstruct missing portfolio snapshots |
| `aggregate_compute` | Recompute country/industry aggregate price series |
| `trading_check_markets` | Check market open status |
| `trading_execute` | Execute pending trade recommendations |
| `trading_rebalance` | Generate new trade recommendations via Planner |
| `trading_balance_fix` | Correct quantity mismatches between DB and broker |
| `planning_refresh` | Refresh planner state without generating trades |
| `backup_r2` | Upload DB backup to Cloudflare R2 |

### Key Architecture Patterns

1. **Singleton Pattern**: Uses `@singleton` decorator for `Database`, `Settings`, `Broker`, `Portfolio`, `Currency`, and other shared resources
2. **Database Access**: All database operations go through `Database` class in `sentinel/database/main.py`
3. **Settings Management**: All configuration stored in database, editable via web UI
4. **Async/Await**: Entire codebase uses async patterns with FastAPI and aiosqlite

## Important Conventions

### Database Pattern

- Never use raw SQL - use Database class methods
- All database calls are async
- Database file: `data/sentinel.db` (project root; override with `SENTINEL_DATA_DIR` env var)
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
pytest                    # All tests
pytest tests/test_database.py -v  # Specific file
pytest -k "test_settings" -v     # Pattern matching
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
- Market hours checking via `BrokerMarketChecker`
- `--all` flag required to run scheduler alongside the web server

### Price Validator

- Runs on startup and during price sync
- Detects spikes (>1000% change) and crashes (<-90%)
- Interpolates invalid data rather than dropping it
- Also used to block trades when live price looks anomalous

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

This project uses Python 3.13+ with virtual environment:

- Always activate venv before running commands
- Package dependencies in `pyproject.toml`
- Lock file: `uv.lock`
- Target Python: 3.13 (configured in `pyproject.toml` and `pyright`)

## Common Tasks

### Adding New API Endpoint

1. Create router in `sentinel/api/routers/`
2. Import in `sentinel/api/routers/__init__.py`
3. Include router in `sentinel/app.py`
4. Add tests in `tests/test_api_*.py`

### Modifying Database Schema

1. Update schema in `sentinel/database/base.py`
2. Add migration logic in Database class
3. Update all affected database methods

### Modifying Strategy Logic

1. Update deterministic signals in `sentinel/strategy/contrarian.py`
2. Update sleeve or weighting behavior in `sentinel/planner/allocation.py`
3. Update trade generation constraints in `sentinel/planner/rebalance.py`
4. Update rules/priorities in `sentinel/planner/rebalance_rules.py`
5. Add/adjust tests in `tests/test_strategy_contrarian.py` and planner tests

### Adding a Scheduled Job

1. Add async task function in `sentinel/jobs/tasks.py`
2. Register in `sentinel/jobs/runner.py`
3. Add default schedule via `db.seed_default_job_schedules()`

## Error Handling

- All API errors return JSON with consistent structure
- Database operations wrapped with proper error handling
- Logging via standard Python logging module
- Critical errors logged with full stack traces

## Code Style

- Ruff configured with 120 character line length
- Target Python version: 3.13+
- Async/await throughout - no sync blocking
- Type hints encouraged but not strictly required
