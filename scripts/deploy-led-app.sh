#!/bin/bash
# Deploy sentinel-led Arduino App to Arduino UNO Q
#
# Usage: ./scripts/deploy-led-app.sh [host] [user] [password]
#
# Defaults:
#   host: 192.168.1.11
#   user: arduino
#   password: aristath

set -e

HOST="${1:-192.168.1.11}"
USER="${2:-arduino}"
PASS="${3:-aristath}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
APP_DIR="$PROJECT_DIR/arduino-app/sentinel-led"
REMOTE_APP_DIR="/home/$USER/ArduinoApps/sentinel-led"

echo "=== Sentinel LED App Deployment ==="
echo "Target: $USER@$HOST"
echo "Source: $APP_DIR"
echo ""

# Check if sshpass is available
if ! command -v sshpass &> /dev/null; then
    echo "Error: sshpass is required. Install with: brew install sshpass"
    exit 1
fi

# Helper functions for SSH/SCP with sshpass (using env var for reliability)
export SSHPASS="$PASS"

run_ssh() {
    sshpass -e ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password "$USER@$HOST" "$@"
}

run_scp() {
    sshpass -e scp -o StrictHostKeyChecking=no -o PreferredAuthentications=password "$@"
}

echo "1. Stopping existing app if running..."
run_ssh "arduino-app-cli app stop sentinel-led 2>/dev/null || true"

echo "2. Creating remote directory..."
run_ssh "mkdir -p $REMOTE_APP_DIR/python $REMOTE_APP_DIR/sketch"

echo "3. Syncing app files..."
run_scp "$APP_DIR/app.yaml" "$USER@$HOST:$REMOTE_APP_DIR/"
run_scp "$APP_DIR/python/main.py" "$USER@$HOST:$REMOTE_APP_DIR/python/"
run_scp "$APP_DIR/sketch/sketch.ino" "$USER@$HOST:$REMOTE_APP_DIR/sketch/"
run_scp "$APP_DIR/sketch/sketch.yaml" "$USER@$HOST:$REMOTE_APP_DIR/sketch/"

echo "4. Setting environment variable for sentinel API..."
# The sentinel service runs on the same device
run_ssh "grep -q SENTINEL_API_URL ~/.bashrc || echo 'export SENTINEL_API_URL=http://localhost:8000' >> ~/.bashrc"

echo "5. Starting app..."
run_ssh "cd $REMOTE_APP_DIR && arduino-app-cli app start ."

echo ""
echo "=== Deployment complete ==="
echo ""
echo "To check logs:  ssh $USER@$HOST 'arduino-app-cli app logs sentinel-led'"
echo "To stop app:    ssh $USER@$HOST 'arduino-app-cli app stop sentinel-led'"
echo "To restart:     ssh $USER@$HOST 'arduino-app-cli app restart sentinel-led'"
