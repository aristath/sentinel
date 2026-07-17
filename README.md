# Sentinel - Autonomous Portfolio Management

> Long-term autonomous portfolio management with deterministic contrarian strategy

## Quick Start

### Development

```bash
# Activate virtual environment
source .venv/bin/activate

# Run web server only
python main.py

# Run web server + background scheduler
python main.py --all

# Optional: run the model-agnostic forecasting service
pip install '.[forecasting]'
uvicorn sentinel.forecasting.service:app --host 127.0.0.1 --port 8010

# Run tests
pytest

# Lint & format
ruff check .
ruff format .
```

### Frontend

```bash
cd web/
npm install
npm run dev  # http://localhost:5173
```

## Documentation

- **[Agent Guide](AGENTS.md)** - Complete developer reference
- **[Architecture Docs](docs/)** - Component documentation
  - [Portfolio Composition](docs/portfolio_composition.md) - Analytics & metrics
  - [Universe Management](docs/universe_management.md) - Security import
  - [Deposit History](docs/deposit_history.md) - Cashflow analytics
  - [Contrarian Strategy](docs/strategy_contrarian.md) - Trading signals

## Features

- 🤖 **Autonomous Trading** - Integrates with TraderNet API for live execution
- 📊 **Contrarian Strategy** - Deterministic signals based on price cycles
- 🎯 **Smart Rebalancing** - Patience-first approach with deposit-aware scheduling
- 📈 **Portfolio Analytics** - Risk/return metrics, composition breakdowns
- 🔭 **Time-Series Forecasts** - Optional forecast service for monthly timing signals
- 🔒 **Safety Guards** - Price anomaly detection, position limits, fee awareness
- 🌍 **Multi-Currency** - Automatic FX conversion and multi-currency support

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     FastAPI Server                       │
│                    (port 8000)                           │
├─────────────────────────────────────────────────────────┤
│  Routers: settings │ portfolio │ securities │ trading   │
│            planner │ jobs      │ backup     │ system    │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    Core Services                         │
├─────────────┬──────────────┬──────────────┬─────────────┤
│   Broker    │   Planner    │   Strategy   │   Cache     │
│  (TraderNet)│ (Rebalance)  │(Contrarian)  │   (TTL)     │
└─────────────┴──────────────┴──────────────┴─────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│          Optional Forecasting Service (port 8010)        │
│      model-agnostic API; first provider is Toto 2.0      │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                 SQLite Database                          │
│              (data/sentinel.db)                          │
│  positions │ prices │ securities │ cashflows │ snapshots │
└─────────────────────────────────────────────────────────┘
```

## Technology Stack

- **Backend**: Python 3.13+, FastAPI, aiosqlite
- **Frontend**: React, Vite, TypeScript
- **Scheduler**: APScheduler with database persistence
- **Broker**: TraderNet API integration
- **Testing**: pytest, pytest-asyncio
- **Quality**: Ruff (linting), Pyright (type checking)

## Rebalancing Philosophy

Sentinel separates the long-term destination from today's execution:

1. **Clara defines the destination** - Strategic scores set relative twelve-month target weights
2. **Opportunity controls timing** - Under-target holdings are bought when their price signal is attractive
3. **Orders form a complete plan** - Ordinary sells exist only to fund an executable selected buy
4. **Patience has a limit** - After a durable waiting window, one fallback buy keeps the portfolio converging
5. **Cash is explicit** - Position caps and configured reserves appear as a cash target instead of missing weight

Live execution treats each `trading:execute` run as a fresh decision window: sync broker state, clear planner inputs, calculate the best currently executable plan for open markets, submit at most one ranked transaction, then replan from broker-confirmed state on the next cycle.

## Key Components

| Component | Purpose |
|---|---|
| `PortfolioComposition` | Analytics: country/industry breakdowns, risk metrics |
| `Planner` | Clara-weighted twelve-month targets with opportunity-timed recommendations |
| `Contrarian` | Deterministic cycle-based trading signals |
| `Forecasting` | Scheduled weekly-return forecasts that gently modify timing |
| `DepositHistory` | Cashflow analytics for self-correction timing |
| `PriceValidator` | Anomaly detection and interpolation |
| `Broker` | TraderNet API wrapper with rate limiting |

## Deployment

- **Docker**: `docker-compose.yml` for Arduino UNO Q
- **Systemd**: Service files in `systemd/`; `sentinel-forecasting.service` is optional
- **Auto-deploy**: Direct to main branch

## License

Internal use only
