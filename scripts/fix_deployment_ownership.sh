#!/bin/bash
# Fix deployment directory ownership and create venv

set -e

echo "Fixing deployment directory ownership..."
sudo chown -R arduino:arduino /home/arduino/arduino-trader

echo "Creating virtual environment..."
cd /home/arduino/arduino-trader
python3 -m venv venv

echo "Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo "Verifying installation..."
test -f venv/bin/uvicorn && echo "✅ uvicorn installed successfully" || echo "❌ uvicorn missing"

echo "Restarting service..."
sudo systemctl restart arduino-trader

echo "Waiting for service to start..."
sleep 5

if sudo systemctl is-active arduino-trader > /dev/null; then
    echo "✅ Service is active"
    curl -s http://localhost:8000/health && echo "" && echo "✅ API is responding"
else
    echo "❌ Service failed to start"
    sudo systemctl status arduino-trader --no-pager | head -20
    exit 1
fi
