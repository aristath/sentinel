#!/bin/bash
# View service logs on Arduino Uno Q

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

# Parse arguments
SERVICE="${1:-trader}"
LINES="${2:-50}"
FOLLOW="${3:-no}"

show_logs() {
    local service_name="$1"
    local lines="$2"
    local follow="$3"

    log_header "Logs for ${service_name}"

    if [ "$follow" = "follow" ] || [ "$follow" = "-f" ]; then
        log_info "Following logs (Ctrl+C to exit)..."
        ssh -t "${ARDUINO_SSH}" "sudo journalctl -u ${service_name} -f -n ${lines}"
    else
        ssh "${ARDUINO_SSH}" "sudo journalctl -u ${service_name} -n ${lines} --no-pager"
    fi
}

case "$SERVICE" in
    trader)
        show_logs "$SERVICE_TRADER_GO" "$LINES" "$FOLLOW"
        ;;
    display-bridge|bridge)
        show_logs "$SERVICE_BRIDGE_GO" "$LINES" "$FOLLOW"
        ;;
    router|arduino-router)
        show_logs "$SERVICE_ARDUINO_ROUTER" "$LINES" "$FOLLOW"
        ;;
    all)
        log_info "Showing logs from all services..."
        ssh "${ARDUINO_SSH}" "sudo journalctl -u ${SERVICE_TRADER_GO} -u ${SERVICE_BRIDGE_GO} -n ${LINES} --no-pager"
        ;;
    *)
        log_error "Unknown service: $SERVICE"
        echo ""
        echo "Usage: $0 [SERVICE] [LINES] [follow]"
        echo ""
        echo "Services:"
        echo "  trader         - Show trader logs (default)"
        echo "  display-bridge - Show display bridge logs"
        echo "  arduino-router - Show arduino-router logs"
        echo "  all            - Show logs from all services"
        echo ""
        echo "Examples:"
        echo "  $0 trader              # Last 50 lines"
        echo "  $0 display-bridge 100  # Last 100 lines"
        echo "  $0 trader 50 -f        # Follow logs"
        exit 1
        ;;
esac
