#!/bin/bash
# Compile and upload Arduino sketch to MCU
# Used by auto-deploy script when sketch files change

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SKETCH_DIR="$REPO_DIR/arduino-app/sketch"
SKETCH_FILE="$SKETCH_DIR/sketch.ino"
FQBN="arduino:zephyr:unoq"
LOG_FILE="/home/arduino/logs/sketch-compile.log"

# Detect serial port - try ttyHS1 first (Arduino Uno Q internal), then ttyACM0
if [ -e "/dev/ttyHS1" ]; then
    SERIAL_PORT="/dev/ttyHS1"
elif [ -e "/dev/ttyACM0" ]; then
    SERIAL_PORT="/dev/ttyACM0"
else
    SERIAL_PORT="/dev/ttyHS1"  # Default fallback
fi

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S'): $1" | tee -a "$LOG_FILE"
}

error_exit() {
    log "ERROR: $1"
    exit 1
}

# Check if sketch file exists
if [ ! -f "$SKETCH_FILE" ]; then
    error_exit "Sketch file not found: $SKETCH_FILE"
fi

# Check if arduino-cli is installed
if ! command -v arduino-cli &> /dev/null; then
    log "Arduino CLI not found, installing..."

    # Install Arduino CLI (download first, don't pipe to shell - security risk)
    INSTALL_SCRIPT=$(mktemp)
    if ! curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh -o "$INSTALL_SCRIPT"; then
        rm -f "$INSTALL_SCRIPT"
        error_exit "Failed to download Arduino CLI installer"
    fi

    bash "$INSTALL_SCRIPT" || {
        rm -f "$INSTALL_SCRIPT"
        error_exit "Failed to install Arduino CLI"
    }
    rm -f "$INSTALL_SCRIPT"

    # Add to PATH if installed to ~/bin
    if [ -f "$HOME/bin/arduino-cli" ]; then
        export PATH="$HOME/bin:$PATH"
    fi

    log "Arduino CLI installed"
fi

# Update core index
log "Updating core index..."
arduino-cli core update-index >> "$LOG_FILE" 2>&1 || log "WARNING: Failed to update core index"

# Install board platform
log "Installing board platform: $FQBN"
arduino-cli core install arduino:zephyr >> "$LOG_FILE" 2>&1 || {
    error_exit "Failed to install arduino:zephyr platform"
}

# Install required libraries
log "Installing required libraries..."
arduino-cli lib install "ArduinoGraphics" >> "$LOG_FILE" 2>&1 || log "WARNING: Failed to install ArduinoGraphics"
arduino-cli lib install "MsgPack@0.4.2" >> "$LOG_FILE" 2>&1 || log "WARNING: Failed to install MsgPack"
arduino-cli lib install "DebugLog@0.8.4" >> "$LOG_FILE" 2>&1 || log "WARNING: Failed to install DebugLog"
arduino-cli lib install "ArxContainer@0.7.0" >> "$LOG_FILE" 2>&1 || log "WARNING: Failed to install ArxContainer"
arduino-cli lib install "ArxTypeTraits@0.3.1" >> "$LOG_FILE" 2>&1 || log "WARNING: Failed to install ArxTypeTraits"

# Compile sketch
log "Compiling sketch: $SKETCH_FILE"
if arduino-cli compile --fqbn "$FQBN" "$SKETCH_DIR" >> "$LOG_FILE" 2>&1; then
    log "Compilation successful"
else
    error_exit "Compilation failed - check $LOG_FILE for details"
fi

# Check if serial port exists
if [ ! -e "$SERIAL_PORT" ]; then
    log "WARNING: Serial port $SERIAL_PORT not found, skipping upload"
    log "Sketch compiled successfully but not uploaded"
    exit 0
fi

# Upload to MCU
log "Uploading sketch to MCU via $SERIAL_PORT..."
if arduino-cli upload --fqbn "$FQBN" --port "$SERIAL_PORT" "$SKETCH_DIR" >> "$LOG_FILE" 2>&1; then
    log "Upload successful"
    exit 0
else
    error_exit "Upload failed - check $LOG_FILE for details"
fi
