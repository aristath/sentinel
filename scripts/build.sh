#!/bin/bash
# Build Go applications for Arduino Uno Q (ARM64 Linux)

set -e  # Exit on error

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

cd "$(dirname "$SCRIPT_DIR")"  # Change to repo root

log_header "Building for Arduino Uno Q (ARM64)"

# Build trader
if [ "$BUILD_TRADER_GO" = "yes" ]; then
    log_info "Building trader..."
    cd trader/cmd/server
    GOOS=linux GOARCH=arm64 go build -o ../../../build/trader
    cd ../../..
    log_success "trader built successfully → build/trader"
fi

# Build display bridge
if [ "$BUILD_BRIDGE_GO" = "yes" ]; then
    log_info "Building display bridge..."
    cd display/bridge
    GOOS=linux GOARCH=arm64 go build -o ../../build/display-bridge
    cd ../..
    log_success "display bridge built successfully → build/display-bridge"
fi

log_header "Build Summary"
ls -lh build/
log_success "All builds complete!"
