#!/bin/bash
# Deploy Arduino Trader to a specific device

set -e

# Check arguments
if [ $# -lt 2 ]; then
    echo "Usage: $0 <device_name> <device_ip>"
    echo ""
    echo "Example:"
    echo "  $0 device1 192.168.1.10"
    echo "  $0 device2 192.168.1.11"
    exit 1
fi

DEVICE_NAME=$1
DEVICE_IP=$2
DEVICE_USER=${3:-arduino}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Deploying Arduino Trader to $DEVICE_NAME ($DEVICE_IP)..."
echo "======================================================"

# Check if we can reach the device
if ! ping -c 1 -W 2 "$DEVICE_IP" &> /dev/null; then
    echo "ERROR: Cannot reach device at $DEVICE_IP"
    exit 1
fi

echo "✓ Device is reachable"

# Check if SSH works
if ! ssh -o ConnectTimeout=5 "$DEVICE_USER@$DEVICE_IP" "echo 'SSH connection successful'" &> /dev/null; then
    echo "ERROR: Cannot SSH to $DEVICE_USER@$DEVICE_IP"
    echo "  Make sure SSH is enabled and you have the correct credentials"
    exit 1
fi

echo "✓ SSH connection successful"

# Create remote directory
echo "Creating remote directory..."
ssh "$DEVICE_USER@$DEVICE_IP" "mkdir -p /home/$DEVICE_USER/arduino-trader"

# Sync code to device
echo "Syncing code to device..."
rsync -av --delete \
    --exclude 'venv/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.git/' \
    --exclude 'data/' \
    --exclude 'logs/' \
    "$PROJECT_ROOT/" \
    "$DEVICE_USER@$DEVICE_IP:/home/$DEVICE_USER/arduino-trader/"

echo "✓ Code synced successfully"

# Copy device-specific configuration
CONFIG_DIR="$PROJECT_ROOT/deploy/configs/dual-device"
if [ -f "$CONFIG_DIR/$DEVICE_NAME.yaml" ]; then
    echo "Copying device configuration..."
    scp "$CONFIG_DIR/$DEVICE_NAME.yaml" \
        "$DEVICE_USER@$DEVICE_IP:/home/$DEVICE_USER/arduino-trader/app/config/device.yaml"

    scp "$CONFIG_DIR/services.yaml" \
        "$DEVICE_USER@$DEVICE_IP:/home/$DEVICE_USER/arduino-trader/app/config/services.yaml"

    echo "✓ Configuration copied"
else
    echo "WARNING: No device-specific config found at $CONFIG_DIR/$DEVICE_NAME.yaml"
fi

# Install dependencies on remote device
echo "Installing dependencies on device..."
ssh "$DEVICE_USER@$DEVICE_IP" "cd /home/$DEVICE_USER/arduino-trader && \
    python3 -m venv venv && \
    source venv/bin/activate && \
    pip install --upgrade pip && \
    pip install -r requirements.txt"

echo "✓ Dependencies installed"

# Generate protobuf files
echo "Generating protobuf files on device..."
ssh "$DEVICE_USER@$DEVICE_IP" "cd /home/$DEVICE_USER/arduino-trader && \
    source venv/bin/activate && \
    ./scripts/generate_protos.sh"

echo "✓ Protobuf files generated"

# Start services
echo "Starting services on device..."
ssh "$DEVICE_USER@$DEVICE_IP" "cd /home/$DEVICE_USER/arduino-trader && \
    ./scripts/start_services_for_device.sh"

echo "✓ Services started"

echo ""
echo "======================================================"
echo "Deployment to $DEVICE_NAME ($DEVICE_IP) complete!"
echo ""
echo "To check service health:"
echo "  ssh $DEVICE_USER@$DEVICE_IP 'cd arduino-trader && ./scripts/health_check.sh'"
echo ""
echo "To view logs:"
echo "  ssh $DEVICE_USER@$DEVICE_IP 'tail -f arduino-trader/logs/*.log'"
