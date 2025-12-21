#!/bin/bash
#
# Arduino Trader - Setup Script for Arduino Uno Q
#
# Run this on the Arduino Uno Q Linux side to set up the trading system.
# Usage: sudo ./setup.sh
#

set -e

echo "====================================="
echo "Arduino Trader - Setup Script"
echo "====================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./setup.sh)"
    exit 1
fi

# Variables
REPO_DIR="/home/arduino/repos/autoTrader"
APP_DIR="/home/arduino/arduino-trader"
VENV_DIR="$APP_DIR/venv"
BIN_DIR="/home/arduino/bin"
LOG_DIR="/home/arduino/logs"
SERVICE_FILE="/etc/systemd/system/arduino-trader.service"

# Step 1: Update system
echo ""
echo "Step 1: Updating system packages..."
apt-get update
apt-get install -y python3 python3-pip python3-venv git

# Step 2: Create directories
echo ""
echo "Step 2: Creating directories..."
mkdir -p /home/arduino/repos
mkdir -p "$BIN_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$APP_DIR/data"
chown -R arduino:arduino /home/arduino/repos "$BIN_DIR" "$LOG_DIR"

# Step 3: Clone or update repository
echo ""
echo "Step 3: Setting up repository..."
if [ -d "$REPO_DIR" ]; then
    echo "Updating existing repository..."
    cd "$REPO_DIR"
    sudo -u arduino git pull
else
    echo "Cloning repository..."
    sudo -u arduino git clone https://github.com/aristath/autoTrader.git "$REPO_DIR"
fi

# Step 4: Create virtual environment
echo ""
echo "Step 4: Setting up Python environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

# Activate venv and install dependencies
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$REPO_DIR/requirements.txt"

# Step 5: Copy application files
echo ""
echo "Step 5: Copying application files..."
cp -r "$REPO_DIR/app" "$APP_DIR/"
cp -r "$REPO_DIR/static" "$APP_DIR/"
cp -r "$REPO_DIR/scripts" "$APP_DIR/"
cp -r "$REPO_DIR/deploy" "$APP_DIR/"
cp "$REPO_DIR/requirements.txt" "$APP_DIR/"
[ -f "$REPO_DIR/run.py" ] && cp "$REPO_DIR/run.py" "$APP_DIR/"

# Step 6: Copy environment file if not exists
if [ ! -f "$APP_DIR/.env" ]; then
    echo ""
    echo "Step 6: Creating environment file..."
    if [ -f "$REPO_DIR/.env.example" ]; then
        cp "$REPO_DIR/.env.example" "$APP_DIR/.env"
    else
        cat > "$APP_DIR/.env" << 'EOF'
DEBUG=false
APP_NAME=Arduino Trader
TRADERNET_API_KEY=your_api_key_here
TRADERNET_API_SECRET=your_api_secret_here
EOF
    fi
    echo "IMPORTANT: Edit $APP_DIR/.env with your Tradernet API credentials!"
fi

# Step 7: Initialize database
echo ""
echo "Step 7: Initializing database..."
cd "$APP_DIR"
python3 scripts/seed_stocks.py || echo "Database already initialized or script not found"

# Step 8: Install systemd service
echo ""
echo "Step 8: Installing systemd service..."
cp "$REPO_DIR/deploy/arduino-trader.service" "$SERVICE_FILE"
systemctl daemon-reload
systemctl enable arduino-trader

# Step 9: Setup auto-deploy
echo ""
echo "Step 9: Setting up auto-deployment..."
cp "$REPO_DIR/arduino-app/deploy/auto-deploy.sh" "$BIN_DIR/"
chmod +x "$BIN_DIR/auto-deploy.sh"
chown arduino:arduino "$BIN_DIR/auto-deploy.sh"

# Add cron job for arduino user (every 5 minutes)
CRON_JOB="*/5 * * * * $BIN_DIR/auto-deploy.sh"
sudo -u arduino bash -c "(crontab -l 2>/dev/null | grep -v 'auto-deploy.sh'; echo '$CRON_JOB') | crontab -"
echo "Cron job installed: $CRON_JOB"

# Step 10: Start service
echo ""
echo "Step 10: Starting service..."
systemctl start arduino-trader

# Check status
echo ""
echo "====================================="
echo "Main App Setup Complete!"
echo "====================================="
echo ""
echo "Service status:"
systemctl status arduino-trader --no-pager || true

echo ""
echo "Next steps:"
echo "1. Edit /home/arduino/arduino-trader/.env with your Tradernet API credentials"
echo "2. Restart service: sudo systemctl restart arduino-trader"
echo "3. Run: ./arduino-app/deploy/setup.sh (as arduino user, not root)"
echo "4. Access dashboard: http://localhost:8000"
echo ""
