#!/bin/bash
#
# Arduino Trader - Setup Script for Arduino Uno Q
#
# Run this on the Arduino Uno Q Linux side to set up the trading system.
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
APP_DIR="/home/arduino/arduino-trader"
VENV_DIR="$APP_DIR/venv"
SERVICE_FILE="/etc/systemd/system/arduino-trader.service"

# Step 1: Update system
echo ""
echo "Step 1: Updating system packages..."
apt-get update
apt-get install -y python3 python3-pip python3-venv git

# Step 2: Clone or update repository
echo ""
echo "Step 2: Setting up application..."
if [ -d "$APP_DIR" ]; then
    echo "Updating existing installation..."
    cd "$APP_DIR"
    git pull
else
    echo "Cloning repository..."
    git clone https://github.com/aristath/autoTrader.git "$APP_DIR"
    cd "$APP_DIR"
fi

# Step 3: Create virtual environment
echo ""
echo "Step 3: Setting up Python environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

# Activate venv and install dependencies
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt

# Step 4: Create data directory
echo ""
echo "Step 4: Setting up data directory..."
mkdir -p "$APP_DIR/data"

# Step 5: Copy environment file if not exists
if [ ! -f "$APP_DIR/.env" ]; then
    echo ""
    echo "Step 5: Creating environment file..."
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    echo "IMPORTANT: Edit $APP_DIR/.env with your Tradernet API credentials!"
fi

# Step 6: Initialize database
echo ""
echo "Step 6: Initializing database..."
python3 "$APP_DIR/scripts/seed_stocks.py"

# Step 7: Install systemd service
echo ""
echo "Step 7: Installing systemd service..."
cp "$APP_DIR/deploy/arduino-trader.service" "$SERVICE_FILE"
systemctl daemon-reload
systemctl enable arduino-trader

# Step 8: Start service
echo ""
echo "Step 8: Starting service..."
systemctl start arduino-trader

# Check status
echo ""
echo "====================================="
echo "Setup Complete!"
echo "====================================="
echo ""
echo "Service status:"
systemctl status arduino-trader --no-pager

echo ""
echo "Next steps:"
echo "1. Edit /home/arduino/arduino-trader/.env with your Tradernet API credentials"
echo "2. Restart service: sudo systemctl restart arduino-trader"
echo "3. Access dashboard: http://localhost:8000"
echo "4. Set up Cloudflare Tunnel for remote access (see deploy/cloudflared-setup.sh)"
echo ""
