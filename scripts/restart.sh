#!/bin/bash
# Restart services on Arduino Uno Q

set -e  # Exit on error

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

# Parse arguments
SERVICE="${1:-all}"

restart_service() {
    local service_name="$1"
    log_info "Restarting ${service_name}..."

    if ssh "${ARDUINO_SSH}" "sudo systemctl restart ${service_name}" 2>/dev/null; then
        log_success "${service_name} restarted"

        # Wait a moment and check status
        sleep 1
        if ssh "${ARDUINO_SSH}" "sudo systemctl is-active ${service_name}" >/dev/null 2>&1; then
            log_success "${service_name} is running"
        else
            log_error "${service_name} failed to start"
            log_info "Check logs with: ./scripts/logs.sh ${service_name}"
            return 1
        fi
    else
        log_error "Failed to restart ${service_name}"
        log_warn "Service may not be installed. Check with: ./scripts/status.sh"
        return 1
    fi
}

log_header "Restarting Services on Arduino Uno Q"

case "$SERVICE" in
    all)
        log_info "Restarting all services..."
        restart_service "$SERVICE_TRADER_GO"
        restart_service "$SERVICE_BRIDGE_GO"
        log_success "All services restarted!"
        ;;
    sentinel)
        restart_service "$SERVICE_TRADER_GO"
        ;;
    display-bridge|bridge)
        restart_service "$SERVICE_BRIDGE_GO"
        ;;
    router|arduino-router)
        restart_service "$SERVICE_ARDUINO_ROUTER"
        ;;
    *)
        log_error "Unknown service: $SERVICE"
        echo ""
        echo "Usage: $0 [SERVICE]"
        echo ""
        echo "Services:"
        echo "  all            - Restart all services (default)"
        echo "  sentinel       - Restart Sentinel service"
        echo "  display-bridge - Restart display bridge service"
        echo "  arduino-router - Restart arduino-router service"
        exit 1
        ;;
esac

log_header "Service Status"
ssh "${ARDUINO_SSH}" "sudo systemctl status ${SERVICE_TRADER_GO} ${SERVICE_BRIDGE_GO} --no-pager -l" | grep -E "Active:|Main PID:|Memory:" || true
