# Go Planner Evaluation Service

High-performance evaluation service for Arduino Trader's planning module.

## Architecture

- **HTTP Server**: Gin framework on port 9000
- **Parallelization**: Worker pool with goroutines
- **Memory**: <50MB per instance
- **Performance**: 100+ sequences/sec (10-100x faster than Python)

## API Endpoints

- `POST /api/v1/evaluate/batch` - Evaluate multiple sequences in parallel
- `GET /api/v1/health` - Health check
- `GET /api/v1/metrics` - Prometheus metrics

## Building

```bash
# Local development (macOS/Linux)
go build -o evaluator-go ./cmd/server

# Cross-compile for Arduino Uno Q (ARM64)
GOOS=linux GOARCH=arm64 go build -o evaluator-go ./cmd/server
```

## Running

```bash
./evaluator-go
# Server starts on :9000
```

## Testing

```bash
go test ./...
```

## Deployment

Binary is automatically built by GitHub Actions on push to `services/evaluator-go/**`.
Download artifact and deploy to Arduino Uno Q.
