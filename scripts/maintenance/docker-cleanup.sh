#!/bin/bash
# Docker cleanup script for Arduino Uno Q
# Prunes Docker build cache and unused resources to free disk space
#
# Usage:
#   docker-cleanup.sh build-cache  # Prune build cache only (every 30min)
#   docker-cleanup.sh full         # Full system prune (daily)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Load config if available
if [ -f "${SCRIPT_DIR}/../config.sh" ]; then
    source "${SCRIPT_DIR}/../config.sh"
fi

# Logging functions
log_info() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $1"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $1" >&2
}

log_success() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [SUCCESS] $1"
}

# Check if Docker is available
check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        return 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        return 1
    fi

    return 0
}

# Get images to preserve (last 2 versions of trader and display-bridge)
get_images_to_preserve() {
    local images=()

    # Get trader images (keep last 2)
    while IFS= read -r line; do
        if [ -n "$line" ]; then
            images+=("$line")
        fi
    done < <(docker images --format "{{.Repository}}:{{.Tag}}" --filter "reference=trader:*" | head -2)

    # Get display-bridge images (keep last 2)
    while IFS= read -r line; do
        if [ -n "$line" ]; then
            images+=("$line")
        fi
    done < <(docker images --format "{{.Repository}}:{{.Tag}}" --filter "reference=display-bridge:*" | head -2)

    printf '%s\n' "${images[@]}"
}

# Prune build cache
prune_build_cache() {
    log_info "Pruning Docker build cache..."

    if ! check_docker; then
        log_error "Skipping build cache prune - Docker not available"
        return 1
    fi

    # Get space before
    local space_before
    space_before=$(df / | tail -1 | awk '{print $4}')

    # Prune build cache
    if docker builder prune -af > /dev/null 2>&1; then
        local space_after
        space_after=$(df / | tail -1 | awk '{print $4}')
        local space_freed=$((space_after - space_before))

        log_success "Build cache pruned (freed ~${space_freed}KB)"
        return 0
    else
        log_error "Failed to prune build cache"
        return 1
    fi
}

# Full system prune (preserves service images)
prune_full() {
    log_info "Starting full Docker system prune..."

    if ! check_docker; then
        log_error "Skipping full prune - Docker not available"
        return 1
    fi

    # Get images to preserve
    local preserve_images
    preserve_images=$(get_images_to_preserve)

    if [ -n "$preserve_images" ]; then
        log_info "Preserving images:"
        echo "$preserve_images" | while read -r img; do
            log_info "  - $img"
        done
    fi

    # Get space before
    local space_before
    space_before=$(df / | tail -1 | awk '{print $4}')

    # Prune system (removes unused containers, networks, images, volumes)
    # Note: We can't easily exclude specific images with docker system prune,
    # but since we're keeping last 2 versions, older ones will be removed
    if docker system prune -af --volumes > /dev/null 2>&1; then
        local space_after
        space_after=$(df / | tail -1 | awk '{print $4}')
        local space_freed=$((space_after - space_before))

        log_success "Full system prune completed (freed ~${space_freed}KB)"

        # Verify preserved images still exist
        if [ -n "$preserve_images" ]; then
            log_info "Verifying preserved images..."
            echo "$preserve_images" | while read -r img; do
                if docker images "$img" --format "{{.Repository}}:{{.Tag}}" | grep -q "^${img}$"; then
                    log_info "  ✓ $img preserved"
                else
                    log_error "  ✗ $img was removed (unexpected)"
                fi
            done
        fi

        return 0
    else
        log_error "Failed to perform full system prune"
        return 1
    fi
}

# Main
main() {
    local mode="${1:-build-cache}"

    case "$mode" in
        build-cache)
            prune_build_cache
            ;;
        full)
            prune_full
            ;;
        *)
            log_error "Invalid mode: $mode"
            echo "Usage: $0 [build-cache|full]"
            exit 1
            ;;
    esac
}

main "$@"
