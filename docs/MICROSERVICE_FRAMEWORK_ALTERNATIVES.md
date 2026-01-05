# Microservice Framework Alternatives

This document compares lightweight alternatives to FastAPI/uvicorn for Python microservices in the arduino-trader project.

## Current Setup

- **Framework**: FastAPI 0.109.0
- **Server**: uvicorn 0.27.0
- **Validation**: Pydantic 2.5.3
- **Memory Limit**: 512MB (tradernet service)
- **Deployment**: Systemd (native) or Docker

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

## Recommendation: Starlette + Hypercorn

For your use case (resource-constrained Arduino device), **Starlette + Hypercorn** offers the best balance:

1. **Significant memory savings** (~150-200MB per service)
2. **Low migration effort** (can reuse most code structure)
3. **Still fully async** (no performance loss)
4. **Can keep Pydantic** (use manually for validation if needed)
5. **Production-ready** (used by FastAPI, Reddit, etc.)

### Memory Impact

If you have 3 microservices:
- **Current**: ~1.5GB total (3 × 500MB)
- **With Starlette**: ~900MB total (3 × 300MB)
- **Savings**: ~600MB (40% reduction)

On an embedded device with limited RAM, this is significant.

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

### Phase 1: Quick Win (Hypercorn Only)
- Change systemd service to use `hypercorn` instead of `uvicorn`
- Update requirements.txt
- Test thoroughly
- **Time**: 30 minutes
- **Savings**: ~50-100MB per service

### Phase 2: Full Migration (Starlette)
- Migrate one service at a time (start with simplest: yfinance)
- Update requirements.txt
- Refactor endpoints to Starlette
- Test thoroughly
- **Time**: 2-3 hours per service
- **Savings**: ~150-200MB per service

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

### Hypercorn Only (Keep FastAPI)
```txt
fastapi==0.109.0
hypercorn==0.17.1  # Replace uvicorn
pydantic==2.5.3
```

---

## Testing

After migration, verify:

1. **Health endpoints** work
2. **All API endpoints** return expected responses
3. **Error handling** works correctly
4. **Memory usage** is reduced (check with `ps aux` or `docker stats`)
5. **Performance** is maintained or improved

---

## References

- [Starlette Documentation](https://www.starlette.io/)
- [Hypercorn Documentation](https://hypercorn.readthedocs.io/)
- [Starlette vs FastAPI](https://www.starlette.io/applications/#fastapi)

