# Sentinel API Reference

All endpoints are prefixed with `/api`. The server runs on port `8000` by default.

Interactive docs are available at `/docs` (Swagger UI) and `/redoc` (ReDoc) when the server is running.

---

## Sections

| Section | Prefix | Description |
|---|---|---|
| [Settings](settings.md) | `/api/settings` | Application configuration |
| [LED Display](led.md) | `/api/led` | Hardware LED controller and bridge health |
| [Portfolio](portfolio.md) | `/api/portfolio` | Portfolio state, sync, CAGR, P&L history |
| [Allocation Targets](allocation-targets.md) | `/api/allocation-targets` | Geography and industry target weights |
| [Allocation](allocation.md) | `/api/allocation` | Current vs target allocation data |
| [Securities](securities.md) | `/api/securities` | Security universe management and price history |
| [Prices](prices.md) | `/api/prices` | Bulk price sync |
| [Unified View](unified.md) | `/api/unified` | Merged per-security dashboard data |
| [Trades](trades.md) | `/api/trades` | Trade history |
| [Cash Flows](cashflows.md) | `/api/cashflows` | Cash flow summary |
| [Trading Actions](trading-actions.md) | `/api/securities/{symbol}/buy\|sell` | Direct buy/sell execution |
| [Planner](planner.md) | `/api/planner` | Trade recommendations and ideal allocations |
| [Jobs](jobs.md) | `/api/jobs` | Scheduler management and job history |
| [Backup](backup.md) | `/api/backup` | Cloudflare R2 backup |
| [System](system.md) | `/api/health`, `/api/version` | Health check and version |
| [Cache](cache.md) | `/api/cache` | In-memory cache stats and eviction |
| [Backtest](backtest.md) | `/api/backtest` | Historical simulation via SSE |
| [Exchange Rates](exchange-rates.md) | `/api/exchange-rates` | FX rate management |
| [Markets](markets.md) | `/api/markets` | Exchange open/closed status |
| [Meta](meta.md) | `/api/meta` | Category metadata |
| [Pulse](pulse.md) | `/api/pulse` | Active-security labels for Pulse feature |
