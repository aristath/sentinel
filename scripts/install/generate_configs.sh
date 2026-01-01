#!/bin/bash
#
# Generate Configuration Files
# Creates .env, device.yaml, and services.yaml from templates and user inputs
#

generate_config_files() {
    local app_dir="/home/arduino/arduino-trader"
    local config_dir="${app_dir}/app/config"

    # Create directories if they don't exist
    mkdir -p "$app_dir" "$config_dir"

    # Backup existing configs
    if [ "$INSTALL_TYPE" = "existing" ]; then
        backup_existing_configs
    fi

    # Generate .env file
    generate_env_file

    # Generate device.yaml
    generate_device_yaml

    # Generate services.yaml
    generate_services_yaml

    print_success "Created .env"
    print_success "Created device.yaml"
    print_success "Created services.yaml"
}

backup_existing_configs() {
    local app_dir="/home/arduino/arduino-trader"
    local timestamp=$(date +%Y%m%d_%H%M%S)

    if [ -f "${app_dir}/.env" ]; then
        cp "${app_dir}/.env" "${app_dir}/.env.backup.${timestamp}"
        print_success "Backed up .env"
    fi

    if [ -f "${app_dir}/app/config/device.yaml" ]; then
        cp "${app_dir}/app/config/device.yaml" "${app_dir}/app/config/device.yaml.backup.${timestamp}"
        print_success "Backed up device.yaml"
    fi

    if [ -f "${app_dir}/app/config/services.yaml" ]; then
        cp "${app_dir}/app/config/services.yaml" "${app_dir}/app/config/services.yaml.backup.${timestamp}"
        print_success "Backed up services.yaml"
    fi
}

generate_env_file() {
    local app_dir="/home/arduino/arduino-trader"
    local env_file="${app_dir}/.env"
    local env_example="${SCRIPT_DIR}/.env.example.microservices"

    # Copy from .env.example.microservices and replace API credentials
    if [ -f "$env_example" ]; then
        cp "$env_example" "$env_file"
    else
        # Create minimal .env if example doesn't exist
        cat > "$env_file" << EOF
# Application
DEBUG=false

# Database
DATABASE_PATH=data/trader.db

# Tradernet API (Freedom24)
TRADERNET_API_KEY=your_api_key_here
TRADERNET_API_SECRET=your_api_secret_here
TRADERNET_BASE_URL=https://api.tradernet.com

# Scheduling
MONTHLY_REBALANCE_DAY=1
DAILY_SYNC_HOUR=18

# LED Display (Arduino Uno Q)
LED_SERIAL_PORT=/dev/ttyACM0
LED_BAUD_RATE=115200

# Investment
MONTHLY_DEPOSIT=1000.0
EOF
    fi

    # Replace API credentials (escape special characters to prevent injection)
    API_KEY_ESCAPED=$(printf '%s\n' "$API_KEY" | sed 's/[\/&]/\\&/g')
    API_SECRET_ESCAPED=$(printf '%s\n' "$API_SECRET" | sed 's/[\/&]/\\&/g')

    sed -i "s/^TRADERNET_API_KEY=.*/TRADERNET_API_KEY=${API_KEY_ESCAPED}/" "$env_file"
    sed -i "s/^TRADERNET_API_SECRET=.*/TRADERNET_API_SECRET=${API_SECRET_ESCAPED}/" "$env_file"

    chmod 600 "$env_file"
}

generate_device_yaml() {
    local config_dir="/home/arduino/arduino-trader/app/config"
    local device_yaml="${config_dir}/device.yaml"

    # Build roles array
    local roles_yaml=""
    for service in "${SELECTED_SERVICES[@]}"; do
        roles_yaml+="    - ${service}\n"
    done

    cat > "$device_yaml" << EOF
device:
  id: primary
  name: Arduino Uno Q - Primary
  roles:
$(echo -e "$roles_yaml")
  network:
    bind_address: 0.0.0.0
    advertise_address: localhost
  resources:
    max_workers: 10
    max_memory_mb: 2048
EOF

    chmod 644 "$device_yaml"
}

generate_services_yaml() {
    local config_dir="/home/arduino/arduino-trader/app/config"
    local services_yaml="${config_dir}/services.yaml"
    local all_services=("planning" "scoring" "optimization" "portfolio" "trading" "universe" "gateway")

    # Start YAML file
    cat > "$services_yaml" << 'EOF'
deployment:
  mode: local

tls:
  enabled: false
  mutual: false

services:
EOF

    # Add each service configuration
    for service in "${all_services[@]}"; do
        local mode="remote"
        local address="localhost"
        local port=$(get_service_port "$service")

        # Check if service is selected (local)
        if [[ " ${SELECTED_SERVICES[@]} " =~ " ${service} " ]]; then
            mode="local"
        else
            # Get address from DEVICE_ADDRESSES
            for entry in "${DEVICE_ADDRESSES[@]}"; do
                if [[ $entry == ${service}:* ]]; then
                    address="${entry#*:}"
                    break
                fi
            done
        fi

        cat >> "$services_yaml" << EOF
  ${service}:
    mode: ${mode}
    port: ${port}
    http_port: ${port}
$(if [ "$mode" = "remote" ]; then echo "    address: ${address}"; fi)
    client:
      timeout_seconds: 30
      max_retries: 3
      retry_backoff_ms: 1000
    health_check:
      enabled: true
      interval_seconds: 30

EOF
    done

    chmod 644 "$services_yaml"
}
