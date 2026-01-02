# Go Migration Guide

## What We Built (Phase 2 Complete ✅)

### Core Infrastructure
- ✅ **HTTP Server** - Chi router with middleware (CORS, logging, recovery, timeout)
- ✅ **Database Access** - SQLite with pure Go driver (modernc.org/sqlite)
- ✅ **Configuration** - Environment-based config with godotenv
- ✅ **Structured Logging** - zerolog with pretty console output
- ✅ **Background Scheduler** - robfig/cron for job scheduling
- ✅ **Graceful Shutdown** - Proper signal handling and shutdown

### Current Performance
```
Binary Size:  14MB (compiled)
Memory Usage: 12MB (running)
Startup Time: <1s
API Latency:  <10ms (health check)

Compare to Python:
- Memory: 12MB vs 3,500MB (99.7% reduction! 🎉)
- Startup: <1s vs 10s (10x faster)
```

### Project Structure
```
trader-go/
├── cmd/server/main.go           # ✅ Entry point
├── internal/
│   ├── config/                  # ✅ Configuration
│   ├── database/                # ✅ SQLite access
│   ├── domain/                  # ✅ Domain models
│   ├── scheduler/               # ✅ Job scheduler
│   ├── server/                  # ✅ HTTP server
│   └── modules/                 # 📦 To be migrated
├── pkg/
│   └── logger/                  # ✅ Structured logging
└── scripts/build.sh             # ✅ Build script
```

---

## Next Steps: Module Migration

### Migration Pattern

Each Python module follows this pattern:

```python
# Python: app/modules/MODULE/
├── api/              # HTTP endpoints
├── services/         # Business logic
├── database/         # Data access
├── domain/           # Domain models
└── jobs/             # Background jobs
```

Becomes:

```go
// Go: internal/modules/MODULE/
├── handlers.go       # HTTP endpoints
├── service.go        # Business logic
├── repository.go     # Data access
├── models.go         # Domain models
└── jobs.go           # Background jobs (optional)
```

### Example: Allocation Module (Simplest)

**Step 1: Create module structure**
```bash
mkdir -p internal/modules/allocation
```

**Step 2: Define models** (`internal/modules/allocation/models.go`)
```go
package allocation

type AllocationTarget struct {
    ID         int64   `json:"id"`
    Category   string  `json:"category"` // "country", "industry"
    Code       string  `json:"code"`     // "US", "Technology"
    Target     float64 `json:"target"`   // 0.50 = 50%
    Active     bool    `json:"active"`
}
```

**Step 3: Create repository** (`internal/modules/allocation/repository.go`)
```go
package allocation

import (
    "database/sql"
    "github.com/aristath/arduino-trader/internal/database/repositories"
)

type Repository struct {
    *repositories.BaseRepository
}

func NewRepository(db *sql.DB, log zerolog.Logger) *Repository {
    return &Repository{
        BaseRepository: repositories.NewBase(
            db,
            log.With().Str("repo", "allocation").Logger(),
        ),
    }
}

func (r *Repository) GetAllTargets() ([]AllocationTarget, error) {
    query := `
        SELECT id, category, code, target, active
        FROM allocation_targets
        WHERE active = 1
    `

    rows, err := r.DB().Query(query)
    if err != nil {
        return nil, err
    }
    defer rows.Close()

    var targets []AllocationTarget
    for rows.Next() {
        var t AllocationTarget
        if err := rows.Scan(&t.ID, &t.Category, &t.Code, &t.Target, &t.Active); err != nil {
            return nil, err
        }
        targets = append(targets, t)
    }

    return targets, rows.Err()
}
```

**Step 4: Create service** (`internal/modules/allocation/service.go`)
```go
package allocation

import "github.com/rs/zerolog"

type Service struct {
    repo *Repository
    log  zerolog.Logger
}

func NewService(repo *Repository, log zerolog.Logger) *Service {
    return &Service{
        repo: repo,
        log:  log.With().Str("service", "allocation").Logger(),
    }
}

func (s *Service) GetAllTargets() ([]AllocationTarget, error) {
    return s.repo.GetAllTargets()
}

// Add more business logic methods here
```

**Step 5: Create HTTP handlers** (`internal/modules/allocation/handlers.go`)
```go
package allocation

import (
    "encoding/json"
    "net/http"
)

type Handler struct {
    service *Service
}

func NewHandler(service *Service) *Handler {
    return &Handler{service: service}
}

func (h *Handler) HandleGetTargets(w http.ResponseWriter, r *http.Request) {
    targets, err := h.service.GetAllTargets()
    if err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }

    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(targets)
}
```

**Step 6: Register routes** (in `internal/server/routes.go`)
```go
// Add to setupRoutes()
import "github.com/aristath/arduino-trader/internal/modules/allocation"

// In setupRoutes():
allocHandler := allocation.NewHandler(allocationService)
r.Route("/allocation", func(r chi.Router) {
    r.Get("/targets", allocHandler.HandleGetTargets)
})
```

**Step 7: Wire dependencies** (in `cmd/server/main.go`)
```go
import "github.com/aristath/arduino-trader/internal/modules/allocation"

// In main():
allocRepo := allocation.NewRepository(db.Conn(), log)
allocService := allocation.NewService(allocRepo, log)
```

---

## Migration Order (Recommended)

### Phase 1: Simple CRUD Modules (2-3 weeks)
1. **Allocation** (699 LOC) - Simplest, good starting point
2. **System** (2,120 LOC) - Health checks, stats
3. **Display** (394 LOC) - LED control (needs msgpack/serial libs)

**Why first:** Pure CRUD, minimal business logic, low risk

### Phase 2: Data Access Modules (3-4 weeks)
4. **Cash Flows** (817 LOC) - Ledger management
5. **Dividends** (1,048 LOC) - Dividend tracking
6. **Rebalancing** (1,830 LOC) - Triggers and logic

**Why second:** Moderate complexity, establish patterns

### Phase 3: Core Business Logic (4-6 weeks)
7. **Portfolio** (1,443 LOC) - Position tracking
8. **Universe** (2,255 LOC) - Security management
9. **Trading** (1,869 LOC) - Trade execution (safety-critical!)

**Why third:** Complex business rules, need careful testing

### Phase 4: Complex Modules (6-8 weeks)
10. **Satellites** (6,073 LOC) - Multi-bucket risk management
11. **Analytics** (1,136 LOC) - Portfolio metrics
12. **Planning** (16,599 LOC) - Most complex, already has evaluator-go

**Why last:** Most complex, highest risk, but foundation is solid

---

## Python Service Integration

While migrating, the Go app can call the existing Python app:

```go
// internal/services/python_client.go
type PythonClient struct {
    baseURL string
    client  *http.Client
}

func (c *PythonClient) GetSecurityScore(symbol string) (float64, error) {
    resp, err := c.client.Get(
        fmt.Sprintf("%s/api/scoring/security/%s", c.baseURL, symbol),
    )
    if err != nil {
        return 0, err
    }
    defer resp.Body.Close()

    var result struct {
        Score float64 `json:"score"`
    }
    if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
        return 0, err
    }

    return result.Score, nil
}
```

---

## Testing Strategy

### Unit Tests
```go
// internal/modules/allocation/service_test.go
func TestService_GetAllTargets(t *testing.T) {
    // Use testify for assertions
    // Mock repository
    // Test business logic
}
```

### Integration Tests
```go
// internal/modules/allocation/integration_test.go
func TestAllocationAPI(t *testing.T) {
    // Use real database (in-memory SQLite)
    // Test full HTTP flow
}
```

### Run Tests
```bash
make test
make test-coverage
```

---

## Deployment Strategy

### Parallel Deployment (Safest)
1. Deploy Go app on port 8001
2. Keep Python app on port 8000
3. Gradually shift traffic using nginx/reverse proxy
4. Monitor both simultaneously
5. Switch fully when confident

### Nginx Configuration
```nginx
upstream backend {
    server localhost:8000 weight=10;  # Python (90%)
    server localhost:8001 weight=1;   # Go (10%)
}

server {
    listen 80;
    location / {
        proxy_pass http://backend;
    }
}
```

### Systemd Service
```ini
[Unit]
Description=Arduino Trader Go
After=network.target

[Service]
Type=simple
User=aristath
WorkingDirectory=/home/aristath/trader-go
ExecStart=/home/aristath/trader-go/trader-go
Restart=always
RestartSec=10
Environment="DATABASE_PATH=/home/aristath/data/portfolio.db"

[Install]
WantedBy=multi-user.target
```

---

## Development Workflow

### Daily Development
```bash
# 1. Make changes
vim internal/modules/allocation/service.go

# 2. Format code
make fmt

# 3. Run tests
make test

# 4. Run locally
make run

# 5. Test in browser
curl http://localhost:8000/api/allocation/targets
```

### Before Committing
```bash
make fmt
make lint
make test
```

### Build for Arduino
```bash
make build-arm64
scp trader-go-arm64 arduino:~/trader-go/
ssh arduino 'sudo systemctl restart trader-go'
```

---

## Common Patterns

### Error Handling
```go
// Wrap errors with context
if err != nil {
    return fmt.Errorf("failed to fetch targets: %w", err)
}

// Log errors before returning
if err != nil {
    s.log.Error().Err(err).Msg("Failed to process request")
    return err
}
```

### Logging
```go
// Info
log.Info().
    Str("symbol", symbol).
    Float64("price", price).
    Msg("Price updated")

// Error
log.Error().
    Err(err).
    Str("operation", "fetch_quote").
    Msg("Operation failed")
```

### HTTP Responses
```go
// Success
w.Header().Set("Content-Type", "application/json")
json.NewEncoder(w).Encode(data)

// Error
http.Error(w, "Invalid request", http.StatusBadRequest)

// Custom error
w.Header().Set("Content-Type", "application/json")
w.WriteHeader(http.StatusNotFound)
json.NewEncoder(w).Encode(map[string]string{
    "error": "Resource not found",
})
```

### Database Queries
```go
// Query multiple rows
rows, err := db.Query("SELECT * FROM securities WHERE active = ?", true)
if err != nil {
    return nil, err
}
defer rows.Close()

for rows.Next() {
    var s Security
    if err := rows.Scan(&s.ID, &s.Symbol, &s.Name); err != nil {
        return nil, err
    }
    securities = append(securities, s)
}

// Query single row
var count int
err := db.QueryRow("SELECT COUNT(*) FROM trades").Scan(&count)
```

---

## Success Metrics

### Performance Targets
- ✅ Memory: <1GB (vs 3.5GB Python)
- 🎯 API Latency: <50ms (vs 200ms Python)
- 🎯 Planning Time: 10-15sec (vs 2min Python)
- 🎯 Startup: 2-3sec (vs 10sec Python)

### Code Quality
- Test coverage >80%
- No panics in production
- All errors logged with context
- Clean architecture maintained

### Stability
- Zero downtime deployments
- Graceful degradation (Python fallback)
- Proper monitoring/alerting

---

## Resources

### Go Learning
- [Effective Go](https://go.dev/doc/effective_go)
- [Go by Example](https://gobyexample.com/)
- [Chi Router Docs](https://go-chi.io/)

### Project Tools
- `make help` - Show all make targets
- `make run` - Run locally
- `make test` - Run tests
- `make build-arm64` - Build for Arduino

### Getting Help
- Check existing Go code (evaluator-go)
- Follow patterns in this guide
- Test thoroughly before deploying

---

## Current Status

- ✅ Phase 2 Complete (Foundation)
- 📦 Ready for Phase 3 (Module Migration)
- 🎯 Target: Complete migration in 6-9 months

**Next Action:** Pick first module (Allocation recommended) and start migration!
