#!/bin/bash
# Pre-commit hook script to build frontend and stage dist/ files
# This script is called by pre-commit when frontend files change

set -e

FRONTEND_DIR="frontend"
DIST_DIR="${FRONTEND_DIR}/dist"

# Check if any frontend source files are staged (excluding dist/ and node_modules/)
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E "^${FRONTEND_DIR}/" | grep -vE "^${FRONTEND_DIR}/(dist/|node_modules/)" || true)

if [ -z "$STAGED_FILES" ]; then
    # No frontend source files changed, skip build
    exit 0
fi

# Check if dist/ files are already staged (avoid rebuilding if only dist/ changed)
STAGED_DIST=$(git diff --cached --name-only --diff-filter=ACM | grep -E "^${FRONTEND_DIR}/dist/" || true)

if [ -n "$STAGED_DIST" ] && [ -z "$(echo "$STAGED_FILES" | grep -vE "^${FRONTEND_DIR}/dist/")" ]; then
    # Only dist/ files are staged, no source changes, skip build
    exit 0
fi

echo "Frontend source files changed, building frontend..."

# Change to frontend directory
cd "$FRONTEND_DIR" || exit 1

# Check if node_modules exists, install if needed
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

# Build frontend
echo "Building frontend..."
npm run build

# Stage the dist/ directory
echo "Staging built frontend files..."
cd - > /dev/null || exit 1
git add "${DIST_DIR}/"

echo "Frontend built and staged successfully."
