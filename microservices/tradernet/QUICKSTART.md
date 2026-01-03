# Tradernet Microservice - Quick Start Guide

## Prerequisites

- Docker & Docker Compose installed
- Python 3.11+ (for local development without Docker)
- Go 1.21+ (for trader service)
- Tradernet API credentials

---

## Setup

### 1. Configure Environment Variables

Create `.env` file in `microservices/tradernet/`:

```bash
# Tradernet API Credentials
TRADERNET_API_KEY=your-tradernet-api-key
TRADERNET_API_SECRET=your-tradernet-api-secret

# Service Configuration
PORT=9001
LOG_LEVEL=INFO
```

### 2. Start Tradernet Microservice

#### Option A: Using Docker (Recommended)

```bash
cd microservices/tradernet
docker-compose up -d
```

Verify it's running:
```bash
curl http://localhost:9001/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "tradernet-service",
  "version": "1.0.0",
  "timestamp": "2026-01-02T15:30:00Z",
  "tradernet_connected": true
}
```

#### Option B: Local Development (Without Docker)

```bash
cd microservices/tradernet

# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn app.main:app --reload --port 9001
```

### 3. Configure Go Service

Update `trader/.env`:

```bash
# Add Tradernet microservice URL
TRADERNET_SERVICE_URL=http://localhost:9001

# Existing config...
GO_PORT=8001
PYTHON_SERVICE_URL=http://localhost:8000
DATABASE_PATH=./data/portfolio.db
LOG_LEVEL=info
```

### 4. Start Go Service

```bash
cd trader
go run cmd/server/main.go
```

Expected output:
```
INFO Starting HTTP server port=8001
INFO Connected to Tradernet API
```

---

## Verify Integration

### Test Trade Execution

```bash
curl -X POST http://localhost:8001/api/trades/execute \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL.US",
    "side": "BUY",
    "quantity": 10
  }'
```

### Test Cash Breakdown

```bash
curl http://localhost:8001/api/portfolio/cash-breakdown
```

### Test Transaction History

```bash
curl http://localhost:8001/api/portfolio/transactions
```

### Test Pending Orders

```bash
curl http://localhost:8001/api/trades/pending-orders
```

---

## Troubleshooting

### Microservice Not Connected

**Problem**: `tradernet_connected: false` in health check

**Solutions:**
1. Check credentials:
   ```bash
   echo $TRADERNET_API_KEY
   echo $TRADERNET_API_SECRET
   ```

2. View logs:
   ```bash
   docker-compose logs tradernet
   ```

3. Restart service:
   ```bash
   docker-compose restart tradernet
   ```

### Go Service Can't Reach Microservice

**Problem**: "Failed to contact Tradernet microservice"

**Solutions:**
1. Verify microservice is running:
   ```bash
   curl http://localhost:9001/health
   ```

2. Check TRADERNET_SERVICE_URL in trader/.env:
   ```bash
   grep TRADERNET_SERVICE_URL trader/.env
   ```

3. Verify network connectivity:
   ```bash
   ping localhost
   ```

---

## Monitoring

### View Logs

**Microservice:**
```bash
docker-compose logs -f tradernet
```

**Go Service:**
```bash
# Logs appear in terminal where you ran 'go run'
```

### Health Checks

**Microservice:**
```bash
watch -n 5 'curl -s http://localhost:9001/health | jq'
```

**Go Service:**
```bash
curl http://localhost:8001/health
```

---

## Stopping Services

### Stop Microservice

```bash
cd microservices/tradernet
docker-compose down
```

### Stop Go Service

Press `Ctrl+C` in terminal where it's running

---

## Production Deployment

### Build Docker Image

```bash
cd microservices/tradernet
docker build -t tradernet-service:1.0.0 .
```

### Run in Production

```bash
docker run -d \
  -p 9001:9001 \
  -e TRADERNET_API_KEY="${TRADERNET_API_KEY}" \
  -e TRADERNET_API_SECRET="${TRADERNET_API_SECRET}" \
  --name tradernet \
  --restart unless-stopped \
  tradernet-service:1.0.0
```

### Health Monitoring

Add to your monitoring stack:

```bash
# Prometheus
- job_name: 'tradernet'
  static_configs:
    - targets: ['localhost:9001']

# Or simple check
*/5 * * * * curl -f http://localhost:9001/health || alert
```

---

## Testing

### Run Unit Tests

```bash
cd microservices/tradernet
pytest
```

### Run with Coverage

```bash
pytest --cov=app tests/
```

### Integration Tests

```bash
# Ensure both services are running
# Then test each endpoint
./scripts/test-integration.sh  # TODO: Create this script
```

---

## API Documentation

Once running, view auto-generated API docs:

**OpenAPI/Swagger UI:**
http://localhost:9001/docs

**ReDoc:**
http://localhost:9001/redoc

---

## Getting Help

- **Microservice README**: `microservices/tradernet/README.md`
- **API Design Doc**: `microservices/tradernet/DESIGN.md`
- **Migration Status**: `microservices/tradernet/MIGRATION_STATUS.md`
- **GitHub Issues**: https://github.com/anthropics/claude-code/issues

---

## Quick Reference

### Service Ports
- **Tradernet Microservice**: 9001
- **Go Service**: 8001
- **Python Service**: 8000

### Key Endpoints
- **Health**: GET /health
- **Trade**: POST /api/trading/place-order
- **Positions**: GET /api/portfolio/positions
- **Cash**: GET /api/portfolio/cash-balances
- **Transactions**: GET /api/transactions/cash-movements

### Environment Variables
```bash
# Tradernet Microservice
TRADERNET_API_KEY=...
TRADERNET_API_SECRET=...
PORT=9001

# Go Service
TRADERNET_SERVICE_URL=http://localhost:9001
GO_PORT=8001
```
