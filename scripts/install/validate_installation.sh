#!/bin/bash
#
# Validate Installation
# Performs health checks on installed services
#

validate_installation() {
    echo ""
    print_msg "${BLUE}" "  Waiting for services to start (10s)..."
    sleep 10

    local all_healthy=true

    # Test local services
    if [ ${#SELECTED_SERVICES[@]} -gt 0 ]; then
        echo ""
        print_msg "${BLUE}" "  Local services:"
        for service in "${SELECTED_SERVICES[@]}"; do
            if test_service_health "$service" "localhost"; then
                print_success "$service: HEALTHY"
            else
                print_warning "$service: NOT RESPONDING"
                all_healthy=false
            fi
        done
    fi

    # Test remote services
    local remote_services=()
    local all_services=("planning" "scoring" "optimization" "portfolio" "trading" "universe" "gateway")

    for service in "${all_services[@]}"; do
        if [[ ! " ${SELECTED_SERVICES[@]} " =~ " ${service} " ]]; then
            remote_services+=("$service")
        fi
    done

    if [ ${#remote_services[@]} -gt 0 ]; then
        echo ""
        print_msg "${BLUE}" "  Remote services:"
        for service in "${remote_services[@]}"; do
            local address=$(get_remote_service_address "$service")
            if [ -n "$address" ]; then
                if test_service_health "$service" "$address"; then
                    print_success "$service ($address): HEALTHY"
                else
                    print_warning "$service ($address): NOT RESPONDING"
                fi
            fi
        done
    fi

    echo ""
    if $all_healthy; then
        print_msg "${GREEN}" "  ✓ All services healthy!"
    else
        print_warning "Some services are not responding. Check logs with: docker compose logs"
    fi
}

test_service_health() {
    local service=$1
    local host=$2
    local port=$(get_service_port "$service")

    # Try HTTP health endpoint
    if curl -s -f --connect-timeout 5 "http://${host}:${port}/health" > /dev/null 2>&1; then
        return 0
    fi

    # Fallback: check if port is listening
    if nc -z "$host" "$port" 2>/dev/null; then
        return 0
    fi

    return 1
}

get_remote_service_address() {
    local service=$1

    for entry in "${DEVICE_ADDRESSES[@]}"; do
        if [[ $entry == ${service}:* ]]; then
            echo "${entry#*:}"
            return
        fi
    done
}
