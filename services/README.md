# Arduino Trader Microservices

This directory contains the gRPC microservices for Arduino Trader.

## Services

1. **Planning** (port 50051) - Portfolio planning and opportunity identification
2. **Scoring** (port 50052) - Security scoring and analysis
3. **Optimization** (port 50053) - Portfolio optimization
4. **Portfolio** (port 50054) - Portfolio state management
5. **Trading** (port 50055) - Trade execution
6. **Universe** (port 50056) - Security universe and market data
7. **Gateway** (port 50057) - API gateway and workflow orchestration

## Running Services

### Local Development (Single Service)

To run a single service locally:

```bash
# From project root
python -m services.planning.main
```

### Docker Compose (All Services)

To run all services together:

```bash
# Build and start all services
docker-compose up --build

# Run in detached mode
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

### Individual Docker Container

To build and run a single service in Docker:

```bash
# Build
docker build -f services/planning/Dockerfile -t arduino-trader-planning .

# Run
docker run -p 50051:50051 \
  -v $(pwd)/app/config:/app/app/config:ro \
  arduino-trader-planning
```

## Configuration

Services read configuration from:
- `app/config/device.yaml` - Device identification and roles
- `app/config/services.yaml` - Service deployment configuration

### Environment Variables

- `DEVICE_CONFIG_PATH` - Path to device.yaml (default: auto-detected)
- `SERVICES_CONFIG_PATH` - Path to services.yaml (default: auto-detected)

## Testing

### Health Check

Each service implements a health check RPC:

```python
from contracts import planning_pb2, planning_pb2_grpc
import grpc

async def check_health():
    channel = grpc.aio.insecure_channel('localhost:50051')
    stub = planning_pb2_grpc.PlanningServiceStub(channel)
    response = await stub.HealthCheck(planning_pb2.Empty())
    print(f"Healthy: {response.healthy}, Status: {response.status}")
```

### gRPC Testing Tools

Use grpcurl for testing:

```bash
# List services
grpcurl -plaintext localhost:50051 list

# Call health check
grpcurl -plaintext localhost:50051 \
  arduino_trader.planning.PlanningService/HealthCheck
```

## Development

### Adding a New RPC Method

1. Update the protobuf definition in `contracts/protos/<service>.proto`
2. Regenerate protos: `./scripts/generate_protos.sh`
3. Implement the method in `services/<service>/grpc_servicer.py`
4. Update the local implementation in `app/modules/<service>/services/local_<service>_service.py`

### Code Structure

Each service has:
- `grpc_servicer.py` - gRPC interface implementation
- `main.py` - Server entrypoint
- `requirements.txt` - Python dependencies
- `Dockerfile` - Container configuration

## Deployment

### Single Device

All services run on one Arduino Uno Q:

```yaml
# app/config/device.yaml
device:
  id: "primary"
  roles: ["all"]
```

### Dual Device

Services distributed across two Arduino Uno Q devices:

```yaml
# Device 1
device:
  id: "compute-1"
  roles: ["planning", "scoring", "optimization"]

# Device 2
device:
  id: "state-1"
  roles: ["portfolio", "trading", "universe", "gateway"]
```

Update service modes in `app/config/services.yaml`:

```yaml
services:
  planning:
    mode: "remote"  # Use gRPC instead of in-process
    device_id: "compute-1"
```

## Monitoring

### Logs

Services log to stdout/stderr. View with:

```bash
# Docker Compose
docker-compose logs -f planning

# Individual container
docker logs -f <container-id>
```

### Metrics

TODO: Implement Prometheus metrics export

### Health Checks

TODO: Implement health check endpoints for monitoring systems

## Troubleshooting

### Port Already in Use

If a port is already in use:

```bash
# Find process using port
lsof -i :50051

# Kill process
kill -9 <pid>
```

### Connection Refused

1. Check service is running: `docker-compose ps`
2. Check logs: `docker-compose logs <service>`
3. Verify configuration in `app/config/services.yaml`
4. Test with grpcurl: `grpcurl -plaintext localhost:50051 list`

### gRPC Errors

Common errors:
- `UNAVAILABLE`: Service not running or network issue
- `DEADLINE_EXCEEDED`: Timeout (check `timeout_seconds` in config)
- `UNAUTHENTICATED`: TLS/auth issue (not yet implemented)

## Next Steps

- [ ] Implement servicers for remaining 6 services
- [ ] Add comprehensive error handling
- [ ] Implement retry logic with exponential backoff
- [ ] Add circuit breakers for fault isolation
- [ ] Implement TLS/mTLS for production
- [ ] Add Prometheus metrics
- [ ] Set up distributed tracing
- [ ] Create integration tests
- [ ] Create deployment scripts for Arduino Uno Q
