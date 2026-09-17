# API reference

Sentinel's application endpoints are prefixed with `/api`. Production and the
default local server use port 8000. A running instance publishes generated
OpenAPI at `/openapi.json`, Swagger UI at `/docs`, and ReDoc at `/redoc`.

Unless an endpoint says otherwise, request and response bodies are JSON. FastAPI
validation failures use status 422; application failures normally return an
object with a `detail` field. There is no authentication layer because Sentinel
is designed for its trusted local network.

## Sections

| Section | Prefix | Description |
|---|---|---|
| [Settings](settings.md) | `/api/settings` | Application configuration |
| [AI research](ai.md) | `/api/ai` | Direct prompting, pipeline status, research units, requests, history, artifacts |
| [AI memory](memory.md) | `/api/memory` | Deduplicated pgvector research memory |
| [Editable tasks](tasks.md) | `/api/tasks`, `/api/task-runs`, `/api/scheduler` | Task definitions, files, execution, and queue |
| [LED Display](led.md) | `/api/led` | Hardware LED controller and bridge health |
| [Portfolio](portfolio.md) | `/api/portfolio` | Portfolio state, sync, CAGR, P&L history, composition |
| [Securities](securities.md) | `/api/securities` | Security universe management and price history |
| [Prices](prices.md) | `/api/prices` | Bulk price sync |
| [Unified View](unified.md) | `/api/unified` | Merged per-security dashboard data |
| [Trades](trades.md) | `/api/trades` | Trade history |
| [Cash Flows](cashflows.md) | `/api/cashflows` | Cash flow summary |
| [Trading Actions](trading-actions.md) | `/api/securities/{symbol}/buy\|sell` | Direct buy/sell execution |
| [Planner](planner.md) | `/api/planner` | Trade recommendations and ideal allocations |
| [Jobs](jobs.md) | `/api/jobs` | Scheduler management and job history |
| [Forecasts](forecasts.md) | `/api/forecasts` | Forecast service/run status and symbol results |
| [Backup](backup.md) | `/api/backup` | Cloudflare R2 backup |
| [System](system.md) | `/api/health`, `/api/version` | Health check and version |
| [Cache](cache.md) | `/api/cache` | In-memory cache stats and eviction |
| [Backtest](backtest.md) | `/api/backtest` | Historical simulation via SSE |
| [Exchange Rates](exchange-rates.md) | `/api/exchange-rates` | FX rate management |
| [Markets](markets.md) | `/api/markets` | Exchange open/closed status |
| [Meta](meta.md) | `/api/meta` | Category metadata |
| [Pulse](pulse.md) | `/api/pulse` | Active-security labels for Pulse feature |

## Contract maintenance

Every public method/path pair in the running FastAPI application must have a
matching heading in this directory. Run from the repository root:

```bash
source .venv/bin/activate
python scripts/check_docs.py
```

The generated OpenAPI schema is authoritative for route discovery. These pages
add behavioral constraints and examples that cannot be inferred from the schema
alone.
