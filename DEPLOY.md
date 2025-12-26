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
├── scripts/
│   ├── led_display_native.py  # Native LED display script
│   └── compile_and_upload_sketch.sh  # Sketch compilation script
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

# Run setup script (installs both main app and LED display)
sudo deploy/setup.sh
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

### 5. Setup LED Display Service

The setup script automatically installs the LED display service. Manual setup:

```bash
# Install LED display service
sudo cp /home/arduino/repos/autoTrader/deploy/led-display.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable led-display

# Install Arduino CLI (if not already installed)
curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh

# Compile and upload sketch
chmod +x /home/arduino/repos/autoTrader/scripts/compile_and_upload_sketch.sh
/home/arduino/repos/autoTrader/scripts/compile_and_upload_sketch.sh

# Start LED display service
sudo systemctl start led-display
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

### 7. Configure Sudo Permissions for Auto-Deploy

The auto-deploy script needs passwordless sudo access to restart the `arduino-trader` service. Without this, deployments will pull the code but the service won't restart, leaving old code running.

```bash
# Create sudoers file for arduino-trader service commands
sudo tee /etc/sudoers.d/arduino-trader << 'EOF'
arduino ALL=(ALL) NOPASSWD: /usr/bin/systemctl start arduino-trader
arduino ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop arduino-trader
arduino ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart arduino-trader
arduino ALL=(ALL) NOPASSWD: /usr/bin/systemctl is-active arduino-trader
arduino ALL=(ALL) NOPASSWD: /usr/bin/systemctl status arduino-trader
EOF

# Set correct permissions
sudo chmod 440 /etc/sudoers.d/arduino-trader

# Verify the file is valid
sudo visudo -c
```

> **Important:** Without this configuration, the auto-deploy script cannot restart the service after pulling updates, and changes won't take effect until manual restart.

### 8. (Optional) Setup Cloudflare Tunnel

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
| led-display | systemd enabled | `sudo systemctl enable led-display` |
| auto-deploy | cron job | Runs every 5 minutes |

## Troubleshooting

### Main app not starting
```bash
sudo systemctl status arduino-trader
journalctl -u arduino-trader -n 50
```

### LED display not working
```bash
# Check service status
sudo systemctl status led-display

# View logs
sudo journalctl -u led-display -f

# Check serial port
ls -l /dev/ttyACM0

# Restart service
sudo systemctl restart led-display

# Recompile and upload sketch if needed
/home/arduino/arduino-trader/scripts/compile_and_upload_sketch.sh
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
sudo systemctl stop arduino-trader led-display
rm -rf /home/arduino/arduino-trader
# Then run setup again
sudo /home/arduino/repos/autoTrader/deploy/setup.sh
```

## LED Display Features

The 8x13 LED matrix displays scrolling text with 3-pool priority system:

1. **Error Pool** (highest priority): Error messages like "BACKUP FAILED", "ORDER PLACEMENT FAILED"
2. **Processing Pool** (medium priority): Activity messages like "SYNCING...", "BUY AAPL €500"
3. **Next Actions Pool** (lowest priority, default): Portfolio value, cash balance, recommendations

The display automatically shows the highest priority non-empty text. Text scrolls horizontally across the matrix.

### Sketch Compilation

When the sketch (`.ino` file) changes, the auto-deploy script automatically:
1. Stops the LED display service
2. Compiles the sketch using Arduino CLI
3. Uploads to the MCU via serial port
4. Restarts the LED display service

Manual compilation:
```bash
/home/arduino/arduino-trader/scripts/compile_and_upload_sketch.sh
```

## Sync Intervals

| Task | Interval |
|------|----------|
| Tradernet portfolio sync | Every 2 minutes |
| Yahoo price sync | Every 7 minutes |
| Cash rebalance check | Every 15 minutes |
| LED heartbeat | Every 20 seconds |
| WiFi check | Every 30 seconds |
| Auto-deploy check | Every 5 minutes |
