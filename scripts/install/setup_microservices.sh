#!/bin/bash
#
# Setup Microservices
# Builds and starts Docker containers for selected services
#

setup_microservices() {
    local app_dir="/home/arduino/arduino-trader"

    # Copy application files if not already there
    if [ ! -d "${app_dir}/app" ]; then
        print_msg "${BLUE}" "  Copying application files..."
        cp -r "${SCRIPT_DIR}/app" "$app_dir/"
        cp -r "${SCRIPT_DIR}/services" "$app_dir/"
        cp -r "${SCRIPT_DIR}/static" "$app_dir/" 2>/dev/null || true
        cp "${SCRIPT_DIR}/docker-compose.yml" "$app_dir/"
        cp "${SCRIPT_DIR}/requirements.txt" "$app_dir/"
        print_success "Application files copied"
    fi

    # Stop existing containers if modifying
    if [ "$INSTALL_TYPE" = "existing" ]; then
        print_msg "${BLUE}" "  Stopping existing containers..."
        cd "$app_dir"
        docker compose down 2>/dev/null || docker-compose down 2>/dev/null || true
        print_success "Stopped existing containers"
    fi

    # Build and start selected services
    cd "$app_dir"

    print_msg "${BLUE}" "  Building Docker images (this may take 5-10 minutes)..."
    local build_services=$(echo "${SELECTED_SERVICES[@]}" | tr ' ' '\n')

    # Build images
    if docker compose version &> /dev/null; then
        docker compose build ${SELECTED_SERVICES[@]}
    else
        docker-compose build ${SELECTED_SERVICES[@]}
    fi

    print_success "Docker images built"

    # Start services
    print_msg "${BLUE}" "  Starting services..."
    for service in "${SELECTED_SERVICES[@]}"; do
        print_msg "${BLUE}" "    - ${service}"
    done

    if docker compose version &> /dev/null; then
        docker compose up -d ${SELECTED_SERVICES[@]}
    else
        docker-compose up -d ${SELECTED_SERVICES[@]}
    fi

    print_success "Services started"

    # Setup systemd service for auto-start (optional)
    setup_systemd_service
}

setup_systemd_service() {
    local service_file="/etc/systemd/system/arduino-trader.service"

    # Only setup on Arduino Uno Q
    if [ ! -d "/home/arduino" ]; then
        return
    fi

    cat > "$service_file" << 'EOF'
[Unit]
Description=Arduino Trader Microservices
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/arduino/arduino-trader
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
User=arduino
Group=arduino

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable arduino-trader.service

    print_success "Systemd service configured"
}

print_installation_summary() {
    local app_url="http://localhost:8000"

    if [ ${#SELECTED_SERVICES[@]} -eq 7 ]; then
        echo "Mode: Single-device (all services)"
    else
        echo "Mode: Distributed (${#SELECTED_SERVICES[@]} local services)"
    fi

    echo "Path: /home/arduino/arduino-trader"
    echo "Services: ${SELECTED_SERVICES[*]}"
    echo ""
    echo "Access:"
    echo "  Web Dashboard:    $app_url"
    echo "  API Docs:         $app_url/docs"
    echo ""
    echo "Manage Services:"
    echo "  Start:   docker compose up -d"
    echo "  Stop:    docker compose down"
    echo "  Logs:    docker compose logs -f"
    echo ""
}
