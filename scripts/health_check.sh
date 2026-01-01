#!/bin/bash
# Health check for all gRPC services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Services and their ports
declare -A SERVICES=(
    ["planning"]="50051"
    ["scoring"]="50052"
    ["optimization"]="50053"
    ["portfolio"]="50054"
    ["trading"]="50055"
    ["universe"]="50056"
    ["gateway"]="50057"
)

# Check if grpcurl is installed
if ! command -v grpcurl &> /dev/null; then
    echo "${YELLOW}Warning: grpcurl not installed. Install with: brew install grpcurl${NC}"
    echo "Falling back to port checks only..."
    GRPCURL_AVAILABLE=false
else
    GRPCURL_AVAILABLE=true
fi

echo "Checking health of all services..."
echo "=================================="

HEALTHY_COUNT=0
TOTAL_COUNT=0

for service in "${!SERVICES[@]}"; do
    port="${SERVICES[$service]}"
    TOTAL_COUNT=$((TOTAL_COUNT + 1))

    # Check if port is listening
    if ! nc -z localhost "$port" 2>/dev/null; then
        echo -e "${RED}✗${NC} $service (port $port): NOT RUNNING"
        continue
    fi

    # If grpcurl is available, try health check
    if [ "$GRPCURL_AVAILABLE" = true ]; then
        # Try health check (different services may have different RPC names)
        if timeout 2 grpcurl -plaintext localhost:$port list >/dev/null 2>&1; then
            echo -e "${GREEN}✓${NC} $service (port $port): HEALTHY"
            HEALTHY_COUNT=$((HEALTHY_COUNT + 1))
        else
            echo -e "${YELLOW}⚠${NC} $service (port $port): LISTENING (health check failed)"
        fi
    else
        echo -e "${GREEN}✓${NC} $service (port $port): LISTENING"
        HEALTHY_COUNT=$((HEALTHY_COUNT + 1))
    fi
done

echo "=================================="
echo "Health check complete: $HEALTHY_COUNT/$TOTAL_COUNT services healthy"

if [ $HEALTHY_COUNT -eq $TOTAL_COUNT ]; then
    echo -e "${GREEN}All services are healthy!${NC}"
    exit 0
elif [ $HEALTHY_COUNT -gt 0 ]; then
    echo -e "${YELLOW}Some services are not healthy${NC}"
    exit 1
else
    echo -e "${RED}No services are running!${NC}"
    exit 2
fi
