#!/bin/bash
# Configuration for Arduino Uno Q deployment scripts
# Override these by setting environment variables

# Arduino device connection
export ARDUINO_HOST="${ARDUINO_HOST:-192.168.1.11}"
export ARDUINO_USER="${ARDUINO_USER:-arduino}"
export ARDUINO_DEPLOY_PATH="${ARDUINO_DEPLOY_PATH:-/opt/arduino-trader}"

# SSH connection string
export ARDUINO_SSH="${ARDUINO_USER}@${ARDUINO_HOST}"

# Build settings
export BUILD_TRADER_GO="${BUILD_TRADER_GO:-yes}"
export BUILD_BRIDGE_GO="${BUILD_BRIDGE_GO:-yes}"

# Service names
export SERVICE_TRADER_GO="trader"
export SERVICE_BRIDGE_GO="display-bridge"
export SERVICE_ARDUINO_ROUTER="arduino-router"

# Colors for output
export COLOR_RESET='\033[0m'
export COLOR_RED='\033[0;31m'
export COLOR_GREEN='\033[0;32m'
export COLOR_YELLOW='\033[1;33m'
export COLOR_BLUE='\033[0;34m'
export COLOR_CYAN='\033[0;36m'

# Helper functions
log_info() {
    echo -e "${COLOR_CYAN}[INFO]${COLOR_RESET} $1"
}

log_success() {
    echo -e "${COLOR_GREEN}[SUCCESS]${COLOR_RESET} $1"
}

log_error() {
    echo -e "${COLOR_RED}[ERROR]${COLOR_RESET} $1"
}

log_warn() {
    echo -e "${COLOR_YELLOW}[WARN]${COLOR_RESET} $1"
}

log_header() {
    echo -e "\n${COLOR_BLUE}===${COLOR_RESET} $1 ${COLOR_BLUE}===${COLOR_RESET}\n"
}
