#!/bin/bash
# Deploy binaries to Arduino Uno Q device

set -e  # Exit on error

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

cd "$(dirname "$SCRIPT_DIR")"  # Change to repo root

log_header "Deploying to Arduino Uno Q"
log_info "Target: ${ARDUINO_SSH}:${ARDUINO_DEPLOY_PATH}"

# Ensure build directory exists
if [ ! -d "build" ]; then
    log_error "Build directory not found. Run ./scripts/build.sh first."
    exit 1
fi

# Check connectivity
log_info "Testing SSH connection..."
if ! ssh -o ConnectTimeout=5 "${ARDUINO_SSH}" "echo 'Connection successful'" >/dev/null 2>&1; then
    log_error "Cannot connect to ${ARDUINO_SSH}"
    log_info "Ensure the Arduino device is powered on and accessible"
    exit 1
fi
log_success "SSH connection verified"

# Create deployment directory if it doesn't exist
log_info "Ensuring deployment directory exists..."
ssh "${ARDUINO_SSH}" "mkdir -p ${ARDUINO_DEPLOY_PATH}"

# Deploy trader
if [ -f "build/trader" ]; then
    log_info "Deploying trader..."
    scp build/trader "${ARDUINO_SSH}:${ARDUINO_DEPLOY_PATH}/"
    ssh "${ARDUINO_SSH}" "chmod +x ${ARDUINO_DEPLOY_PATH}/trader"
    log_success "trader deployed"
else
    log_warn "build/trader not found, skipping"
fi

# Deploy display-bridge
if [ -f "build/display-bridge" ]; then
    log_info "Deploying display-bridge..."
    scp build/display-bridge "${ARDUINO_SSH}:${ARDUINO_DEPLOY_PATH}/"
    ssh "${ARDUINO_SSH}" "chmod +x ${ARDUINO_DEPLOY_PATH}/display-bridge"
    log_success "display-bridge deployed"
else
    log_warn "build/display-bridge not found, skipping"
fi

# Deploy data directory (if needed)
if [ "$DEPLOY_DATA" = "yes" ]; then
    log_info "Deploying data directory..."
    scp -r data/ "${ARDUINO_SSH}:${ARDUINO_DEPLOY_PATH}/"
    log_success "Data directory deployed"
fi

log_header "Deployment Summary"
ssh "${ARDUINO_SSH}" "ls -lh ${ARDUINO_DEPLOY_PATH}/ | grep -E 'trader|display-bridge|data'"
log_success "Deployment complete!"
log_info "Run './scripts/restart.sh' to restart services"
