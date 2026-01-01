#!/bin/bash
# Start gRPC services for the current device based on device.yaml configuration

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Load device configuration
DEVICE_CONFIG="${DEVICE_CONFIG_PATH:-app/config/device.yaml}"
SERVICES_CONFIG="${SERVICES_CONFIG_PATH:-app/config/services.yaml}"

if [ ! -f "$DEVICE_CONFIG" ]; then
    echo "ERROR: Device config not found at $DEVICE_CONFIG"
    exit 1
fi

if [ ! -f "$SERVICES_CONFIG" ]; then
    echo "ERROR: Services config not found at $SERVICES_CONFIG"
    exit 1
fi

echo "Starting services for this device..."
echo "Device config: $DEVICE_CONFIG"
echo "Services config: $SERVICES_CONFIG"

# Parse device ID from config
DEVICE_ID=$(grep "^device_id:" "$DEVICE_CONFIG" | awk '{print $2}' | tr -d '"')
echo "Device ID: $DEVICE_ID"

# Find which services should run on this device
# Services with mode: "local" or device_id matching this device
SERVICES_TO_START=()

for service in planning scoring optimization portfolio trading universe gateway; do
    # Check if service should run on this device
    SERVICE_MODE=$(grep -A 5 "^  $service:" "$SERVICES_CONFIG" | grep "mode:" | awk '{print $2}')
    SERVICE_DEVICE=$(grep -A 5 "^  $service:" "$SERVICES_CONFIG" | grep "device_id:" | awk '{print $2}' | tr -d '"')

    if [ "$SERVICE_MODE" = "local" ] || [ "$SERVICE_DEVICE" = "$DEVICE_ID" ]; then
        SERVICES_TO_START+=("$service")
    fi
done

echo "Services to start on this device: ${SERVICES_TO_START[@]}"

# Start each service
for service in "${SERVICES_TO_START[@]}"; do
    echo "Starting $service service..."

    # Start service in background
    python -m services.$service.main &
    SERVICE_PID=$!

    echo "  Started $service (PID: $SERVICE_PID)"

    # Wait a bit before starting next service
    sleep 2
done

echo ""
echo "✓ All services started successfully!"
echo "  Use './deploy/scripts/check-services-status.sh' to check health"
echo "  Use 'pkill -f \"services.*main\"' to stop all services"
