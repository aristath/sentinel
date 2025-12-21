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
│  │   FastAPI App   │────┼────│   LED Controller    │    │
│  │   + SQLite DB   │    │    │   8x13 Matrix +     │    │
│  │   + APScheduler │    │    │   4 RGB LEDs        │    │
│  └─────────────────┘    │    └─────────────────────┘    │
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
- **Frontend**: Alpine.js, Tailwind CSS, Chart.js (CDN)
- **APIs**: Freedom24/Tradernet, Yahoo Finance (yfinance)
- **Scheduling**: APScheduler
- **MCU**: Arduino sketch for STM32U585

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

# Restart service
sudo systemctl restart arduino-trader
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

# LED Display
LED_SERIAL_PORT=/dev/ttyACM0
```

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

### Status
- `GET /api/status` - System health
- `GET /api/status/tradernet` - Tradernet connection
- `GET /api/status/led` - LED display state
- `POST /api/status/sync/prices` - Manual price sync

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

# View logs
sudo journalctl -u arduino-trader -f

# Restart
sudo systemctl restart arduino-trader

# Stop
sudo systemctl stop arduino-trader
```

## License

MIT
