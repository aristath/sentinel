#!/bin/bash
# Full deployment pipeline: build, deploy, restart

set -e  # Exit on error

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

log_header "Full Deployment to Arduino Uno Q"
log_info "This will: build → deploy → restart"
echo ""

# Ask for confirmation
read -p "Continue? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_warn "Deployment cancelled"
    exit 0
fi

# Step 1: Build
log_header "Step 1/3: Building"
"${SCRIPT_DIR}/build.sh"

# Step 2: Deploy
log_header "Step 2/3: Deploying"
"${SCRIPT_DIR}/deploy.sh"

# Step 3: Restart
log_header "Step 3/3: Restarting Services"
"${SCRIPT_DIR}/restart.sh" all

# Final status
log_header "Deployment Complete!"
echo ""
"${SCRIPT_DIR}/status.sh"

log_success "All done! Services are running."
log_info "Monitor logs with: ./scripts/logs.sh trader 50 -f"
