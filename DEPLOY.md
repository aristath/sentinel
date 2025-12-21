# Arduino Trader - Deployment Guide

Complete setup instructions for deploying Arduino Trader on an Arduino Uno Q board.

## Prerequisites

- Arduino Uno Q board with Linux environment
- SSH access to the board
- GitHub repository access (https://github.com/aristath/autoTrader)
- Tradernet API credentials

## Directory Structure

After setup, the board will have:

```
/home/arduino/
├── repos/autoTrader/          # Git repository (source of truth)
├── arduino-trader/            # Main FastAPI application
│   ├── app/                   # Python application code
│   ├── static/                # Web dashboard
│   ├── data/                  # SQLite database
│   ├── venv/                  # Python virtual environment
│   └── .env                   # Configuration (API keys)
├── ArduinoApps/trader-display/ # Arduino LED display app
│   ├── python/main.py         # Display logic
│   ├── sketch/sketch.ino      # MCU firmware
│   └── app.yaml               # App configuration
├── bin/
│   └── auto-deploy.sh         # Auto-deployment script
└── logs/
    └── auto-deploy.log        # Deployment logs
```

## Quick Setup

SSH into the Arduino and run:

```bash
# Clone repository
cd /home/arduino
mkdir -p repos && cd repos
git clone https://github.com/aristath/autoTrader.git
cd autoTrader

# Run setup scripts
sudo deploy/setup.sh
./arduino-app/deploy/setup.sh
```

## Manual Setup Steps

### 1. Initial System Setup

```bash
# Update system
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv git

# Create directories
mkdir -p /home/arduino/repos
mkdir -p /home/arduino/bin
mkdir -p /home/arduino/logs
```

### 2. Clone Repository

```bash
cd /home/arduino/repos
git clone https://github.com/aristath/autoTrader.git
```

### 3. Setup Main FastAPI Application

```bash
# Create app directory and venv
mkdir -p /home/arduino/arduino-trader
cd /home/arduino/arduino-trader
python3 -m venv venv

# Install dependencies
source venv/bin/activate
pip install -r /home/arduino/repos/autoTrader/requirements.txt

# Copy application files
cp -r /home/arduino/repos/autoTrader/app .
cp -r /home/arduino/repos/autoTrader/static .
cp -r /home/arduino/repos/autoTrader/scripts .
mkdir -p data

# Create .env file
cat > .env << 'EOF'
DEBUG=false
APP_NAME=Arduino Trader
TRADERNET_API_KEY=your_api_key_here
TRADERNET_API_SECRET=your_api_secret_here
EOF

# Initialize database
python scripts/seed_stocks.py
```

### 4. Install Systemd Service

```bash
sudo cp /home/arduino/repos/autoTrader/deploy/arduino-trader.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable arduino-trader
sudo systemctl start arduino-trader
```

The service file (`/etc/systemd/system/arduino-trader.service`):

```ini
[Unit]
Description=Arduino Trader - Automated Portfolio Management
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/arduino/arduino-trader
Environment=PATH=/home/arduino/arduino-trader/venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/home/arduino/arduino-trader/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=arduino-trader
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

### 5. Setup Arduino LED Display App

```bash
# Copy app to ArduinoApps
cp -r /home/arduino/repos/autoTrader/arduino-app /home/arduino/ArduinoApps/trader-display

# Set as default app (auto-starts on boot)
arduino-app-cli properties set default user:trader-display

# Start the app
arduino-app-cli app start user:trader-display
```

### 6. Setup Auto-Deployment

The auto-deploy script checks GitHub every 5 minutes and deploys changes automatically.

```bash
# Copy deploy script
cp /home/arduino/repos/autoTrader/arduino-app/deploy/auto-deploy.sh /home/arduino/bin/
chmod +x /home/arduino/bin/auto-deploy.sh

# Add cron job
(crontab -l 2>/dev/null; echo "*/5 * * * * /home/arduino/bin/auto-deploy.sh") | crontab -
```

### 7. (Optional) Setup Cloudflare Tunnel

For remote access without exposing ports:

```bash
# Install cloudflared
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
sudo dpkg -i cloudflared.deb

# Login and create tunnel (follow prompts)
cloudflared tunnel login
cloudflared tunnel create arduino-trader

# Configure tunnel
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml << 'EOF'
tunnel: <tunnel-id>
credentials-file: /home/arduino/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: portfolio.yourdomain.com
    service: http://localhost:8000
  - service: http_status:404
EOF

# Run as service
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

## Verification

After setup, verify everything is working:

```bash
# Check main service
sudo systemctl status arduino-trader

# Check Arduino app
arduino-app-cli app list

# Check cron job
crontab -l

# Check web dashboard
curl http://localhost:8000/health

# View logs
journalctl -u arduino-trader -f
tail -f /home/arduino/logs/auto-deploy.log
```

## Services on Boot

Both services are configured to start automatically:

| Service | Auto-start | Command |
|---------|------------|---------|
| arduino-trader | systemd enabled | `sudo systemctl enable arduino-trader` |
| trader-display | default app | `arduino-app-cli properties set default user:trader-display` |
| auto-deploy | cron job | Runs every 5 minutes |

## Troubleshooting

### Main app not starting
```bash
sudo systemctl status arduino-trader
journalctl -u arduino-trader -n 50
```

### LED display not working
```bash
arduino-app-cli app logs user:trader-display
arduino-app-cli app restart user:trader-display
```

### Auto-deploy not running
```bash
# Check cron
crontab -l
# Check logs
tail -50 /home/arduino/logs/auto-deploy.log
# Run manually
/home/arduino/bin/auto-deploy.sh
```

### Reset everything
```bash
sudo systemctl stop arduino-trader
arduino-app-cli app stop user:trader-display
rm -rf /home/arduino/arduino-trader
rm -rf /home/arduino/ArduinoApps/trader-display
# Then run setup again
```

## LED Display Features

The 8x13 LED matrix shows:

- **Rows 0-4**: Portfolio value in thousands (big digits)
- **Column 12**: Progress bar for remainder (each pixel = 200 EUR)
- **Row 7, Col 0**: Heartbeat pulse (sine wave animation)
- **Rows 6-7, Cols 3-5**: API call indicator (pulses during sync)
- **Rows 6-7, Cols 11-12**: Web request indicator

### Night Mode
Display automatically dims to 30% between 11pm-7am for LED longevity.

## Sync Intervals

| Task | Interval |
|------|----------|
| Tradernet portfolio sync | Every 2 minutes |
| Yahoo price sync | Every 7 minutes |
| Cash rebalance check | Every 15 minutes |
| LED heartbeat | Every 20 seconds |
| WiFi check | Every 30 seconds |
| Auto-deploy check | Every 5 minutes |
