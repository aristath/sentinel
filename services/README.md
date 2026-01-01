# Planning Microservices Architecture

This directory contains the microservice decomposition of the Planning service for parallel evaluation and 2.5× performance improvement.

## Architecture Overview

The monolithic Planning service (3795 lines in `holistic_planner.py`) has been split into 4 specialized microservices:

```
┌─────────────┐
│ Coordinator │ (Port 8011)
└──────┬──────┘
       │
       ├─────────────┬─────────────┬─────────────┐
       │             │             │             │
       ▼             ▼             ▼             ▼
┌─────────────┐ ┌─────────┐ ┌───────────┐ ┌───────────┐
│ Opportunity │ │Generator│ │Evaluator-1│ │Evaluator-2│
│  (8008)     │ │ (8009)  │ │  (8010)   │ │  (8020)   │
└─────────────┘ └─────────┘ └───────────┘ └───────────┘
                                            ┌───────────┐
                                            │Evaluator-3│
                                            │  (8030)   │
                                            └───────────┘
```

## Services

### 1. Opportunity Service (Port 8008)

**Purpose:** Identify trading opportunities from portfolio state

**Endpoints:**
- `POST /opportunity/identify` - Identify opportunities
- `GET /opportunity/health` - Health check

**Features:**
- Weight-based opportunity identification
- Heuristic-based fallback
- 5 opportunity categories:
  - Profit taking (sell high performers)
  - Averaging down (buy dips)
  - Rebalance sells (reduce overweight)
  - Rebalance buys (increase underweight)
  - Opportunity buys (new positions)

**Files:**
- `services/opportunity/` - FastAPI service
- `app/modules/planning/services/local_opportunity_service.py` - Domain wrapper
- `app/infrastructure/http_clients/opportunity_client.py` - HTTP client

### 2. Generator Service (Port 8009)

**Purpose:** Generate and filter action sequences

**Endpoints:**
- `POST /generator/generate` - Generate sequences (streaming)
- `GET /generator/health` - Health check

**Features:**
- 10 pattern types (direct buys, profit-taking, rebalance, etc.)
- Combinatorial generation
- Correlation-aware filtering
- Feasibility filtering
- Batch streaming (500-1000 sequences per batch)

**Files:**
- `services/generator/` - FastAPI service
- `app/modules/planning/services/local_generator_service.py` - Domain wrapper
- `app/infrastructure/http_clients/generator_client.py` - HTTP client

### 3. Evaluator Service (Ports 8010, 8020, 8030)

**Purpose:** Simulate and score action sequences

**Endpoints:**
- `POST /evaluator/evaluate` - Evaluate sequences
- `GET /evaluator/health` - Health check

**Features:**
- Portfolio simulation via `simulate_sequence()`
- Beam search (maintains top K sequences)
- Transaction cost calculation
- Feasibility checking
- Runs 3 parallel instances for distributed workload

**Files:**
- `services/evaluator/` - FastAPI service
- `app/modules/planning/services/local_evaluator_service.py` - Domain wrapper
- `app/infrastructure/http_clients/evaluator_client.py` - HTTP client

**Configuration:**
- Port configured via `EVALUATOR_PORT` environment variable
- Supports multiple instances for parallel evaluation

### 4. Coordinator Service (Port 8011)

**Purpose:** Orchestrate the complete planning workflow

**Endpoints:**
- `POST /coordinator/create-plan` - Create holistic plan
- `GET /coordinator/health` - Health check

**Workflow:**
1. Call Opportunity Service → identify opportunities
2. Call Generator Service → stream sequences in batches
3. Distribute batches to Evaluator instances (round-robin)
4. Aggregate results in global beam
5. Build final plan from best sequence

**Features:**
- Round-robin load balancing across evaluators
- Global beam aggregation
- Error handling with partial results
- Execution statistics

**Files:**
- `services/coordinator/` - FastAPI service
- `app/modules/planning/services/local_coordinator_service.py` - Domain wrapper
- `app/infrastructure/http_clients/coordinator_client.py` - HTTP client

## Running Services

### Local Development

Start all services:
```bash
docker-compose up opportunity generator evaluator-1 evaluator-2 evaluator-3 coordinator
```

Start individual service:
```bash
docker-compose up opportunity
```

### Service Ports

| Service      | Port(s)           | Purpose                    |
|--------------|-------------------|----------------------------|
| Opportunity  | 8008              | Opportunity identification |
| Generator    | 8009              | Sequence generation        |
| Evaluator    | 8010, 8020, 8030  | Sequence evaluation (3x)   |
| Coordinator  | 8011              | Workflow orchestration     |

### Health Checks

Check all services:
```bash
curl http://localhost:8008/opportunity/health
curl http://localhost:8009/generator/health
curl http://localhost:8010/evaluator/health
curl http://localhost:8020/evaluator/health
curl http://localhost:8030/evaluator/health
curl http://localhost:8011/coordinator/health
```

## Configuration

### Docker Compose

Services are configured in `docker-compose.yml`:
- Each service has its own container
- All mount `app/config` for shared configuration
- Connected via `arduino-trader` network
- Coordinator depends on all other services

### Service Discovery

Services are registered in `app/config/services.yaml`:
- Opportunity: 10s timeout, 30s health check
- Generator: 30s timeout (streaming), 30s health check
- Evaluator: 120s timeout (heavy compute), 60s health check, 3 instances
- Coordinator: 300s timeout (full workflow), 30s health check

### Service Locator

HTTP clients registered in `app/infrastructure/service_discovery/service_locator.py`:
```python
locator = get_service_locator()
opportunity_client = locator.create_http_client("opportunity")
generator_client = locator.create_http_client("generator")
evaluator_client = locator.create_http_client("evaluator")
coordinator_client = locator.create_http_client("coordinator")
```

## Performance

### Current (Monolithic)
- Execution time: ~86 seconds per plan
- Single-threaded evaluation
- RAM accumulation with all sequences in memory

### Target (Microservices)
- Execution time: ~32-34 seconds per plan
- **2.5-3× speedup** via parallel evaluation
- Batch streaming prevents RAM accumulation
- 3 parallel Evaluator instances

### Bottleneck
The Evaluator service is the performance bottleneck (60s per batch). Parallelizing across 3 instances provides the speedup:
- 1 evaluator: 60s × 3 batches = 180s
- 3 evaluators: 60s (parallel) = 60s
- **Speedup: 3×**

## Data Flow

```
1. Coordinator receives CreatePlanRequest
   ↓
2. Coordinator → Opportunity Service
   Returns: Categorized opportunities
   ↓
3. Coordinator → Generator Service (streaming)
   Yields: Batches of sequences (500-1000 each)
   ↓
4. For each batch:
   Coordinator → Evaluator (round-robin)
   Returns: Top K sequences with scores
   ↓
5. Coordinator aggregates in global beam
   Maintains: Top K across all batches
   ↓
6. Coordinator builds final plan
   Returns: HolisticPlan with execution stats
```

## Model Conversions

Each service converts between Pydantic API models and domain models:

**Opportunity Service:**
- `PortfolioContextInput` → `PortfolioContext`
- `PositionInput` → `Position`
- `SecurityInput` → `Security`
- `ActionCandidate` → `ActionCandidateModel`

**Generator Service:**
- `OpportunitiesInput` → `Dict[str, List[ActionCandidate]]`
- `ActionCandidateModel` ↔ `ActionCandidate`

**Evaluator Service:**
- `PortfolioContextInput` → `PortfolioContext`
- `ActionCandidateModel` ↔ `ActionCandidate`
- Returns `SequenceEvaluationResult`

**Coordinator Service:**
- Converts between all service model types
- Aggregates results into `HolisticPlanModel`

## Design Principles

### 1. Thin Adapter Layer
Services delegate to existing production-tested domain logic in `holistic_planner.py` rather than reimplementing business logic.

### 2. Backward Compatibility
The existing Planning API (`POST /planning/create`) can route to Coordinator Service internally while maintaining the same external interface.

### 3. Device-Agnostic
Services can run on 1-N devices. Topology is configured via `services.yaml`, not hardcoded.

### 4. Graceful Degradation
- Fallback to monolithic planner if microservices unavailable
- Partial results if some evaluator batches fail
- Retry logic with circuit breakers

## Development

### Adding New Pattern Types

1. Update `holistic_planner.py` with new pattern logic
2. Services automatically use new patterns (thin wrapper)
3. No microservice code changes needed

### Adding New Scoring Metrics

1. Implement scoring function in `app/modules/scoring/domain/`
2. Update `LocalEvaluatorService.evaluate_sequences()` to call new function
3. Add metrics to `SequenceEvaluationResult.metrics`

### Scaling Evaluators

Add more evaluator instances in `docker-compose.yml`:
```yaml
evaluator-4:
  build:
    context: .
    dockerfile: services/evaluator/Dockerfile
  ports:
    - "8040:8040"
  environment:
    - EVALUATOR_PORT=8040
```

Update `services.yaml`:
```yaml
evaluator:
  instances:
    - port: 8010
    - port: 8020
    - port: 8030
    - port: 8040  # New instance
```

## Testing

### Unit Tests
```bash
pytest tests/unit/services/opportunity/
pytest tests/unit/services/generator/
pytest tests/unit/services/evaluator/
pytest tests/unit/services/coordinator/
```

### Integration Tests
```bash
pytest tests/integration/services/planning/test_planning_microservices.py
```

### Equivalence Test
```bash
pytest tests/integration/services/planning/test_planning_equivalence.py
```

Verifies microservice results match monolithic planner results.

### Performance Test
```bash
pytest tests/performance/test_planning_microservices_performance.py
```

Verifies 2.5× speedup is achieved.

## Monitoring

### Metrics
- Request latency per service
- Batch processing time (Evaluator)
- Beam aggregation time (Coordinator)
- Round-robin distribution fairness
- Error rates and circuit breaker trips

### Logs
All services log to stdout with structured logging:
- Request/response traces
- Performance metrics
- Error details
- Beam state updates

## Troubleshooting

### Service Not Starting
```bash
# Check logs
docker-compose logs opportunity

# Check health endpoint
curl http://localhost:8008/opportunity/health
```

### Slow Performance
- Check Evaluator logs for bottlenecks
- Verify 3 Evaluator instances are running
- Check round-robin distribution in Coordinator logs
- Monitor batch sizes (should be 500-1000)

### Coordinator Timeout
- Increase `COORDINATOR_TIMEOUT` in environment
- Check if all dependent services are healthy
- Verify network connectivity between services

## Future Enhancements

1. **Full Scoring Integration**: Replace placeholder scores in Evaluator with complete scoring logic
2. **Correlation-Aware Filtering**: Implement in Generator service
3. **Monte Carlo Evaluation**: Optional stochastic scenario testing in Evaluator
4. **Metrics Caching**: Pre-fetch metrics in Evaluator for faster scoring
5. **Adaptive Batch Sizing**: Dynamic batch size based on sequence complexity
6. **Priority Queue**: Evaluate high-priority sequences first
7. **Result Caching**: Cache evaluation results for identical sequences
8. **Distributed Tracing**: Add OpenTelemetry for cross-service tracing

## License

Part of the Arduino Trader autonomous portfolio management system.
