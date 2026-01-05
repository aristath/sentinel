#!/bin/bash
#
# Cloudflare Tunnel Setup for Arduino Trader
#
# This script sets up cloudflared to expose the dashboard securely.
# Prerequisites: Cloudflare account with a domain
#

set -e

echo "====================================="
echo "Cloudflare Tunnel Setup"
echo "====================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./cloudflared-setup.sh)"
    exit 1
fi

# Step 1: Install cloudflared
echo ""
echo "Step 1: Installing cloudflared..."

# Detect architecture
ARCH=$(uname -m)
case $ARCH in
    aarch64|arm64)
        CF_ARCH="arm64"
        ;;
    armv7l)
        CF_ARCH="arm"
        ;;
    x86_64)
        CF_ARCH="amd64"
        ;;
    *)
        echo "Unsupported architecture: $ARCH"
        exit 1
        ;;
esac

# Download and install
CLOUDFLARED_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-$CF_ARCH"
curl -L "$CLOUDFLARED_URL" -o /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared

echo "cloudflared installed: $(cloudflared --version)"

# Step 2: Login to Cloudflare
echo ""
echo "Step 2: Authenticating with Cloudflare..."
echo "A browser window will open. Log in and authorize the tunnel."
echo ""
cloudflared tunnel login

# Step 3: Create tunnel
echo ""
echo "Step 3: Creating tunnel..."
read -p "Enter a name for your tunnel (e.g., arduino-trader): " TUNNEL_NAME

cloudflared tunnel create "$TUNNEL_NAME"

# Get tunnel ID
TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
echo "Tunnel created with ID: $TUNNEL_ID"

# Step 4: Create config file
echo ""
echo "Step 4: Creating configuration..."

read -p "Enter your domain (e.g., trader.example.com): " DOMAIN

mkdir -p /etc/cloudflared

cat > /etc/cloudflared/config.yml << EOF
tunnel: $TUNNEL_ID
credentials-file: /root/.cloudflared/$TUNNEL_ID.json

ingress:
  - hostname: $DOMAIN
    service: http://localhost:8001
  - service: http_status:404
EOF

echo "Configuration created at /etc/cloudflared/config.yml"

# Step 5: Create DNS record
echo ""
echo "Step 5: Creating DNS record..."
cloudflared tunnel route dns "$TUNNEL_NAME" "$DOMAIN"

# Step 6: Install as service
echo ""
echo "Step 6: Installing as service..."
cloudflared service install

# Step 7: Start service
echo ""
echo "Step 7: Starting tunnel..."
systemctl start cloudflared
systemctl enable cloudflared

echo ""
echo "====================================="
echo "Cloudflare Tunnel Setup Complete!"
echo "====================================="
echo ""
echo "Your Arduino Trader dashboard is now accessible at:"
echo "https://$DOMAIN"
echo ""
echo "Useful commands:"
echo "  Check status:  systemctl status cloudflared"
echo "  View logs:     journalctl -u cloudflared -f"
echo "  Restart:       systemctl restart cloudflared"
echo ""
