#!/bin/bash
# Deploy script for Sentinel to Arduino UNO Q
# Usage: ./scripts/deploy.sh [--with-data]

set -e

REMOTE_HOST="arduino@192.168.1.11"
REMOTE_DIR="~/sentinel"
SSH_PASS="aristath"
WITH_DATA=false

# Parse arguments
if [[ "$1" == "--with-data" ]]; then
    WITH_DATA=true
fi

echo "=== Deploying Sentinel ==="

# Create tarball excluding unnecessary files
echo "[1/5] Creating code tarball..."
tar --exclude='.venv' \
    --exclude='data' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='node_modules' \
    --exclude='.pytest_cache' \
    --exclude='*.pyc' \
    --exclude='.DS_Store' \
    --exclude='._*' \
    -czf /tmp/sentinel_code.tar.gz \
    sentinel/ web/ Dockerfile docker-compose.yml pyproject.toml main.py .env 2>/dev/null || true

echo "[2/5] Uploading code to device..."
sshpass -p "$SSH_PASS" scp /tmp/sentinel_code.tar.gz "$REMOTE_HOST:/tmp/"

echo "[3/5] Extracting on device..."
sshpass -p "$SSH_PASS" ssh "$REMOTE_HOST" "mkdir -p $REMOTE_DIR && cd $REMOTE_DIR && tar -xzf /tmp/sentinel_code.tar.gz && rm /tmp/sentinel_code.tar.gz"

if [ "$WITH_DATA" = true ]; then
    echo "[4/5] Syncing data directory..."
    rsync -avz --progress \
        -e "sshpass -p $SSH_PASS ssh" \
        data/ "$REMOTE_HOST:$REMOTE_DIR/data/"
else
    echo "[4/5] Skipping data sync (use --with-data to include)"
fi

echo "[5/5] Rebuilding container..."
sshpass -p "$SSH_PASS" ssh "$REMOTE_HOST" "cd $REMOTE_DIR && docker compose up -d --build"

echo "=== Deploy complete ==="
echo "View logs: sshpass -p '$SSH_PASS' ssh $REMOTE_HOST 'docker logs -f sentinel'"
