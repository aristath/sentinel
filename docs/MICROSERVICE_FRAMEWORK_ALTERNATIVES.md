# Microservice Framework Alternatives

This document compares lightweight alternatives to FastAPI/uvicorn for Python microservices in the arduino-trader project.

## Current Setup

- **Framework**: FastAPI 0.109.0
- **Server**: uvicorn 0.27.0
- **Validation**: Pydantic 2.5.3
- **Memory Limit**: 512MB per service
- **Deployment**:
  - **tradernet** (port 9002): Systemd + venv (native)
  - **yfinance** (port 9003): Systemd + venv (native)
  - **pypfopt** (port 9001): Docker (dockerized)

## Alternatives Comparison

### 1. Starlette + Hypercorn (Recommended ⭐)

**Why**: FastAPI is built on Starlette, so migration is straightforward.

**Pros**:
- ~40-50% smaller memory footprint than FastAPI
- Faster startup time
- Can still use Pydantic manually for validation (optional)
- Fully async (same performance characteristics)
- Minimal code changes required
- Hypercorn is lighter than uvicorn

**Cons**:
- No automatic request/response validation
- Need to manually handle JSON serialization
- Less "magic" - more explicit code

**Memory Savings**: ~150-200MB per service

**Migration Effort**: Low (2-3 hours per service)

---

### 2. Flask (Synchronous)

**Why**: Very lightweight, minimal dependencies, proven framework.

**Pros**:
- Lightest option (~20-30MB base footprint)
- Minimal dependencies (only Werkzeug + Jinja2)
- Simple, familiar syntax
- Mature and stable
- Flask 2.0+ has basic async support (but less mature)
- Works well with Gunicorn (production-ready)

**Cons**:
- **Synchronous by default** - need to change all `async def` → `def`
- Flask 2.0 async is less mature than true async frameworks
- Manual validation (no built-in like FastAPI/Pydantic)
- Single-user system makes sync acceptable, but async is more future-proof

**Memory Savings**: ~120-150MB per service

**Migration Effort**: Medium (3-4 hours per service - need to remove async/await)

**Note**: Since your service methods (yfinance, etc.) are synchronous anyway, Flask works fine. The async endpoints in FastAPI aren't providing real benefit here.

---

### 3. Quart (Async Flask)

**Why**: Flask-compatible but with full async support.

**Pros**:
- **Flask-compatible API** - minimal syntax changes from Flask
- Full async/await support (better than Flask 2.0)
- Lighter than FastAPI
- Can keep async endpoints
- Active development

**Cons**:
- Different API than FastAPI (more refactoring)
- Smaller ecosystem than Starlette/FastAPI
- Still need to change route decorators

**Memory Savings**: ~100-150MB per service

**Migration Effort**: Medium (4-6 hours per service)

**Best For**: If you prefer Flask syntax but want async capabilities.

---

### 4. Sanic

**Why**: Very fast, production-ready async framework.

**Pros**:
- Extremely fast
- Built-in async support
- Good performance benchmarks

**Cons**:
- Very different API (significant refactoring)
- Less popular than Starlette/FastAPI

**Memory Savings**: ~150MB per service

**Migration Effort**: High (6-8 hours per service)

---

### 5. Hypercorn Only (Keep FastAPI)

**Why**: Easiest migration - just swap the server.

**Pros**:
- Minimal code changes (just change server command)
- Some memory savings from hypercorn
- Keep all FastAPI features

**Cons**:
- Still using FastAPI overhead (less savings)

**Memory Savings**: ~50-100MB per service

**Migration Effort**: Very Low (30 minutes)

---

## Recommendation

### Option A: Starlette + Hypercorn (Best Balance) ⭐

For your use case (resource-constrained Arduino device), **Starlette + Hypercorn** offers the best balance:

1. **Significant memory savings** (~150-200MB per service)
2. **Low migration effort** (can reuse most code structure)
3. **Still fully async** (no performance loss)
4. **Can keep Pydantic** (use manually for validation if needed)
5. **Production-ready** (used by FastAPI, Reddit, etc.)

### Option B: Flask (Simplest, Lightest)

Since your service methods are **synchronous anyway** (yfinance, PyPortfolioOpt), Flask is also a great option:

1. **Lightest option** (~120-150MB savings per service)
2. **Simplest code** - no async complexity
3. **Mature and stable**
4. **Minimal dependencies**

**Trade-off**: Need to change `async def` → `def`, but since your underlying calls are sync, you don't lose anything.

### Comparison Table

| Framework | Memory Savings | Migration Effort | Async | Best For |
|-----------|---------------|------------------|-------|----------|
| **Starlette + Hypercorn** | ~150-200MB | Low (2-3h) | ✅ Full async | Best balance |
| **Flask + Gunicorn** | ~120-150MB | Medium (3-4h) | ❌ Sync | Simplest, lightest |
| **Quart** | ~100-150MB | Medium (4-6h) | ✅ Full async | Flask syntax + async |
| **Hypercorn Only** | ~50-100MB | Very Low (30min) | ✅ Full async | Quick win |
| **Sanic** | ~150MB | High (6-8h) | ✅ Full async | Not recommended |

### Memory Impact

With 3 microservices (2 venv, 1 Docker):
- **Current**: ~1.5GB total (3 × 500MB each)
- **With Starlette**: ~900MB total (3 × 300MB each)
- **With Flask**: ~1.05GB total (3 × 350MB each)
- **Savings (Starlette)**: ~600MB (40% reduction)
- **Savings (Flask)**: ~450MB (30% reduction)

On an embedded device with limited RAM (Arduino Uno Q), this is significant.

---

## Migration Example

See `examples/starlette_example.py` for a complete migration example of the yfinance service.

### Key Changes

1. **Remove FastAPI imports**, use Starlette:
   ```python
   from starlette.applications import Starlette
   from starlette.routing import Route
   from starlette.responses import JSONResponse
   ```

2. **Manual JSON handling** (no automatic Pydantic validation):
   ```python
   async def get_quote(request):
       symbol = request.path_params['symbol']
       # Manual validation if needed
       price = service.get_current_price(symbol)
       return JSONResponse({"success": True, "data": {"symbol": symbol, "price": price}})
   ```

3. **CORS middleware** (Starlette compatible):
   ```python
   from starlette.middleware.cors import CORSMiddleware
   app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
   ```

4. **Run with Hypercorn**:
   ```bash
   hypercorn app.main:app --bind 0.0.0.0:9003
   ```

### Pydantic Usage (Optional)

You can still use Pydantic manually:

```python
from pydantic import BaseModel, ValidationError

class BatchQuotesRequest(BaseModel):
    symbols: list[str]

async def get_batch_quotes(request):
    try:
        body = await request.json()
        req = BatchQuotesRequest(**body)
        # Use req.symbols...
    except ValidationError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
```

---

## Implementation Plan

Given your deployment setup (2 venv services, 1 Docker service), here's a recommended migration strategy:

### Service-Specific Considerations

**Venv Services (tradernet, yfinance):**
- Easy to migrate - just update venv and systemd service file
- Can test locally before deploying
- No Docker rebuild needed

**Docker Service (pypfopt):**
- Requires Dockerfile changes
- Need to rebuild Docker image
- Slightly more complex (but still straightforward)

### Recommended Migration Order

1. **yfinance** (venv) - Simplest service, good test case
2. **tradernet** (venv) - Similar to yfinance
3. **pypfopt** (Docker) - More complex, migrate last

### Phase 1: Quick Win (Hypercorn Only)

**For venv services (tradernet, yfinance):**
```bash
# 1. Update requirements.txt (replace uvicorn with hypercorn)
# 2. Recreate venv or update:
cd microservices/yfinance
source venv/bin/activate
pip install hypercorn
pip uninstall uvicorn
# 3. Update systemd service file:
# Change: uvicorn → hypercorn
# ExecStart=/opt/arduino-trader/microservices/yfinance/venv/bin/hypercorn app.main:app --bind 0.0.0.0:9003
# 4. Restart service:
sudo systemctl restart yfinance
```

**For Docker service (pypfopt):**
```bash
# 1. Update requirements.txt
# 2. Rebuild Docker image:
docker-compose build pypfopt
# 3. Update docker-compose.yml CMD (if needed) or Dockerfile
# 4. Restart container:
docker-compose up -d pypfopt
```

**Time**: ~30 minutes per service
**Savings**: ~50-100MB per service

### Phase 2: Full Migration (Starlette/Flask)

**For venv services:**
1. Update requirements.txt
2. Recreate venv: `python3 -m venv venv --clear`
3. Install new requirements: `pip install -r requirements.txt`
4. Refactor code (see examples)
5. Update systemd service file (hypercorn/gunicorn command)
6. Test locally first
7. Deploy and restart service

**For Docker service:**
1. Update requirements.txt
2. Refactor code
3. Rebuild Docker image: `docker-compose build pypfopt`
4. Update Dockerfile CMD if needed
5. Restart container: `docker-compose up -d pypfopt`

**Time**: 2-4 hours per service (depending on framework choice)
**Savings**: ~120-200MB per service

---

## Requirements Changes

### Starlette + Hypercorn
```txt
starlette==0.37.2
hypercorn==0.17.1
# Keep Pydantic if using for validation
pydantic==2.5.3
# Keep your domain libraries
yfinance>=0.2.28
```

### Flask + Gunicorn
```txt
flask==3.0.0
gunicorn==21.2.0
# Optional: Keep Pydantic for validation
pydantic==2.5.3
# Keep your domain libraries
yfinance>=0.2.28
```

### Quart (Async Flask)
```txt
quart==0.19.4
hypercorn==0.17.1
# Optional: Keep Pydantic for validation
pydantic==2.5.3
yfinance>=0.2.28
```

### Hypercorn Only (Keep FastAPI)
```txt
fastapi==0.109.0
hypercorn==0.17.1  # Replace uvicorn
pydantic==2.5.3
```

---

## Testing

After migration, verify:

1. **Health endpoints** work:
   ```bash
   curl http://localhost:9001/health  # pypfopt
   curl http://localhost:9002/health  # tradernet
   curl http://localhost:9003/health  # yfinance
   ```

2. **All API endpoints** return expected responses

3. **Error handling** works correctly

4. **Memory usage** is reduced:
   ```bash
   # For venv services (systemd):
   systemctl status tradernet  # Check memory usage
   systemctl status yfinance

   # For Docker service:
   docker stats pypfopt-service
   ```

5. **Performance** is maintained or improved

## Deployment-Specific Notes

### Venv Services (tradernet, yfinance)

**Systemd Service Files:**
- Located: `tradernet.service`, `yfinance.service`
- Update `ExecStart` line to use new server (hypercorn/gunicorn)
- Update path if venv location changes
- Memory limits already set (MemoryMax=512M)

**Example systemd update for Starlette+Hypercorn:**
```ini
ExecStart=/opt/arduino-trader/microservices/yfinance/venv/bin/hypercorn app.main:app --bind 0.0.0.0:9003
```

**Example systemd update for Flask+Gunicorn:**
```ini
ExecStart=/opt/arduino-trader/microservices/yfinance/venv/bin/gunicorn -w 2 -b 0.0.0.0:9003 app.main:app
```

### Docker Service (pypfopt)

**Dockerfile:**
- Update CMD to use new server
- Requirements.txt changes require rebuild

**Example Dockerfile CMD for Starlette+Hypercorn:**
```dockerfile
CMD ["hypercorn", "app.main:app", "--bind", "0.0.0.0:9001"]
```

**Example Dockerfile CMD for Flask+Gunicorn:**
```dockerfile
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:9001", "app.main:app"]
```

---

## References

- [Starlette Documentation](https://www.starlette.io/)
- [Hypercorn Documentation](https://hypercorn.readthedocs.io/)
- [Starlette vs FastAPI](https://www.starlette.io/applications/#fastapi)
