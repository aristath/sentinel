# Portfolio Manager

**Autonomous portfolio management system for retirement fund management**

Portfolio Manager is a production-ready autonomous trading system that manages a real retirement fund. It runs on an Arduino Uno Q, handling monthly deposits, automatic trading, dividend reinvestment, and portfolio management with zero human intervention.

**This manages real money. Every line of code matters. Every decision has consequences.**

## Overview

Portfolio Manager is an autonomous retirement fund management system that combines modern portfolio theory with adaptive market strategies. The system operates on a **slow-growth, long-term philosophy** (2-3 trades per week), prioritizing quality, diversification, and risk-adjusted returns over speculative gains.

### Economic Theories & Models

The system implements a comprehensive suite of financial theories:

- **Modern Portfolio Theory (Markowitz)**: Mean-variance optimization for efficient frontier construction
- **Hierarchical Risk Parity (HRP)**: Risk-based portfolio construction using correlation clustering
- **Adaptive Market Hypothesis (AMH)**: Dynamic adaptation of scoring weights and optimization strategies as markets evolve
- **Quantum-Inspired Probability Models**: Advanced bubble detection and value trap identification using quantum-inspired probability distributions (see `docs/QUANTUM_PROBABILITY_IMPLEMENTATION.md`)
- **Regime-Aware Risk Management**: Market regime detection (bull/bear/sideways) with adaptive correlation matrices and multi-scale optimization
- **Symbolic Regression**: Formula discovery for optimal scoring combinations across different market conditions (with walk-forward validation and complexity limits to prevent overfitting)
- **Risk-Adjusted Metrics**: Sharpe ratio, Sortino ratio, and volatility-adjusted returns
- **Total Return Focus**: Combined growth (CAGR) and dividend yield for comprehensive return measurement
- **Kelly Criterion (Constrained)**: Optimal position sizing based on expected edge and confidence, with hard guardrails to prevent excessive concentration
- **Conditional Value at Risk (CVaR)**: Tail risk measurement at 95% confidence level, complementing volatility-based metrics for extreme loss awareness
- **Black-Litterman Model**: Bayesian portfolio optimization that integrates scoring system views with market equilibrium, reducing extreme allocations and handling estimation uncertainty
- **Factor Exposure Tracking**: Monitor portfolio factor tilts (value, quality, momentum, size) for diagnostics and portfolio understanding

### Investment Philosophy

**What the System Favors:**
- **Quality over quantity**: ~45% of security scoring emphasizes long-term fundamentals and financial strength (adapts with market regime: 45% neutral, 45% bull, 50% bear)
- **Dividend income**: 18% weight on dividend yield, consistency, and growth (total return = growth + dividends)
- **Diversification**: Geographic, sector, and position-level diversification with optimizer alignment
- **Risk-adjusted performance**: Sharpe and Sortino ratios prioritized over raw returns
- **Gradual rebalancing**: Avoids large portfolio shifts, preferring incremental adjustments (even during regime changes - uses monthly deposits and selective buying rather than selling to rebalance)
- **Dynamic adaptation**: Scoring weights and optimization strategies evolve with market conditions over months/years
- **Regime awareness**: Different strategies for bull, bear, and sideways markets
- **Optimal position sizing**: Kelly-optimal sizing based on expected returns and confidence, with adaptive fractional Kelly that adjusts by market regime
- **Tail risk awareness**: CVaR constraints ensure portfolio can withstand extreme market events, with regime-aware limits that tighten in bear markets
- **Bayesian optimization**: Black-Litterman model integrates scoring system confidence with market equilibrium for smoother, more stable allocations
- **Factor diversification**: Explicit tracking of value, quality, momentum, and size factors ensures balanced portfolio characteristics

**What the System Avoids:**
- **Value traps**: Cheap securities with declining fundamentals or negative momentum
- **Bubbles**: High CAGR securities with poor risk metrics (low Sharpe/Sortino, high volatility, weak fundamentals)
- **Low-quality securities**: Quality gates filter out securities below minimum thresholds (fundamentals < 0.6, long-term < 0.5)
- **Excessive transaction costs**: Evaluates and minimizes trading costs in sequence planning
- **Large rebalancing moves**: Gradual adjustment prevents sudden portfolio shifts (>30% imbalance threshold)
- **Static strategies**: Continuously adapts to changing market conditions rather than fixed allocations
- **Speculative trading**: Focuses on 2-3 trades per week, not high-frequency strategies
- **Suboptimal position sizing**: No longer uses simple constraint-based sizing; all positions sized using Kelly-optimal calculations
- **Tail risk blindness**: Explicitly measures and constrains extreme losses (CVaR) beyond volatility metrics
- **Estimation uncertainty**: Black-Litterman model accounts for uncertainty in expected returns, preventing overconfidence in predictions
- **Factor concentration**: Monitors factor exposures to avoid unintended factor tilts that could expose portfolio to systematic risks

The optimizer blends Mean-Variance (return-focused) and HRP (risk-focused) strategies using an adaptive blend that responds to market regime:
- **Bull markets**: 70% MV / 30% HRP (return-focused)
- **Neutral markets**: 50% MV / 50% HRP (balanced)
- **Bear markets**: 30% MV / 70% HRP (risk-focused)

The blend adapts smoothly via linear interpolation based on the continuous regime score (-1.0 to +1.0). The planner identifies opportunities through value, quality, dividend, and technical analysis. All decisions are evaluated through a multi-factor scoring system that balances expected returns, risk, quality, and transaction costs.

The optimizer integrates advanced position sizing and risk management:
- **Kelly-optimal position sizing**: All positions sized using Kelly Criterion with adaptive fractional Kelly (0.25-0.75 multiplier based on regime and confidence)
- **CVaR constraints**: Portfolio tail risk constrained at 95% confidence level, with regime-aware adjustments that tighten limits in bear markets
- **Black-Litterman adjusted returns**: When enabled, expected returns are adjusted using Bayesian views derived from security scores, reducing extreme allocations
- **Factor exposure tracking**: Portfolio factor loadings (value, quality, momentum, size) are calculated and monitored for diagnostics

## Table of Contents

- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Getting Started](#getting-started)
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
Note: All functionality has been migrated to Go - Tradernet API is integrated directly via Go SDK (no microservices needed).
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

**Note:**
- Planning evaluation is built into the main trader application using an in-process worker pool (no separate microservice).
- Tradernet API is now integrated directly via Go SDK embedded in the main application (no microservice needed).
- All functionality has been migrated to Go - no Python microservices are used.

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
- Existing SQLite databases (7-database architecture)
- Tradernet API credentials

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

#### 4. Run Main Application

```bash
cd trader
./trader
```

### Verify Installation

```bash
# Check main app health
curl http://localhost:8001/health

# Get portfolio summary
curl http://localhost:8001/api/portfolio/summary
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
- `POST /api/planning/recommendations` - Generate new recommendations
- `GET /api/planning/status` - Planning job status
- `GET /api/planning/configs` - List planner configurations
- `POST /api/planning/configs` - Create planner configuration
- `GET /api/planning/configs/{id}` - Get planner configuration
- `PUT /api/planning/configs/{id}` - Update planner configuration
- `DELETE /api/planning/configs/{id}` - Delete planner configuration
- `POST /api/planning/configs/validate` - Validate planner configuration
- `GET /api/planning/configs/{id}/history` - Configuration history
- `POST /api/planning/batch` - Batch plan generation
- `POST /api/planning/execute` - Execute plan
- `GET /api/planning/stream` - SSE stream for planning events

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

**sync_cycle** (Every 30 minutes)
- Sync portfolio positions from broker
- Sync cash balances
- Sync executed trades
- Update security prices (market-aware)
- Process cash flows (deposits, dividends, fees)
- Update LED display ticker

**planner_batch** (Event-driven)
- Triggered by planning requests or recommendations refresh
- Generate trading recommendations
- Evaluate sequences using built-in evaluation service
- Score opportunities
- Create optimal trade plans

**event_based_trading** (Event-driven)
- Triggered when new recommendations are available
- Monitor for planning completion
- Execute approved trades
- Enforces minimum execution intervals (30 minutes)

**dividend_reinvestment** (Daily at 10:00 AM)
- Detect new dividends
- Classify high-yield (≥3%) vs low-yield (<3%)
- Auto-reinvest high-yield dividends (DRIP)
- Accumulate low-yield as pending bonuses

**tag_update** (Daily at 3:00 AM)
- Re-evaluate and update tags for all securities
- Update quality, opportunity, and risk tags
- Support fast filtering and quality gates

**adaptive_market** (Daily at 6:00 AM)
- Monitor market conditions and adapt portfolio strategy
- Update scoring weights based on market regime
- Adjust optimizer blend (MV/HRP) dynamically

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

**formula_discovery** (1st day at 5:00 AM)
- Run symbolic regression to discover optimal formulas
- Update scoring formulas based on historical performance
- Regime-specific formula optimization

### Manual Triggers

Operational jobs can be manually triggered via API:

```bash
POST /api/system/jobs/health-check
POST /api/system/jobs/sync-cycle
POST /api/system/jobs/dividend-reinvestment
POST /api/system/jobs/planner-batch
POST /api/system/jobs/event-based-trading
POST /api/system/jobs/tag-update
```

Note: Reliability jobs (backups, maintenance, cleanup) run automatically on schedule and are not exposed for manual triggering.

---

## Development

### Prerequisites

- Go 1.22+
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
│   │   │   │   ├── adaptation/   # Adaptive Market Hypothesis
│   │   │   ├── market_hours/  # Market hours & holidays
│   │   │   ├── opportunities/# Opportunity identification
│   │   │   ├── optimization/ # Portfolio optimization
│   │   │   ├── planning/     # Planning & recommendations
│   │   │   ├── portfolio/    # Portfolio management
│   │   │   ├── quantum/     # Quantum probability models
│   │   │   ├── rebalancing/  # Rebalancing logic
│   │   │   ├── scoring/      # Security scoring
│   │   │   ├── sequences/    # Trade sequence generation
│   │   │   ├── settings/     # Settings management
│   │   │   ├── symbolic_regression/ # Formula discovery
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
│   └── app/                 # Python display app (Arduino App Framework - separate from main Go app)
├── scripts/                 # Utility scripts (status, logs, restart, build)
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

**Coverage:**
```bash
# Go
go test -cover ./...
```

---

## Deployment

**Deployment is fully automated** by the Go trader service. The system automatically:
- Checks for code changes every 5 minutes
- Downloads pre-built binaries from GitHub Actions
- Deploys Go services, frontend, display app, and sketch
- Restarts services automatically
- No manual deployment scripts required

### Automated Deployment

The trader service includes a built-in deployment manager that:
- Monitors the git repository for changes
- Downloads ARM64 binaries from GitHub Actions artifacts
- Deploys all components (trader service, frontend, display app, sketch)
- Handles service restarts gracefully
- Provides API endpoints for manual triggers

**Manual Deployment Trigger:**
```bash
# Trigger deployment manually via API
curl -X POST http://localhost:8001/api/system/deployment/deploy

# Check deployment status
curl http://localhost:8001/api/system/deployment/status
```

### Build for Production

#### Main Application (ARM64 for Arduino Uno Q)

Builds are handled automatically by GitHub Actions. For local builds:

```bash
cd trader

# Cross-compile for ARM64
GOOS=linux GOARCH=arm64 go build -o trader-arm64 ./cmd/server

# Or use build script
./scripts/build.sh arm64
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

#### Additional Services

The system is self-contained and runs as a single Go application. No additional microservices or Docker containers are required.

### Initial Setup

For the first-time setup on a new device:

1. **Install systemd service** (see Systemd Services section below)
2. **Start the trader service**: `sudo systemctl start trader`
3. **Configure credentials** via Settings UI or API

After initial setup, deployment is fully automated. The service will:
- Automatically detect code changes
- Download and deploy new versions
- Restart services as needed

### Deployment Checklist (Initial Setup Only)

**Pre-Deployment:**
- [ ] Backup all databases (if upgrading existing installation)
- [ ] Verify schema migrations applied
- [ ] Test in research mode
- [ ] Check Tradernet credentials
- [ ] Review settings and targets

**Deployment:**
1. Install systemd service (first time only)
2. Start the trader service: `sudo systemctl start trader`
3. Verify health endpoints
4. Monitor logs for 24 hours

**Post-Deployment:**
- [ ] Verify first sync cycle completes
- [ ] Check portfolio values match broker
- [ ] Monitor background jobs execution
- [ ] Validate planning recommendations
- [ ] Check cash balances are correct

**Note:** After initial setup, all future deployments are automatic. No manual intervention required.

### Monitoring

**Health Checks:**
```bash
# Main app
curl http://localhost:8001/health

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
# Defaults to /home/arduino/data if not set
# Always resolved to absolute path
TRADER_DATA_DIR=/path/to/data


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

# Start service
sudo systemctl start trader

# Stop service
sudo systemctl stop trader

# View logs
journalctl -u trader -f

# Health checks
curl http://localhost:8001/health
```

### Utility Scripts

The following utility scripts are available for manual operations:

- `scripts/status.sh` - Check service status on Arduino device
- `scripts/logs.sh [SERVICE]` - View service logs
- `scripts/restart.sh [SERVICE]` - Restart services manually
- `scripts/config.sh` - Configuration file (used by other scripts)
- `scripts/pre-commit-build-frontend.sh` - Git pre-commit hook for frontend builds
- `trader/scripts/build.sh [arch]` - Build script (used by Makefile)

**Note:** Deployment is fully automated. These scripts are for monitoring and troubleshooting only.

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

**Technology:** Go, SQLite
**Hardware:** Arduino Uno Q (ARM64)
**Purpose:** Retirement fund management with zero human intervention

---

*This is not a toy. It manages real money for my future. Every line of code matters. Every decision has consequences.*
