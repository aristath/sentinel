# Arduino Trader - Go Edition

Complete rewrite of the Arduino Trader portfolio management system in Go for improved performance and reduced memory footprint.

## Architecture

**Target:** Single embedded binary with modular internal structure
**Memory:** <1GB total (vs 3.5GB Python)
**Performance:** 5-10x faster API responses, 10-100x faster planning

## Project Structure

```
trader-go/
├── cmd/server/              # Application entry point
├── internal/                # Private application code
│   ├── config/             # Configuration management
│   ├── database/           # SQLite access layer
│   ├── domain/             # Domain models
│   ├── modules/            # Business modules
│   ├── services/           # Python service clients (temporary)
│   ├── scheduler/          # Background job scheduler
│   ├── middleware/         # HTTP middleware
│   └── server/             # HTTP server & routes
├── pkg/                    # Public reusable packages
│   ├── cache/             # In-memory cache
│   ├── events/            # Event system
│   └── logger/            # Structured logging
└── scripts/               # Build & deployment scripts
```

## Technology Stack

- **Router:** Chi (stdlib-based, lightweight)
- **Database:** SQLite with modernc.org/sqlite (pure Go, no CGo)
- **Scheduler:** robfig/cron
- **Logging:** zerolog (structured, fast)
- **Config:** godotenv

## Getting Started

### Prerequisites

- Go 1.22+
- Existing Arduino Trader database (portfolio.db)

### Installation

```bash
# Clone repository
cd trader-go

# Install dependencies
go mod download

# Copy environment file
cp .env.example .env

# Edit .env with your configuration
nano .env

# Build
go build -o trader-go ./cmd/server

# Run
./trader-go
```

### Development

```bash
# Run with auto-reload (install air first: go install github.com/cosmtrek/air@latest)
air

# Run tests
go test ./...

# Run with race detector
go run -race ./cmd/server

# Format code
go fmt ./...

# Lint
golangci-lint run
```

## Migration Strategy

### Phase 1: Foundation (CURRENT)
✅ Core HTTP server with Chi
✅ SQLite database access
✅ Configuration management
✅ Structured logging
✅ Background scheduler
✅ Middleware (CORS, logging, recovery)

### Phase 2: Module Migration
1. System & Allocation (simple CRUD)
2. Display (msgpack RPC to LED)
3. Portfolio & Universe (data access)
4. Trading (business logic)
5. Planning (most complex)
6. Satellites (risk management)
7. Analytics (portfolio metrics)

### Phase 3: Python Services
Extract remaining Python-only code:
- Scoring → Python microservice
- Optimization → Python microservice
- Trading Gateway → Python microservice (Tradernet SDK)
- Market Data → Python microservice (yfinance)

## API Endpoints

### System
- `GET /health` - Health check
- `GET /api/system/status` - System status & metrics

### TODO: Add as modules are migrated
- Portfolio endpoints
- Trading endpoints
- Planning endpoints
- etc.

## Performance Targets

| Metric | Python | Go Target | Status |
|--------|--------|-----------|--------|
| Memory | 3.5GB | <1GB | 🎯 |
| API latency | 200ms | <50ms | 🎯 |
| Planning time | 2min | 10-15sec | 🎯 |
| Startup time | 10s | 2-3s | 🎯 |

## Development Guidelines

### Clean Architecture
- Domain layer is pure (no external dependencies)
- Dependency flows inward (handlers → services → repositories → domain)
- Use interfaces for dependencies
- Constructor injection only

### Error Handling
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

### Testing
- Unit tests for business logic
- Integration tests for database access
- Use testify for assertions
- Mock external dependencies

### Logging
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

## Deployment

### Build for Arduino Uno Q (ARM64)

```bash
# Cross-compile for ARM64
GOOS=linux GOARCH=arm64 go build -o trader-go-arm64 ./cmd/server

# Or use the build script
./scripts/build.sh arm64
```

### Systemd Service

```ini
[Unit]
Description=Arduino Trader Go Service
After=network.target

[Service]
Type=simple
User=aristath
WorkingDirectory=/home/aristath/trader-go
ExecStart=/home/aristath/trader-go/trader-go
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Contributing

This is a personal project managing real retirement funds. Changes must be:
1. Thoroughly tested
2. Reviewed for correctness
3. Performance-validated
4. Documented

## License

Private - All Rights Reserved
