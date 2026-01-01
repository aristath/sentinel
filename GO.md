# Go Migration Strategy

## Executive Summary

After comprehensive dependency analysis, **6 out of 11 microservices** can be rewritten in Go for massive performance and memory improvements, while 5 must stay in Python due to dependencies on tradernet-sdk and financial calculation libraries.

**Impact**: 54% memory reduction (~3.6GB saved) + 10-100x faster planning cycles

---

## Architecture: Python + Go

### Services That MUST Stay Python

#### 1. **Universe** (Port 8001)
- **Why**: Uses `tradernet-sdk` for price syncing
- **Memory**: 500MB
- **Verdict**: ✋ Keep Python

#### 2. **Portfolio** (Port 8002)
- **Why**: Uses `tradernet-sdk` for position syncing
- **Memory**: 500MB
- **Verdict**: ✋ Keep Python

#### 3. **Trading** (Port 8003)
- **Why**: Uses `tradernet-sdk` for trade execution
- **Critical**: TradeExecutionService wraps SDK with edge-case handling
- **Memory**: 500MB
- **Verdict**: ✋ Keep Python

#### 4. **Scoring** (Port 8004)
- **Why**: Heavy financial calculations
- **Dependencies**:
  - `pandas-ta` (EMA, RSI, Bollinger Bands)
  - `empyrical` (Sharpe, Volatility, Max Drawdown)
  - `numpy/pandas` for array operations
- **Memory**: 500MB
- **Verdict**: ✋ Keep Python

#### 5. **Optimization** (Port 8005)
- **Why**: Portfolio optimization algorithms
- **Dependencies**: `PyPortfolioOpt` (Mean-Variance, HRP)
- **Memory**: 500MB
- **Verdict**: ✋ Keep Python

**Total Python footprint**: ~2.5GB

---

### Services That CAN Move to Go

#### Tier 1: High Impact, Low Risk

##### 1. **Gateway** (Port 8007) ⭐ TOP PRIORITY
- **Current**: 500MB Python
- **After Go**: 50MB
- **What it does**: HTTP routing, health checks, system orchestration
- **Dependencies**: None (pure HTTP)
- **Go advantages**:
  - 5-10x lower latency
  - Better HTTP/2 support
  - Excellent concurrency
  - 10x less memory
- **Complexity**: Low - pure reverse proxy
- **Effort**: 1-2 days
- **Savings**: 450MB

##### 2. **Coordinator** (Port 8011)
- **Current**: 500MB Python
- **After Go**: 50MB
- **What it does**: Orchestrates Opportunity → Generator → Evaluator workflow
- **Dependencies**: HTTP clients only
- **Go advantages**: Better goroutine-based concurrency
- **Complexity**: Low
- **Effort**: 1-2 days
- **Savings**: 450MB

#### Tier 2: High Impact, Medium Complexity

##### 3. **Evaluator** (Ports 8010/8020/8030) ⭐ BIGGEST WIN
- **Current**: 1.5GB Python (3 instances × 500MB)
- **After Go**: 150MB (3 instances × 50MB)
- **What it does**:
  - Fetches **pre-computed metrics** from database
  - Runs pure math scoring formulas (no numpy!)
  - Portfolio simulation (pure logic)
- **Key insight**: All financial calculations done by Scoring service → stored in DB → Evaluator just uses them
- **Go advantages**:
  - **10-100x faster** computation
  - No Python GIL constraints
  - True parallel goroutines
  - **Planning cycles: minutes → seconds**
- **Complexity**: Medium-High (most complex business logic)
- **Effort**: 1-2 weeks
- **Savings**: 1.35GB + massive speedup

##### 4. **Generator** (Port 8009)
- **Current**: 500MB Python
- **After Go**: 50MB
- **What it does**: Combinatorial sequence generation
- **Dependencies**: Pure logic, no financial libs
- **Go advantages**: 10-50x faster combinatorics
- **Complexity**: Medium
- **Effort**: 3-5 days
- **Savings**: 450MB

##### 5. **Opportunity** (Port 8008)
- **Current**: 500MB Python
- **After Go**: 50MB
- **What it does**: Identifies trading opportunities (pure logic)
- **Dependencies**: None - holistic_planner uses zero numpy/pandas
- **Go advantages**: Faster opportunity identification
- **Complexity**: Medium
- **Effort**: 3-5 days
- **Savings**: 450MB

##### 6. **Planning** (Port 8006)
- **Current**: 500MB Python
- **After Go**: 50MB
- **What it does**: Plan CRUD operations
- **Dependencies**: Database only
- **Go advantages**: Faster DB operations
- **Complexity**: Low
- **Effort**: 2-3 days
- **Savings**: 450MB

**Total Go footprint**: ~450MB (vs 3.5GB in Python)
**Total savings**: ~3.6GB (54% reduction)

---

## Numpy Operations Analysis

### What Scoring Service Uses (Stays Python)

All financial calculations happen in **Scoring service only**:

```python
# Simple numpy operations used:
np.array([...])        # Convert list to array
np.mean(closes)        # Calculate average
np.diff(closes)        # Calculate returns: closes[i] - closes[i-1]
np.any(closes <= 0)    # Validate no zero/negative prices
np.isfinite(value)     # Validate no NaN/Inf

# Complex financial libraries (hard to port):
pandas_ta.ema()        # Exponential Moving Average
pandas_ta.rsi()        # Relative Strength Index
pandas_ta.bbands()     # Bollinger Bands
empyrical.sharpe_ratio()      # Risk-adjusted returns
empyrical.annual_volatility() # Annualized volatility
empyrical.max_drawdown()      # Maximum drawdown
```

### What Evaluator Uses (Can Move to Go)

**Zero numpy!** Just pure math with pre-computed metrics:

```python
# Fetches from database (already computed by Scoring service)
metrics = {
    "CAGR_5Y": 0.12,           # Pre-computed
    "DIVIDEND_YIELD": 0.03,     # Pre-computed
    "SHARPE_RATIO": 1.5,        # Pre-computed
    "VOLATILITY_5Y": 0.18,      # Pre-computed
    ...
}

# Then just arithmetic:
total_return_score = cagr + dividend_yield  # Simple addition
stability_score = volatility_score * 0.5 + drawdown_score * 0.3  # Weighted avg
```

**This is trivial to port to Go!**

---

## Architecture Comparison

### Current (All Python)
```
Total Memory: ~6.5GB

Gateway         500MB  ┐
Universe        500MB  │ Can't reduce (tradernet-sdk)
Portfolio       500MB  │
Trading         500MB  │
Scoring         500MB  │ Can't reduce (numpy/pandas)
Optimization    500MB  ┘
Planning        500MB  ┐
Coordinator     500MB  │
Opportunity     500MB  │ Can reduce to ~50MB each in Go
Generator       500MB  │
Evaluator-1     500MB  │
Evaluator-2     500MB  │
Evaluator-3     500MB  ┘
```

### Proposed (Python + Go)
```
Total Memory: ~3.0GB (54% reduction)

Universe        500MB  ┐
Portfolio       500MB  │ Python (tradernet-sdk)
Trading         500MB  │
Scoring         500MB  │ Python (numpy/pandas)
Optimization    500MB  ┘

Gateway          50MB  ┐
Planning         50MB  │
Coordinator      50MB  │ Go (pure logic/HTTP)
Opportunity      50MB  │
Generator        50MB  │
Evaluator-1      50MB  │
Evaluator-2      50MB  │
Evaluator-3      50MB  ┘
```

**Planning performance**: Minutes → Seconds (10-100x faster)

---

## Performance Gains

### Evaluator (Biggest Bottleneck)
- **Current**: Python event loop, GIL constraints, slow simulation
- **Go**: True parallel goroutines, no GIL, compiled code
- **Expected**: 10-100x faster sequence evaluation
- **Impact**: Planning cycles from minutes to seconds

### Generator
- **Current**: Slow Python combinatorics
- **Go**: Fast array operations, efficient memory allocation
- **Expected**: 10-50x faster sequence generation
- **Impact**: Explore more sequences in same time budget

### Gateway
- **Current**: Python async overhead, uvicorn
- **Go**: Native HTTP/2, zero-allocation routing
- **Expected**: 5-10x lower latency
- **Impact**: Faster response for all API calls

---

## Implementation Plan

### Phase 1: Quick Wins (Week 1-2)

#### Step 1: Clean Requirements.txt (Day 1)
**Immediate 2-3GB memory savings**

Remove from 6 services (Gateway, Coordinator, Generator, Evaluator, Opportunity, Planning):
- pandas, numpy, yfinance
- empyrical-reloaded, pandas-ta, pyfolio-reloaded
- PyPortfolioOpt, scikit-learn
- tradernet-sdk

Keep only:
- fastapi, uvicorn, pydantic
- PyYAML, httpx, aiosqlite
- python-dotenv, pydantic-settings

#### Step 2: Gateway → Go (Day 2-3)
- Simplest rewrite (pure HTTP proxy)
- Proves out Go deployment pipeline
- Immediate latency improvement
- **Savings**: 450MB

#### Step 3: Coordinator → Go (Day 4-5)
- Second simplest (HTTP orchestration)
- Validates multi-service Go deployment
- **Savings**: 450MB

### Phase 2: Performance Critical (Week 3-6)

#### Step 4: Evaluator → Go (Week 3-4)
- **Biggest performance win**
- Most complex, but highest ROI
- Port simulation logic and scoring formulas
- Database queries for metrics
- **Savings**: 1.35GB + 10-100x speedup

#### Step 5: Generator → Go (Week 5)
- Port combinatorial generation
- Sequence filtering logic
- **Savings**: 450MB + 10-50x speedup

#### Step 6: Opportunity → Go (Week 6)
- Port opportunity identification
- Weight-based and heuristic logic
- **Savings**: 450MB

### Phase 3: Polish (Week 7+)

#### Step 7: Planning → Go (Week 7)
- CRUD operations
- Database queries
- **Savings**: 450MB

---

## Go Library Stack

### HTTP Server
- `net/http` (stdlib) or `fiber` (FastAPI-like)
- Built-in HTTP/2, WebSocket support
- Zero external dependencies for basic routing

### Database
- `database/sql` (stdlib) for SQLite
- `sqlx` for query building
- `go-sqlite3` driver

### Serialization
- `encoding/json` (stdlib)
- `gopkg.in/yaml.v3` for YAML config

### HTTP Client
- `net/http` (stdlib)
- Connection pooling built-in

### Testing
- `testing` (stdlib)
- `testify` for assertions

**All mature, stable, well-documented libraries!**

---

## Deployment Considerations

### Docker Images
- **Python**: 500MB base image
- **Go**: 10-20MB base image (scratch or alpine)
- **Savings**: 95% smaller images

### Startup Time
- **Python**: 2-5 seconds (import overhead)
- **Go**: 50-200ms (compiled binary)
- **Improvement**: 10-25x faster restarts

### Resource Usage
- **Python**: 50-100MB baseline per service
- **Go**: 5-10MB baseline per service
- **Savings**: 90% less overhead

### Cross-Compilation
- Go can cross-compile for Arduino Uno Q (Linux ARM)
- Single `GOOS=linux GOARCH=arm64 go build` command
- No virtual environment needed

---

## Risk Mitigation

### Keep Python Services Stable
- **Universe, Portfolio, Trading**: Critical for trading, don't touch
- **Scoring, Optimization**: Complex algorithms, not worth porting
- **Strategy**: Leave these 5 services completely alone

### Incremental Migration
1. Start with Gateway (lowest risk)
2. Prove deployment works
3. Move to Coordinator (medium risk)
4. Finally Evaluator (highest complexity)

### Rollback Plan
- Keep Python versions running during migration
- Use feature flags to route traffic
- Monitor performance metrics
- Easy rollback if issues

### Testing Strategy
- Port unit tests alongside code
- Integration tests for API compatibility
- Load testing to verify performance gains
- Canary deployments for each service

---

## Success Metrics

### Memory Usage
- **Target**: <3GB total (from 6.5GB)
- **Measure**: Docker stats, htop
- **Goal**: Run comfortably on Arduino Uno Q (2GB RAM)

### Performance
- **Target**: Planning cycles <30 seconds (from minutes)
- **Measure**: End-to-end planning time
- **Goal**: Interactive planning experience

### Latency
- **Target**: API response <100ms p99 (from ~500ms)
- **Measure**: Gateway response times
- **Goal**: Snappy dashboard experience

### Stability
- **Target**: Zero regression in trading accuracy
- **Measure**: Backtest results, trade execution success rate
- **Goal**: Maintain or improve current quality

---

## Next Steps

1. **Today**: Clean requirements.txt (1 hour)
   - Remove bloat from 6 services
   - Immediate 2-3GB memory savings
   - Validate all services still start

2. **This Week**: Gateway → Go (2-3 days)
   - Implement HTTP proxy in Go
   - Deploy alongside Python version
   - Switch traffic over
   - Prove concept

3. **Next Week**: Coordinator → Go (2-3 days)
   - Port orchestration logic
   - Validate planning workflow
   - Measure performance gains

4. **Weeks 3-4**: Evaluator → Go (1-2 weeks)
   - Most complex but biggest win
   - Port simulation and scoring
   - Target 10-100x speedup

**Total Timeline**: 6-8 weeks to full migration
**Expected Result**: 54% memory reduction + 10-100x faster planning

---

## Conclusion

The path is clear:
- **5 services stay Python** (tradernet-sdk + financial libs)
- **6 services move to Go** (pure logic, no complex deps)
- **54% memory savings** (~3.6GB freed)
- **10-100x performance gains** for planning cycles
- **Cleaner architecture** with only 2 languages

This is achievable, low-risk, and high-impact for Arduino Uno Q deployment.
