#!/bin/bash
# Script to add package comments to Go packages

set -e

cd "$(dirname "$0")/.." || exit 1

# Function to add package comment to first .go file in a package
add_package_comment() {
    local pkg_path="$1"
    local comment="$2"

    # Find first non-test .go file in package
    local first_file=$(find "$pkg_path" -maxdepth 1 -name "*.go" ! -name "*_test.go" | sort | head -1)

    if [ -z "$first_file" ]; then
        echo "No .go files found in $pkg_path"
        return
    fi

    # Check if package comment already exists
    if grep -q "^// Package " "$first_file"; then
        echo "Package comment already exists in $first_file"
        return
    fi

    # Get package name
    local pkg_name=$(grep "^package " "$first_file" | head -1 | awk '{print $2}')

    if [ -z "$pkg_name" ]; then
        echo "Could not find package name in $first_file"
        return
    fi

    # Add package comment before package declaration
    # Create temp file with comment
    {
        echo "// $comment"
        echo "package $pkg_name"
        tail -n +2 "$first_file"
    } > "$first_file.tmp" && mv "$first_file.tmp" "$first_file"

    echo "Added package comment to $first_file"
}

# Add comments to packages (paths relative to project root)
add_package_comment "internal/modules/charts" "Package charts provides charting and visualization functionality."
add_package_comment "internal/modules/cleanup" "Package cleanup provides data cleanup and maintenance functionality."
add_package_comment "internal/modules/display" "Package display provides display and monitoring functionality."
add_package_comment "internal/modules/dividends" "Package dividends provides dividend tracking and management functionality."
add_package_comment "internal/modules/evaluation" "Package evaluation provides evaluation functionality for portfolio analysis."
add_package_comment "internal/modules/market_hours" "Package market_hours provides market hours and trading schedule functionality."
add_package_comment "internal/modules/opportunities" "Package opportunities provides trading opportunity identification functionality."
add_package_comment "internal/modules/optimization" "Package optimization provides portfolio optimization functionality."
add_package_comment "internal/modules/planning" "Package planning provides portfolio planning and strategy generation functionality."
add_package_comment "internal/modules/portfolio" "Package portfolio provides portfolio management functionality."
add_package_comment "internal/modules/quantum" "Package quantum provides quantum probability models for asset returns."
add_package_comment "internal/modules/rebalancing" "Package rebalancing provides portfolio rebalancing functionality."
add_package_comment "internal/modules/scoring" "Package scoring provides security scoring functionality."
add_package_comment "internal/modules/sequences" "Package sequences provides trading sequence generation functionality."
add_package_comment "internal/modules/settings" "Package settings provides application settings management functionality."
add_package_comment "internal/modules/symbolic_regression" "Package symbolic_regression provides symbolic regression for formula discovery."
add_package_comment "internal/modules/trading" "Package trading provides trade execution functionality."
add_package_comment "internal/modules/universe" "Package universe provides security universe management functionality."
add_package_comment "internal/reliability" "Package reliability provides reliability and monitoring functionality."
add_package_comment "internal/scheduler" "Package scheduler provides job scheduling functionality."
add_package_comment "internal/server" "Package server provides HTTP server and routing functionality."
add_package_comment "internal/services" "Package services provides core business services."
add_package_comment "internal/ticker" "Package ticker provides ticker and streaming functionality."
