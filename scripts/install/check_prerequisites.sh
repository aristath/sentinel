#!/bin/bash
#
# Check Prerequisites
# Validates that all required tools and resources are available
#

check_prerequisites() {
    local failed=0

    # Check Python 3.10+
    if command -v python3 &> /dev/null; then
        local python_version=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
        local python_major=$(echo "$python_version" | cut -d. -f1)
        local python_minor=$(echo "$python_version" | cut -d. -f2)

        if [ "$python_major" -ge 3 ] && [ "$python_minor" -ge 10 ]; then
            print_success "Python $(python3 --version | cut -d' ' -f2) installed"
        else
            print_warning "Python $python_version found, but 3.10+ required"
            failed=1
        fi
    else
        print_warning "Python 3 not found"
        failed=1
    fi

    # Check Docker
    if command -v docker &> /dev/null; then
        print_success "Docker $(docker --version | cut -d' ' -f3 | tr -d ',') installed"
    else
        print_warning "Docker not found"
        failed=1
    fi

    # Check Docker Compose
    if docker compose version &> /dev/null; then
        print_success "Docker Compose available"
    elif command -v docker-compose &> /dev/null; then
        print_success "Docker Compose (standalone) available"
    else
        print_warning "Docker Compose not found"
        failed=1
    fi

    # Check git
    if command -v git &> /dev/null; then
        print_success "Git installed"
    else
        print_warning "Git not found"
        failed=1
    fi

    # Check disk space (min 1.5GB)
    local available_space=$(df -BG . | tail -1 | awk '{print $4}' | tr -d 'G')
    if [ "$available_space" -ge 2 ]; then
        print_success "$available_space GB free disk space"
    else
        print_warning "Only $available_space GB free (minimum 2GB recommended)"
    fi

    # Check ports (if fresh install or all services selected)
    if [ "$INSTALL_TYPE" = "fresh" ] || [ ${#SELECTED_SERVICES[@]} -eq 7 ]; then
        check_port_availability
    fi

    # Offer to install Arduino CLI if not present
    if ! command -v arduino-cli &> /dev/null; then
        print_warning "Arduino CLI not installed (required for LED display setup)"
        echo ""
        read -p "Install Arduino CLI now? [y/N]: " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            install_arduino_cli
        fi
    else
        print_success "Arduino CLI installed"
    fi

    if [ $failed -ne 0 ]; then
        error_exit "Prerequisites check failed. Please install missing requirements."
    fi
}

check_port_availability() {
    local ports=(8000 8001 8002 8003 8004 8005 8007)
    local ports_in_use=()

    for port in "${ports[@]}"; do
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
            ports_in_use+=($port)
        fi
    done

    if [ ${#ports_in_use[@]} -gt 0 ]; then
        print_warning "Ports in use: ${ports_in_use[*]}"
        echo "  These services may need to be stopped before installation."
    else
        print_success "HTTP ports 8000-8007 available"
    fi
}

install_arduino_cli() {
    print_msg "${BLUE}" "Installing Arduino CLI..."

    local install_dir="/usr/local/bin"
    local tmp_dir=$(mktemp -d)
    local install_script="${tmp_dir}/arduino-install.sh"

    cd "$tmp_dir"

    # Download install script (don't pipe to shell - security risk)
    print_msg "${BLUE}" "Downloading Arduino CLI installer..."
    if ! curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh -o "$install_script"; then
        print_warning "Failed to download Arduino CLI installer"
        cd - > /dev/null
        rm -rf "$tmp_dir"
        return 1
    fi

    # Execute downloaded script
    bash "$install_script"

    if [ -f "bin/arduino-cli" ]; then
        sudo mv bin/arduino-cli "$install_dir/"
        sudo chmod +x "$install_dir/arduino-cli"
        print_success "Arduino CLI installed successfully"
    else
        print_warning "Arduino CLI installation failed"
    fi

    cd - > /dev/null
    rm -rf "$tmp_dir"
}
