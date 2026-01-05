#!/bin/bash
# Deployment cleanup script for Arduino Uno Q
# Cleans temporary files, old binary backups, and Go build cache
#
# Usage:
#   deployment-cleanup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load config if available
if [ -f "${SCRIPT_DIR}/../config.sh" ]; then
    source "${SCRIPT_DIR}/../config.sh"
fi

# Default paths (can be overridden)
APP_DIR="${APP_DIR:-$HOME/app}"
BIN_DIR="${BIN_DIR:-${APP_DIR}/bin}"
TMP_DIR="${TMP_DIR:-${BIN_DIR}/.tmp}"
# REPO_DIR: Use explicit path if set, otherwise calculate from script location, otherwise use APP_DIR
REPO_DIR="${REPO_DIR:-$(cd "${SCRIPT_DIR}/../.." 2>/dev/null && pwd || echo "${APP_DIR}/repo")}"

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

# Get disk usage percentage for a path
get_disk_usage() {
    local path="$1"
    df "$path" | tail -1 | awk '{print $5}' | sed 's/%//'
}

# Clean temporary files
clean_temp_files() {
    log_info "Cleaning temporary files in ${TMP_DIR}..."

    if [ ! -d "$TMP_DIR" ]; then
        log_info "Temp directory does not exist, skipping"
        return 0
    fi

    local count=0
    local size_freed=0

    # Count and calculate size before
    if [ -n "$(ls -A "$TMP_DIR" 2>/dev/null)" ]; then
        size_freed=$(du -sk "$TMP_DIR" 2>/dev/null | awk '{print $1}' || echo "0")
        count=$(find "$TMP_DIR" -type f 2>/dev/null | wc -l)

        # Remove all temp files
        rm -rf "${TMP_DIR}"/*
        rm -rf "${TMP_DIR}"/.[!.]* 2>/dev/null || true

        log_success "Cleaned ${count} temp files (freed ~${size_freed}KB)"
    else
        log_info "No temp files to clean"
    fi
}

# Clean old binary backups (keep last 3)
clean_binary_backups() {
    log_info "Cleaning old binary backups in ${BIN_DIR}..."

    if [ ! -d "$BIN_DIR" ]; then
        log_info "Bin directory does not exist, skipping"
        return 0
    fi

    # Find all .bak files
    local backup_files
    backup_files=$(find "$BIN_DIR" -name "*.bak" -type f 2>/dev/null | sort -V || true)

    if [ -z "$backup_files" ]; then
        log_info "No binary backups to clean"
        return 0
    fi

    # Count total backups
    local total_count
    total_count=$(echo "$backup_files" | wc -l)

    if [ "$total_count" -le 3 ]; then
        log_info "Only ${total_count} backups found (keeping all)"
        return 0
    fi

    # Keep last 3, remove the rest
    local to_remove
    to_remove=$(echo "$backup_files" | head -n -3)
    local remove_count
    remove_count=$(echo "$to_remove" | grep -c . || echo "0")

    if [ "$remove_count" -gt 0 ]; then
        local size_freed=0
        while IFS= read -r file; do
            if [ -f "$file" ]; then
                local file_size
                file_size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null || echo "0")
                size_freed=$((size_freed + file_size / 1024))
                rm -f "$file"
            fi
        done <<< "$to_remove"

        log_success "Removed ${remove_count} old backups (freed ~${size_freed}KB)"
    fi
}

# Clean Go build cache (only if disk > 85%)
clean_go_cache() {
    log_info "Checking Go build cache..."

    if ! command -v go &> /dev/null; then
        log_info "Go is not installed, skipping Go cache cleanup"
        return 0
    fi

    # Check disk usage
    local disk_usage
    disk_usage=$(get_disk_usage "/")

    if [ "$disk_usage" -lt 85 ]; then
        log_info "Disk usage is ${disk_usage}% (< 85%), skipping Go cache cleanup"
        return 0
    fi

    log_info "Disk usage is ${disk_usage}% (>= 85%), cleaning Go build cache..."

    # Get cache size before
    local cache_dir
    cache_dir=$(go env GOCACHE 2>/dev/null || echo "$HOME/.cache/go-build")

    local size_before=0
    if [ -d "$cache_dir" ]; then
        size_before=$(du -sk "$cache_dir" 2>/dev/null | awk '{print $1}' || echo "0")
    fi

    # Clean cache
    if go clean -cache > /dev/null 2>&1; then
        local size_after=0
        if [ -d "$cache_dir" ]; then
            size_after=$(du -sk "$cache_dir" 2>/dev/null | awk '{print $1}' || echo "0")
        fi
        local size_freed=$((size_before - size_after))

        log_success "Go build cache cleaned (freed ~${size_freed}KB)"
    else
        log_error "Failed to clean Go build cache"
    fi
}

# Clean large log files in repo
clean_large_logs() {
    log_info "Cleaning large log files (>10MB) in ${REPO_DIR}..."

    if [ ! -d "$REPO_DIR" ]; then
        log_info "Repo directory does not exist, skipping"
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
    done < <(find "$REPO_DIR" -name "*.log" -type f -size +10M 2>/dev/null || true)

    if [ "$count" -gt 0 ]; then
        log_success "Truncated ${count} large log files (freed ~${size_freed}KB)"
    else
        log_info "No large log files found"
    fi
}

# Main
main() {
    log_info "Starting deployment cleanup..."

    clean_temp_files
    clean_binary_backups
    clean_go_cache
    clean_large_logs

    log_success "Deployment cleanup completed"
}

main "$@"
