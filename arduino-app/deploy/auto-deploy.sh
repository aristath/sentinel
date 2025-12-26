#!/bin/bash
# Auto-deploy script for Arduino Trader
# Runs via cron every 5 minutes to check for updates and deploy changes
# Handles: Main FastAPI app and sketch compilation/upload

set -euo pipefail

# Configuration
REPO_DIR="/home/arduino/repos/autoTrader"
MAIN_APP_DIR="/home/arduino/arduino-trader"
LOG_FILE="/home/arduino/logs/auto-deploy.log"
VENV_DIR="$MAIN_APP_DIR/venv"
SERVICE_NAME="arduino-trader"

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S'): $1" >> "$LOG_FILE"
}

# Error handling
error_exit() {
    log "ERROR: $1"
    exit 1
}

# Restart systemd service with retry logic
restart_service() {
    local max_attempts=3
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        log "Attempt $attempt/$max_attempts: Restarting $SERVICE_NAME service"

        if sudo systemctl restart "$SERVICE_NAME" 2>>"$LOG_FILE"; then
            # Wait for service to start
            sleep 2

            # Verify service is running
            if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
                log "$SERVICE_NAME service restarted successfully"
                return 0
            else
                log "WARNING: Restart command succeeded but service is not active"
            fi
        else
            log "WARNING: Failed to restart $SERVICE_NAME (attempt $attempt)"
        fi

        attempt=$((attempt + 1))
        if [ $attempt -le $max_attempts ]; then
            log "Waiting 5 seconds before retry..."
            sleep 5
        fi
    done

    log "ERROR: Failed to restart $SERVICE_NAME after $max_attempts attempts"
    return 1
}

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Change to repo directory
cd "$REPO_DIR" || error_exit "Cannot change to repo directory: $REPO_DIR"

# Detect current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ -z "$CURRENT_BRANCH" ]; then
    error_exit "Cannot detect current branch"
fi

log "Checking for updates on branch: $CURRENT_BRANCH"

# Fetch latest changes
if ! git fetch origin 2>>"$LOG_FILE"; then
    error_exit "Failed to fetch from origin"
fi

# Get commit hashes
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$CURRENT_BRANCH" 2>/dev/null || git rev-parse "origin/main" 2>/dev/null)

if [ -z "$REMOTE" ]; then
    log "WARNING: Cannot find remote branch, skipping update"
    exit 0
fi

# Check if there are changes
if [ "$LOCAL" = "$REMOTE" ]; then
    log "No changes detected (LOCAL: ${LOCAL:0:8} == REMOTE: ${REMOTE:0:8})"
    exit 0
fi

log "Changes detected: LOCAL ${LOCAL:0:8} -> REMOTE ${REMOTE:0:8}"

# Get list of changed files
CHANGED_FILES=$(git diff --name-only "$LOCAL" "$REMOTE" 2>>"$LOG_FILE" || true)

if [ -z "$CHANGED_FILES" ]; then
    log "No changed files detected, but commits differ. Pulling anyway..."
    git pull origin "$CURRENT_BRANCH" >> "$LOG_FILE" 2>&1 || error_exit "Failed to pull changes"
    log "Update complete (no file changes detected)"
    exit 0
fi

log "Changed files: $(echo "$CHANGED_FILES" | tr '\n' ' ')"

# Categorize changes
MAIN_APP_CHANGED=false
SKETCH_CHANGED=false
REQUIREMENTS_CHANGED=false
DEPLOY_SCRIPT_CHANGED=false

while IFS= read -r file; do
    # Check for main app changes
    if [[ "$file" == app/* ]] || \
       [[ "$file" == static/* ]] || \
       [[ "$file" == *.py ]] || \
       [[ "$file" == requirements.txt ]] || \
       [[ "$file" == deploy/arduino-trader.service ]] || \
       [[ "$file" == scripts/* ]] || \
       [[ "$file" == data/* ]]; then
        MAIN_APP_CHANGED=true
        if [[ "$file" == requirements.txt ]]; then
            REQUIREMENTS_CHANGED=true
        fi
    fi
    
    # Check for sketch changes
    if [[ "$file" == arduino-app/sketch/* ]]; then
        SKETCH_CHANGED=true
    fi

    # Check for deploy script changes
    if [[ "$file" == arduino-app/deploy/auto-deploy.sh ]]; then
        DEPLOY_SCRIPT_CHANGED=true
    fi
done <<< "$CHANGED_FILES"

# Self-update: Update this script if it changed
if [ "$DEPLOY_SCRIPT_CHANGED" = true ]; then
    log "Deploy script changed - updating self..."
    cp "$REPO_DIR/arduino-app/deploy/auto-deploy.sh" /home/arduino/bin/auto-deploy.sh
    chmod +x /home/arduino/bin/auto-deploy.sh
    log "Deploy script updated"
fi

# Pull latest changes
log "Pulling latest changes from origin/$CURRENT_BRANCH"
if ! git pull origin "$CURRENT_BRANCH" >> "$LOG_FILE" 2>&1; then
    error_exit "Failed to pull changes"
fi

# Deploy main FastAPI app if needed
if [ "$MAIN_APP_CHANGED" = true ]; then
    log "Deploying main FastAPI app..."

    # Sync files to main app directory using cp (rsync not available)
    log "Syncing files to $MAIN_APP_DIR"

    # Create target directory if it doesn't exist
    mkdir -p "$MAIN_APP_DIR"

    # Copy main app directories/files (excluding venv, .env, arduino-app, .git)
    for item in app static scripts data deploy requirements.txt run.py; do
        if [ -e "$REPO_DIR/$item" ]; then
            cp -r "$REPO_DIR/$item" "$MAIN_APP_DIR/" 2>>"$LOG_FILE" || log "WARNING: Failed to copy $item"
        fi
    done

    # Clean up __pycache__ directories
    find "$MAIN_APP_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$MAIN_APP_DIR" -name "*.pyc" -delete 2>/dev/null || true

    log "Main app files synced"
    
    # Update Python dependencies if requirements.txt changed
    if [ "$REQUIREMENTS_CHANGED" = true ]; then
        log "Updating Python dependencies..."
        if [ -d "$VENV_DIR" ]; then
            if source "$VENV_DIR/bin/activate" 2>>"$LOG_FILE"; then
                if pip install -r "$MAIN_APP_DIR/requirements.txt" >> "$LOG_FILE" 2>&1; then
                    log "Dependencies updated successfully"
                else
                    log "WARNING: Failed to update dependencies, continuing anyway"
                fi
            else
                log "WARNING: Failed to activate virtual environment"
            fi
        else
            log "WARNING: Virtual environment not found at $VENV_DIR"
        fi
    fi
    
    # Restart systemd service with retry logic
    restart_service
fi

# Handle sketch changes (compile and upload)
if [ "$SKETCH_CHANGED" = true ]; then
    log "Sketch files changed - compiling and uploading..."
    
    # Stop LED display service during upload
    log "Stopping LED display service for sketch upload"
    sudo systemctl stop led-display >> "$LOG_FILE" 2>&1 || log "WARNING: Failed to stop LED display service"
    
    # Wait a moment for service to stop
    sleep 2
    
    # Compile and upload sketch using native script
    if [ -f "$MAIN_APP_DIR/scripts/compile_and_upload_sketch.sh" ]; then
        log "Running sketch compilation script..."
        if bash "$MAIN_APP_DIR/scripts/compile_and_upload_sketch.sh" >> "$LOG_FILE" 2>&1; then
            log "Sketch compiled and uploaded successfully"
        else
            log "ERROR: Sketch compilation/upload failed - check logs"
        fi
    else
        log "WARNING: compile_and_upload_sketch.sh not found"
    fi
    
    # Restart LED display service
    log "Restarting LED display service"
    if sudo systemctl start led-display >> "$LOG_FILE" 2>&1; then
        log "LED display service restarted"
    else
        log "WARNING: Failed to restart LED display service"
    fi
fi

log "Deployment complete"
exit 0
