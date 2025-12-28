# Arduino Trader

Automated portfolio management system for Arduino Uno Q with monthly rebalancing, stock scoring, and LED status display.

## Features

- **Automated Monthly Rebalancing**: Invests monthly deposits according to allocation targets
- **Stock Scoring Engine**: Technical (50%), Analyst (30%), Fundamental (20%) weighted scores
- **Geographic Allocation**: EU 50%, Asia 30%, US 20%
- **Industry Diversification**: Equal weight across 5 sectors
- **Web Dashboard**: Real-time portfolio view with Alpine.js + Tailwind CSS
- **LED Status Display**: At-a-glance portfolio health on Arduino Uno Q's LED matrix
- **Remote Access**: Secure access via Cloudflare Tunnel

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Arduino Uno Q                        │
├─────────────────────────┬───────────────────────────────┤
│      Linux (MPU)        │         MCU (STM32U585)       │
│  ┌─────────────────┐    │    ┌─────────────────────┐    │
│  │   FastAPI App   │    │    │   LED Controller    │    │
│  │   + SQLite DB   │    │    │   8x13 Matrix +     │    │
│  │   + APScheduler │    │    │   4 RGB LEDs        │    │
│  └────────┬────────┘    │    └──────────┬──────────┘    │
│           │             │               │                │
│           │             │               │                │
│  ┌────────▼────────┐    │               │                │
│  │ LED Display     │────┼───────────────┘                │
│  │ (Native Python) │    │  Router Bridge                 │
│  └─────────────────┘    │                               │
│          │              │                               │
│          ▼              │                               │
│  ┌─────────────────┐    │                               │
│  │   Cloudflared   │    │                               │
│  └────────┬────────┘    │                               │
└───────────┼─────────────┴───────────────────────────────┘
            │
            ▼
    ┌───────────────┐
    │   Internet    │
    │ (Your Phone)  │
    └───────────────┘
```

## Tech Stack

- **Backend**: Python 3.10+, FastAPI, SQLite
- **Frontend**: Alpine.js, Tailwind CSS (standalone CLI), Lightweight Charts
- **APIs**: Freedom24/Tradernet, Yahoo Finance (yfinance)
- **Scheduling**: APScheduler
- **MCU**: Arduino sketch for STM32U585 (compiled with Arduino CLI)
- **LED Display**: Native Python script (no Docker required)

## Quick Start

### Local Development

```bash
# Clone repository
git clone https://github.com/aristath/autoTrader.git
cd autoTrader

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file and add your API keys
cp .env.example .env
# Edit .env with your Tradernet credentials

# Initialize database
python scripts/seed_stocks.py

# Run development server
uvicorn app.main:app --reload
```

### Arduino Uno Q Deployment

```bash
# SSH into your Arduino Uno Q
ssh root@<arduino-ip>

# Download and run setup script
curl -O https://raw.githubusercontent.com/aristath/autoTrader/main/deploy/setup.sh
chmod +x setup.sh
sudo ./setup.sh

# Edit configuration
nano /home/arduino/arduino-trader/.env

# Restart services
sudo systemctl restart arduino-trader led-display
```

### LED Display Setup

The LED display runs as a native Python script (no Docker required) and communicates with the MCU via Router Bridge (msgpack RPC over Unix socket).

The setup script automatically:
- Installs the LED display systemd service
- Compiles and uploads the Arduino sketch to the MCU
- Starts the LED display service

The display shows:
- **Error messages** (highest priority): "BACKUP FAILED", "ORDER PLACEMENT FAILED", etc.
- **Processing messages** (medium priority): "SYNCING...", "BUY AAPL €500", etc.
- **Next actions** (lowest priority, default): Portfolio value, cash balance, recommendations

**Manual sketch compilation** (if needed):
```bash
/home/arduino/arduino-trader/scripts/compile_and_upload_sketch.sh
```

**Service management**:
```bash
# Check status
sudo systemctl status led-display

# View logs
sudo journalctl -u led-display -f

# Restart
sudo systemctl restart led-display
```

### Cloudflare Tunnel Setup

```bash
# On Arduino Uno Q
curl -O https://raw.githubusercontent.com/aristath/autoTrader/main/deploy/cloudflared-setup.sh
chmod +x cloudflared-setup.sh
sudo ./cloudflared-setup.sh
```

## Configuration

Edit `.env` file:

```env
# Tradernet API (Freedom24)
TRADERNET_API_KEY=your_api_key
TRADERNET_API_SECRET=your_api_secret

# Investment
MONTHLY_DEPOSIT=1000.0

# Scheduling
MONTHLY_REBALANCE_DAY=1
DAILY_SYNC_HOUR=18

# LED Display (optional, uses Arduino App framework)
# LED_ENABLED=true
```

## API Endpoints

### Portfolio
- `GET /api/portfolio` - Current positions with values
- `GET /api/portfolio/summary` - Total value and allocations
- `GET /api/portfolio/history` - Historical portfolio snapshots
- `GET /api/portfolio/transactions` - Portfolio transaction history
- `GET /api/portfolio/cash-breakdown` - Cash balance breakdown
- `GET /api/portfolio/analytics` - Portfolio analytics and metrics

### Stocks
- `GET /api/stocks` - Stock universe with scores and priorities
- `GET /api/stocks/{symbol}` - Get single stock details
- `POST /api/stocks` - Add new stock to universe
- `PUT /api/stocks/{symbol}` - Update stock settings
- `DELETE /api/stocks/{symbol}` - Remove stock from universe
- `POST /api/stocks/refresh-all` - Recalculate all stock scores
- `POST /api/stocks/{symbol}/refresh` - Refresh single stock score
- `POST /api/stocks/{symbol}/refresh-data` - Refresh stock data from APIs

### Trades
- `GET /api/trades` - Trade history
- `POST /api/trades/execute` - Execute manual trade
- `GET /api/trades/allocation` - Current vs target allocation

### Recommendations
- `GET /api/trades/recommendations` - Get trading recommendations (holistic planner)
- `POST /api/trades/recommendations/execute` - Execute recommendation sequence

### Allocation
- `GET /api/allocation/targets` - Get allocation targets (country/industry)
- `PUT /api/allocation/targets/country` - Update country allocation weights
- `PUT /api/allocation/targets/industry` - Update industry allocation weights
- `GET /api/allocation/current` - Current allocation vs targets
- `GET /api/allocation/deviations` - Allocation deviation scores

### Cash Flows
- `GET /api/cash-flows` - Cash flow transactions (with filters)
- `GET /api/cash-flows/sync` - Sync cash flows from Tradernet
- `GET /api/cash-flows/summary` - Cash flow summary statistics

### Charts
- `GET /api/charts/sparklines` - Stock price sparklines
- `GET /api/charts/stocks/{symbol}` - Historical price chart data

### Optimizer
- `GET /api/optimizer` - Portfolio optimizer status and last results
- `POST /api/optimizer/run` - Run portfolio optimization

### Settings
- `GET /api/settings` - Get all settings
- `PUT /api/settings/{key}` - Update a setting value
- `GET /api/settings/trading-mode` - Get trading mode (live/research)
- `POST /api/settings/trading-mode` - Set trading mode
- `POST /api/settings/restart-service` - Restart main service
- `POST /api/settings/restart` - Restart application
- `POST /api/settings/reset-cache` - Clear all caches
- `GET /api/settings/cache-stats` - Cache statistics
- `POST /api/settings/reschedule-jobs` - Reschedule background jobs

### Status
- `GET /api/status` - System health and status
- `GET /api/status/display/text` - LED display text (for native script)
- `GET /api/status/led/display/stream` - LED display state SSE stream (for Arduino App)
- `GET /api/status/tradernet` - Tradernet connection status
- `GET /api/status/jobs` - Background job health monitoring
- `GET /api/status/database/stats` - Database statistics
- `GET /api/status/markets` - Market hours and status
- `GET /api/status/disk` - Disk usage information
- `POST /api/status/sync/portfolio` - Manual portfolio sync
- `POST /api/status/sync/prices` - Manual price sync
- `POST /api/status/sync/historical` - Sync historical data
- `POST /api/status/sync/daily-pipeline` - Run daily sync pipeline
- `POST /api/status/sync/recommendations` - Refresh recommendations
- `POST /api/status/maintenance/daily` - Run daily maintenance tasks

## Stock Universe

25 diversified stocks across 3 regions and 5 industries:

| Region | Stocks |
|--------|--------|
| EU (50%) | ASML, SAP, LVMH, Novo Nordisk, Siemens, BNP, Airbus, Sanofi |
| Asia (30%) | SoftBank, NTT, Toyota, Sony, Samsung, Alibaba, ICBC, WuXi |
| US (20%) | Apple, Microsoft, J&J, JPMorgan, Caterpillar, P&G, UnitedHealth, Visa, Home Depot |

## Scoring Algorithm

### Technical Score (50%)
- **Trend (40%)**: Price vs 50/200-day moving averages
- **Momentum (35%)**: 14/30-day rate of change
- **Volatility (25%)**: Lower volatility = higher score

### Analyst Score (30%)
- **Recommendations (60%)**: Buy/Hold/Sell consensus
- **Price Target (40%)**: Upside potential

### Fundamental Score (20%)
- **Valuation (40%)**: P/E ratio
- **Growth (35%)**: Revenue/earnings growth
- **Profitability (25%)**: Margins

## LED Display Modes

| Mode | Description |
|------|-------------|
| Idle | Subtle wave animation |
| Health | Geographic allocation bars |
| Trading | Flash animation during trades |
| Error | Blinking X pattern |

### RGB LEDs
- **LED 1**: System status (green=OK, blue=syncing, red=error)
- **LEDs 2-4**: EU/Asia/US allocation indicators

## Service Management

```bash
# View status
sudo systemctl status arduino-trader
sudo systemctl status led-display

# View logs
sudo journalctl -u arduino-trader -f
sudo journalctl -u led-display -f

# Restart
sudo systemctl restart arduino-trader
sudo systemctl restart led-display

# Stop
sudo systemctl stop arduino-trader
sudo systemctl stop led-display
```

## License

MIT
