#!/bin/bash
# Initial setup script for Arduino Uno Q trader-display app
# Run this once on a new board to set up auto-deployment

set -e

REPO_URL="https://github.com/aristath/autoTrader.git"
REPO_DIR="/home/arduino/repos/autoTrader"
APP_DIR="/home/arduino/ArduinoApps/trader-display"

echo "=== Arduino Trader Display Setup ==="

# Create directories
echo "Creating directories..."
mkdir -p /home/arduino/repos
mkdir -p /home/arduino/bin
mkdir -p /home/arduino/logs
mkdir -p "$APP_DIR"

# Clone repo if not exists
if [ -d "$REPO_DIR/.git" ]; then
    echo "Repo already exists, pulling latest..."
    cd "$REPO_DIR"
    git pull origin main
else
    echo "Cloning repository..."
    cd /home/arduino/repos
    git clone "$REPO_URL"
fi

# Copy deploy script
echo "Installing deploy script..."
cp "$REPO_DIR/arduino-app/deploy/auto-deploy.sh" /home/arduino/bin/
chmod +x /home/arduino/bin/auto-deploy.sh

# Initial sync
echo "Syncing app files..."
rsync -av --delete "$REPO_DIR/arduino-app/" "$APP_DIR/"

# Set up cron job (if not already set)
if ! crontab -l 2>/dev/null | grep -q "auto-deploy.sh"; then
    echo "Setting up cron job..."
    (crontab -l 2>/dev/null; echo "*/5 * * * * /home/arduino/bin/auto-deploy.sh") | crontab -
else
    echo "Cron job already exists"
fi

# Start the app
echo "Starting trader-display app..."
arduino-app-cli app restart user:trader-display

echo ""
echo "=== Setup Complete ==="
echo "The app will auto-update every 5 minutes from GitHub."
echo "Logs: /home/arduino/logs/auto-deploy.log"
