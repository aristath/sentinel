# Arduino Trader

**Autonomous portfolio management system for retirement fund management**

Arduino Trader is a production-ready autonomous trading system that manages a real retirement fund. It runs on an Arduino Uno Q, handling monthly deposits, automatic trading, dividend reinvestment, and portfolio management with zero human intervention.

**This manages real money. Every line of code matters. Every decision has consequences.**

## Table of Contents

- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Getting Started](#getting-started)
- [Microservices](#microservices)
- [API Reference](#api-reference)
- [Background Jobs](#background-jobs)
- [Development](#development)
- [Deployment](#deployment)
- [Configuration](#configuration)
- [Security Universe](#security-universe)

---

## Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    Arduino Uno Q (ARM64)                      │
│                                                                │
│  ┌───────────────────────────────────────────────────────┐   │
│  │           trader (Main Application)                 │   │
│  │                                                         │   │
│  │  • Portfolio Management                                 │   │
│  │  • Autonomous Trading                                   │   │
│  │  • Risk Management                                      │   │
│  │  • Dividend Reinvestment (DRIP)                        │   │
│  │  • Emergency Rebalancing                               │   │
│  │  • Market Regime Detection                             │   │
│  │  • Cash Flow Processing                                │   │
│  │  • Background Job Scheduler                            │   │
│  │  • Planning Evaluation (built-in)                      │   │
│  │                                                         │   │
│  │  Port: 8001 (HTTP API)                                 │   │
│  │  Databases: SQLite (7 databases)                       │   │
│  └───────────┬─────────────────────────┬──────────────────┘   │
│              │                         │                       │
└──────────────┼─────────────────────────┼───────────────────────┘
               │                         │
               │ HTTP
               ▼
       ┌──────────────────────────────┐
       │   unified (Python)           │
       │                              │
       │  • Portfolio Optimization    │
       │    (PyPFOpt)                 │
       │  • Broker API Gateway        │
       │    (Tradernet)               │
       │  • Market Data               │
       │    (Yahoo Finance)           │
       │                              │
       │  Port: 9000                  │
       └──────────────────────────────┘
```

### Design Principles

**Autonomous Operation**
- Runs without human intervention
- Handles monthly deposits automatically
- Self-healing and graceful degradation
- Operates intelligently when services are unavailable

**Clean & Lean**
- No legacy code, no deprecations, no dead code
- Single user, single device - no backwards compatibility
- Every file, function, and line earns its place

**Proper Solutions**
- Fix root causes, not symptoms
- Understand full impact before changes
- Production-grade error handling

---

## Technology Stack

### Main Application (trader)

**Language:** Go 1.22+
- **HTTP Router:** Chi (stdlib-based, lightweight)
- **Database:** SQLite with modernc.org/sqlite (pure Go, no CGo)
- **Scheduler:** robfig/cron for background jobs
- **Logging:** zerolog (structured, high-performance)
- **Configuration:** godotenv

**Architecture:** Clean Architecture
- Domain layer is pure (no external dependencies)
- Dependency flows inward (handlers → services → repositories → domain)
- Repository pattern for all data access
- Constructor injection only

**Performance Targets:**
- Memory: <1GB (vs 3.5GB Python)
- API Latency: <50ms (vs 200ms Python)
- Planning: 10-15s (vs 2min Python)
- Startup: 2-3s (vs 10s Python)

### Microservices

1. **unified** (Python/FastAPI) - Unified microservice combining all Python services
   - Port: 9000
   - Purpose: Portfolio optimization, broker API gateway, and market data
   - Libraries:
     - PyPortfolioOpt (portfolio optimization)
     - Tradernet SDK v2.0.0 (trading execution)
     - yfinance (market data)
   - Routes:
     - `/api/pypfopt/*` - Portfolio optimization endpoints
     - `/api/tradernet/api/*` - Broker API endpoints
     - `/api/yfinance/api/*` - Market data endpoints
     - `/health` - Unified health check

**Note:** Planning evaluation is built into the main trader application using an in-process worker pool (no separate microservice).

### Hardware

**Arduino Uno Q** (ARM64)
- Embedded Linux system
- LED matrix display for status
- Low power consumption
- Runs 24/7

---

## Getting Started

### Prerequisites

- Go 1.22+ (for building trader)
- Python 3.10+ (for microservices)
- Existing SQLite databases (7-database architecture)
- Tradernet API credentials
- Docker (optional, for containerized deployment)

### Installation

#### 1. Clone Repository

```bash
cd /path/to/arduino-trader
```

#### 2. Build Main Application

```bash
cd trader

# Install dependencies
go mod download

# Build
go build -o trader ./cmd/server

# Or build for Arduino Uno Q (ARM64)
GOOS=linux GOARCH=arm64 go build -o trader-arm64 ./cmd/server
```

#### 3. Configure Credentials

**Recommended: Use Settings UI**

1. Start the application: `./trader`
2. Open the web UI (default: http://localhost:8001)
3. Click the Settings icon (gear) in the header
4. Navigate to the **Credentials** tab
5. Enter your Tradernet API Key and Secret

**Alternative: Use API**

```bash
# Set credentials via API
curl -X PUT http://localhost:8001/api/settings/tradernet_api_key \
  -H "Content-Type: application/json" \
  -d '{"value": "your_api_key"}'

curl -X PUT http://localhost:8001/api/settings/tradernet_api_secret \
  -H "Content-Type: application/json" \
  -d '{"value": "your_api_secret"}'
```

**Legacy: .env file (deprecated)**

The `.env` file is no longer required. If you need to set infrastructure settings (ports, service URLs), you can create a `.env` file, but API credentials should be configured via the Settings UI.

#### 4. Start Microservices

**Option A: Docker Compose (Recommended)**

```bash
# Start all microservices
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

**Option B: Manual Start**

```bash

# Unified microservice
cd microservices/unified
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export TRADERNET_API_KEY="your_key"  # Optional, can be passed via headers
export TRADERNET_API_SECRET="your_secret"  # Optional, can be passed via headers
uvicorn app.main:app --host 0.0.0.0 --port 9000
```

#### 5. Run Main Application

```bash
cd trader
./trader
```

### Verify Installation

```bash
# Check main app health
curl http://localhost:8001/health

# Check unified microservice
curl http://localhost:9000/health

# Get portfolio summary
curl http://localhost:8001/api/portfolio/summary
```

---

## Microservices

### unified (Unified Microservice)

**Purpose:** Single Python service combining portfolio optimization, broker API gateway, and market data services.

**Port:** 9000

**Technology:** Python 3.11+ with FastAPI

**Key Features:**
- Portfolio optimization (PyPFOpt)
- Trading execution and portfolio sync (Tradernet)
- Market data and fundamentals (Yahoo Finance)

**API Endpoints:**

**Portfolio Optimization (`/api/pypfopt/*`):**
- `POST /api/pypfopt/optimize/progressive` - Progressive optimization (used by planner)
- `POST /api/pypfopt/optimize/mean-variance` - Classic Markowitz optimization
- `POST /api/pypfopt/optimize/hrp` - Hierarchical Risk Parity
- `POST /api/pypfopt/risk-model/covariance` - Calculate covariance matrix

**Broker API (`/api/tradernet/api/*`):**
- Trading execution, portfolio sync, market data via Tradernet SDK v2.0.0

**Key Features:**
- Order execution (BUY/SELL)
- Portfolio position sync
- Cash balance tracking
- Trade history retrieval
- Market data (quotes, historical OHLC)
- Security lookup (symbol/ISIN resolution)

**API Endpoints:**

**Trading:**
- `POST /api/trading/place-order` - Execute trade
- `GET /api/trading/pending-orders` - Get pending orders
- `GET /api/trading/pending-orders/{symbol}` - Check symbol pending orders
- `GET /api/trading/pending-totals` - Get pending order totals by currency

**Portfolio:**
- `GET /api/portfolio/positions` - Get current positions
- `GET /api/portfolio/cash-balances` - Get cash balances
- `GET /api/portfolio/cash-total-eur` - Total cash in EUR

**Transactions:**
- `GET /api/transactions/cash-movements` - Withdrawal history
- `GET /api/transactions/cash-flows` - All cash flows (dividends, fees)
- `GET /api/transactions/executed-trades` - Trade history

**Market Data:**
- `GET /api/market-data/quote/{symbol}` - Get quote
- `POST /api/market-data/quotes` - Batch quotes
- `GET /api/market-data/historical/{symbol}` - Historical OHLC

**Security Lookup:**
- `GET /api/securities/find` - Find security by symbol/ISIN
- `GET /api/securities/info/{symbol}` - Security metadata

**Market Data (`/api/yfinance/api/*`):**
- Current prices, historical data, fundamentals, analyst data via yfinance

**Environment Variables:**
```bash
TRADERNET_API_KEY=your_api_key  # Optional, can be passed via headers
TRADERNET_API_SECRET=your_api_secret  # Optional, can be passed via headers
PORT=9000
LOG_LEVEL=INFO
```

---

## Database Architecture

The system uses a clean 7-database architecture:

1. **universe.db** - Investment universe (securities, groups)
2. **config.db** - Application configuration (settings, allocation targets)
3. **ledger.db** - Immutable financial audit trail (trades, cash flows, dividends)
4. **portfolio.db** - Current portfolio state (positions, scores, metrics, snapshots)
5. **agents.db** - Strategy management (sequences, evaluations)
6. **history.db** - Historical time-series data (prices, rates, cleanup tracking)
7. **cache.db** - Ephemeral operational data (recommendations, cache)

All databases use SQLite with WAL mode and profile-specific PRAGMAs for optimal performance and safety.

---

## Portfolio Management

The system manages a single unified portfolio with a configurable trading strategy. Cash balances are represented as synthetic securities in the portfolio database, allowing for seamless integration with position tracking and portfolio calculations.

### Cash-as-Securities Architecture

Cash balances are stored as positions in `portfolio.db` using synthetic securities with symbols like `CASH:EUR`, `CASH:USD`, etc. This approach allows cash to be treated consistently with other positions, enabling:

- Unified portfolio calculations
- Automatic cash balance tracking
- Seamless integration with position sync
- Direct cash position management

### Configuration

The planner configuration is stored in `config.db` and managed through the UI with settings like sliders, number inputs, and checkboxes.

---

## API Reference

### System

- `GET /health` - Health check
- `GET /api/system/status` - System status & metrics
- `GET /api/system/jobs` - Background job status
- `POST /api/system/jobs/{job_name}/run` - Trigger job manually
- `GET /api/system/logs` - Recent logs
- `POST /api/system/restart` - Restart services

### Portfolio

- `GET /api/portfolio/summary` - Portfolio summary with positions
- `GET /api/portfolio/positions` - All positions
- `GET /api/portfolio/positions/{isin}` - Position details
- `GET /api/portfolio/allocation` - Current allocation
- `GET /api/portfolio/performance` - Performance metrics
- `GET /api/portfolio/cash-balances` - Cash by currency
- `GET /api/portfolio/total-value` - Total portfolio value (EUR)

### Trading

- `GET /api/trades` - Trade history
- `GET /api/trades/{id}` - Trade details
- `POST /api/trades/execute` - Execute manual trade (with 7-layer safety validation)
- `GET /api/trades/pending` - Pending orders

### Planning & Recommendations

- `GET /api/planning/recommendations` - Current recommendations
- `POST /api/planning/generate` - Generate new recommendations
- `GET /api/planning/status` - Planning job status
- `GET /api/planning/config` - Planner configuration
- `POST /api/planning/config` - Update planner config
- `POST /api/planning/recommendations/dismiss/{id}` - Dismiss recommendation

### Allocation

- `GET /api/allocation/status` - Allocation status
- `GET /api/allocation/targets` - Target allocations
- `POST /api/allocation/targets` - Update targets
- `GET /api/allocation/rebalance` - Rebalancing suggestions
- `POST /api/allocation/rebalance/execute` - Execute rebalancing

### Securities (Universe)

- `GET /api/securities` - List all securities
- `GET /api/securities/{isin}` - Security details
- `POST /api/securities` - Create security
- `POST /api/securities/add-by-identifier` - Add by symbol/ISIN
- `PUT /api/securities/{isin}` - Update security
- `POST /api/securities/{isin}/refresh-data` - Refresh security data
- `DELETE /api/securities/{isin}` - Remove security

### Dividends

- `GET /api/dividends` - Dividend history
- `GET /api/dividends/pending` - Pending dividends
- `POST /api/dividends/reinvest` - Manual DRIP trigger
- `GET /api/dividends/settings` - DRIP settings
- `POST /api/dividends/settings` - Update DRIP settings

### Analytics

- `GET /api/analytics/performance` - Performance metrics
- `GET /api/analytics/risk` - Risk metrics
- `GET /api/analytics/attribution` - Performance attribution
- `GET /api/analytics/concentration` - Concentration analysis

### Charts

- `GET /api/charts/sparklines` - Sparkline data for dashboard
- `GET /api/charts/historical/{isin}` - Historical price chart

### Settings

- `GET /api/settings` - All settings
- `GET /api/settings/{key}` - Get setting
- `POST /api/settings/{key}` - Update setting
- `POST /api/settings/trading-mode` - Switch trading mode (live/research)
- `GET /api/settings/cache/clear` - Clear caches


---

## Background Jobs

The system runs scheduled background jobs for autonomous operation:

### Operational Jobs

**sync_cycle** (Every 5 minutes)
- Sync portfolio positions from broker
- Sync cash balances
- Sync executed trades
- Update security prices (market-aware)
- Process cash flows (deposits, dividends, fees)
- Update LED display ticker

**planner_batch** (Every 15 minutes)
- Generate trading recommendations
- Evaluate sequences using built-in evaluation service
- Score opportunities
- Create optimal trade plans

**event_based_trading** (Every 5 minutes)
- Monitor for planning completion
- Execute approved trades
- Enforces minimum execution intervals (30 minutes)

**dividend_reinvestment** (Daily at 10:00 AM)
- Detect new dividends
- Classify high-yield (≥3%) vs low-yield (<3%)
- Auto-reinvest high-yield dividends (DRIP)
- Accumulate low-yield as pending bonuses

**health_check** (Daily at 4:00 AM)
- Database integrity checks
- Auto-recovery for corrupted databases
- Health monitoring for all 7 databases

### Reliability Jobs

**history_cleanup** (Daily at midnight)
- Clean up old historical data
- Maintain database size

**hourly_backup** (Every hour)
- Automated hourly backups of all databases

**daily_backup** (Daily at 1:00 AM)
- Daily backup before maintenance

**daily_maintenance** (Daily at 2:00 AM)
- Database maintenance tasks
- Vacuum operations
- Index optimization

**weekly_backup** (Sunday at 1:00 AM)
- Weekly backup

**weekly_maintenance** (Sunday at 3:30 AM)
- Weekly maintenance tasks

**monthly_backup** (1st day at 1:00 AM)
- Monthly backup

**monthly_maintenance** (1st day at 4:00 AM)
- Monthly maintenance tasks

### Manual Triggers

Operational jobs can be manually triggered via API:

```bash
POST /api/system/jobs/health-check
POST /api/system/jobs/sync-cycle
POST /api/system/jobs/dividend-reinvestment
POST /api/system/jobs/planner-batch
POST /api/system/jobs/event-based-trading
```

Note: Reliability jobs (backups, maintenance, cleanup) run automatically on schedule and are not exposed for manual triggering.

---

## Development

### Prerequisites

- Go 1.22+
- Python 3.10+
- Docker (optional)
- golangci-lint (for linting)
- air (for auto-reload during development)

### Project Structure

```
arduino-trader/
├── trader/                      # Main Go application
│   ├── cmd/server/             # Application entry point
│   ├── internal/               # Private application code
│   │   ├── config/            # Configuration management
│   │   ├── database/          # SQLite access layer
│   │   ├── domain/            # Domain models
│   │   ├── modules/           # Business modules
│   │   │   ├── allocation/   # Allocation management
│   │   │   ├── cash_flows/   # Cash flow processing
│   │   │   ├── cash_utils/   # Cash utility functions
│   │   │   ├── charts/       # Chart data & visualization
│   │   │   ├── cleanup/      # Data cleanup jobs
│   │   │   ├── display/      # LED display management
│   │   │   ├── dividends/    # Dividend processing
│   │   │   ├── evaluation/   # Sequence evaluation (built-in)
│   │   │   ├── opportunities/# Opportunity identification
│   │   │   ├── optimization/ # Portfolio optimization
│   │   │   ├── planning/     # Planning & recommendations
│   │   │   ├── portfolio/    # Portfolio management
│   │   │   ├── rebalancing/  # Rebalancing logic
│   │   │   ├── scoring/      # Security scoring
│   │   │   ├── sequences/    # Trade sequence generation
│   │   │   ├── settings/     # Settings management
│   │   │   ├── trading/      # Trade execution
│   │   │   └── universe/     # Security universe
│   │   ├── services/         # External service clients
│   │   ├── scheduler/        # Background job scheduler
│   │   ├── middleware/       # HTTP middleware
│   │   └── server/           # HTTP server & routes
│   ├── pkg/                  # Public reusable packages
│   │   ├── cache/           # In-memory cache
│   │   ├── events/          # Event system
│   │   └── logger/          # Structured logging
│   └── static/              # Static web assets
├── display/                  # Display system (LED matrix)
│   ├── sketch/              # Arduino C++ sketch
│   └── app/                 # Python display app (Arduino App Framework)
├── microservices/           # Python microservices
│   ├── pypfopt/            # Portfolio optimization (Python)
│   └── tradernet/          # Broker API gateway (Python)
├── scripts/                 # Build & deployment scripts
└── README.md                # This file
```

### Development Workflow

#### Main Application (trader)

```bash
cd trader

# Install dependencies
go mod download

# Install development tools
go install github.com/cosmtrek/air@latest
go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest

# Run with auto-reload
air

# Run tests
go test ./...

# Run tests with coverage
go test -cover ./...

# Run tests with race detector
go test -race ./...

# Format code
go fmt ./...

# Lint
golangci-lint run

# Build
go build -o trader ./cmd/server
```

#### Microservices

Microservices are documented in their respective directories:
- `microservices/pypfopt/`
- `microservices/tradernet/`

### Code Guidelines

#### Clean Architecture

- Domain layer is pure (no external dependencies)
- Dependency flows inward (handlers → services → repositories → domain)
- Use interfaces for dependencies
- Constructor injection only

#### Error Handling

```go
// Return errors, don't panic
func GetSecurity(id int64) (*domain.Security, error) {
    if id <= 0 {
        return nil, fmt.Errorf("invalid security ID: %d", id)
    }
    // ...
}

// Wrap errors with context
if err != nil {
    return fmt.Errorf("failed to fetch security: %w", err)
}
```

#### Testing

- Unit tests for business logic
- Integration tests for database access
- Use testify for assertions
- Mock external dependencies

Example test:

```go
func TestExample(t *testing.T) {
    // Example test
    // MIN(0.9, 0.7) = 0.7
    assert.Equal(t, 0.7, aggression)
}
```

#### Logging

```go
log.Info().
    Str("symbol", symbol).
    Float64("price", price).
    Msg("Security price updated")

log.Error().
    Err(err).
    Str("symbol", symbol).
    Msg("Failed to fetch quote")
```

### Testing

**Main Application:**
```bash
cd trader
go test ./...
```

**Microservices:**
```bash
# pypfopt
cd microservices/pypfopt
pytest

# tradernet
cd microservices/tradernet
pytest
```

**Coverage:**
```bash
# Go
go test -cover ./...

# Python
pytest --cov=app tests/
```

---

## Deployment

### Build for Production

#### Main Application (ARM64 for Arduino Uno Q)

```bash
cd trader

# Cross-compile for ARM64
GOOS=linux GOARCH=arm64 go build -o trader-arm64 ./cmd/server

# Or use build script
./scripts/build.sh arm64
```

#### Microservices (Docker)

```bash
# Build all services
docker-compose build

# Build specific service
docker build -t pypfopt:latest microservices/pypfopt
docker build -t tradernet:latest microservices/tradernet
```

### Systemd Services

#### Main Application

Create `/etc/systemd/system/trader.service`:

```ini
[Unit]
Description=Arduino Trader Go Service
After=network.target

[Service]
Type=simple
User=aristath
WorkingDirectory=/home/aristath/arduino-trader/trader
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/aristath/arduino-trader/trader/trader
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Microservices

Create systemd services for each microservice or use docker-compose.

**Using Docker Compose (Recommended):**

```bash
# Start all microservices
docker-compose up -d

# Enable auto-start on boot
sudo systemctl enable docker
```

### Deployment Checklist

**Pre-Deployment:**
- [ ] Backup all databases
- [ ] Verify schema migrations applied
- [ ] Test in research mode
- [ ] Verify microservices running
- [ ] Check Tradernet credentials
- [ ] Review settings and targets

**Deployment:**
1. Stop existing services
2. Deploy new binary
3. Start microservices (docker-compose up -d)
4. Start main application (systemctl start trader)
5. Verify health endpoints
6. Monitor logs for 24 hours

**Post-Deployment:**
- [ ] Verify first sync cycle completes
- [ ] Check portfolio values match broker
- [ ] Monitor background jobs execution
- [ ] Validate planning recommendations
- [ ] Check cash balances are correct

### Monitoring

**Health Checks:**
```bash
# Main app
curl http://localhost:8001/health

# Microservices
curl http://localhost:9000/health  # unified microservice
```

**System Status:**
```bash
curl http://localhost:8001/api/system/status
```

**Job Status:**
```bash
curl http://localhost:8001/api/system/jobs
```

**Logs:**
```bash
# Systemd logs
journalctl -u trader -f

# Docker logs
docker-compose logs -f
```

### Rollback Plan

**Emergency Stop:**
```bash
sudo systemctl stop trader
```

**Switch to Research Mode:**
```bash
curl -X POST http://localhost:8001/api/settings/trading-mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "research"}'
```

**Full Rollback:**
1. Stop Go service: `sudo systemctl stop trader`
2. Restore previous binary
3. Restart: `sudo systemctl start trader`
4. Verify: `curl http://localhost:8001/health`

---

## Configuration

### API Credentials (Recommended)

**Configure via Settings UI:**

1. Open the Settings modal (gear icon in the header)
2. Navigate to the **Credentials** tab
3. Enter your Tradernet API Key and Secret
4. Credentials are stored securely in the settings database

**Configure via API:**

```bash
# Set Tradernet API Key
PUT /api/settings/tradernet_api_key
{
  "value": "your_api_key"
}

# Set Tradernet API Secret
PUT /api/settings/tradernet_api_secret
{
  "value": "your_api_secret"
}
```

**Note:** Credentials stored in the settings database take precedence over environment variables. The `.env` file is no longer required for credentials (see Legacy Configuration below).

### Settings API

Runtime settings can be configured via API:

```bash
# Get all settings
GET /api/settings

# Get specific setting
GET /api/settings/{key}

# Update setting
POST /api/settings/{key}
{
  "value": "new_value"
}
```

**Key Settings:**

| Setting | Default | Description |
|---------|---------|-------------|
| trading_mode | research | Trading mode (live/research) |
| tradernet_api_key | "" | Tradernet API key (configure via UI or API) |
| tradernet_api_secret | "" | Tradernet API secret (configure via UI or API) |
| buy_cooldown_days | 30 | Days before re-buying same security |
| min_hold_days | 90 | Minimum hold time before selling |
| drip_enabled | true | Auto-reinvest dividends ≥3% yield |
| emergency_rebalancing_enabled | true | Auto-rebalance on negative cash |

### Legacy Configuration (.env file - Deprecated)

**Note:** The `.env` file is **deprecated** for API credentials. Use the Settings UI (Credentials tab) or Settings API instead. The `.env` file is still supported for backwards compatibility but will show a deprecation warning.

**Main Application (.env) - Legacy:**

```bash
# Data directory (contains all 7 databases)
DATA_DIR=../data

# Microservice URLs
UNIFIED_SERVICE_URL=http://localhost:9000

# Tradernet API (DEPRECATED - use Settings UI instead)
TRADERNET_API_KEY=your_api_key
TRADERNET_API_SECRET=your_api_secret

# Server
GO_PORT=8001
LOG_LEVEL=info  # debug, info, warn, error
```

**Infrastructure settings** (service URLs, ports, etc.) may still be configured via environment variables as they are deployment-specific and not user-facing.

---

## Security Universe

The system manages a diversified security universe. Default configuration includes stocks across:

- **EU (50%)**: ASML, SAP, LVMH, Novo Nordisk, Siemens, BNP, Airbus, Sanofi
- **Asia (30%)**: SoftBank, NTT, Toyota, Sony, Samsung, Alibaba, ICBC, WuXi
- **US (20%)**: Apple, Microsoft, J&J, JPMorgan, Caterpillar, P&G, UnitedHealth, Visa, Home Depot

Securities can be added/removed via API or automatically via security discovery/universe pruning jobs.

**Add Security:**
```bash
POST /api/securities/add-by-identifier
{
  "identifier": "AAPL.US",  # symbol or ISIN
  "min_lot": 1,
  "allow_buy": true,
  "allow_sell": true
}
```


---

## Commands

### Development

```bash
# Run main app with auto-reload
cd trader && air

# Run tests
go test ./...

# Format code
go fmt ./...

# Lint
golangci-lint run

# Build
go build -o trader ./cmd/server
```

### Production

```bash
# Build for Arduino Uno Q
GOOS=linux GOARCH=arm64 go build -o trader-arm64 ./cmd/server

# Start services
sudo systemctl start trader
docker-compose up -d

# Stop services
sudo systemctl stop trader
docker-compose down

# View logs
journalctl -u trader -f
docker-compose logs -f

# Health checks
curl http://localhost:8001/health
```

---

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

---

## License

Private - All Rights Reserved

This system manages real retirement funds. All code is proprietary and confidential.

---

## Acknowledgments

Built for autonomous portfolio management on Arduino Uno Q hardware.

**Technology:** Go, Python, SQLite, FastAPI, Docker
**Hardware:** Arduino Uno Q (ARM64)
**Purpose:** Retirement fund management with zero human intervention

---

*This is not a toy. It manages real money for my future. Every line of code matters. Every decision has consequences.*
