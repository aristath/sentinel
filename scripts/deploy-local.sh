#!/bin/bash
# Device-local deployment script
# Runs on the Arduino device itself to trigger deployment and restart services
# This script pulls latest code and relies on auto-deploy, or triggers manual deployment

set -e  # Exit on error

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

cd "$(dirname "$SCRIPT_DIR")"  # Change to repo root

log_header "Device-Local Deployment"
log_info "This script runs on the Arduino device"

# Check if we're running on the device (not via SSH from dev machine)
if [ -n "${SSH_CLIENT:-}" ] || [ -n "${SSH_CONNECTION:-}" ]; then
    # We're SSH'd in, so we're on the device
    ON_DEVICE=true
else
    # Check if we're actually on the device by checking for device-specific paths
    if [ -d "/home/arduino/app/bin" ] && [ -f "/home/arduino/app/bin/trader" ]; then
        ON_DEVICE=true
    else
        log_error "This script must run on the Arduino device"
        log_info "Deployment is handled automatically by the auto-deploy system"
        exit 1
    fi
fi

# Step 1: Pull latest code
log_header "Step 1: Pulling latest code from git"
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
log_info "Current branch: ${CURRENT_BRANCH}"

if git fetch origin "${CURRENT_BRANCH}" >/dev/null 2>&1; then
    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse origin/${CURRENT_BRANCH})

    if [ "$LOCAL" != "$REMOTE" ]; then
        log_info "New commits available, pulling..."
        git pull origin "${CURRENT_BRANCH}"
        log_success "Code updated"
    else
        log_info "Already up to date"
    fi
else
    log_warn "Failed to fetch from git, continuing anyway"
fi

# Step 2: Trigger deployment (auto-deploy or manual)
log_header "Step 2: Triggering deployment"

# Try to trigger deployment via API (if service is running)
if curl -s -f http://localhost:8080/health >/dev/null 2>&1; then
    log_info "Service is running, triggering deployment via API..."
    DEPLOY_RESULT=$(curl -s -X POST http://localhost:8080/api/system/deployment/deploy 2>&1)
    if echo "$DEPLOY_RESULT" | grep -q "success"; then
        log_success "Deployment triggered successfully"
        echo "$DEPLOY_RESULT" | head -20
    else
        log_warn "Deployment API call failed or returned error"
        log_info "Auto-deploy will run automatically in the next cycle (every 5 minutes)"
        log_info "Or the deployment manager will detect changes on next check"
    fi
else
    log_info "Service not running, auto-deploy will handle deployment on startup"
fi

# Step 3: Restart services
log_header "Step 3: Restarting services"

if command -v systemctl >/dev/null 2>&1; then
    # Restart trader service
    if sudo systemctl restart trader 2>/dev/null; then
        log_success "trader service restarted"
        sleep 2
        if sudo systemctl is-active trader >/dev/null 2>&1; then
            log_success "trader service is running"
        else
            log_error "trader service failed to start"
            sudo systemctl status trader --no-pager -l | head -15
        fi
    else
        log_warn "Failed to restart trader service (may not be installed)"
    fi

    # Restart display-bridge service
    if sudo systemctl restart display-bridge 2>/dev/null; then
        log_success "display-bridge service restarted"
        sleep 1
        if sudo systemctl is-active display-bridge >/dev/null 2>&1; then
            log_success "display-bridge service is running"
        else
            log_warn "display-bridge service failed to start"
        fi
    else
        log_warn "Failed to restart display-bridge service (may not be installed)"
    fi

    # Restart tradernet service
    if sudo systemctl restart tradernet 2>/dev/null; then
        log_success "tradernet service restarted"
        sleep 2
        if sudo systemctl is-active tradernet >/dev/null 2>&1; then
            log_success "tradernet service is running"
        else
            log_error "tradernet service failed to start"
            sudo systemctl status tradernet --no-pager -l | head -15
        fi
    else
        log_warn "Failed to restart tradernet service (may not be installed)"
    fi
else
    log_warn "systemctl not available, skipping service restart"
fi

# Final status
log_header "Deployment Complete!"
log_info "Services should be running with latest code"
log_info "Auto-deploy will continue to monitor for changes every 5 minutes"
