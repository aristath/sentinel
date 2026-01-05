#!/bin/bash
# System cleanup script for Arduino Uno Q
# Performs system-level cleanup: apt-get, journalctl, old kernels, Docker logs
# This script requires root privileges
#
# Usage:
#   sudo system-cleanup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run as root" >&2
    echo "Usage: sudo $0" >&2
    exit 1
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

# Clean apt-get cache
clean_apt_cache() {
    log_info "Cleaning apt-get cache..."

    if ! command -v apt-get &> /dev/null; then
        log_info "apt-get is not available, skipping"
        return 0
    fi

    # Get space before
    local space_before
    space_before=$(df / | tail -1 | awk '{print $4}')

    # Clean apt cache
    if apt-get clean > /dev/null 2>&1 && apt-get autoclean > /dev/null 2>&1; then
        local space_after
        space_after=$(df / | tail -1 | awk '{print $4}')
        local space_freed=$((space_after - space_before))

        log_success "apt-get cache cleaned (freed ~${space_freed}KB)"
    else
        log_error "Failed to clean apt-get cache"
    fi
}

# Vacuum journal logs
vacuum_journal() {
    log_info "Vacuuming systemd journal logs (limit to 100MB)..."

    if ! command -v journalctl &> /dev/null; then
        log_info "journalctl is not available, skipping"
        return 0
    fi

    # Get journal size before
    local size_before=0
    if [ -d /var/log/journal ]; then
        size_before=$(du -sk /var/log/journal 2>/dev/null | awk '{print $1}' || echo "0")
    fi

    # Vacuum journal
    if journalctl --vacuum-size=100M > /dev/null 2>&1; then
        local size_after=0
        if [ -d /var/log/journal ]; then
            size_after=$(du -sk /var/log/journal 2>/dev/null | awk '{print $1}' || echo "0")
        fi
        local size_freed=$((size_before - size_after))

        log_success "Journal logs vacuumed (freed ~${size_freed}KB)"
    else
        log_error "Failed to vacuum journal logs"
    fi
}

# Remove old kernels (keep last 2)
remove_old_kernels() {
    log_info "Removing old kernels (keeping last 2)..."

    if ! command -v dpkg &> /dev/null || ! command -v apt-get &> /dev/null; then
        log_info "dpkg/apt-get not available, skipping kernel removal"
        return 0
    fi

    # Get list of installed kernel images
    local kernels
    kernels=$(dpkg -l | grep -E "^ii.*linux-image-[0-9]" | awk '{print $2}' | sort -V || true)

    if [ -z "$kernels" ]; then
        log_info "No kernel images found"
        return 0
    fi

    # Count kernels
    local kernel_count
    kernel_count=$(echo "$kernels" | wc -l)

    if [ "$kernel_count" -le 2 ]; then
        log_info "Only ${kernel_count} kernel(s) found (keeping all)"
        return 0
    fi

    # Get kernels to remove (all except last 2)
    local kernels_to_remove
    kernels_to_remove=$(echo "$kernels" | head -n -2)
    local remove_count
    remove_count=$(echo "$kernels_to_remove" | grep -c . || echo "0")

    if [ "$remove_count" -gt 0 ]; then
        log_info "Removing ${remove_count} old kernel(s):"
        echo "$kernels_to_remove" | while read -r kernel; do
            log_info "  - $kernel"
        done

        # Remove kernels (non-interactive)
        if echo "$kernels_to_remove" | xargs -r apt-get purge -y > /dev/null 2>&1; then
            log_success "Removed ${remove_count} old kernel(s)"
        else
            log_error "Failed to remove some kernels"
        fi
    fi
}

# Clean Docker container logs
clean_docker_logs() {
    log_info "Cleaning large Docker container logs (>10MB)..."

    local docker_log_dir="/var/lib/docker/containers"

    if [ ! -d "$docker_log_dir" ]; then
        log_info "Docker log directory does not exist, skipping"
        return 0
    fi

    local count=0
    local size_freed=0

    # Find and truncate large log files
    while IFS= read -r file; do
        if [ -f "$file" ]; then
            local file_size
            file_size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null || echo "0")
            local file_size_mb=$((file_size / 1024 / 1024))

            if [ "$file_size_mb" -gt 10 ]; then
                truncate -s 0 "$file" 2>/dev/null || true
                size_freed=$((size_freed + file_size / 1024))
                count=$((count + 1))
                log_info "  Truncated: $file (${file_size_mb}MB)"
            fi
        fi
    done < <(find "$docker_log_dir" -name "*.log" -type f -size +10M 2>/dev/null || true)

    if [ "$count" -gt 0 ]; then
        log_success "Truncated ${count} Docker log files (freed ~${size_freed}KB)"
    else
        log_info "No large Docker log files found"
    fi
}

# Main
main() {
    log_info "Starting system cleanup..."

    clean_apt_cache
    vacuum_journal
    remove_old_kernels
    clean_docker_logs

    log_success "System cleanup completed"
}

main "$@"
