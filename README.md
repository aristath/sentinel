# Arduino Trader

Autonomous portfolio management system for Arduino Uno Q. Manages retirement fund with monthly deposits, automated rebalancing, and intelligent security selection.

**This is not a toy.** It manages real money. Every line of code matters.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Background Jobs](#background-jobs)
- [Security Scoring](#security-scoring)
- [Trading System](#trading-system)
- [Multi-Bucket Portfolio System](#multi-bucket-portfolio-system)
- [LED Display](#led-display)
- [Deployment](#deployment)
- [Development](#development)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

## Features

### Core Capabilities

- **Multi-Bucket Portfolio System**: Core + satellite architecture with independent trading strategies per bucket
- **Event-Based Trading**: Executes trades only after holistic planner completes all scenario evaluations
- **Automated Rebalancing**: Invests monthly deposits according to allocation targets
- **Holistic Planner**: Evaluates multiple trading sequences to find optimal portfolio adjustments
- **Security Scoring Engine**: Multi-factor scoring (Technical 50%, Analyst 30%, Fundamental 20%)
- **Portfolio Optimizer**: Mean-Variance and Hierarchical Risk Parity (HRP) optimization
- **Geographic Allocation**: Configurable country/region targets (default: EU 50%, Asia 30%, US 20%)
- **Industry Diversification**: Configurable industry group targets
- **Dividend Reinvestment**: Automatic reinvestment of dividend payments
- **Universe Management**: Automatic security discovery and pruning
- **Web Dashboard**: Real-time portfolio view with Alpine.js + Tailwind CSS
- **LED Status Display**: At-a-glance portfolio health on Arduino Uno Q's 8x13 LED matrix
- **Remote Access**: Secure access via Cloudflare Tunnel

### System Features

- **Clean Architecture**: Strict separation of domain, application, and infrastructure layers
- **Repository Pattern**: All data access through interfaces
- **Dependency Injection**: FastAPI `Depends()` for all dependencies
- **Event-Driven**: Domain events for system coordination
- **Autonomous Operation**: Runs without human intervention
- **Graceful Degradation**: Operates intelligently when APIs are unavailable
- **Comprehensive Testing**: Unit and integration tests with high coverage

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Arduino Uno Q                        │
├─────────────────────────┬───────────────────────────────┤
│      Linux (MPU)        │         MCU (STM32U585)       │
│  ┌─────────────────┐    │    ┌─────────────────────┐    │
│  │   FastAPI App   │    │    │   LED Controller    │    │
│  │   + SQLite DB   │    │    │   8x13 Matrix +     │    │
│  │   + APScheduler │    │    │   4 RGB LEDs        │    │
│  └────────┬────────┘    │    └──────────┬──────────┘    │
│           │             │               │                │
│  ┌────────▼────────┐    │               │                │
│  │ LED Display      │────┼───────────────┘                │
│  │ (Docker App)     │    │  Router Bridge                 │
│  └─────────────────┘    │  (msgpack RPC)                 │
│          │              │                               │
│          ▼              │                               │
│  ┌─────────────────┐    │                               │
│  │   Cloudflared    │    │                               │
│  └────────┬────────┘    │                               │
└───────────┼─────────────┴───────────────────────────────┘
            │
            ▼
    ┌───────────────┐
    │   Internet   │
    │ (Your Phone) │
    └───────────────┘
```

### Code Structure

The codebase is organized into **self-contained modules**, each containing all functionality for a specific feature:

```
app/
├── modules/             # Feature modules (self-contained)
│   ├── allocation/      # Allocation targets and concentration alerts
│   │   ├── api/         # API endpoints
│   │   ├── database/    # Repository implementations
│   │   ├── domain/      # Domain models
│   │   ├── services/    # Application services
│   │   └── jobs/        # Background jobs
│   │
│   ├── analytics/       # Portfolio analytics (attribution, metrics, reconstruction)
│   ├── cash_flows/      # Cash flow ledger and sync
│   ├── display/         # LED display services
│   ├── dividends/       # Dividend reinvestment and history
│   ├── optimization/    # Portfolio optimization (Mean-Variance, HRP)
│   ├── planning/        # Holistic planner and recommendations
│   ├── portfolio/       # Positions, snapshots, history
│   ├── rebalancing/     # Rebalancing logic and services
│   ├── scoring/         # Security and portfolio scoring
│   ├── system/          # Health checks, sync cycle, system stats
│   ├── trading/         # Trade execution, safety, frequency
│   └── universe/        # Security management, discovery, external APIs
│
├── core/                # Shared infrastructure
│   ├── cache/           # SimpleCache
│   ├── database/        # DatabaseManager, schemas, queue
│   ├── events/          # Event system
│   ├── logging/         # Correlation ID logging
│   └── middleware/      # Rate limiting middleware
│
├── shared/              # Shared domain concepts
│   └── domain/
│       ├── events/      # Shared event definitions
│       └── value_objects/  # Currency, Money, Price, etc.
│
├── domain/              # Legacy domain (being phased out)
│   ├── repositories/    # Repository interfaces (Protocol-based)
│   ├── services/        # Shared domain services
│   └── models.py        # Re-exports from modules
│
├── infrastructure/      # External concerns
│   ├── external/        # API clients (Tradernet, Yahoo Finance)
│   ├── hardware/        # LED display controller
│   └── dependencies.py  # FastAPI dependency injection
│
├── application/         # Legacy application services (being phased out)
│   └── services/        # Shared services (currency exchange, etc.)
│
├── repositories/        # Legacy repositories (being phased out)
│   └── ...              # Some repositories still here (calculations, settings, etc.)
│
├── api/                 # Legacy API endpoints (being phased out)
│   ├── charts.py        # Charts API
│   ├── settings.py      # Settings API
│   └── errors.py        # Error handlers
│
└── jobs/               # Background jobs (infrastructure-level)
    ├── scheduler.py     # Job scheduler
    ├── event_based_trading.py
    ├── daily_sync.py
    ├── maintenance.py
    └── ...
```

### Architecture Principles

1. **Domain Layer is Pure**: No imports from infrastructure, repositories, or external APIs
2. **Dependency Flows Inward**: API → Application → Domain
3. **Repository Pattern**: All data access through interfaces
4. **Dependency Injection**: FastAPI `Depends()` for dependencies
5. **Thin Controllers**: API endpoints delegate to services/repositories

### Architecture Violations

Some pragmatic violations exist for performance/convenience on the Arduino's constrained environment:

1. **Global Module Registries** (`app/modules/planning/domain/calculations/base.py`)
   - **Violation**: Uses global mutable state for module registration
   - **Rationale**: Simplifies plugin architecture, reduces boilerplate
   - **Trade-off**: Accepted for ease of adding new calculators/patterns/filters
   - **Mitigation**: Each registry is independent; import order controlled by `__init__.py`

Other violations are documented in code comments where they occur.

### REST Microservices

The system includes 7 REST microservices that can run locally or distributed across multiple Arduino devices:

```
services/
├── universe/        # Security management (Port 8001)
│   ├── models.py          # Pydantic request/response models
│   ├── dependencies.py    # Dependency injection
│   ├── routes.py          # 8 REST endpoints
│   └── main.py            # FastAPI application
│
├── portfolio/       # Position management (Port 8002)
│   └── ...                # 7 REST endpoints
│
├── trading/         # Trade execution (Port 8003)
│   └── ...                # 6 REST endpoints
│
├── scoring/         # Security scoring (Port 8004)
│   └── ...                # 4 REST endpoints
│
├── optimization/    # Portfolio optimization (Port 8005)
│   └── ...                # 3 REST endpoints
│
├── planning/        # Portfolio planning (Port 8006)
│   └── ...                # 4 REST endpoints
│
└── gateway/         # System orchestration (Port 8007)
    └── ...                # 4 REST endpoints
```

**Architecture Benefits:**
- **35-43% memory savings** per service vs gRPC (525-910MB total)
- **Simple HTTP/JSON** - no protobuf compilation, universal compatibility
- **Built-in resilience** - circuit breakers, retries, automatic failover
- **OpenAPI documentation** - interactive docs at `/docs` for each service
- **Flexible deployment** - run all locally or distribute across devices

**Starting Services:**
```bash
# Start individual service
cd services/universe
../../venv/bin/python main.py

# Start all services
for svc in universe portfolio trading scoring optimization planning gateway; do
    cd services/$svc && ../../venv/bin/python main.py &
done
```

**Using HTTP Clients:**
```python
from app.infrastructure.service_discovery import get_service_locator

locator = get_service_locator()
universe_client = locator.create_http_client("universe")

# Get tradable securities
securities = await universe_client.get_securities(tradable_only=True)
```

**Resource Considerations:**

For Arduino Uno Q deployment (2GB RAM, limited CPU):
- **Local mode** (all services in main process): ~63MB memory, minimal overhead
- **Distributed mode** (across multiple devices): ~476MB total (68MB per service)
- Batch operations are optimized for constrained environments
- Services use connection pooling and keep-alive optimization

## Quick Start

### Microservices Installation (Recommended)

**Interactive installer** for easy setup:

```bash
# Clone repository
git clone https://github.com/aristath/autoTrader.git
cd autoTrader

# Run interactive installer
sudo ./install.sh

# Follow the prompts:
# 1. Select services (use 'all' for single-device)
# 2. Enter Tradernet API credentials
# 3. Wait for installation (~15 minutes)
```

Access the dashboard at `http://localhost:8000`

**Installation Options:**
- **Single-device**: Select "all" services during installation
- **Distributed**: Run installer on each device, select specific services
- **Modifying existing**: Re-run installer to add/remove services

### Local Development (Monolith)

For development/testing on the main branch:

```bash
# Clone repository
git clone https://github.com/aristath/autoTrader.git
cd autoTrader

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file and add your API keys
cp .env.example .env
# Edit .env with your Tradernet credentials

# Initialize database
python scripts/seed_stocks.py

# Run development server
uvicorn app.main:app --reload
```

Access the dashboard at `http://localhost:8000`

## Configuration

### Environment Variables

Create `.env` file:

```env
# Application
DEBUG=false
APP_NAME=Arduino Trader

# Tradernet API (Freedom24)
TRADERNET_API_KEY=your_api_key
TRADERNET_API_SECRET=your_api_secret
TRADERNET_BASE_URL=https://api.tradernet.com

# Scheduling (optional, defaults shown)
DAILY_SYNC_HOUR=18
CASH_CHECK_INTERVAL_MINUTES=15

# Investment / Rebalancing (optional, defaults shown)
MIN_CASH_THRESHOLD=400.0
MAX_TRADES_PER_CYCLE=5
MIN_STOCK_SCORE=0.5

# Price Fetching / Retry (optional, defaults shown)
PRICE_FETCH_MAX_RETRIES=3
PRICE_FETCH_RETRY_DELAY_BASE=1.0

# Rate Limiting (optional, defaults shown)
RATE_LIMIT_MAX_REQUESTS=60
RATE_LIMIT_WINDOW_SECONDS=60
RATE_LIMIT_TRADE_MAX=10
RATE_LIMIT_TRADE_WINDOW=60

# Job Failure Tracking (optional, defaults shown)
JOB_FAILURE_THRESHOLD=5
JOB_FAILURE_WINDOW_HOURS=1

# Data Retention (optional, defaults shown)
DAILY_PRICE_RETENTION_DAYS=365
SNAPSHOT_RETENTION_DAYS=90
BACKUP_RETENTION_COUNT=7

# External API Rate Limiting (optional, defaults shown)
EXTERNAL_API_RATE_LIMIT_DELAY=0.33
```

### Database Settings

Many settings are stored in the database and can be configured via the Settings API or UI:

- `job_sync_cycle_minutes` - Sync cycle interval (default: 5)
- `job_maintenance_hour` - Daily maintenance hour (default: 3)
- `job_auto_deploy_minutes` - Auto-deploy interval (default: 5)
- `incremental_planner_enabled` - Enable incremental planner (default: 1)
- `trading_mode` - "live" or "research" (default: "research")
- `transaction_cost_fixed` - Fixed transaction cost per trade
- `transaction_cost_percent` - Percentage transaction cost

## API Reference

### Portfolio

- `GET /api/portfolio` - Current positions with values
- `GET /api/portfolio/summary` - Total value and allocations
- `GET /api/portfolio/history` - Historical portfolio snapshots
- `GET /api/portfolio/transactions` - Portfolio transaction history
- `GET /api/portfolio/cash-breakdown` - Cash balance breakdown
- `GET /api/portfolio/analytics` - Portfolio analytics and metrics

### Securities

- `GET /api/securities` - Securities universe with scores and priorities (stocks, ETFs, ETCs)
- `GET /api/securities/{isin}` - Get single security details by ISIN (e.g., US0378331005)
- `POST /api/securities` - Add new security to universe
- `POST /api/securities/add-by-identifier` - Add security by symbol or ISIN
- `PUT /api/securities/{isin}` - Update security settings (ISIN required)
- `DELETE /api/securities/{isin}` - Remove security from universe (ISIN required)
- `POST /api/securities/refresh-all` - Recalculate all security scores
- `POST /api/securities/{isin}/refresh` - Refresh single security score (ISIN required)
- `POST /api/securities/{isin}/refresh-data` - Refresh security data from APIs (ISIN required)

### Trades

- `GET /api/trades` - Trade history
- `POST /api/trades/execute` - Execute manual trade
- `GET /api/trades/allocation` - Current vs target allocation

### Recommendations

- `GET /api/trades/recommendations` - Get trading recommendations (holistic planner)
- `GET /api/trades/recommendations/stream` - Stream recommendations via SSE
- `POST /api/trades/recommendations/execute` - Execute recommendation sequence

### Planner

- `POST /api/planner/regenerate-sequences` - Regenerate sequences for current portfolio
- `GET /api/planner/status` - Planner status (sequences, progress)
- `GET /api/planner/status/stream` - Stream planner status via SSE

### Allocation

- `GET /api/allocation/targets` - Get allocation targets (country/industry)
- `GET /api/allocation/current` - Current allocation vs targets
- `GET /api/allocation/deviations` - Allocation deviation scores
- `GET /api/allocation/groups/country` - Get country groups
- `GET /api/allocation/groups/industry` - Get industry groups
- `PUT /api/allocation/groups/country` - Update country groups
- `PUT /api/allocation/groups/industry` - Update industry groups
- `DELETE /api/allocation/groups/country/{group_name}` - Delete country group
- `DELETE /api/allocation/groups/industry/{group_name}` - Delete industry group
- `GET /api/allocation/groups/available/countries` - Available countries
- `GET /api/allocation/groups/available/industries` - Available industries
- `GET /api/allocation/groups/allocation` - Group allocation breakdown
- `PUT /api/allocation/groups/targets/country` - Update country group targets
- `PUT /api/allocation/groups/targets/industry` - Update industry group targets

### Cash Flows

- `GET /api/cash-flows` - Cash flow transactions (with filters)
- `GET /api/cash-flows/sync` - Sync cash flows from Tradernet
- `GET /api/cash-flows/summary` - Cash flow summary statistics

### Charts

- `GET /api/charts/sparklines` - Security price sparklines
- `GET /api/charts/securities/{isin}` - Historical price chart data (ISIN required, e.g., US0378331005)

### Optimizer

- `GET /api/optimizer` - Portfolio optimizer status and last results
- `POST /api/optimizer/run` - Run portfolio optimization

### Settings

- `GET /api/settings` - Get all settings
- `PUT /api/settings/{key}` - Update a setting value
- `GET /api/settings/trading-mode` - Get trading mode (live/research)
- `POST /api/settings/trading-mode` - Set trading mode
- `POST /api/settings/restart-service` - Restart main service
- `POST /api/settings/restart` - Restart application
- `POST /api/settings/reset-cache` - Clear all caches
- `GET /api/settings/cache-stats` - Cache statistics
- `POST /api/settings/reschedule-jobs` - Reschedule background jobs

### Status

- `GET /api/status` - System health and status
- `GET /api/status/led/display` - LED display state (for Docker app)
- `GET /api/status/led/display/stream` - LED display state SSE stream
- `GET /api/status/tradernet` - Tradernet connection status
- `GET /api/status/jobs` - Background job health monitoring
- `GET /api/status/database/stats` - Database statistics
- `GET /api/status/markets` - Market hours and status
- `GET /api/status/disk` - Disk usage information
- `GET /api/status/logs` - Application logs
- `GET /api/status/logs/errors` - Error logs only
- `POST /api/status/sync/portfolio` - Manual portfolio sync
- `POST /api/status/sync/prices` - Manual price sync
- `POST /api/status/sync/historical` - Sync historical data
- `POST /api/status/sync/daily-pipeline` - Run daily sync pipeline
- `POST /api/status/sync/recommendations` - Refresh recommendations
- `POST /api/status/maintenance/daily` - Run daily maintenance tasks
- `POST /api/status/jobs/sync-cycle` - Trigger sync cycle job
- `POST /api/status/jobs/weekly-maintenance` - Trigger weekly maintenance
- `POST /api/status/jobs/dividend-reinvestment` - Trigger dividend reinvestment
- `POST /api/status/jobs/universe-pruning` - Trigger universe pruning
- `POST /api/status/jobs/planner-batch` - Trigger planner batch job
- `POST /api/status/jobs/security-discovery` - Trigger security discovery
- `POST /api/status/locks/clear` - Clear stale lock files

### Health Check

- `GET /health` - Health check with service status

## Background Jobs

The system runs 9 scheduled jobs plus 1 background task:

### Scheduled Jobs

1. **sync_cycle** - Every 5 minutes (configurable)
   - Syncs trades, cash flows, portfolio, prices (market-aware)
   - Updates LED display
   - Calls emergency_rebalance internally when negative balances detected

2. **stocks_data_sync** - Hourly
   - Historical data sync (per symbol, only if not synced in 24h)
   - Metrics calculation
   - Score refresh

3. **daily_maintenance** - Daily at configured hour (default: 3:00)
   - Database backup
   - Data cleanup (expired prices, snapshots, caches)
   - WAL checkpoint

4. **weekly_maintenance** - Sunday, 1 hour after daily maintenance
   - Integrity checks
   - Expired backup cleanup

5. **dividend_reinvestment** - Daily, 30 minutes after daily maintenance
   - Automatic reinvestment of dividend payments

6. **universe_pruning** - Monthly on 1st at configured hour
   - Removes low-quality stocks from universe

7. **stock_discovery** - Monthly on 15th at 2:00
   - Discovers and adds high-quality stocks
   - Checks `stock_discovery_enabled` setting internally

8. **planner_batch** - Every 30 minutes (fallback only)
   - Processes next batch of sequences for holistic planner
   - Only runs if incremental mode enabled
   - API-driven batches triggered by event-based trading handle normal processing
   - This scheduled job is a fallback; normal processing is API-driven

9. **auto_deploy** - Every 5 minutes (configurable)
   - Checks GitHub for updates
   - Deploys changes automatically
   - Compiles and uploads sketch if changed

### Background Task

- **event_based_trading** - Continuous (not scheduled, runs as background task)
  - Waits for planning completion (all sequences evaluated)
  - Triggers API-driven planner_batch chains for faster processing
  - Gets optimal recommendation from best result
  - Checks trading conditions (P&L guardrails, frequency limits)
  - Checks market hours (with flexible behavior)
  - Executes trade if allowed
  - Monitors portfolio for changes (two-phase: 30s for 5min, then 1min for 15min)
  - Restarts loop when portfolio hash changes
  - Automatically restarts if it crashes

### Job Configuration

Job intervals can be configured via Settings API:
- `job_sync_cycle_minutes` - Sync cycle interval
- `job_maintenance_hour` - Daily maintenance hour
- `job_auto_deploy_minutes` - Auto-deploy interval

Use `POST /api/settings/reschedule-jobs` to apply changes.

## Security Scoring

The scoring system uses 8 groups with weighted components:

### Technical Score (50% weight)

1. **Trend (40%)**: Price vs 50/200-day moving averages
2. **Momentum (35%)**: 14/30-day rate of change
3. **Volatility (25%)**: Lower volatility = higher score

### Analyst Score (30% weight)

1. **Recommendations (60%)**: Buy/Hold/Sell consensus
2. **Price Target (40%)**: Upside potential

### Fundamental Score (20% weight)

1. **Valuation (40%)**: P/E ratio
2. **Growth (35%)**: Revenue/earnings growth
3. **Profitability (25%)**: Margins

### Scoring Groups

The system uses 8 scoring groups:
- Technical indicators
- Analyst recommendations
- Fundamental metrics
- Market regime analysis
- And more...

Scores are recalculated periodically via `daily_pipeline` job or manually via API.

## Trading System

### Event-Based Trading

The system uses an event-driven approach for trade execution:

1. **Planning Phase**: Holistic planner generates and evaluates trading sequences
2. **Completion Wait**: Event-based trading loop waits for all sequences to be evaluated
3. **Optimal Selection**: Gets best recommendation from planner results
4. **Condition Checks**: Validates trading conditions (P&L guardrails, market hours)
5. **Execution**: Executes trade if conditions met
6. **Monitoring**: Monitors portfolio for changes (two-phase monitoring)
7. **Restart**: Restarts loop when portfolio hash changes

### Market Hours Behavior

- **SELL orders**: Always require market hours check → must execute when market is open
- **BUY orders on flexible markets** (NYSE, NASDAQ, XETR, LSE, etc.): Can execute anytime
- **BUY orders on strict markets** (XHKG, XSHG, XTSE, XASX): Require market hours check

### Holistic Planner

The planner evaluates multiple trading sequences to find optimal portfolio adjustments:

- Generates sequences based on current portfolio state
- Evaluates each sequence for end-state score
- Uses parallel evaluation for performance
- Filters infeasible sequences (insufficient cash, invalid actions)
- Early termination when no improvement found
- Returns best sequence as recommendation

### Trading Modes

- **Research Mode** (default): Recommendations generated but not executed
- **Live Mode**: Recommendations automatically executed

Set via `POST /api/settings/trading-mode`.

## LED Display

The LED display runs as a Docker app via Arduino App Framework and communicates with the MCU via Router Bridge (msgpack RPC over Unix socket).

### Display Features

- **8x13 LED Matrix**: Scrolling text using native Font_5x7
- **4 RGB LEDs**: Status indicators (LED 3: sync, LED 4: processing)
- **Priority System**: 3-pool priority (error > processing > next actions)

### Priority System

1. **Error Pool** (highest priority): "BACKUP FAILED", "ORDER PLACEMENT FAILED", etc.
2. **Processing Pool** (medium priority): "SYNCING...", "BUY AAPL €500", etc.
3. **Next Actions Pool** (lowest priority, default): Portfolio value, cash balance, recommendations

The display automatically shows the highest priority non-empty text.

### How It Works

```
FastAPI → /api/status/led/display → Docker Python App → Router Bridge → STM32 MCU → LED Matrix
```

1. Docker Python app (`arduino-app/python/main.py`) polls `/api/status/led/display` every 2 seconds
2. Receives display state with priority
3. Calls MCU functions via Router Bridge:
   - `scrollText(text, speed)` - Scroll text across LED matrix
   - `setRGB3(r, g, b)` - Set RGB LED 3 color
   - `setRGB4(r, g, b)` - Set RGB LED 4 color
4. MCU renders scrolling text using native Font_5x7

### Setup

The LED display is automatically set up by the main deployment script. Manual sketch compilation:

```bash
/home/arduino/arduino-trader/scripts/compile_and_upload_sketch.sh
```

The Docker app is managed by Arduino App Framework and starts automatically on boot.

## Deployment

### Initial Setup

```bash
# SSH into Arduino Uno Q
ssh arduino@192.168.1.11  # Password: aristath

# Clone repository
cd /home/arduino
mkdir -p repos && cd repos
git clone https://github.com/aristath/autoTrader.git
cd autoTrader

# Run setup script
sudo deploy/setup.sh
```

The setup script:
- Creates Python virtual environment
- Installs dependencies
- Sets up systemd service (`arduino-trader`)
- Deploys LED display Docker app
- Compiles and uploads Arduino sketch
- Configures auto-deployment

### Directory Structure

After setup:

```
/home/arduino/
├── repos/autoTrader/          # Git repository (source of truth)
├── arduino-trader/            # Main FastAPI application
│   ├── app/                   # Python application code
│   ├── static/                # Web dashboard
│   ├── data/                  # SQLite databases
│   ├── venv/                  # Python virtual environment
│   └── .env                   # Configuration (API keys)
├── bin/
│   └── auto-deploy.sh         # Legacy auto-deployment script (no longer used)
└── logs/
    └── auto-deploy.log        # Deployment logs
```

### Service Management

```bash
# View status
sudo systemctl status arduino-trader

# View logs
sudo journalctl -u arduino-trader -f

# Restart
sudo systemctl restart arduino-trader

# Stop
sudo systemctl stop arduino-trader
```

### Auto-Deployment

The system uses Python-based deployment infrastructure for reliable automatic updates:

1. **Checks GitHub for updates** every 5 minutes (configurable via Settings UI)
2. **If changes detected**, pulls and syncs files using staged deployment
3. **If sketch files changed**, compiles and uploads sketch automatically
4. **Restarts services** and verifies health checks
5. **File-based locking** prevents concurrent deployments

**Features:**
- Retry logic for network operations (Git fetch/pull)
- Staged deployment with atomic swaps (space-efficient)
- Health checks after service restart
- Better error handling and logging
- Deployment status API endpoints

**Sudo Configuration Required:**

The deployment system needs passwordless sudo access for service management:

```bash
sudo tee /etc/sudoers.d/arduino-trader << 'EOF'
arduino ALL=(ALL) NOPASSWD: /usr/bin/systemctl start arduino-trader
arduino ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop arduino-trader
arduino ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart arduino-trader
arduino ALL=(ALL) NOPASSWD: /usr/bin/systemctl is-active arduino-trader
arduino ALL=(ALL) NOPASSWD: /usr/bin/systemctl status arduino-trader
EOF

sudo chmod 440 /etc/sudoers.d/arduino-trader
sudo visudo -c
```

**Deployment Status API:**

- `GET /api/status/deploy/status` - Get current deployment status (commits, service status, staging info)
- `POST /api/status/deploy/trigger` - Manually trigger deployment check

### Cloudflare Tunnel (Optional)

For remote access without exposing ports:

```bash
# Install cloudflared
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
sudo dpkg -i cloudflared.deb

# Login and create tunnel
cloudflared tunnel login
cloudflared tunnel create arduino-trader

# Configure tunnel
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml << 'EOF'
tunnel: <tunnel-id>
credentials-file: /home/arduino/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: portfolio.yourdomain.com
    service: http://localhost:8000
  - service: http_status:404
EOF

# Run as service
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

## Development

### Code Style

- **Types**: Use `Optional[T]` for nullable types (not `T | None`)
- **I/O**: All I/O operations are async
- **Imports**: Explicit only, no wildcards. Use isort with black profile
- **Naming**: Clarity over brevity (`calculate_portfolio_allocation` not `calc_alloc`)

### Commands

```bash
# Format code
make format          # Black + isort

# Lint code
make lint            # Flake8 + mypy + pydocstyle

# Auto-fix linting
make lint-fix        # Black + isort

# Type checking
make type-check      # mypy

# Security checks
make security        # bandit + safety

# Run all checks
make check           # lint + type-check + security

# Format and check everything
make all             # format + check

# Test coverage
make test-coverage   # pytest with coverage

# Find dead code
make dead-code       # vulture
```

### Architecture Guidelines

1. **Domain Layer**: Pure business logic, no infrastructure dependencies
2. **Repository Pattern**: All data access through interfaces
3. **Dependency Injection**: Use FastAPI `Depends()` for dependencies
4. **Thin Controllers**: API endpoints delegate to services/repositories
5. **Error Handling**: Use `ServiceResult`/`CalculationResult` for operations that can fail

### Adding New Features

The codebase uses a **modular architecture**. Each feature should be self-contained in its own module:

1. **Create Module**: Create a new directory under `app/modules/` (e.g., `app/modules/my_feature/`)
2. **Module Structure**: Each module contains:
   - `api/` - API endpoints (FastAPI routers)
   - `database/` - Repository implementations
   - `domain/` - Domain models and business logic
   - `services/` - Application services (orchestration)
   - `jobs/` - Background jobs (if needed)
   - `external/` - External API clients (if needed)
3. **Repository Interface**: Add to `app/domain/repositories/protocols.py` if shared
4. **Dependencies**: Use FastAPI `Depends()` in `app/infrastructure/dependencies.py`
5. **Register Router**: Add module router to `app/main.py`

**Example**: To add a new "notifications" feature:
- Create `app/modules/notifications/` with subdirectories
- Add `app/modules/notifications/api/notifications.py` with router
- Add `app/modules/notifications/database/notification_repository.py`
- Register router in `app/main.py`: `app.include_router(notifications.router, ...)`

### Testing Philosophy

- **When tests fail, investigate the implementation first, not the tests**
- Tests exist to catch bugs - a failing test is doing its job
- Test edge cases, not just happy paths
- Unit tests for domain logic (no DB, no network)
- Integration tests for APIs and repositories
- Never decrease coverage

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/domain/test_scoring.py
```

### Test Structure

- `tests/unit/` - Unit tests (no database, no network)
- `tests/integration/` - Integration tests (with test database)
- `tests/fixtures/` - Test fixtures

### Test Coverage

Tests cover:
- Domain logic (scoring, analytics, planning)
- Repository implementations
- API endpoints
- Background jobs
- Error recovery paths
- External API failure handling

## Troubleshooting

### Main App Not Starting

```bash
# Check service status
sudo systemctl status arduino-trader

# View logs
sudo journalctl -u arduino-trader -n 50

# Check configuration
cat /home/arduino/arduino-trader/.env

# Verify database
ls -la /home/arduino/arduino-trader/data/
```

### LED Display Not Working

```bash
# Check API endpoint
curl http://localhost:8000/api/status/led/display

# Check Docker app status (Arduino App Framework)
# Verify arduino-router service is running

# Recompile and upload sketch
/home/arduino/arduino-trader/scripts/compile_and_upload_sketch.sh
```

### Auto-Deploy Not Running

```bash
# Check scheduler job status
curl http://localhost:8000/api/status/jobs

# Check deployment status
curl http://localhost:8000/api/status/deploy/status

# Check application logs (deployment logs are in main app logs now)
sudo journalctl -u arduino-trader -f

# Manually trigger deployment via API
curl -X POST http://localhost:8000/api/status/deploy/trigger

# Verify interval setting
# Check Settings > System > Job Scheduling > Auto-Deploy in UI
```

### Jobs Not Running

```bash
# Check job health
curl http://localhost:8000/api/status/jobs

# Check scheduler status
# Review application logs for job errors

# Manually trigger job
curl -X POST http://localhost:8000/api/status/jobs/sync-cycle
```

### Database Issues

```bash
# Check database stats
curl http://localhost:8000/api/status/database/stats

# Check disk usage
curl http://localhost:8000/api/status/disk

# Clear stale locks
curl -X POST http://localhost:8000/api/status/locks/clear
```

### Reset Everything

```bash
# Stop service
sudo systemctl stop arduino-trader

# Backup data (optional)
cp -r /home/arduino/arduino-trader/data /home/arduino/arduino-trader/data.backup

# Remove application
rm -rf /home/arduino/arduino-trader

# Run setup again
sudo /home/arduino/repos/autoTrader/deploy/setup.sh
```

## Multi-Bucket Portfolio System

The system implements a **core + satellite** portfolio architecture that enables independent trading strategies within a single portfolio:

### Architecture

- **Core bucket (70-85%)**: Conservative, diversified strategy for long-term stability
- **Satellite buckets (15-30% combined)**: Multiple independent strategies testing different approaches

Each bucket operates autonomously with its own:
- Universe of securities (filtered by `bucket_id`)
- Trading strategy and parameters
- Risk management (aggression levels, hibernation)
- Cash balance tracking (EUR/USD)
- Performance measurement

### Database Schema

The satellites module uses **8 tables** in `satellites.db`:

1. **buckets** - Bucket definitions (id, name, bucket_type, status, target_allocation_pct, high_water_mark)
2. **bucket_balances** - Per-bucket cash balances (bucket_id, currency, balance)
3. **bucket_transactions** - Audit trail (deposit/withdrawal/transfer_in/transfer_out/trade/dividend)
4. **satellite_settings** - Strategy configuration (preset, sliders, toggles, dividend_handling)
5. **bucket_performance** - Performance metrics tracking
6. **bucket_rebalance_history** - Rebalancing event history
7. **bucket_trade_history** - Trade attribution
8. **bucket_dividend_routing** - Dividend routing rules

**Critical invariant maintained**: `SUM(bucket_balances[EUR]) == actual_broker_balance[EUR]`

Daily reconciliation ensures virtual balances match reality.

### Core Features

#### 1. Automatic Deposit Splitting

When deposits arrive, they're automatically split across buckets based on target allocations:

```python
# Example: €1000 deposit with 3 buckets
Core: €700 (70% target)
Satellite A: €200 (20% target)
Satellite B: €100 (10% target)
```

#### 2. Independent Trading Strategies

Each satellite can use a different strategy preset:

- **Momentum Hunter** (Aggressive): Risk 70%, Hold 30 days, Breakout entry, Focused positions (10-15 stocks)
- **Steady Eddy** (Conservative): Risk 30%, Hold 144 days, Dip buyer, Diversified (15-20 stocks)
- **Dip Buyer** (Value): Risk 50%, Hold 126 days, Pure dip entry, Moderate spread
- **Dividend Catcher** (Income): Risk 40%, Hold 36 days, Balanced entry, Broad spread (20+ stocks)

Strategy parameters map sliders (0.0-1.0) to concrete trading parameters:
- `risk_appetite` → position size (15-40%), stop loss (5-20%)
- `hold_duration` → target hold days (1-180)
- `entry_style` → dip buyer (0.0) vs breakout buyer (1.0)
- `position_spread` → max positions (3-23)
- `profit_taking` → take profit threshold (5-30%)

#### 3. Dynamic Risk Management (Aggression)

Aggression level (0-1) scales position sizes based on:

**Allocation Factor:**
- ≥100% of target → 1.0 (full aggression)
- 80-100% → 0.8
- 60-80% → 0.6
- 40-60% → 0.4
- <40% → 0.0 (hibernation)

**Drawdown Factor:**
- <15% drawdown → 1.0
- 15-25% → 0.7
- 25-35% → 0.3
- ≥35% → 0.0 (hibernation)

**Final aggression = MIN(allocation_factor, drawdown_factor)** - most conservative wins.

#### 4. Safety Systems

**Automatic Hibernation:**
- Triggered at 35%+ drawdown
- All trading stops
- Auto-resumes when drawdown improves to <30%

**Circuit Breaker:**
- Pauses bucket after 5 consecutive losses
- Requires manual review to resume

**Win Cooldown:**
- Triggers after >20% monthly gain
- Reduces aggression by 25% for 30 days
- Prevents overleveraging during euphoria

**Graduated Re-Awakening:**
After hibernation, gradual recovery:
1. First trade: 25% position size
2. After 1 win: 50%
3. After 2 wins: 75%
4. After 3 wins: 100% (fully re-awakened)
5. Any loss: Reset to 25%

#### 5. Performance-Based Allocation (Meta-Allocator)

Quarterly (every 3 months), satellite allocations adjust based on performance:

**Metrics calculated:**
- Sharpe ratio (return / volatility)
- Sortino ratio (return / downside volatility)
- Max drawdown
- Calmar ratio (return / max drawdown)
- Win rate, profit factor
- Composite score (weighted combination)

**Reallocation:**
1. Rank satellites by composite score
2. Allocate budget proportionally to scores
3. Apply min/max constraints (3-12% per satellite)
4. Apply dampening (50% toward target)
5. Update target allocations

#### 6. Cash Balance Integrity

**Daily reconciliation:**
- Checks invariant: `SUM(bucket_balances) == actual_balance`
- Auto-corrects drift within €1
- Alerts on larger discrepancies

All trades automatically update bucket balances. Research mode trades don't affect balances.

### API Endpoints

Base URL: `/api/satellites`

**Bucket Management:**
- `POST /satellites` - Create satellite
- `GET /satellites` - List all buckets
- `GET /satellites/{id}` - Get bucket details
- `DELETE /satellites/{id}` - Retire satellite
- `POST /satellites/{id}/pause` - Pause trading
- `POST /satellites/{id}/resume` - Resume trading
- `POST /satellites/{id}/hibernate` - Force hibernation

**Cash Operations:**
- `GET /satellites/{id}/balances` - Get balances
- `POST /satellites/{id}/balances/transfer` - Transfer cash
- `GET /satellites/{id}/balances/transactions` - Transaction history
- `GET /satellites/reconciliation` - Run reconciliation
- `POST /satellites/reconciliation/{currency}/force` - Force reconcile

**Settings:**
- `GET /satellites/{id}/settings` - Get settings
- `POST /satellites/{id}/settings` - Update settings
- `POST /satellites/{id}/apply-preset` - Apply strategy preset
- `GET /presets` - List available presets

**Security Assignment:**
- `PUT /api/securities/{isin}` - Assign security to bucket (set `bucket_id` field)

### Daily Operations

**Morning (Maintenance Job):**
1. Update high water marks for all buckets
2. Check for hibernation triggers (35%+ drawdown)
3. Check for recovery opportunities (<30% drawdown)
4. Check consecutive losses → circuit breaker
5. Log aggression status for all satellites

**Throughout Day (Trading):**
1. Each bucket runs its own planner
2. Plans filtered to bucket's universe
3. Position sizes scaled by aggression
4. Trades automatically update bucket balances

**Evening (Reconciliation Job):**
1. Check `SUM(bucket_balances) == actual_balance`
2. Auto-correct small drift (±€1)
3. Alert on larger discrepancies
4. Generate reconciliation report

**On Deposit:**
1. Detect deposit transaction
2. Calculate allocation per bucket (based on targets)
3. Split deposit across buckets
4. Record transactions for audit trail

**Quarterly (Every 3 Months):**
1. Calculate performance metrics for all satellites
2. Rank by composite score
3. Adjust target allocations
4. Strong performers get more, weak get less
5. Apply dampening to smooth changes

### Configuration

**Settings (via SettingsRepository):**

```python
satellite_budget_pct = 0.20        # 20% total to satellites
satellite_min_pct = 0.03           # 3% minimum per satellite
satellite_max_pct = 0.12           # 12% maximum per satellite
reallocation_dampening = 0.50      # 50% toward target quarterly
```

**Apply Strategy Preset via API:**

```bash
POST /api/satellites/{id}/apply-preset
{
  "preset_name": "momentum_hunter"
}
```

**Or configure manually:**

```bash
POST /api/satellites/{id}/settings
{
  "risk_appetite": 0.7,
  "hold_duration": 0.3,
  "entry_style": 0.8,
  "position_spread": 0.4,
  "profit_taking": 0.6,
  "trailing_stops": true,
  "follow_regime": true
}
```

### Testing

**116 tests, all passing:**
- 96 satellites module tests (domain models, aggression, parameter mapping, presets, reconciliation)
- 15 cash flows tests (deposit processing, splitting)
- 5 integration tests (trade-bucket integration)

The system is production-ready with complete cash integrity, risk management, and performance-based optimization.

## Security Universe

The system manages a diversified security universe. Default configuration includes stocks across:

- **EU (50%)**: ASML, SAP, LVMH, Novo Nordisk, Siemens, BNP, Airbus, Sanofi
- **Asia (30%)**: SoftBank, NTT, Toyota, Sony, Samsung, Alibaba, ICBC, WuXi
- **US (20%)**: Apple, Microsoft, J&J, JPMorgan, Caterpillar, P&G, UnitedHealth, Visa, Home Depot

Stocks can be added/removed via API or automatically via security discovery/universe pruning jobs.

## Tech Stack

- **Backend**: Python 3.10+, FastAPI, SQLite
- **Frontend**: Alpine.js, Tailwind CSS (standalone CLI), Lightweight Charts
- **APIs**: Freedom24/Tradernet, Yahoo Finance (yfinance)
- **Scheduling**: APScheduler
- **MCU**: Arduino sketch for STM32U585 (compiled with Arduino CLI)
- **LED Display**: Docker app via Arduino App Framework
- **Optimization**: PyPortfolioOpt (Mean-Variance, HRP)
- **Analytics**: empyrical-reloaded, pyfolio-reloaded, pandas-ta

## License

MIT
