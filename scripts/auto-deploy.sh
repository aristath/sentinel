#!/bin/bash
# Auto-deploy script for Sentinel.
# Polls git for new commits on main, pulls, updates deps if needed, restarts.
# Designed to run via systemd timer on the target device.

set -euo pipefail

REPO_DIR="/home/arduino/sentinel"
VENV_DIR="$REPO_DIR/.venv"
LED_APP_SRC="$REPO_DIR/arduino-app/sentinel"
LED_APP_DEST="/home/arduino/ArduinoApps/sentinel"
LOG_DIR="/home/arduino/logs"
LOG_FILE="$LOG_DIR/auto-deploy.log"
MAX_LOG_SIZE=$((10 * 1024 * 1024))
MAX_LOG_FILES=3
BRANCH="main"

# SSH multiplexing to prevent connection exhaustion
# Uses a control socket that auto-closes after 30s idle
SSH_CONTROL_DIR="/tmp/ssh-deploy-$$"
SSH_CONTROL_PATH="$SSH_CONTROL_DIR/control-%r@%h:%p"
export GIT_SSH_COMMAND="ssh -o ControlMaster=auto -o ControlPath=$SSH_CONTROL_PATH -o ControlPersist=30 -o BatchMode=yes"

cleanup_ssh() {
    # Close any open SSH control connections
    if [ -d "$SSH_CONTROL_DIR" ]; then
        for socket in "$SSH_CONTROL_DIR"/control-*; do
            [ -e "$socket" ] && ssh -o ControlPath="$socket" -O exit _ 2>/dev/null || true
        done
        rm -rf "$SSH_CONTROL_DIR"
    fi
}
trap cleanup_ssh EXIT

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG_FILE"
}

rotate_logs() {
    [ ! -f "$LOG_FILE" ] && return
    local size
    size=$(wc -c < "$LOG_FILE")
    [ "$size" -lt "$MAX_LOG_SIZE" ] && return

    [ -f "$LOG_FILE.$MAX_LOG_FILES" ] && rm "$LOG_FILE.$MAX_LOG_FILES"
    for i in $(seq $((MAX_LOG_FILES - 1)) -1 1); do
        [ -f "$LOG_FILE.$i" ] && mv "$LOG_FILE.$i" "$LOG_FILE.$((i + 1))"
    done
    mv "$LOG_FILE" "$LOG_FILE.1"
}

mkdir -p "$LOG_DIR" "$SSH_CONTROL_DIR"
chmod 700 "$SSH_CONTROL_DIR"
rotate_logs
cd "$REPO_DIR"

# Create venv if missing
if [ ! -d "$VENV_DIR" ]; then
    log "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip --quiet
    if systemctl is-enabled --quiet sentinel-forecasting 2>/dev/null || systemctl is-active --quiet sentinel-forecasting 2>/dev/null; then
        "$VENV_DIR/bin/pip" install '.[forecasting]' --quiet
    else
        "$VENV_DIR/bin/pip" install . --quiet
    fi
    log "Virtual environment created and dependencies installed"
fi

# Fetch and compare
git fetch origin "$BRANCH" --quiet

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$BRANCH")

[ "$LOCAL" = "$REMOTE" ] && exit 0

log "New commits: ${LOCAL:0:7} -> ${REMOTE:0:7}"

# Snapshot dependency file before pull
DEPS_HASH_BEFORE=$(md5sum pyproject.toml | cut -d' ' -f1)

git pull origin "$BRANCH" --quiet
log "Pulled latest changes"

# Update deps if pyproject.toml changed. The forecasting service is optional
# and carries heavy model dependencies, so only install its extra when that
# systemd unit is already enabled or running on the device.
DEPS_HASH_AFTER=$(md5sum pyproject.toml | cut -d' ' -f1)
if [ "$DEPS_HASH_BEFORE" != "$DEPS_HASH_AFTER" ]; then
    log "pyproject.toml changed, updating dependencies..."
    if systemctl is-enabled --quiet sentinel-forecasting 2>/dev/null || systemctl is-active --quiet sentinel-forecasting 2>/dev/null; then
        "$VENV_DIR/bin/pip" install '.[forecasting]' --quiet
    else
        "$VENV_DIR/bin/pip" install . --quiet
    fi
    log "Dependencies updated"
fi

# Update systemd units if changed
UNITS_CHANGED=false
for unit in sentinel.service sentinel-forecasting.service sentinel-deploy.service sentinel-deploy.timer; do
    if ! diff -q "$REPO_DIR/systemd/$unit" "/etc/systemd/system/$unit" &>/dev/null; then
        sudo cp "$REPO_DIR/systemd/$unit" "/etc/systemd/system/$unit"
        UNITS_CHANGED=true
        log "Updated $unit"
    fi
done
if [ "$UNITS_CHANGED" = true ]; then
    sudo systemctl daemon-reload
    log "Systemd daemon reloaded"
fi

# Update LED app if changed
if git diff --name-only "$LOCAL" "$REMOTE" -- arduino-app/sentinel/ | grep -q .; then
    log "LED app changed, updating..."
    mkdir -p "$LED_APP_DEST"
    rm -rf "$LED_APP_DEST/python" "$LED_APP_DEST/sketch"
    cp "$LED_APP_SRC/app.yaml" "$LED_APP_DEST/"
    cp -R "$LED_APP_SRC/python" "$LED_APP_DEST/"
    cp -R "$LED_APP_SRC/sketch" "$LED_APP_DEST/"
    # On-device, the running app id shows up as "user:sentinel".
    # Stop by id first (most reliable), then fall back to the short name.
    arduino-app-cli app stop user:sentinel 2>/dev/null || arduino-app-cli app stop sentinel 2>/dev/null || true
    cd "$LED_APP_DEST" && arduino-app-cli app start .
    cd "$REPO_DIR"
    log "LED app updated and restarted"
fi

# Restart the app
log "Restarting sentinel..."
sudo systemctl restart sentinel
if systemctl is-active --quiet sentinel-forecasting 2>/dev/null; then
    log "Restarting sentinel-forecasting..."
    sudo systemctl restart sentinel-forecasting
fi
log "Deploy complete ($(git rev-parse --short HEAD))"
