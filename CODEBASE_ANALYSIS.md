# Arduino Trader - Codebase Analysis

## Executive Summary

**Arduino Trader** is an automated portfolio management system designed to run on Arduino Uno Q hardware. It implements a sophisticated stock scoring and rebalancing algorithm with a clean architecture pattern, featuring:

- **Automated monthly rebalancing** based on cash deposits
- **Multi-factor stock scoring** (8 scoring groups with configurable weights)
- **Geographic and industry diversification** (EU 50%, Asia 30%, US 20%)
- **Web dashboard** with real-time portfolio visualization
- **LED status display** on Arduino Uno Q's 8x13 matrix
- **Remote access** via Cloudflare Tunnel

---

## Architecture Overview

### Dual-Brain Hardware Architecture

The Arduino Uno Q features a **dual-processor architecture**:

```
┌─────────────────────────────────────────────────────────┐
│                    Arduino Uno Q                        │
│              (Dual-Brain Architecture)                  │
├─────────────────────────┬───────────────────────────────┤
│   Linux MPU             │      STM32U585 MCU            │
│   (Qualcomm QRB2210)    │      (Microcontroller)        │
│                         │                               │
│  ┌──────────────────┐  │  ┌──────────────────────┐   │
│  │   FastAPI App    │  │  │   C++ Sketch         │   │
│  │   + SQLite DB    │  │  │   (sketch.ino)       │   │
│  │   + APScheduler  │  │  │                      │   │
│  │   + Python Jobs  │  │  │  - LED Matrix Ctrl   │   │
│  └────────┬─────────┘  │  │  - RGB LEDs 3 & 4    │   │
│           │             │  │  - Real-time I/O      │   │
│           │ Router      │  │                      │   │
│           │ Bridge      │  │                      │   │
│           └─────────────┼──┴──────────────────────┘   │
│                         │                               │
│  ┌──────────────────┐  │                               │
│  │  LED 1 & 2       │  │  ┌──────────────────────┐   │
│  │  (sysfs control) │  │  │  LED Matrix 8x13     │   │
│  │  - LED 1: User   │  │  │  RGB LED 3 & 4       │   │
│  │  - LED 2: System │  │  │                      │   │
│  └──────────────────┘  │  └──────────────────────┘   │
│           │             │                               │
│           ▼             │                               │
│  ┌──────────────────┐  │                               │
│  │   Cloudflared     │  │                               │
│  │   (Tunnel)        │  │                               │
│  └──────────────────┘  │                               │
└─────────────────────────┴───────────────────────────────┘
```

**Linux MPU (Main Processing Unit)**:
- **Processor**: Qualcomm Dragonwing QRB2210
- **OS**: Linux-based
- **Responsibilities**:
  - FastAPI web application
  - SQLite database management
  - APScheduler background jobs
  - External API integration (Tradernet, Yahoo Finance)
  - Business logic and scoring algorithms
  - LED 1 & 2 control via `/sys/class/leds/` (sysfs)

**STM32U585 MCU (Microcontroller Unit)**:
- **Processor**: STM32U585 ARM Cortex-M33
- **Responsibilities**:
  - Real-time LED matrix control (8x13 pixels)
  - RGB LEDs 3 & 4 control
  - Hardware-level I/O operations
  - Native ArduinoGraphics text rendering
  - Low-latency hardware control

**Router Bridge**:
- **Purpose**: Inter-processor communication
- **Mechanism**: Allows Python code on Linux to call C++ functions on MCU
- **Usage**: Arduino App framework provides `Bridge.call()` API
- **Example**: `Bridge.call("draw", frame_data)` sends frame to MCU

**Communication Flow**:
1. FastAPI app emits domain events (e.g., `SystemEvent.TRADE_EXECUTED`)
2. LED display service (`led_display.py`) updates display state
3. Python bridge (`arduino-app/python/main.py`) polls `/api/status/led/display` every 30 seconds
4. Python bridge calls MCU functions via Router Bridge:
   - `Bridge.call("draw", frame)` - Update LED matrix
   - `Bridge.call("setRGB3", r, g, b)` - Set RGB LED 3
   - `Bridge.call("scrollText", text, speed)` - Scroll text

### Clean Architecture Pattern

The project follows **Clean Architecture** principles with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────┐
│                    API Layer (FastAPI)                  │
│  Thin controllers - request/response handling only      │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│            Application Services Layer                    │
│  Orchestration: PortfolioService, RebalancingService,  │
│  ScoringService, TradeExecutionService, etc.           │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│                  Domain Layer                            │
│  Pure business logic - no infrastructure dependencies   │
│  - Models, Value Objects, Services, Events             │
│  - Scoring algorithms, Planning strategies              │
│  - Repository interfaces (protocols)                    │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              Infrastructure Layer                        │
│  - Database (SQLite repositories)                       │
│  - External APIs (Tradernet, Yahoo Finance)             │
│  - Hardware (LED display)                               │
│  - Caching, Rate limiting, Logging                      │
└─────────────────────────────────────────────────────────┘
```

### Key Architectural Principles

1. **Domain Layer Independence**: Pure business logic with no infrastructure dependencies
2. **Repository Pattern**: Interfaces in domain, implementations in infrastructure
3. **Dependency Injection**: FastAPI dependencies for testability
4. **Event-Driven**: Domain events for decoupled communication
5. **Caching Strategy**: Tiered caching (slow-changing scores cached longer)

---

## Project Structure

### Core Directories

```
arduino-trader/
├── app/
│   ├── domain/              # Pure business logic
│   │   ├── models.py        # Domain entities (Stock, Position, Trade, etc.)
│   │   ├── value_objects/   # Currency, TradeSide, RecommendationStatus
│   │   ├── scoring/         # 8-group scoring system
│   │   ├── planning/        # Rebalancing strategies
│   │   ├── analytics/      # Portfolio analytics
│   │   ├── events/          # Domain events
│   │   ├── services/        # Domain services (SettingsService)
│   │   └── repositories/    # Repository interfaces (protocols)
│   │
│   ├── application/         # Application services (orchestration)
│   │   └── services/       # RebalancingService, PortfolioService, etc.
│   │
│   ├── infrastructure/     # External concerns
│   │   ├── database/       # SQLite repositories, schemas
│   │   ├── hardware/       # LED display controller
│   │   ├── cache.py        # Caching layer
│   │   └── events.py       # Event bus implementation
│   │
│   ├── api/                # FastAPI routes (thin controllers)
│   │   ├── portfolio.py
│   │   ├── stocks.py
│   │   ├── trades.py
│   │   ├── allocation.py
│   │   ├── cash_flows.py
│   │   ├── charts.py
│   │   ├── settings.py
│   │   └── status.py
│   │
│   ├── services/           # Legacy services (backward compatibility)
│   │   ├── allocator.py   # Position sizing, priority calculation
│   │   ├── tradernet.py   # Tradernet API client
│   │   └── yahoo.py       # Yahoo Finance integration
│   │
│   ├── repositories/      # Repository implementations
│   │   ├── stock.py
│   │   ├── position.py
│   │   ├── trade.py
│   │   ├── portfolio.py
│   │   └── ...
│   │
│   ├── jobs/              # Background jobs (APScheduler)
│   │   ├── scheduler.py
│   │   ├── daily_sync.py
│   │   ├── cash_rebalance.py
│   │   ├── score_refresh.py
│   │   └── ...
│   │
│   ├── main.py            # FastAPI application entry point
│   └── config.py          # Configuration (Pydantic Settings)
│
├── arduino-app/           # Arduino Uno Q LED display app (dual-brain)
│   ├── sketch/sketch.ino  # C++ sketch for STM32U585 MCU (hardware control)
│   └── python/main.py    # Python bridge (runs on Linux MPU, communicates via Router Bridge)
│
├── static/                # Frontend (Alpine.js + Tailwind CSS)
│   ├── index.html
│   ├── components/        # Web components
│   └── js/               # JavaScript modules
│
├── tests/                 # Test suite
│   ├── unit/             # Unit tests (domain logic)
│   └── integration/      # Integration tests (repositories, APIs)
│
└── scripts/               # Utility scripts
    ├── seed_stocks.py
    ├── migrate_*.py
    └── ...
```

---

## Database Architecture

### Multi-Database Design

The system uses **4 separate SQLite databases** for separation of concerns:

1. **`config.db`** - Master data (rarely changes)
   - Stock universe
   - Allocation targets (geography/industry)
   - Application settings
   - Recommendations (with UUIDs for dismissal tracking)

2. **`ledger.db`** - Append-only transaction log
   - Trades (executed orders)
   - Cash flows (deposits, withdrawals, dividends)

3. **`state.db`** - Current state (frequently updated)
   - Positions (current holdings)
   - Stock scores (calculated scores)
   - Portfolio snapshots (daily summaries)

4. **`cache.db`** - Computed aggregates
   - Cached calculations
   - Performance metrics

5. **`history/{symbol}.db`** - Per-symbol price data
   - Daily OHLC prices
   - Monthly aggregated prices (for CAGR calculations)

### Key Database Features

- **WAL mode** for better concurrency
- **Schema versioning** with migration support
- **Portfolio hash** for recommendation deduplication
- **Data retention policies** (configurable retention periods)

---

## Stock Scoring System

### 8-Group Scoring Structure

The scoring system combines 8 scoring groups with configurable weights:

| Group | Weight (Default) | Cache TTL | Description |
|-------|------------------|-----------|-------------|
| **Long-term Performance** | 20% | 7 days | CAGR, Sortino, Sharpe ratios |
| **Fundamentals** | 15% | 7 days | Financial strength, consistency |
| **Opportunity** | 15% | 4 hours | 52W high distance, P/E ratio |
| **Dividends** | 12% | 7 days | Yield, dividend consistency |
| **Short-term Performance** | 10% | 4 hours | Recent momentum, drawdown |
| **Technicals** | 10% | 4 hours | RSI, Bollinger Bands, EMA |
| **Opinion** | 10% | 24 hours | Analyst recommendations, price targets |
| **Diversification** | 8% | Never | Geography, industry, averaging down |

### Scoring Components

**Long-term Performance** (`long_term.py`):
- CAGR (Compound Annual Growth Rate)
- Sortino ratio (downside risk-adjusted returns)
- Sharpe ratio (risk-adjusted returns)

**Fundamentals** (`fundamentals.py`):
- Financial strength metrics
- Revenue/earnings consistency
- Profitability margins

**Opportunity** (`opportunity.py`):
- Distance from 52-week high (buying opportunity)
- P/E ratio vs market average

**Dividends** (`dividends.py`):
- Dividend yield
- Dividend consistency over time

**Short-term Performance** (`short_term.py`):
- Recent momentum (30-day returns)
- Current drawdown severity

**Technicals** (`technicals.py`):
- RSI (Relative Strength Index)
- Bollinger Bands position
- EMA (Exponential Moving Average) trends

**Opinion** (`opinion.py`):
- Analyst consensus (Buy/Hold/Sell)
- Price target upside potential

**Diversification** (`diversification.py`):
- Geographic allocation fit
- Industry allocation fit
- Averaging down opportunities

### Sell Scoring (5 Groups)

Separate scoring system for sell recommendations:

| Group | Weight | Description |
|-------|--------|-------------|
| **Underperformance** | 35% | Return vs target |
| **Time Held** | 18% | Position age |
| **Portfolio Balance** | 18% | Overweight detection |
| **Instability** | 14% | Bubble/volatility signals |
| **Drawdown** | 15% | Current drawdown severity |

---

## Rebalancing Algorithm

### Cash-Based Rebalancing

The system uses a **"drip execution"** strategy:

1. **Check cash balance** every 15 minutes (configurable)
2. **Execute ONE trade per cycle** (max 5 trades per cycle)
3. **Priority: SELL before BUY**
4. **Fresh data sync** before each decision

### Rebalancing Process

```python
1. Sync trades from Tradernet (for cooldown calculations)
2. Sync portfolio (fresh positions and prices)
3. Build portfolio context (allocations, positions, scores)
4. Calculate recommendations:
   a. Sell recommendations (if any positions need rebalancing)
   b. Buy recommendations (if cash available)
5. Execute ONE trade (highest priority)
6. Wait for next cycle (15 minutes)
```

### Position Sizing

Position sizes are calculated using multiple factors:

- **Base size**: Calculated from transaction costs (€2 fixed + 0.2% variable → ~€250 minimum)
- **Conviction multiplier**: Based on stock score (0.8x - 1.2x)
- **Priority multiplier**: Based on combined priority (0.8x - 1.0x)
- **Volatility penalty**: Reduces size for high volatility
- **Risk-adjusted multiplier**: Based on Sortino ratio

### Allocation Targets

**Geographic Allocation:**
- EU: 50%
- Asia: 30%
- US: 20%

**Industry Allocation:**
- Technology: 20%
- Healthcare: 20%
- Finance: 20%
- Consumer: 20%
- Industrial: 20%

### Performance-Adjusted Weights

The system can adjust allocation weights based on historical performance:
- Uses PyFolio for performance attribution
- Analyzes last 365 days of returns
- Slightly increases targets for outperforming regions/industries
- Cached for 48 hours (expensive calculation)

---

## Background Jobs (APScheduler)

### Scheduled Jobs

| Job | Interval | Description |
|-----|----------|-------------|
| **Portfolio Sync** | 15 min | Sync positions from Tradernet |
| **Trade Sync** | 5 min | Sync executed trades |
| **Price Sync** | 5 min | Fetch prices from Yahoo Finance |
| **Score Refresh** | 30 min | Recalculate all stock scores |
| **Rebalance Check** | 15 min | Check cash and execute trades |
| **Cash Flow Sync** | Daily (18:00) | Sync cash flows from Tradernet |
| **Historical Data Sync** | Daily (22:00) | Sync historical price data |
| **Daily Maintenance** | Daily (03:00) | Backup, cleanup, WAL checkpoint |
| **Weekly Maintenance** | Sunday (04:00) | Extended maintenance tasks |
| **Health Check** | Hourly | Database health monitoring |

### Job Failure Tracking

- Tracks consecutive failures per job
- Alerts after 5 failures in 1 hour (configurable)
- Logs warnings for individual failures

---

## API Endpoints

### Portfolio
- `GET /api/portfolio` - Current positions
- `GET /api/portfolio/summary` - Total value and allocations

### Stocks
- `GET /api/stocks` - Stock universe with scores
- `POST /api/stocks/refresh-all` - Recalculate all scores
- `POST /api/stocks/{symbol}/refresh` - Refresh single stock

### Trades
- `GET /api/trades` - Trade history
- `GET /api/trades/allocation` - Current vs target allocation
- `POST /api/trades/rebalance/preview` - Preview rebalance trades
- `POST /api/trades/rebalance/execute` - Execute rebalance

### Allocation
- `GET /api/allocation` - Geographic and industry allocations
- `GET /api/allocation/targets` - Allocation targets
- `PUT /api/allocation/targets` - Update targets

### Cash Flows
- `GET /api/cash-flows` - Cash flow history
- `POST /api/cash-flows/sync` - Manual sync

### Charts
- `GET /api/charts/portfolio` - Portfolio value over time
- `GET /api/charts/returns` - Portfolio returns

### Settings
- `GET /api/settings` - All settings
- `PUT /api/settings` - Update settings
- `GET /api/settings/jobs` - Job interval settings

### Status
- `GET /api/status` - System health
- `GET /api/status/tradernet` - Tradernet connection
- `GET /api/status/led` - LED display state
- `POST /api/status/sync/prices` - Manual price sync

---

## External Integrations

### Tradernet API (Freedom24)

**Purpose**: Broker integration for trading and portfolio data

**Operations**:
- Get portfolio positions
- Get executed trades
- Get cash balance
- Execute buy/sell orders
- Get cash flows
- Get exchange rates

**Client**: `app/services/tradernet.py`
- Uses `tradernet-sdk` package
- Connection management with retry logic
- Rate limiting (3 req/sec)

### Yahoo Finance

**Purpose**: Stock price data and fundamentals

**Operations**:
- Fetch daily prices (OHLC)
- Fetch historical data
- Get fundamentals (P/E, revenue, etc.)
- Get analyst recommendations

**Client**: `app/services/yahoo.py`
- Uses `yfinance` package
- Caching for performance
- Error handling with retries

---

## LED Display (Arduino Uno Q Dual-Brain)

### Hardware Components

**Linux MPU Controlled (via sysfs)**:
- **LED 1**: User-controlled RGB (GPIO_41, GPIO_42, GPIO_60)
  - Blue pulse on API calls
  - Controlled via `/sys/class/leds/red:user/brightness` etc.
- **LED 2**: System indicators (GPIO_39, GPIO_40, GPIO_47)
  - Cyan flash on web requests
  - Controlled via `/sys/class/leds/red:panic/brightness` etc.

**STM32U585 MCU Controlled (via Router Bridge)**:
- **8x13 LED Matrix**: Portfolio status display
  - Real-time animations (wave, expanding ring)
  - Scrolling text via native ArduinoGraphics
  - Frame-by-frame control
- **RGB LED 3**: Sync indicator (blue during sync operations)
- **RGB LED 4**: Processing indicator (orange during heavy processing)

### Display Modes

| Mode | Description | Hardware |
|------|-------------|----------|
| **Normal** | Scrolling ticker with portfolio info | MCU (Matrix) |
| **Syncing** | Faster horizontal wave animation | MCU (Matrix) |
| **Trading** | Expanding ring celebration (3s) | MCU (Matrix) |
| **Error** | Scrolling error text | MCU (Matrix) |
| **Activity** | Temporary activity messages | MCU (Matrix) |

### Dual-Brain Communication Architecture

```
FastAPI (Linux MPU)
    │
    │ Domain Events
    ▼
LED Display Service (led_display.py)
    │ Updates DisplayState
    ▼
API Endpoint (/api/status/led/display)
    │
    │ HTTP Poll (every 30s)
    ▼
Python Bridge (arduino-app/python/main.py)
    │
    │ Router Bridge API
    ▼
C++ Sketch (arduino-app/sketch/sketch.ino)
    │
    │ Direct Hardware Control
    ▼
LED Matrix & RGB LEDs 3 & 4
```

**Router Bridge Functions** (exposed by C++ sketch):
- `draw(frame_data)` - Send 8x13 frame to LED matrix
- `setRGB3(r, g, b)` - Set RGB LED 3 color
- `setRGB4(r, g, b)` - Set RGB LED 4 color
- `scrollText(text, speed)` - Scroll text using ArduinoGraphics
- `printText(text, x, y)` - Display static text

**Linux MPU LED Control** (Direct sysfs):
- **LED 1**: User-controlled RGB LED
  - Blue pulse during API calls (`pulse_led1_blue()`)
  - Controlled via `/sys/class/leds/red:user/brightness` (GPIO_41)
  - PWM frequency: ~2 kHz
- **LED 2**: System indicator LED (can be overridden)
  - Cyan flash on web requests (`flash_led2_cyan()`)
  - Controlled via `/sys/class/leds/red:panic/brightness` (GPIO_39)
  - Also used for WLAN (green) and Bluetooth (blue) status

**Benefits of Dual-Brain Architecture**:
1. **Separation of Concerns**: Linux handles business logic, MCU handles real-time hardware
2. **Performance**: MCU provides low-latency hardware control without blocking Linux
3. **Reliability**: MCU continues hardware control even if Linux app crashes
4. **Efficiency**: MCU uses minimal power for hardware control
5. **Real-time**: MCU can handle time-sensitive animations without Linux overhead
6. **Flexibility**: Different control methods (sysfs for simple LEDs, Router Bridge for complex matrix)

---

## Frontend (Web Dashboard)

### Technology Stack

- **Alpine.js**: Lightweight JavaScript framework
- **Tailwind CSS**: Utility-first CSS framework
- **Lightweight Charts**: Financial charting library

### Components

- `stock-table.js` - Stock universe with scores
- `portfolio-summary.js` - Portfolio overview
- `allocation-radar.js` - Geographic/industry allocation
- `trades-table.js` - Trade history
- `stock-chart.js` - Individual stock charts
- `sparkline-charts.js` - Mini charts for quick view

### Features

- Real-time portfolio updates
- Interactive charts
- Stock scoring visualization
- Allocation radar charts
- Trade history with filtering
- Settings management

---

## Testing Strategy

### Test Structure

```
tests/
├── unit/              # Unit tests (domain logic)
│   ├── domain/       # Domain models, services, value objects
│   └── services/     # Service layer tests
│
└── integration/      # Integration tests
    ├── test_repositories.py
    ├── test_transactions.py
    ├── test_external_api_failures.py
    └── test_error_recovery.py
```

### Test Coverage

- **Domain logic**: Fully tested (models, scoring, planning)
- **Repositories**: Integration tests with SQLite
- **API endpoints**: Integration tests
- **Error handling**: Failure scenarios tested

---

## Configuration

### Environment Variables

```env
# Tradernet API
TRADERNET_API_KEY=your_api_key
TRADERNET_API_SECRET=your_api_secret

# Investment
MONTHLY_DEPOSIT=1000.0

# Scheduling
DAILY_SYNC_HOUR=18
CASH_CHECK_INTERVAL_MINUTES=15

# Trading
MIN_CASH_THRESHOLD=400.0
MIN_TRADE_SIZE=400.0
MAX_TRADES_PER_CYCLE=5
MIN_STOCK_SCORE=0.5

# Rate Limiting
RATE_LIMIT_MAX_REQUESTS=60
RATE_LIMIT_WINDOW_SECONDS=60
```

### Database Settings

Settings stored in `config.db` (key-value store):
- Job intervals (configurable per job)
- Trading thresholds
- Scoring weights
- Allocation targets

---

## Key Design Patterns

### 1. Repository Pattern
- **Interfaces**: `app/domain/repositories/protocols.py`
- **Implementations**: `app/repositories/*.py`
- **Benefits**: Easy to swap implementations, testable

### 2. Domain Events
- **Events**: `app/domain/events/*.py`
- **Bus**: `app/infrastructure/events.py`
- **Usage**: Decoupled communication (LED display, logging)

### 3. Factory Pattern
- **Factories**: `app/domain/factories/*.py`
- **Purpose**: Create domain objects with validation

### 4. Strategy Pattern
- **Strategies**: `app/domain/planning/strategies/*.py`
- **Purpose**: Different rebalancing strategies

### 5. Caching Strategy
- **Tiered caching**: Different TTLs for different data types
- **Score cache**: `app/domain/scoring/cache.py`
- **Recommendation cache**: `app/infrastructure/recommendation_cache.py`

---

## Performance Optimizations

### Caching

1. **Score Cache**: Tiered TTLs (4h - 7 days based on volatility)
2. **Recommendation Cache**: 48h TTL for expensive calculations
3. **API Response Cache**: Short TTL for external API calls

### Database Optimizations

- **WAL mode**: Better concurrency
- **Indexes**: On frequently queried columns
- **Data retention**: Automatic cleanup of old data
- **Connection pooling**: Reused database connections

### Rate Limiting

- **External APIs**: 3 req/sec (configurable delay)
- **Internal API**: 60 req/min (configurable)
- **Trade execution**: 10 req/min (stricter)

---

## Security Considerations

### API Security

- **Rate limiting**: Prevents abuse
- **Correlation IDs**: Request tracking
- **Input validation**: Pydantic models

### Data Security

- **Environment variables**: Sensitive data in `.env`
- **SQL injection**: Parameterized queries
- **File locking**: Prevents concurrent job execution

### Remote Access

- **Cloudflare Tunnel**: Secure remote access
- **No exposed ports**: All traffic through tunnel

---

## Deployment

### Arduino Uno Q Setup

1. **Systemd Service**: `deploy/arduino-trader.service`
2. **Setup Script**: `deploy/setup.sh`
3. **Cloudflare Tunnel**: `deploy/cloudflared-setup.sh`

### Service Management

```bash
sudo systemctl status arduino-trader
sudo journalctl -u arduino-trader -f
sudo systemctl restart arduino-trader
```

### LED Display App

```bash
arduino-app-cli app start user:trader-display
arduino-app-cli app logs user:trader-display
```

---

## Known Limitations & Future Improvements

### Current Limitations

1. **Single broker**: Only Tradernet/Freedom24 supported
2. **SQLite only**: No PostgreSQL/MySQL support (though architecture supports it)
3. **Limited sell logic**: Sell recommendations are conservative
4. **No backtesting**: Historical strategy testing not implemented

### Potential Improvements

1. **Multi-broker support**: Add more broker integrations
2. **Backtesting framework**: Test strategies on historical data
3. **Machine learning**: ML-based scoring enhancements
4. **Real-time alerts**: Push notifications for important events
5. **Portfolio analytics**: More advanced analytics dashboard

---

## Code Quality

### Standards

- **Python**: PEP 8 style guide
- **Type hints**: Used throughout codebase
- **Docstrings**: Comprehensive documentation
- **Testing**: pytest with good coverage

### Static Analysis

- **Pydantic**: Runtime type validation
- **Type hints**: Static type checking support

---

## Dependencies

### Core Backend

- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `aiosqlite` - Async SQLite
- `apscheduler` - Job scheduling
- `pydantic` - Data validation
- `httpx` - HTTP client

### Financial Libraries

- `yfinance` - Yahoo Finance data
- `pandas` - Data manipulation
- `numpy` - Numerical computing
- `empyrical-reloaded` - Financial metrics
- `pandas-ta` - Technical analysis
- `pyfolio` - Portfolio analytics

### External APIs

- `tradernet-sdk` - Tradernet API client

---

## Conclusion

The **Arduino Trader** codebase demonstrates:

✅ **Clean Architecture** with clear separation of concerns  
✅ **Comprehensive scoring system** with 8 scoring groups  
✅ **Robust rebalancing algorithm** with drip execution  
✅ **Multi-database design** for scalability  
✅ **Well-tested** with unit and integration tests  
✅ **Production-ready** with proper error handling, logging, and monitoring  
✅ **Hardware integration** with Arduino Uno Q LED display  

The codebase is well-structured, maintainable, and follows best practices for a production trading system.

