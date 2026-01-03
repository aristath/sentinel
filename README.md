# Arduino Trader

**Autonomous portfolio management system for retirement fund management**

Arduino Trader is a production-ready autonomous trading system that manages a real retirement fund. It runs on an Arduino Uno Q, handling monthly deposits, automatic trading, dividend reinvestment, and multi-bucket portfolio strategies with zero human intervention.

**This manages real money. Every line of code matters. Every decision has consequences.**

## Table of Contents

- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Getting Started](#getting-started)
- [Microservices](#microservices)
- [Multi-Bucket Portfolio System](#multi-bucket-portfolio-system)
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
│  │           trader-go (Main Application)                 │   │
│  │                                                         │   │
│  │  • Portfolio Management                                 │   │
│  │  • Autonomous Trading                                   │   │
│  │  • Multi-Bucket Strategies                             │   │
│  │  • Risk Management                                      │   │
│  │  • Dividend Reinvestment (DRIP)                        │   │
│  │  • Emergency Rebalancing                               │   │
│  │  • Market Regime Detection                             │   │
│  │  • Cash Flow Processing                                │   │
│  │  • Background Job Scheduler                            │   │
│  │                                                         │   │
│  │  Port: 8080 (HTTP API)                                 │   │
│  │  Databases: SQLite (portfolio.db, state.db, etc.)     │   │
│  └───────────┬─────────────┬───────────────┬─────────────┘   │
│              │             │               │                  │
└──────────────┼─────────────┼───────────────┼──────────────────┘
               │             │               │
               │ HTTP        │ HTTP          │ HTTP
               ▼             ▼               ▼
       ┌──────────────┐ ┌──────────────┐ ┌─────────────────┐
       │ evaluator │ │   pypfopt    │ │   tradernet     │
       │   (Go)       │ │   (Python)   │ │    (Python)     │
       │              │ │              │ │                 │
       │ Planning     │ │ Portfolio    │ │ Broker API      │
       │ Evaluation   │ │ Optimization │ │ Trading Gateway │
       │ Simulation   │ │              │ │                 │
       │ Monte Carlo  │ │ Mean-Variance│ │ Market Data     │
       │              │ │ HRP          │ │ Order Execution │
       │              │ │ Covariance   │ │                 │
       │              │ │              │ │                 │
       │ Port: 9000   │ │ Port: 9001   │ │ Port: 9002      │
       └──────────────┘ └──────────────┘ └─────────────────┘
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

### Main Application (trader-go)

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

1. **evaluator** (Go) - Planning evaluation service
   - Port: 9000
   - Purpose: High-performance sequence evaluation (10-100x faster than Python)
   - Features: Worker pools, Monte Carlo simulation, batch processing

2. **pypfopt** (Python/FastAPI) - Portfolio optimization service
   - Port: 9001
   - Purpose: Mean-Variance Optimization, Hierarchical Risk Parity
   - Library: PyPortfolioOpt

3. **tradernet** (Python/FastAPI) - Broker API gateway
   - Port: 9002
   - Purpose: Trading execution, portfolio sync, market data
   - Library: Tradernet SDK v1.0.5

### Hardware

**Arduino Uno Q** (ARM64)
- Embedded Linux system
- LED matrix display for status
- Low power consumption
- Runs 24/7

---

## Getting Started

### Prerequisites

- Go 1.22+ (for building trader-go)
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
cd trader-go

# Install dependencies
go mod download

# Copy environment file
cp .env.example .env

# Edit configuration
nano .env

# Build
go build -o trader-go ./cmd/server

# Or build for Arduino Uno Q (ARM64)
GOOS=linux GOARCH=arm64 go build -o trader-go-arm64 ./cmd/server
```

#### 3. Configure Environment

Edit `.env` file:

```bash
# Database paths
STATE_DB_PATH=/path/to/state.db
PORTFOLIO_DB_PATH=/path/to/portfolio.db
LEDGER_DB_PATH=/path/to/ledger.db
SATELLITES_DB_PATH=/path/to/satellites.db

# Microservice URLs
EVALUATOR_GO_URL=http://localhost:9000
PYPFOPT_URL=http://localhost:9001
TRADERNET_URL=http://localhost:9002

# Tradernet API
TRADERNET_API_KEY=your_api_key
TRADERNET_API_SECRET=your_api_secret

# Trading mode
TRADING_MODE=research  # or 'live'

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
# Terminal 1: evaluator
cd services/evaluator
go run main.go

# Terminal 2: pypfopt
cd services/pypfopt
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 9001

# Terminal 3: tradernet
cd services/tradernet
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export TRADERNET_API_KEY="your_key"
export TRADERNET_API_SECRET="your_secret"
uvicorn app.main:app --port 9002
```

#### 5. Run Main Application

```bash
cd trader-go
./trader-go
```

### Verify Installation

```bash
# Check main app health
curl http://localhost:8080/health

# Check evaluator
curl http://localhost:9000/health

# Check pypfopt
curl http://localhost:9001/health

# Check tradernet
curl http://localhost:9002/health

# Get portfolio summary
curl http://localhost:8080/api/portfolio/summary
```

---

## Microservices

### 1. evaluator (Planning Evaluation Service)

**Purpose:** High-performance sequence evaluation and simulation for the planning module.

**Port:** 9000

**Technology:** Go with worker pools for parallel evaluation

**Key Features:**
- Batch sequence evaluation (100+ sequences/second)
- Monte Carlo simulation (100x faster than Python)
- Stochastic evaluation (10x faster)
- Low memory footprint (<50MB)
- Graceful degradation (Python fallback if unavailable)

**API Endpoints:**
- `POST /api/v1/evaluate/batch` - Batch evaluate trade sequences
- `POST /api/v1/evaluate/monte-carlo` - Monte Carlo simulation
- `POST /api/v1/evaluate/stochastic` - Stochastic evaluation
- `POST /api/v1/simulate/batch` - Batch portfolio simulation
- `GET /health` - Health check

**Performance:**
- Evaluation: 10-20x faster than Python
- Monte Carlo: 100x faster than Python
- Memory: <50MB vs 500MB+ Python

**Documentation:** See `services/evaluator/README.md`

---

### 2. pypfopt (Portfolio Optimization Service)

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

**Documentation:** See `services/pypfopt/README.md`

---

### 3. tradernet (Broker API Gateway)

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
TRADING_MODE=production  # or 'research'
```

**Documentation:** See `services/tradernet/README.md`

---

## Multi-Bucket Portfolio System

The system implements a **core + satellite** portfolio architecture that enables independent trading strategies within a single portfolio.

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

1. **buckets** - Bucket definitions (id, name, type, status, target_pct, high_water_mark)
2. **bucket_balances** - Per-bucket cash balances (bucket_id, currency, balance)
3. **bucket_transactions** - Audit trail (deposit/withdrawal/transfer/trade/dividend)
4. **satellite_settings** - Strategy configuration (preset, sliders, toggles, dividend_handling)
5. **bucket_performance** - Performance metrics tracking
6. **bucket_rebalance_history** - Rebalancing event history
7. **bucket_trade_history** - Trade attribution
8. **bucket_dividend_routing** - Dividend routing rules

**Critical invariant maintained:** `SUM(bucket_balances[EUR]) == actual_broker_balance[EUR]`

Daily reconciliation ensures virtual balances match reality.

### Core Features

#### 1. Automatic Deposit Splitting

When deposits arrive, they're automatically split across buckets based on target allocations:

```
Example: €1000 deposit with 3 buckets
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

**Settings (via Settings API):**

```
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

### Satellites

See [Multi-Bucket Portfolio System](#multi-bucket-portfolio-system) section above for complete satellite endpoints.

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

**satellite_maintenance** (Daily at 11:00 AM)
- Update high water marks
- Check hibernation triggers (35%+ drawdown)
- Check recovery opportunities (<30% drawdown)
- Circuit breaker checks (5 consecutive losses)
- Log aggression levels

**satellite_reconciliation** (Daily at 11:30 PM)
- Verify cash balance invariant
- Auto-correct small drift (±€1)
- Alert on large discrepancies
- Generate reconciliation report

**planning_generation** (Daily at 2:00 PM)
- Generate trading recommendations
- Evaluate sequences
- Score opportunities
- Create optimal trade plans

### Weekly Jobs

**satellite_evaluation** (Weekly Sunday at 3:00 AM)
- Calculate performance metrics
- Update bucket scores
- Check for rebalancing triggers

### Quarterly Jobs

**satellite_reallocation** (Quarterly: Jan 1, Apr 1, Jul 1, Oct 1 at 4:00 AM)
- Rank satellites by composite score
- Adjust target allocations
- Apply performance-based rebalancing
- Update bucket targets

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

Job names: `sync_cycle`, `dividend_reinvestment`, `satellite_maintenance`, `satellite_reconciliation`, `planning_generation`, `satellite_evaluation`, `satellite_reallocation`

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
├── trader-go/                    # Main Go application
│   ├── cmd/server/              # Application entry point
│   ├── internal/                # Private application code
│   │   ├── config/             # Configuration management
│   │   ├── database/           # SQLite access layer
│   │   ├── domain/             # Domain models
│   │   ├── modules/            # Business modules
│   │   │   ├── allocation/    # Allocation management
│   │   │   ├── analytics/     # Analytics & metrics
│   │   │   ├── dividends/     # Dividend processing
│   │   │   ├── planning/      # Planning & recommendations
│   │   │   ├── portfolio/     # Portfolio management
│   │   │   ├── satellites/    # Multi-bucket strategies
│   │   │   ├── scoring/       # Security scoring
│   │   │   ├── settings/      # Settings management
│   │   │   ├── trading/       # Trade execution
│   │   │   └── universe/      # Security universe
│   │   ├── services/          # External service clients
│   │   ├── scheduler/         # Background job scheduler
│   │   ├── middleware/        # HTTP middleware
│   │   └── server/            # HTTP server & routes
│   ├── pkg/                   # Public reusable packages
│   │   ├── cache/            # In-memory cache
│   │   ├── events/           # Event system
│   │   └── logger/           # Structured logging
│   └── scripts/              # Build & deployment scripts
├── services/                  # Microservices
│   ├── evaluator/         # Planning evaluation (Go)
│   ├── pypfopt/              # Portfolio optimization (Python)
│   └── tradernet/            # Broker API gateway (Python)
├── docs/                     # Documentation (if needed)
├── docker-compose.yml        # Multi-service orchestration
└── README.md                 # This file
```

### Development Workflow

#### Main Application (trader-go)

```bash
cd trader-go

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
go build -o trader-go ./cmd/server
```

#### Microservices

See individual service READMEs:
- `services/evaluator/README.md`
- `services/pypfopt/README.md`
- `services/tradernet/README.md`

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
func TestCalculateAggression(t *testing.T) {
    bucket := &Bucket{
        TargetPct: 0.20,
        HighWaterMark: 10000.0,
    }

    currentValue := 8000.0
    currentAllocation := 0.18

    aggression := bucket.CalculateAggression(currentValue, currentAllocation)

    // Allocation factor: 0.18/0.20 = 0.9 (90% of target)
    // Drawdown factor: (10000-8000)/10000 = 0.2 (20% drawdown) → 0.7
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
cd trader-go
go test ./...
```

**Microservices:**
```bash
# evaluator
cd services/evaluator
go test ./...

# pypfopt
cd services/pypfopt
pytest

# tradernet
cd services/tradernet
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
cd trader-go

# Cross-compile for ARM64
GOOS=linux GOARCH=arm64 go build -o trader-go-arm64 ./cmd/server

# Or use build script
./scripts/build.sh arm64
```

#### Microservices (Docker)

```bash
# Build all services
docker-compose build

# Build specific service
docker build -t pypfopt:latest services/pypfopt
docker build -t tradernet:latest services/tradernet
```

### Systemd Services

#### Main Application

Create `/etc/systemd/system/trader-go.service`:

```ini
[Unit]
Description=Arduino Trader Go Service
After=network.target

[Service]
Type=simple
User=aristath
WorkingDirectory=/home/aristath/arduino-trader/trader-go
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/aristath/arduino-trader/trader-go/trader-go
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
4. Start main application (systemctl start trader-go)
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
curl http://localhost:9000/health  # evaluator
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
journalctl -u trader-go -f

# Docker logs
docker-compose logs -f
```

### Rollback Plan

**Emergency Stop:**
```bash
sudo systemctl stop trader-go
```

**Switch to Research Mode:**
```bash
curl -X POST http://localhost:8080/api/settings/trading-mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "research"}'
```

**Full Rollback:**
1. Stop Go service: `sudo systemctl stop trader-go`
2. Restore previous binary
3. Restart: `sudo systemctl start trader-go`
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
SATELLITES_DB_PATH=/path/to/satellites.db

# Microservice URLs
EVALUATOR_GO_URL=http://localhost:9000
PYPFOPT_URL=http://localhost:9001
TRADERNET_URL=http://localhost:9002

# Tradernet API
TRADERNET_API_KEY=your_api_key
TRADERNET_API_SECRET=your_api_secret

# Trading mode
TRADING_MODE=research  # or 'live'

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
| satellite_budget_pct | 0.20 | Total satellite allocation (20%) |
| satellite_min_pct | 0.03 | Minimum per satellite (3%) |
| satellite_max_pct | 0.12 | Maximum per satellite (12%) |
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

**Assign to Bucket:**
```bash
PUT /api/securities/{isin}
{
  "bucket_id": "satellite_1"
}
```

---

## Commands

### Development

```bash
# Run main app with auto-reload
cd trader-go && air

# Run tests
go test ./...

# Format code
go fmt ./...

# Lint
golangci-lint run

# Build
go build -o trader-go ./cmd/server
```

### Production

```bash
# Build for Arduino Uno Q
GOOS=linux GOARCH=arm64 go build -o trader-go-arm64 ./cmd/server

# Start services
sudo systemctl start trader-go
docker-compose up -d

# Stop services
sudo systemctl stop trader-go
docker-compose down

# View logs
journalctl -u trader-go -f
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
