#!/bin/bash
# Monitor planner status and trades

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/scripts/config.sh"

LOG_FILE="${ARDUINO_DEPLOY_PATH}/data/logs/arduino-trader.log"

echo "=== Monitoring Planner Status ==="
echo "Timestamp: $(date)"
echo "Target: ${ARDUINO_SSH}"

# Check for errors
echo ""
echo "--- Recent Errors ---"
ssh "${ARDUINO_SSH}" "tail -200 ${LOG_FILE} 2>/dev/null | grep -iE 'error|exception|failed.*evaluate|failed.*plan' | tail -10" || echo "  (No errors or log file not accessible)"

# Check planner batch status
echo ""
echo "--- Planner Batch Status ---"
ssh "${ARDUINO_SSH}" "tail -100 ${LOG_FILE} 2>/dev/null | grep -iE 'planner.*batch|generated.*sequences|inserted.*sequences|evaluated' | tail -10" || echo "  (No planner activity or log file not accessible)"

# Check event-based trading
echo ""
echo "--- Event-Based Trading Status ---"
ssh "${ARDUINO_SSH}" "tail -100 ${LOG_FILE} 2>/dev/null | grep -iE 'event.*based.*trading|waiting.*planning|all.*sequences.*evaluated|trade.*execut|executing.*trade' | tail -10" || echo "  (No event-based trading activity or log file not accessible)"

# Check service status
echo ""
echo "--- Service Status ---"
if ssh "${ARDUINO_SSH}" "sudo systemctl is-active trader" >/dev/null 2>&1; then
    echo "✅ trader service is active"
    ssh "${ARDUINO_SSH}" "sudo systemctl status trader --no-pager -l | head -5"
else
    echo "❌ trader service is not active"
fi

echo ""
echo "=== End of Status Check ==="
echo ""
