#!/bin/bash
#
# Add reboot cronjob to Arduino device
#
# This script adds a cronjob to reboot the device periodically.
# WARNING: Frequent reboots can disrupt trading operations.
#
# Usage: sudo ./add-reboot-cron.sh [interval_hours]
#        Default: 2 hours
#

set -e

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./add-reboot-cron.sh)"
    exit 1
fi

INTERVAL_HOURS=${1:-2}

if [ "$INTERVAL_HOURS" -lt 1 ] || [ "$INTERVAL_HOURS" -gt 24 ]; then
    echo "Error: Interval must be between 1 and 24 hours"
    exit 1
fi

echo "====================================="
echo "Adding Reboot Cronjob"
echo "====================================="
echo ""
echo "WARNING: This will reboot the device every $INTERVAL_HOURS hours."
echo "This may disrupt trading operations if trades are in progress."
echo ""
read -p "Continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Cancelled."
    exit 0
fi

# Create reboot script that gracefully stops services first
REBOOT_SCRIPT="/home/arduino/bin/graceful-reboot.sh"
cat > "$REBOOT_SCRIPT" << 'EOF'
#!/bin/bash
# Graceful reboot script - stops services before rebooting

LOG_FILE="/home/arduino/logs/reboot.log"
echo "$(date '+%Y-%m-%d %H:%M:%S'): Starting graceful reboot..." >> "$LOG_FILE"

# Stop services gracefully
systemctl stop arduino-trader 2>&1 | tee -a "$LOG_FILE"
systemctl stop led-display 2>&1 | tee -a "$LOG_FILE"

# Wait a moment for services to stop
sleep 2

# Sync filesystem
sync

# Reboot
echo "$(date '+%Y-%m-%d %H:%M:%S'): Rebooting..." >> "$LOG_FILE"
reboot
EOF

chmod +x "$REBOOT_SCRIPT"
chown arduino:arduino "$REBOOT_SCRIPT"

# Calculate cron schedule (every N hours)
# Cron format: minute hour day month weekday
# We'll run at minute 0 of every Nth hour
CRON_SCHEDULE="0 */${INTERVAL_HOURS} * * * $REBOOT_SCRIPT"

# Add to root's crontab (reboot requires root)
(crontab -l 2>/dev/null | grep -v "graceful-reboot.sh"; echo "$CRON_SCHEDULE") | crontab -

echo ""
echo "Reboot cronjob installed:"
echo "  Schedule: Every $INTERVAL_HOURS hours (at minute 0)"
echo "  Script: $REBOOT_SCRIPT"
echo ""
echo "To remove: sudo crontab -e (then delete the graceful-reboot.sh line)"
echo ""
