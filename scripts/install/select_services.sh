#!/bin/bash
#
# Service Selection
# Interactive selection of which services to run on this device
#

select_services() {
    local all_services=("planning" "scoring" "optimization" "portfolio" "trading" "universe" "gateway")
    local service_ports=("8006" "8004" "8005" "8002" "8003" "8001" "8007")
    local current_services=()

    # If existing install, read current services
    if [ "$INSTALL_TYPE" = "existing" ]; then
        local device_config="/home/arduino/arduino-trader/app/config/device.yaml"
        if [ -f "$device_config" ] && command -v yq &> /dev/null; then
            current_services=($(yq '.device.roles[]' "$device_config" 2>/dev/null))
        fi
    fi

    echo ""
    echo "Which services should run on THIS device?"
    echo ""

    # Display services with current status
    for i in "${!all_services[@]}"; do
        local service="${all_services[$i]}"
        local port="${service_ports[$i]}"
        local num=$((i + 1))
        local status=""

        if [ "$INSTALL_TYPE" = "existing" ]; then
            if [[ " ${current_services[@]} " =~ " ${service} " ]]; then
                status="  Currently: LOCAL"
            else
                status="  Currently: REMOTE"
            fi
        fi

        printf "  [%d] %-15s (HTTP %s)%s\n" "$num" "$service" "$port" "$status"
    done

    echo ""
    echo "Options:"
    echo "  - Enter numbers (e.g., 1,2,6,7 for Planning, Scoring, Universe, Gateway)"
    echo "  - Enter 'all' for single-device deployment (all 7 services)"
    echo ""

    # Get user selection
    local selection=""
    while true; do
        read -p "Select: " selection

        if [ "$selection" = "all" ]; then
            SELECTED_SERVICES=("${all_services[@]}")
            echo ""
            print_msg "${GREEN}" "→ Running ALL services on this device (single-device mode)"
            print_msg "${GREEN}" "→ Ports 8001-8007 will be used (Gateway also exposed on 8000)"
            break
        else
            # Parse comma-separated numbers
            IFS=',' read -ra numbers <<< "$selection"
            local valid=true
            SELECTED_SERVICES=()

            for num in "${numbers[@]}"; do
                # Trim whitespace
                num=$(echo "$num" | xargs)

                if [[ "$num" =~ ^[1-7]$ ]]; then
                    local idx=$((num - 1))
                    SELECTED_SERVICES+=("${all_services[$idx]}")
                else
                    echo "Invalid selection: $num"
                    valid=false
                    break
                fi
            done

            if $valid && [ ${#SELECTED_SERVICES[@]} -gt 0 ]; then
                echo ""
                print_msg "${GREEN}" "→ Selected: ${SELECTED_SERVICES[*]} (${#SELECTED_SERVICES[@]} services)"

                if [ ${#SELECTED_SERVICES[@]} -lt 7 ]; then
                    # Distributed mode
                    local unselected=()
                    for service in "${all_services[@]}"; do
                        if [[ ! " ${SELECTED_SERVICES[@]} " =~ " ${service} " ]]; then
                            unselected+=("$service")
                        fi
                    done
                    print_msg "${YELLOW}" "→ Moving to other devices: ${unselected[*]} (${#unselected[@]} services)"
                    print_msg "${BLUE}" "→ Deployment mode: DISTRIBUTED"
                fi
                break
            else
                echo "Invalid selection. Please try again."
            fi
        fi
    done

    # Validate that gateway is selected if not all services
    if [ ${#SELECTED_SERVICES[@]} -lt 7 ]; then
        if [[ ! " ${SELECTED_SERVICES[@]} " =~ " gateway " ]]; then
            print_warning "Gateway service not selected. At least one device must run the gateway."
            read -p "Continue anyway? [y/N]: " -n 1 -r
            echo ""
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                select_services  # Restart selection
                return
            fi
        fi
    fi
}
