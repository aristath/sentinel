#!/bin/bash
# Quick sync code without full rebuild
# Use when only Python code changed (not dependencies)
# Usage: ./scripts/sync-code.sh

set -e

REMOTE_HOST="arduino@192.168.1.11"
REMOTE_DIR="~/sentinel"
SSH_PASS="aristath"

echo "=== Syncing code ==="

# Sync Python code only
tar --exclude='__pycache__' --exclude='*.pyc' -czf /tmp/sentinel_py.tar.gz sentinel/ main.py

sshpass -p "$SSH_PASS" scp /tmp/sentinel_py.tar.gz "$REMOTE_HOST:/tmp/"
sshpass -p "$SSH_PASS" ssh "$REMOTE_HOST" "cd $REMOTE_DIR && tar -xzf /tmp/sentinel_py.tar.gz && rm /tmp/sentinel_py.tar.gz"

echo "Restarting container..."
sshpass -p "$SSH_PASS" ssh "$REMOTE_HOST" "docker restart sentinel"

echo "=== Done ==="
