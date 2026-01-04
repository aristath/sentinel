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
│  │  Port: 8080 (HTTP API)                                 │   │
│  │  Databases: SQLite (portfolio.db, state.db, etc.)     │   │
│  └───────────┬─────────────────────────┬──────────────────┘   │
│              │                         │                       │
└──────────────┼─────────────────────────┼───────────────────────┘
               │                         │
               │ HTTP                    │ HTTP
               ▼                         ▼
       ┌──────────────┐          ┌─────────────────┐
       │   pypfopt    │          │   tradernet     │
       │   (Python)   │          │    (Python)     │
       │              │          │                 │
       │ Portfolio    │          │ Broker API      │
       │ Optimization │          │ Trading Gateway │
       │              │          │                 │
       │ Mean-Variance│          │ Market Data     │
       │ HRP          │          │ Order Execution │
       │ Covariance   │          │                 │
       │              │          │                 │
       │ Port: 9001   │          │ Port: 9002      │
       └──────────────┘          └─────────────────┘
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

1. **pypfopt** (Python/FastAPI) - Portfolio optimization service
   - Port: 9001
   - Purpose: Mean-Variance Optimization, Hierarchical Risk Parity
   - Library: PyPortfolioOpt

2. **tradernet** (Python/FastAPI) - Broker API gateway
   - Port: 9002
   - Purpose: Trading execution, portfolio sync, market data
   - Library: Tradernet SDK v1.0.5

**Note:** Planning evaluation is now built into the main trader application (no separate microservice needed).

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
- Existing SQLite databases (portfolio.db, state.db, ledger.db, etc.)
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

# Copy environment file
cp .env.example .env

# Edit configuration
nano .env

# Build
go build -o trader ./cmd/server

# Or build for Arduino Uno Q (ARM64)
GOOS=linux GOARCH=arm64 go build -o trader-arm64 ./cmd/server
```

#### 3. Configure Environment

Edit `.env` file:

```bash
# Database paths
STATE_DB_PATH=/path/to/state.db
PORTFOLIO_DB_PATH=/path/to/portfolio.db
LEDGER_DB_PATH=/path/to/ledger.db

# Microservice URLs
EVALUATOR_GO_URL=http://localhost:9000
PYPFOPT_URL=http://localhost:9001
TRADERNET_URL=http://localhost:9002

# Tradernet API
TRADERNET_API_KEY=your_api_key
TRADERNET_API_SECRET=your_api_secret

# Server
PORT=8080
LOG_LEVEL=info
```

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

# Terminal 1: pypfopt
cd microservices/pypfopt
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 9001

# Terminal 2: tradernet
cd microservices/tradernet
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export TRADERNET_API_KEY="your_key"
export TRADERNET_API_SECRET="your_secret"
uvicorn app.main:app --port 9002
```

#### 5. Run Main Application

```bash
cd trader
./trader
```

### Verify Installation

```bash
# Check main app health
curl http://localhost:8080/health


# Check pypfopt
curl http://localhost:9001/health

# Check tradernet
curl http://localhost:9002/health

# Get portfolio summary
curl http://localhost:8080/api/portfolio/summary
```

---

## Microservices


### 1. pypfopt (Portfolio Optimization Service)

**Purpose:** Mean-Variance Optimization and Hierarchical Risk Parity using PyPortfolioOpt library.

**Port:** 9001

**Technology:** Python 3.10+ with FastAPI

**Key Features:**
- Progressive optimization (main endpoint)
- Mean-Variance Optimization (Markowitz)
- Hierarchical Risk Parity (HRP)
- Covariance matrix calculation
- Risk model computation

**API Endpoints:**
- `POST /optimize/progressive` - Progressive optimization (used by planner)
- `POST /optimize/mean-variance` - Classic Markowitz optimization
- `POST /optimize/hrp` - Hierarchical Risk Parity
- `POST /risk-model/covariance` - Calculate covariance matrix
- `GET /health` - Health check

**Integration:**
Used by the planning module to optimize portfolio allocations based on expected returns and risk constraints.

**Documentation:** See `microservices/pypfopt/README.md`

---

### 2. tradernet (Broker API Gateway)

**Purpose:** Trading execution, portfolio synchronization, and market data via Tradernet broker API.

**Port:** 9002

**Technology:** Python 3.10+ with FastAPI, Tradernet SDK v1.0.5

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

**Environment Variables:**
```bash
TRADERNET_API_KEY=your_api_key
TRADERNET_API_SECRET=your_api_secret
PORT=9002
LOG_LEVEL=INFO
```

**Documentation:** See `microservices/tradernet/README.md`

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

The planner configuration is stored in `config.db` and managed through the UI with settings like sliders, number inputs, and checkboxes. This replaces the previous TOML-based configuration system.

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

### Daily Jobs

**sync_cycle** (Daily at 9:00 AM)
- Sync portfolio positions from broker
- Sync cash balances
- Sync executed trades
- Update security prices
- Process cash flows (deposits, dividends, fees)

**dividend_reinvestment** (Daily at 10:00 AM)
- Detect new dividends
- Classify high-yield (≥3%) vs low-yield (<3%)
- Auto-reinvest high-yield dividends (DRIP)
- Accumulate low-yield as pending bonuses

**planning_generation** (Daily at 2:00 PM)
- Generate trading recommendations
- Evaluate sequences
- Score opportunities
- Create optimal trade plans


### On-Demand Jobs

**emergency_rebalancing** (Triggered on negative cash balance)
- Detect negative balance emergency
- Select positions to sell
- Generate emergency sell orders
- Execute rebalancing trades

**market_regime_detection** (Runs with planning)
- Analyze market conditions
- Detect regime changes (bull/bear/volatile)
- Adjust strategy parameters

### Manual Triggers

All jobs can be manually triggered via API:

```bash
POST /api/system/jobs/{job_name}/run
```

Job names: `sync_cycle`, `dividend_reinvestment`, `planning_generation`

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
│   │   │   ├── analytics/    # Analytics & metrics
│   │   │   ├── dividends/    # Dividend processing
│   │   │   ├── planning/     # Planning & recommendations
│   │   │   ├── portfolio/    # Portfolio management
│   │   │   ├── satellites/   # Multi-bucket strategies
│   │   │   ├── scoring/      # Security scoring
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
├── display/                  # Display system
│   ├── bridge/              # Go bridge service
│   ├── sketch/              # Arduino C++ sketch
│   └── app/                 # Docker Python display app
├── microservices/           # Python microservices
│   ├── pypfopt/            # Portfolio optimization (Python)
│   └── tradernet/          # Broker API gateway (Python)
├── legacy/                  # Legacy Python code (migration reference)
│   ├── app/                # Old Python application
│   └── tests/              # Old Python tests
├── scripts/                 # Build & deployment scripts
├── docs/                    # Documentation
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

See individual service READMEs:
- `microservices/evaluator/README.md`
- `microservices/pypfopt/README.md`
- `microservices/tradernet/README.md`

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
# evaluator
cd microservices/evaluator
go test ./...

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
- [ ] Verify satellite balance reconciliation
- [ ] Monitor background jobs execution
- [ ] Check emergency rebalancing doesn't trigger
- [ ] Validate planning recommendations

### Monitoring

**Health Checks:**
```bash
# Main app
curl http://localhost:8080/health

# Microservices
curl http://localhost:9001/health  # pypfopt
curl http://localhost:9002/health  # tradernet
```

**System Status:**
```bash
curl http://localhost:8080/api/system/status
```

**Job Status:**
```bash
curl http://localhost:8080/api/system/jobs
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
curl -X POST http://localhost:8080/api/settings/trading-mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "research"}'
```

**Full Rollback:**
1. Stop Go service: `sudo systemctl stop trader`
2. Restore previous binary
3. Restart: `sudo systemctl start trader`
4. Verify: `curl http://localhost:8080/health`

---

## Configuration

### Environment Variables

**Main Application (.env):**

```bash
# Database paths
STATE_DB_PATH=/path/to/state.db
PORTFOLIO_DB_PATH=/path/to/portfolio.db
LEDGER_DB_PATH=/path/to/ledger.db

# Microservice URLs
EVALUATOR_GO_URL=http://localhost:9000
PYPFOPT_URL=http://localhost:9001
TRADERNET_URL=http://localhost:9002

# Tradernet API
TRADERNET_API_KEY=your_api_key
TRADERNET_API_SECRET=your_api_secret

# Server
PORT=8080
LOG_LEVEL=info  # debug, info, warn, error

# Background Jobs
ENABLE_SCHEDULER=true

# Display (LED Matrix)
DISPLAY_HOST=localhost
DISPLAY_PORT=5555
```

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
| buy_cooldown_days | 30 | Days before re-buying same security |
| min_hold_days | 90 | Minimum hold time before selling |
| drip_enabled | true | Auto-reinvest dividends ≥3% yield |
| emergency_rebalancing_enabled | true | Auto-rebalance on negative cash |

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
curl http://localhost:8080/health
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
