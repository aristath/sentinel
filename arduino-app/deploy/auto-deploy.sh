#!/bin/bash
# Auto-deploy script for Arduino Uno Q trader-display app
# Runs via cron every 5 minutes to check for updates

REPO_DIR="/home/arduino/repos/autoTrader"
APP_DIR="/home/arduino/ArduinoApps/trader-display"
LOG_FILE="/home/arduino/logs/auto-deploy.log"

cd "$REPO_DIR" || exit 1

# Fetch and check for changes
git fetch origin 2>/dev/null
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" != "$REMOTE" ]; then
    echo "$(date): Updating from $LOCAL to $REMOTE" >> "$LOG_FILE"
    git pull origin main >> "$LOG_FILE" 2>&1

    # Sync arduino-app to ArduinoApps
    rsync -av --delete "$REPO_DIR/arduino-app/" "$APP_DIR/" >> "$LOG_FILE" 2>&1

    # Restart the app
    arduino-app-cli app restart user:trader-display >> "$LOG_FILE" 2>&1
    echo "$(date): Deploy complete" >> "$LOG_FILE"
fi
