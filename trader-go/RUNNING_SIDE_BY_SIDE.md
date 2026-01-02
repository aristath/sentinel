# Running Python and Go Servers Side-by-Side

This document explains how to run both the Python (FastAPI) and Go servers simultaneously for testing and gradual migration.

## Port Configuration

- **Python FastAPI**: Port **8000** (default)
- **Go Server**: Port **8001** (default)

Both servers serve the same static files and provide web UIs for testing.

## Starting Both Servers

### Option 1: Separate Terminals

**Terminal 1 - Python Server:**
```bash
cd /Users/aristath/arduino-trader
# Activate venv if needed
source venv/bin/activate
# Run with uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Go Server:**
```bash
cd /Users/aristath/arduino-trader/trader-go
# Run the server
go run cmd/server/main.go
```

### Option 2: Using Environment Variables

You can override the default ports:

**Python:**
```bash
# Python doesn't use PORT env var by default, so specify in uvicorn command
uvicorn app.main:app --port 8000
```

**Go:**
```bash
# Override Go port (though default is already 8001)
GO_PORT=8001 go run cmd/server/main.go
```

## Accessing the Services

### Web UIs

- **Python Dashboard**: http://localhost:8000
- **Go Dashboard**: http://localhost:8001

Both serve the same static files from `./static/` directory and render the same UI.

### API Endpoints

#### Python API (Port 8000)
- Health: http://localhost:8000/health
- System Status: http://localhost:8000/api/system/status
- All Python modules: allocation, portfolio, securities, trades, planning, etc.

#### Go API (Port 8001)
- Health: http://localhost:8001/health
- System Status: http://localhost:8001/api/system/status
- **Migrated Modules**:
  - `/api/allocation/*` - Allocation targets and deviations
  - `/api/portfolio/*` - Portfolio positions and history
  - `/api/securities/*` - Securities universe
  - `/api/trades/*` - Trade history
  - `/api/dividends/*` - **NEW!** Dividend DRIP tracking

## Testing Migrated Modules

When testing migrated modules, you can compare responses:

```bash
# Compare portfolio data
curl http://localhost:8000/api/portfolio/summary  # Python
curl http://localhost:8001/api/portfolio/summary  # Go

# Test new dividends API (Go only)
curl http://localhost:8001/api/dividends/unreinvested
```

## Python → Go Communication

The Python service can proxy certain operations to Go:

- `PYTHON_SERVICE_URL` in Go config points to `http://localhost:8000`
- Go can call Python for operations not yet migrated

The Python `dividend_reinvestment` job calls the Go dividend API:
```python
GO_API_BASE_URL = "http://localhost:8001"  # Points to Go server
```

## Production Deployment

In production on Arduino Uno Q, you would typically run:

1. **During Migration**: Both servers running side-by-side
   - Python: 8000 (main service, handles UI)
   - Go: 8001 (handles migrated modules)

2. **After Full Migration**: Only Go server
   - Go: 8000 (takes over as main service)

## Environment Variables

Create a `.env` file in the project root:

```bash
# Go Server
GO_PORT=8001
DEV_MODE=true
LOG_LEVEL=debug

# Python FastAPI uses its own config
# (see app/config.py for Python settings)
```

## Systemd Services (Arduino Uno Q)

On the Arduino, you can run both as systemd services:

```bash
# Python service (existing)
systemctl --user status arduino-trader

# Go service (new)
systemctl --user status arduino-trader-go
```

Both services can coexist during the migration period.
