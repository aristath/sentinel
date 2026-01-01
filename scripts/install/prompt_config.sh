#!/bin/bash
#
# Configuration Prompts
# Collect required configuration (API credentials only)
#

prompt_configuration() {
    echo ""

    # Check if we have existing credentials
    if [ "$INSTALL_TYPE" = "existing" ]; then
        local env_file="/home/arduino/arduino-trader/.env"
        if [ -f "$env_file" ]; then
            local existing_key=$(grep "^TRADERNET_API_KEY=" "$env_file" | cut -d'=' -f2)
            if [ -n "$existing_key" ]; then
                local masked_key="${existing_key:0:4}...${existing_key: -4}"
                echo "Tradernet API credentials:"
                echo "  Current API Key: $masked_key"
                read -p "  Keep existing credentials? [Y/n]: " -n 1 -r
                echo ""

                if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                    # Keep existing credentials
                    API_KEY="$existing_key"
                    API_SECRET=$(grep "^TRADERNET_API_SECRET=" "$env_file" | cut -d'=' -f2)
                    print_msg "${BLUE}" "→ Using existing Tradernet API credentials"
                    return
                fi
            fi
        fi
    fi

    # Prompt for new credentials
    echo "Tradernet API credentials (required to connect to broker):"

    while true; do
        read -p "  API Key: " API_KEY
        if [ -z "$API_KEY" ]; then
            print_warning "API Key cannot be empty"
            continue
        fi
        if [ ${#API_KEY} -lt 16 ]; then
            print_warning "API Key seems too short (minimum 16 characters)"
            continue
        fi
        break
    done

    while true; do
        read -p "  API Secret: " API_SECRET
        if [ -z "$API_SECRET" ]; then
            print_warning "API Secret cannot be empty"
            continue
        fi
        if [ ${#API_SECRET} -lt 16 ]; then
            print_warning "API Secret seems too short (minimum 16 characters)"
            continue
        fi
        break
    done

    echo ""
    print_msg "${BLUE}" "All other settings use defaults from .env.example."
    print_msg "${BLUE}" "You can change them later via Settings UI or by editing .env"
}
