#!/bin/bash
# Setup script for tradernet virtual environment
# Creates Python 3.13 virtual environment and installs dependencies

set -e

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

cd "$(dirname "$SCRIPT_DIR")"  # Change to repo root

VENV_PATH="/opt/arduino-trader/microservices/tradernet/venv"
REQUIREMENTS_PATH="/opt/arduino-trader/microservices/tradernet/requirements.txt"
SERVICE_DIR="/opt/arduino-trader/microservices/tradernet"

log_header "Tradernet Virtual Environment Setup"
log_info "Target: ${ARDUINO_SSH}"
log_info "Venv Path: ${VENV_PATH}"

# Check Python 3.13
log_info "Checking Python version..."
PYTHON_VERSION=$(ssh "${ARDUINO_SSH}" "python3 --version 2>&1" | grep -oP 'Python \K[0-9]+\.[0-9]+' || echo "")
if [ -z "$PYTHON_VERSION" ]; then
    log_error "Python 3 not found on device"
    exit 1
fi

if [[ ! "$PYTHON_VERSION" =~ ^3\.(1[3-9]|[2-9][0-9])$ ]] && [ "$PYTHON_VERSION" != "3.13" ]; then
    log_warn "Python version is ${PYTHON_VERSION}, expected 3.13 or higher"
    log_info "Continuing anyway, but compatibility is not guaranteed"
fi

log_success "Python ${PYTHON_VERSION} found"

# Check if python3-venv is available
log_info "Checking for python3-venv..."
if ! ssh "${ARDUINO_SSH}" "python3 -m venv --help >/dev/null 2>&1"; then
    log_error "python3-venv module not available"
    log_info "Please install python3-venv on the device: sudo apt-get install python3-venv"
    exit 1
fi
log_success "python3-venv available"

# Create service directory if it doesn't exist
log_info "Ensuring service directory exists..."
ssh "${ARDUINO_SSH}" "sudo mkdir -p ${SERVICE_DIR}"
ssh "${ARDUINO_SSH}" "sudo chown -R ${ARDUINO_USER}:${ARDUINO_USER} ${SERVICE_DIR}"
log_success "Service directory ready"

# Remove existing venv if it exists
log_info "Removing existing venv (if any)..."
ssh "${ARDUINO_SSH}" "rm -rf ${VENV_PATH}" || true
log_success "Old venv removed"

# Create virtual environment
log_info "Creating virtual environment..."
ssh "${ARDUINO_SSH}" "cd ${SERVICE_DIR} && python3 -m venv venv"
if [ $? -ne 0 ]; then
    log_error "Failed to create virtual environment"
    exit 1
fi
log_success "Virtual environment created"

# Ensure arduino user owns the venv
log_info "Setting permissions..."
ssh "${ARDUINO_SSH}" "sudo chown -R ${ARDUINO_USER}:${ARDUINO_USER} ${VENV_PATH}"
log_success "Permissions set"

# Verify requirements.txt exists
log_info "Checking requirements.txt..."
if ! ssh "${ARDUINO_SSH}" "test -f ${REQUIREMENTS_PATH}"; then
    log_error "requirements.txt not found at ${REQUIREMENTS_PATH}"
    log_info "Please ensure tradernet code is deployed first"
    exit 1
fi
log_success "requirements.txt found"

# Install dependencies
log_info "Installing dependencies (this may take 30-60 seconds)..."
ssh "${ARDUINO_SSH}" "cd ${SERVICE_DIR} && source venv/bin/activate && pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt"
if [ $? -ne 0 ]; then
    log_error "Failed to install dependencies"
    exit 1
fi
log_success "Dependencies installed"

# Verify installation
log_info "Verifying installation..."
ssh "${ARDUINO_SSH}" "cd ${SERVICE_DIR} && source venv/bin/activate && python -c 'import fastapi; import uvicorn; import tradernet; print(\"All imports successful\")'"
if [ $? -ne 0 ]; then
    log_error "Installation verification failed"
    exit 1
fi
log_success "Installation verified"

log_header "Virtual Environment Setup Complete!"
log_info "Venv location: ${VENV_PATH}"
log_info "Ready for systemd service deployment"
