#!/bin/bash
#
# Configure Device Addresses
# For distributed deployments, collect IP addresses of remote services
#

configure_device_addresses() {
    local all_services=("planning" "scoring" "optimization" "portfolio" "trading" "universe" "gateway")
    local remote_services=()

    # Determine which services are remote (not in SELECTED_SERVICES)
    for service in "${all_services[@]}"; do
        if [[ ! " ${SELECTED_SERVICES[@]} " =~ " ${service} " ]]; then
            remote_services+=("$service")
        fi
    done

    if [ ${#remote_services[@]} -eq 0 ]; then
        # All services are local
        return
    fi

    echo ""
    echo "Where are these services running?"
    echo ""

    # Collect addresses for each remote service
    local service_addresses=()
    declare -A address_map

    for service in "${remote_services[@]}"; do
        local service_port=$(get_service_port "$service")
        local address=""
        local existing_address=""

        # Check if we already have an address for this service
        if [ "$INSTALL_TYPE" = "existing" ]; then
            existing_address=$(get_existing_service_address "$service")
        fi

        if [ -n "$existing_address" ]; then
            echo "  $service (HTTP $service_port):"
            read -p "    Device address [$existing_address]: " address
            address=${address:-$existing_address}
        else
            while true; do
                echo "  $service (HTTP $service_port):"
                read -p "    Device address [192.168.1.x]: " address

                if [ -z "$address" ]; then
                    print_warning "Address cannot be empty"
                    continue
                fi

                # Validate IP format
                if ! validate_ip "$address"; then
                    print_warning "Invalid IP address format"
                    continue
                fi

                break
            done
        fi

        # Test connectivity
        if test_connectivity "$address" "$service_port"; then
            print_success "Connection test passed"
        else
            print_warning "Cannot connect to $address:$service_port (service may not be running yet)"
        fi

        # Store address
        address_map["$service"]="$address"
        service_addresses+=("$service:$address")

        # Check if other services use the same address
        local same_device_services=()
        for other_service in "${remote_services[@]}"; do
            if [ "$other_service" != "$service" ] && [ -z "${address_map[$other_service]}" ]; then
                # Ask if this service is on the same device
                read -p "  Is $other_service also on $address? [y/N]: " -n 1 -r
                echo ""
                if [[ $REPLY =~ ^[Yy]$ ]]; then
                    address_map["$other_service"]="$address"
                    same_device_services+=("$other_service")
                    service_addresses+=("$other_service:$address")
                fi
            fi
        done

        if [ ${#same_device_services[@]} -gt 0 ]; then
            print_msg "${BLUE}" "  → Also using $address: ${same_device_services[*]}"
        fi
    done

    # Store device addresses for config generation
    DEVICE_ADDRESSES=("${service_addresses[@]}")

    echo ""
    print_msg "${BLUE}" "→ Remote service configuration:"
    for entry in "${service_addresses[@]}"; do
        print_msg "${BLUE}" "  - $entry"
    done
}

get_service_port() {
    case $1 in
        "universe") echo "8001" ;;
        "portfolio") echo "8002" ;;
        "trading") echo "8003" ;;
        "scoring") echo "8004" ;;
        "optimization") echo "8005" ;;
        "planning") echo "8006" ;;
        "gateway") echo "8007" ;;
        *) echo "8001" ;;
    esac
}

get_existing_service_address() {
    local service=$1
    local services_config="/home/arduino/arduino-trader/app/config/services.yaml"

    if [ -f "$services_config" ] && command -v yq &> /dev/null; then
        yq ".services.$service.address" "$services_config" 2>/dev/null | grep -v "null"
    fi
}

validate_ip() {
    local ip=$1
    if [[ $ip =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
        return 0
    fi
    return 1
}

test_connectivity() {
    local address=$1
    local port=$2

    # Try ping first
    if ping -c 1 -W 1 "$address" &> /dev/null; then
        # Try curl if service is running
        if curl -s --connect-timeout 2 "http://$address:$port/health" &> /dev/null; then
            return 0
        fi
        # Ping succeeded but service not responding (may not be set up yet)
        return 0
    fi

    return 1
}
