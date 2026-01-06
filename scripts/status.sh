#!/bin/bash
# Check service status on Arduino Uno Q

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

log_header "Service Status on Arduino Uno Q"
log_info "Host: ${ARDUINO_SSH}"
echo ""

# Check if we can connect
if ! ssh -o ConnectTimeout=5 "${ARDUINO_SSH}" "echo 'OK'" >/dev/null 2>&1; then
    log_error "Cannot connect to ${ARDUINO_SSH}"
    exit 1
fi

# Function to check service status
check_service() {
    local service_name="$1"
    local display_name="$2"

    echo -n "${display_name}: "

    if ssh "${ARDUINO_SSH}" "sudo systemctl is-active ${service_name}" >/dev/null 2>&1; then
        echo -e "${COLOR_GREEN}RUNNING${COLOR_RESET}"

        # Get process info
        local pid=$(ssh "${ARDUINO_SSH}" "sudo systemctl show ${service_name} --property=MainPID --value")
        if [ "$pid" != "0" ]; then
            local mem=$(ssh "${ARDUINO_SSH}" "ps -p ${pid} -o rss= 2>/dev/null | awk '{print \$1/1024 \"MB\"}'")
            local cpu=$(ssh "${ARDUINO_SSH}" "ps -p ${pid} -o %cpu= 2>/dev/null")
            echo "  └─ PID: ${pid}, Memory: ${mem}, CPU: ${cpu}%"
        fi
    elif ssh "${ARDUINO_SSH}" "sudo systemctl is-enabled ${service_name}" >/dev/null 2>&1; then
        echo -e "${COLOR_RED}STOPPED${COLOR_RESET} (but enabled)"
    else
        echo -e "${COLOR_YELLOW}NOT INSTALLED${COLOR_RESET}"
    fi
}

# Check all services
check_service "$SERVICE_TRADER_GO" "trader"
check_service "$SERVICE_BRIDGE_GO" "display-bridge"
check_service "$SERVICE_ARDUINO_ROUTER" "arduino-router"

echo ""
log_header "Recent Errors"

# Show recent errors from all services
if ssh "${ARDUINO_SSH}" "sudo journalctl -p err -u ${SERVICE_TRADER_GO} -u ${SERVICE_BRIDGE_GO} --since '5 minutes ago' --no-pager" 2>/dev/null | grep -q .; then
    ssh "${ARDUINO_SSH}" "sudo journalctl -p err -u ${SERVICE_TRADER_GO} -u ${SERVICE_BRIDGE_GO} --since '5 minutes ago' --no-pager -n 5"
else
    log_success "No errors in the last 5 minutes"
fi

echo ""
log_header "Quick Actions"
echo "  View logs:     ./scripts/logs.sh [SERVICE]"
echo "  Restart:       ./scripts/restart.sh [SERVICE]"
echo "  Trigger deploy: curl -X POST http://localhost:8001/api/system/deployment/deploy"
