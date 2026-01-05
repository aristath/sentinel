#!/bin/bash
# Automated setup script for Arduino Uno Q deployment
# This script sets up everything on the Arduino device for first-time deployment

set -e

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

cd "$(dirname "$SCRIPT_DIR")"  # Change to repo root

log_header "Arduino Uno Q Initial Setup"
log_info "Target: ${ARDUINO_SSH}"
log_info "Deploy Path: ${ARDUINO_DEPLOY_PATH}"

# Check connectivity
log_info "Testing SSH connection..."
if ! ssh -o ConnectTimeout=5 "${ARDUINO_SSH}" "echo 'Connection successful'" >/dev/null 2>&1; then
    log_error "Cannot connect to ${ARDUINO_SSH}"
    log_info "Please ensure:"
    log_info "  1. Arduino device is powered on"
    log_info "  2. Device is accessible on network (${ARDUINO_HOST})"
    log_info "  3. SSH is enabled and accessible"
    exit 1
fi
log_success "SSH connection verified"

# Step 1: Create directories
log_header "Step 1: Creating directories"
ssh "${ARDUINO_SSH}" "sudo mkdir -p ${ARDUINO_DEPLOY_PATH}"
ssh "${ARDUINO_SSH}" "sudo mkdir -p ${ARDUINO_DEPLOY_PATH}/data"
ssh "${ARDUINO_SSH}" "sudo chown -R ${ARDUINO_USER}:${ARDUINO_USER} ${ARDUINO_DEPLOY_PATH}"
log_success "Directories created"

# Step 2: Check Docker
log_header "Step 2: Checking Docker"
if ssh "${ARDUINO_SSH}" "command -v docker" >/dev/null 2>&1; then
    log_success "Docker is installed"
    if ssh "${ARDUINO_SSH}" "sudo systemctl is-active docker" >/dev/null 2>&1; then
        log_success "Docker is running"
    else
        log_warn "Docker is not running, attempting to start..."
        ssh "${ARDUINO_SSH}" "sudo systemctl start docker" || log_error "Failed to start Docker"
    fi
else
    log_error "Docker is not installed"
    log_info "Please install Docker on the Arduino device first"
    exit 1
fi

# Step 3: Deploy systemd service files
log_header "Step 3: Deploying systemd service files"

# Deploy trader.service
log_info "Deploying trader.service..."
scp trader.service "${ARDUINO_SSH}:/tmp/trader.service"
ssh "${ARDUINO_SSH}" "sudo mv /tmp/trader.service /etc/systemd/system/trader.service"
ssh "${ARDUINO_SSH}" "sudo chmod 644 /etc/systemd/system/trader.service"

# Deploy display-bridge.service
if [ -f "display/bridge/display-bridge.service" ]; then
    log_info "Deploying display-bridge.service..."
    scp display/bridge/display-bridge.service "${ARDUINO_SSH}:/tmp/display-bridge.service"
    ssh "${ARDUINO_SSH}" "sudo mv /tmp/display-bridge.service /etc/systemd/system/display-bridge.service"
    ssh "${ARDUINO_SSH}" "sudo chmod 644 /etc/systemd/system/display-bridge.service"
fi

# Reload systemd
ssh "${ARDUINO_SSH}" "sudo systemctl daemon-reload"
ssh "${ARDUINO_SSH}" "sudo systemctl enable trader" || log_warn "Failed to enable trader service"
ssh "${ARDUINO_SSH}" "sudo systemctl enable display-bridge" 2>/dev/null || log_warn "display-bridge service not enabled (may not be needed)"
log_success "Systemd services installed"

# Configure passwordless sudo for systemctl (for deploy-local.sh script)
log_header "Step 3b: Configuring passwordless sudo for systemctl"
log_info "Setting up passwordless sudo for systemctl commands..."
SYSTEMCTL_PATH=$(ssh "${ARDUINO_SSH}" "which systemctl")
SUDOERS_CONTENT="arduino ALL=(ALL) NOPASSWD: ${SYSTEMCTL_PATH}"
ssh "${ARDUINO_SSH}" "echo '$SUDOERS_CONTENT' | sudo tee /etc/sudoers.d/arduino-systemctl > /dev/null"
ssh "${ARDUINO_SSH}" "sudo chmod 0440 /etc/sudoers.d/arduino-systemctl"
if ssh "${ARDUINO_SSH}" "sudo visudo -c -f /etc/sudoers.d/arduino-systemctl" 2>&1 | grep -q "OK"; then
    log_success "Passwordless sudo for systemctl configured"
else
    log_warn "Failed to validate sudoers file (may need manual check)"
fi

# Step 4: Deploy microservices code
log_header "Step 4: Deploying microservices"
log_info "Copying microservices directory..."
ssh "${ARDUINO_SSH}" "mkdir -p ${ARDUINO_DEPLOY_PATH}/microservices"
scp -r microservices/pypfopt "${ARDUINO_SSH}:${ARDUINO_DEPLOY_PATH}/microservices/" || log_error "Failed to copy pypfopt"
scp -r microservices/tradernet "${ARDUINO_SSH}:${ARDUINO_DEPLOY_PATH}/microservices/" || log_error "Failed to copy tradernet"
log_success "Microservices code deployed"

# Step 5: Deploy docker-compose.yml
log_header "Step 5: Deploying docker-compose.yml"
if [ -f "docker-compose.yml" ]; then
    scp docker-compose.yml "${ARDUINO_SSH}:${ARDUINO_DEPLOY_PATH}/docker-compose.yml"
    log_success "docker-compose.yml deployed"
else
    log_warn "docker-compose.yml not found, skipping"
fi

# Step 6: Create .env file template
log_header "Step 6: Creating .env file template"
ENV_CONTENT="# Database paths
DATA_DIR=${ARDUINO_DEPLOY_PATH}/data

# Microservice URLs
PYPFOPT_URL=http://localhost:9001
TRADERNET_URL=http://localhost:9002

# Tradernet API (REPLACE WITH YOUR CREDENTIALS)
TRADERNET_API_KEY=your_api_key_here
TRADERNET_API_SECRET=your_api_secret_here

# Server
GO_PORT=8001
LOG_LEVEL=info

# Background Jobs
ENABLE_SCHEDULER=true

# Display (LED Matrix)
DISPLAY_HOST=localhost
DISPLAY_PORT=5555
"

echo "$ENV_CONTENT" | ssh "${ARDUINO_SSH}" "cat > ${ARDUINO_DEPLOY_PATH}/.env.template"
log_success ".env template created at ${ARDUINO_DEPLOY_PATH}/.env.template"

# Check if .env already exists
if ssh "${ARDUINO_SSH}" "test -f ${ARDUINO_DEPLOY_PATH}/.env"; then
    log_info ".env file already exists, not overwriting"
else
    log_info "Creating .env from template (YOU MUST EDIT THIS WITH YOUR CREDENTIALS)"
    ssh "${ARDUINO_SSH}" "cp ${ARDUINO_DEPLOY_PATH}/.env.template ${ARDUINO_DEPLOY_PATH}/.env"
fi

# Step 7: Build and deploy binaries
log_header "Step 7: Building binaries"
log_info "Building ARM64 binary for Arduino Uno Q..."
cd trader
if [ -f "./scripts/build.sh" ]; then
    ./scripts/build.sh arm64
    log_success "Binary built: trader-go-arm64"
else
    log_error "Build script not found: trader/scripts/build.sh"
    exit 1
fi
cd ..

log_header "Step 8: Deploying binaries"
log_info "Copying binary to device..."
if [ -f "trader/trader-go-arm64" ]; then
    scp trader/trader-go-arm64 "${ARDUINO_SSH}:${ARDUINO_DEPLOY_PATH}/trader"
    ssh "${ARDUINO_SSH}" "chmod +x ${ARDUINO_DEPLOY_PATH}/trader"
    log_success "Binary deployed to ${ARDUINO_DEPLOY_PATH}/trader"
else
    log_error "Built binary not found: trader/trader-go-arm64"
    exit 1
fi

# Step 9: Build microservices Docker images
log_header "Step 9: Building microservice Docker images"
log_info "This may take a few minutes..."
ssh "${ARDUINO_SSH}" "cd ${ARDUINO_DEPLOY_PATH} && docker-compose build" || log_warn "Docker compose build failed (you may need to set TRADERNET credentials first)"

log_header "Setup Complete!"
echo ""
log_info "Next steps:"
log_info "1. Edit ${ARDUINO_DEPLOY_PATH}/.env on the Arduino device with your credentials:"
log_info "   ssh ${ARDUINO_SSH}"
log_info "   nano ${ARDUINO_DEPLOY_PATH}/.env"
log_info ""
log_info "2. Start microservices:"
log_info "   ssh ${ARDUINO_SSH} 'cd ${ARDUINO_DEPLOY_PATH} && docker-compose up -d'"
log_info ""
log_info "3. Start trader service:"
log_info "   ./scripts/restart.sh trader"
log_info ""
log_info "4. Check status:"
log_info "   ./scripts/status.sh"
