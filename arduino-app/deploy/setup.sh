#!/bin/bash
# Arduino LED Display Setup Script
# Run this as the arduino user (not root) after running deploy/setup.sh
# Usage: ./arduino-app/deploy/setup.sh

set -e

REPO_URL="https://github.com/aristath/autoTrader.git"
REPO_DIR="/home/arduino/repos/autoTrader"
APP_DIR="/home/arduino/ArduinoApps/trader-display"

echo "=== Arduino Trader LED Display Setup ==="

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

# Sync app files (using cp since rsync may not be available)
echo "Syncing app files..."
rm -rf "$APP_DIR"/* 2>/dev/null || true
cp -r "$REPO_DIR/arduino-app/"* "$APP_DIR/"

# Set up cron job (if not already set)
if ! crontab -l 2>/dev/null | grep -q "auto-deploy.sh"; then
    echo "Setting up cron job..."
    (crontab -l 2>/dev/null; echo "*/5 * * * * /home/arduino/bin/auto-deploy.sh") | crontab -
else
    echo "Cron job already exists"
fi

# Set as default app (auto-starts on boot)
echo "Setting as default app for auto-start..."
arduino-app-cli properties set default user:trader-display

# Start the app
echo "Starting trader-display app..."
arduino-app-cli app restart user:trader-display || arduino-app-cli app start user:trader-display

echo ""
echo "=== Setup Complete ==="
echo ""
echo "LED Display Status:"
arduino-app-cli app list | grep trader
echo ""
echo "The app will:"
echo "  - Auto-start on boot (set as default)"
echo "  - Auto-update every 5 minutes from GitHub"
echo ""
echo "Logs: /home/arduino/logs/auto-deploy.log"
echo "App logs: arduino-app-cli app logs user:trader-display"
echo ""
