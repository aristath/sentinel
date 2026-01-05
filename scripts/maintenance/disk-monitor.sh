#!/bin/bash
# Disk space monitoring script with LED1 alerts
# Checks root and user filesystem usage and flashes LED1 red if > 90%
#
# Usage:
#   disk-monitor.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# LED1 control paths
LED1_RED="/sys/class/leds/user:red/brightness"
LED1_GREEN="/sys/class/leds/user:green/brightness"
LED1_BLUE="/sys/class/leds/user:blue/brightness"

# Threshold for alert (percentage)
THRESHOLD=90

# Blink interval in seconds (200ms = 0.2s)
BLINK_INTERVAL=0.2

# Logging functions
log_info() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $1"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $1" >&2
}

log_success() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [SUCCESS] $1"
}

# Check if LED1 is available
check_led_available() {
    if [ ! -w "$LED1_RED" ]; then
        return 1
    fi
    return 0
}

# Set LED1 color
set_led1() {
    local r="$1"
    local g="$2"
    local b="$3"
    
    if ! check_led_available; then
        return 1
    fi
    
    # Write brightness values (0-255)
    echo "$r" > "$LED1_RED" 2>/dev/null || return 1
    echo "$g" > "$LED1_GREEN" 2>/dev/null || return 1
    echo "$b" > "$LED1_BLUE" 2>/dev/null || return 1
    
    return 0
}

# Turn LED1 off
led1_off() {
    set_led1 0 0 0
}

# Flash LED1 red (one cycle)
flash_led1_red() {
    set_led1 255 0 0  # Red ON
    sleep "$BLINK_INTERVAL"
    set_led1 0 0 0    # OFF
    sleep "$BLINK_INTERVAL"
}

# Get disk usage percentage for a path
get_disk_usage() {
    local path="$1"
    df "$path" 2>/dev/null | tail -1 | awk '{print $5}' | sed 's/%//' || echo "0"
}

# Check disk usage and control LED
check_and_alert() {
    # Get disk usage for root and user home
    # Use explicit path for user filesystem since script runs as root
    local root_usage
    root_usage=$(get_disk_usage "/")
    local home_usage
    # Explicitly check /home/arduino mount point (separate filesystem)
    home_usage=$(get_disk_usage "/home/arduino")
    
    # Check if either exceeds threshold
    local alert_triggered=0
    local alert_reason=""
    
    if [ "$root_usage" -ge "$THRESHOLD" ]; then
        alert_triggered=1
        alert_reason="root filesystem (${root_usage}%)"
    fi
    
    if [ "$home_usage" -ge "$THRESHOLD" ]; then
        alert_triggered=1
        if [ -n "$alert_reason" ]; then
            alert_reason="${alert_reason} and user filesystem (${home_usage}%)"
        else
            alert_reason="user filesystem (${home_usage}%)"
        fi
    fi
    
    # Control LED based on alert status
    if [ "$alert_triggered" -eq 1 ]; then
        if check_led_available; then
            # Flash red rapidly (one cycle per run - cron will call this every 5 min)
            flash_led1_red
            log_error "DISK SPACE ALERT: ${alert_reason} exceeds ${THRESHOLD}% threshold"
        else
            log_error "DISK SPACE ALERT: ${alert_reason} exceeds ${THRESHOLD}% threshold (LED1 not available)"
        fi
    else
        if check_led_available; then
            # Turn LED off if below threshold
            led1_off
        fi
        log_info "Disk usage OK - root: ${root_usage}%, user: ${home_usage}%"
    fi
}

# Main
main() {
    # Check if running as root (required for LED control)
    if [ "$EUID" -ne 0 ]; then
        log_error "This script must be run as root to control LED1"
        log_error "Usage: sudo $0"
        exit 1
    fi
    
    check_and_alert
}

main "$@"

