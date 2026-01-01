#!/bin/bash
#
# Arduino Trader - Interactive Installation Script
# Microservices (REST API) Architecture
#
# This script provides an interactive installation experience for the Arduino Trader
# microservices architecture. It supports both fresh installations and modifications
# to existing installations.
#
# Usage: sudo ./install.sh
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Installation state variables
INSTALL_TYPE=""  # "fresh" or "existing"
SELECTED_SERVICES=()
DEVICE_ADDRESSES=()
API_KEY=""
API_SECRET=""

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_SCRIPTS_DIR="${SCRIPT_DIR}/scripts/install"

# Print colored message
print_msg() {
    local color=$1
    shift
    echo -e "${color}$@${NC}"
}

# Print section header
print_header() {
    echo ""
    print_msg "${BLUE}" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    print_msg "${BLUE}" "$1"
    print_msg "${BLUE}" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
}

# Print step
print_step() {
    print_msg "${GREEN}" "[$1/$2] $3"
}

# Print error and exit
error_exit() {
    print_msg "${RED}" "✗ ERROR: $1"
    exit 1
}

# Print success
print_success() {
    print_msg "${GREEN}" "  ✓ $1"
}

# Print warning
print_warning() {
    print_msg "${YELLOW}" "  ⚠ $1"
}

# Check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        error_exit "Please run as root (sudo ./install.sh)"
    fi
}

# Source helper scripts
source_helpers() {
    local scripts=(
        "detect_existing.sh"
        "check_prerequisites.sh"
        "select_services.sh"
        "configure_devices.sh"
        "prompt_config.sh"
        "generate_configs.sh"
        "setup_microservices.sh"
        "validate_installation.sh"
    )

    for script in "${scripts[@]}"; do
        local script_path="${INSTALL_SCRIPTS_DIR}/${script}"
        if [ -f "$script_path" ]; then
            source "$script_path"
        else
            error_exit "Missing installation script: $script"
        fi
    done
}

# Main installation flow
main() {
    # Print welcome banner
    clear
    echo "┌─────────────────────────────────────────┐"
    echo "│  Arduino Trader Interactive Installer   │"
    echo "│  Microservices (REST API) - v1.0        │"
    echo "└─────────────────────────────────────────┘"
    echo ""

    # Check root
    check_root

    # Source helper scripts
    source_helpers

    # Phase 1: Detect existing installation
    print_step 1 9 "Checking for Existing Installation"
    detect_existing_installation

    # Phase 2: Check prerequisites
    print_step 2 9 "Checking Prerequisites"
    check_prerequisites

    # Phase 3: Service selection
    print_step 3 9 "Service Selection"
    select_services

    # Phase 4: Device addresses (if distributed)
    if [ ${#SELECTED_SERVICES[@]} -lt 7 ]; then
        print_step 4 9 "Device Address Configuration"
        configure_device_addresses
    else
        print_msg "${BLUE}" "[4/9] Skipping Device Address Configuration (single-device mode)"
    fi

    # Phase 5: Configuration prompts
    print_step 5 9 "Configuration"
    prompt_configuration

    # Phase 6: Generate config files
    print_step 6 9 "Generating Configuration Files"
    generate_config_files

    # Phase 7: Setup microservices
    print_step 7 9 "Setting Up Microservices"
    setup_microservices

    # Phase 8: Health checks
    print_step 8 9 "Running Health Checks"
    validate_installation

    # Phase 9: Installation summary
    print_step 9 9 "Installation Summary"
    print_installation_summary

    print_msg "${GREEN}" "\n═══════════════════════════════════════════"
    print_msg "${GREEN}" "  Installation Complete!"
    print_msg "${GREEN}" "═══════════════════════════════════════════\n"
}

# Run main
main "$@"
