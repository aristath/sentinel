# Sentinel

## What This Is

This is an autonomous portfolio management system that manages my retirement fund. It runs on an Arduino Uno Q, handles monthly deposits, and allocates funds according to scoring algorithms and allocation targets.

**This is not a toy.** It manages real money for my future. Every line of code matters. Every decision has consequences.

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

## Architecture

### Clean Architecture - Strictly Enforced
- **Domain layer is pure**: No imports from infrastructure, repositories, or external APIs
- **Dependency flows inward**: Handlers → Services → Repositories → Domain
- **Repository pattern**: All data access through interfaces
- **Dependency injection**: Constructor injection only, via DI container (`internal/di`)

### Project Structure

```
sentinel/
├── trader/                      # Main Go application
│   ├── cmd/server/             # Application entry point (main.go)
│   ├── internal/               # Private application code
│   │   ├── clients/            # External API clients
│   │   │   ├── tradernet/     # Tradernet API client (Go SDK)
│   │   │   └── yahoo/         # Yahoo Finance client
│   │   ├── config/             # Configuration management
│   │   ├── database/           # SQLite access layer (7-database architecture)
│   │   ├── deployment/         # Automated deployment system
│   │   ├── di/                 # Dependency injection container
│   │   │   ├── databases.go # Database initialization
│   │   │   ├── repositories.go # Repository creation
│   │   │   ├── services.go    # Service creation (single source of truth)
│   │   │   ├── jobs.go        # Job registration
│   │   │   ├── types.go       # Container type definitions
│   │   │   └── wire.go        # Main orchestration
│   │   ├── domain/             # Domain models and interfaces
│   │   ├── events/             # Event bus system
│   │   ├── evaluation/         # Sequence evaluation (built-in worker pool)
│   │   ├── market_regime/      # Market regime detection
│   │   ├── modules/            # Business modules
│   │   │   ├── adaptation/    # Adaptive Market Hypothesis
│   │   │   ├── allocation/    # Allocation management
│   │   │   ├── analytics/     # Analytics and metrics
│   │   │   ├── cash_flows/    # Cash flow processing
│   │   │   ├── charts/        # Chart data & visualization
│   │   │   ├── cleanup/       # Data cleanup jobs
│   │   │   ├── display/       # LED display management
│   │   │   ├── dividends/     # Dividend processing
│   │   │   ├── evaluation/    # Sequence evaluation
│   │   │   ├── market_hours/  # Market hours & holidays
│   │   │   ├── opportunities/ # Opportunity identification
│   │   │   ├── optimization/  # Portfolio optimization
│   │   │   ├── planning/      # Planning & recommendations
│   │   │   ├── portfolio/    # Portfolio management
│   │   │   ├── quantum/       # Quantum probability models
│   │   │   ├── rebalancing/   # Rebalancing logic
│   │   │   ├── scoring/       # Security scoring
│   │   │   ├── sequences/     # Trade sequence generation
│   │   │   ├── settings/      # Settings management
│   │   │   ├── symbolic_regression/ # Formula discovery
│   │   │   ├── trading/       # Trade execution
│   │   │   └── universe/      # Security universe
│   │   ├── queue/              # Background job queue system
│   │   │   ├── manager.go     # Queue manager
│   │   │   ├── scheduler.go   # Time-based scheduler
│   │   │   ├── worker.go      # Worker pool
│   │   │   ├── registry.go    # Job registry
│   │   │   └── history.go     # Job execution history
│   │   ├── reliability/       # Backup and health check services
│   │   ├── scheduler/         # Individual job implementations
│   │   ├── server/            # HTTP server & routes
│   │   ├── services/          # Core services (trade execution, currency exchange)
│   │   ├── testing/           # Test utilities
│   │   ├── ticker/            # LED ticker content generation
│   │   └── utils/             # Utility functions
│   ├── frontend/              # React frontend (Vite)
│   │   ├── src/
│   │   │   ├── components/    # React components
│   │   │   ├── views/         # Page views
│   │   │   ├── stores/        # State management
│   │   │   ├── api/           # API client
│   │   │   └── hooks/         # React hooks
│   │   └── dist/              # Built frontend assets
│   ├── display/               # LED display system
│   │   ├── sketch/            # Arduino C++ sketch
│   │   └── app/               # Python display app (Arduino App Framework)
│   ├── pkg/                   # Public reusable packages
│   │   ├── embedded/          # Embedded frontend assets
│   │   ├── formulas/          # Financial formulas (HRP, Sharpe, CVaR, etc.)
│   │   └── logger/            # Structured logging
│   └── go.mod                 # Go module definition
├── scripts/                    # Utility scripts
├── migrations/                 # Database migrations
└── README.md                   # Main documentation
```

### Database Architecture

The system uses a clean 7-database architecture:

1. **universe.db** - Investment universe (securities, groups)
2. **config.db** - Application configuration (settings, allocation targets)
3. **ledger.db** - Immutable financial audit trail (trades, cash flows, dividends)
4. **portfolio.db** - Current portfolio state (positions, scores, metrics, snapshots)
5. **agents.db** - Strategy management (sequences, evaluations)
6. **history.db** - Historical time-series data (prices, rates, cleanup tracking)
7. **cache.db** - Ephemeral operational data (recommendations, cache)

All databases use SQLite with WAL mode and profile-specific PRAGMAs for optimal performance and safety.

### Dependency Injection

All dependencies are wired through the DI container (`internal/di`):

1. **InitializeDatabases** - Creates all 7 database connections
2. **InitializeRepositories** - Creates all repository instances
3. **InitializeServices** - Creates all service instances (single source of truth)
4. **RegisterJobs** - Registers all background jobs with the queue system

The container (`di.Container`) holds all service instances and is passed to handlers for access to services.

### Background Job System

The system uses a queue-based job system (`internal/queue`) with three components:

1. **QueueManager** - Manages job queue and history
2. **WorkerPool** - Executes jobs asynchronously
3. **TimeScheduler** - Schedules time-based jobs (cron-like)

Jobs are registered via `di.RegisterJobs()` and can be:
- **Time-based**: Scheduled via `TimeScheduler` (e.g., daily at 2 AM)
- **Event-based**: Triggered by events via event listeners
- **Manual**: Triggered via API endpoints

Individual jobs are in `internal/scheduler/` and implement the `scheduler.Job` interface.

### Application Entry Point

The application starts in `cmd/server/main.go`:

1. Loads configuration (`config.Load()`)
2. Initializes logger
3. Creates display manager (LED state)
4. Wires dependencies via `di.Wire()` (returns container and jobs)
5. Initializes HTTP server (`server.New()`)
6. Starts background monitors (LED status, planner actions)
7. Starts HTTP server
8. Waits for shutdown signal

## Code Style

### Types
```go
// Use explicit types, avoid interface{} when possible
func GetSecurity(id int64) (*domain.Security, error) {
    // ...
}
```

### Error Handling
- Return errors, don't panic
- Wrap errors with context: `fmt.Errorf("failed to fetch security: %w", err)`
- Use structured logging with zerolog

### Imports
- Explicit only, no wildcards
- Group: stdlib, third-party, local
- Use `goimports` for formatting

### Naming
- Clarity over brevity
- `CalculatePortfolioAllocation` not `CalcAlloc`
- Use camelCase for unexported, PascalCase for exported

## Error Handling

- Return errors from functions, don't panic
- Wrap errors with context using `fmt.Errorf` with `%w` verb
- Log errors with structured logging (zerolog)
- Degrade gracefully - partial results over total failure

## Testing

- Unit tests for domain logic (no DB, no network)
- Integration tests for APIs and repositories
- Tests before implementation for new features
- Never decrease coverage
- Use `testify` for assertions

## Deployment

Runs on Arduino Uno Q:
- Limited resources - optimize accordingly
- Network may fail - handle gracefully
- LED display shows status - keep it informative

The system includes automated deployment (`internal/deployment`) that:
- Monitors git repository for changes
- Downloads pre-built binaries from GitHub Actions
- Deploys Go services, frontend, display app, and sketch
- Restarts services automatically

## Commands

### Development

```bash


# Install dependencies
go mod download

# Run with auto-reload (requires air)
air

# Run tests
go test ./...

# Run tests with coverage
go test -cover ./...

# Format code
go fmt ./...

# Lint
golangci-lint run

# Build
go build -o sentinel ./cmd/server
```

### Production

```bash
# Build for Arduino Uno Q (ARM64)

GOOS=linux GOARCH=arm64 go build -o sentinel-arm64 ./cmd/server
```

## Key Technologies

- **Language**: Go 1.23+
- **HTTP Router**: Chi (stdlib-based, lightweight)
- **Database**: SQLite with modernc.org/sqlite (pure Go, no CGo)
- **Scheduler**: robfig/cron for time-based scheduling + custom queue system
- **Logging**: zerolog (structured, high-performance)
- **Frontend**: React + Vite
- **Configuration**: godotenv (deprecated for credentials, use Settings UI)

## Important Notes

### When Touching Existing Violations
The codebase has documented violations in the README.md Architecture section. Before fixing or extending them, ask.

### Settings Management
- API credentials should be configured via Settings UI (Credentials tab) or Settings API
- `.env` file is deprecated for credentials (still supported for infrastructure settings)
- Settings are stored in `config.db` and take precedence over environment variables

### Planning Evaluation
- Planning evaluation is built into the main application using an in-process worker pool (`internal/evaluation`)
- No separate microservice needed

### Tradernet Integration
- Tradernet API is integrated directly via Go SDK (`internal/clients/tradernet`)
- No microservice needed

### Frontend
- Frontend is built with Vite and embedded in the Go binary via `pkg/embedded`
- Built assets are in `frontend/dist/`
- Served as static files by the HTTP server
