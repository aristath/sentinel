#!/bin/bash
# Crontab installation/update script for maintenance tasks
# Installs maintenance cronjobs in both user and root crontabs
#
# Usage:
#   update-crontab.sh [--dry-run]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
MAINTENANCE_DIR="$SCRIPT_DIR"

# Default paths
APP_DIR="${APP_DIR:-$HOME/app}"
REPO_PATH="${REPO_PATH:-${APP_DIR}/repo}"

# Dry run mode
DRY_RUN=0
if [ "$1" = "--dry-run" ]; then
    DRY_RUN=1
    echo "DRY RUN MODE - No changes will be made"
    echo ""
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

# Backup crontab
backup_crontab() {
    local user="$1"
    local backup_file

    if [ "$user" = "root" ]; then
        backup_file="/tmp/crontab.root.backup.$(date +%Y%m%d_%H%M%S)"
        if [ "$DRY_RUN" -eq 0 ]; then
            crontab -u root -l > "$backup_file" 2>/dev/null || true
        else
            echo "[DRY RUN] Would backup root crontab to $backup_file"
        fi
    else
        backup_file="/tmp/crontab.${user}.backup.$(date +%Y%m%d_%H%M%S)"
        if [ "$DRY_RUN" -eq 0 ]; then
            crontab -u "$user" -l > "$backup_file" 2>/dev/null || true
        else
            echo "[DRY RUN] Would backup $user crontab to $backup_file"
        fi
    fi

    if [ "$DRY_RUN" -eq 0 ] && [ -f "$backup_file" ]; then
        log_info "Backed up crontab to $backup_file"
    fi
}

# Ensure script is executable
make_executable() {
    local script="$1"
    if [ -f "$script" ]; then
        if [ "$DRY_RUN" -eq 0 ]; then
            chmod +x "$script"
        else
            echo "[DRY RUN] Would make $script executable"
        fi
    fi
}

# Install user crontab
install_user_crontab() {
    local user="${1:-arduino}"
    log_info "Installing user crontab for $user..."

    # Backup existing crontab
    backup_crontab "$user"

    # Make scripts executable
    make_executable "${MAINTENANCE_DIR}/docker-cleanup.sh"
    make_executable "${MAINTENANCE_DIR}/deployment-cleanup.sh"

    # Build crontab entries
    local crontab_entries=()

    # Docker build cache cleanup (every 30 minutes)
    crontab_entries+=("*/30 * * * * ${REPO_PATH}/scripts/maintenance/docker-cleanup.sh build-cache >> /tmp/docker-cleanup.log 2>&1")

    # Full Docker prune (daily at 2:00 AM)
    crontab_entries+=("0 2 * * * ${REPO_PATH}/scripts/maintenance/docker-cleanup.sh full >> /tmp/docker-cleanup.log 2>&1")

    # Deployment cleanup (daily at 2:30 AM)
    crontab_entries+=("30 2 * * * ${REPO_PATH}/scripts/maintenance/deployment-cleanup.sh >> /tmp/deployment-cleanup.log 2>&1")

    # Get existing crontab (excluding our maintenance entries)
    local existing_crontab
    existing_crontab=$(crontab -u "$user" -l 2>/dev/null | grep -v "docker-cleanup.sh" | grep -v "deployment-cleanup.sh" | grep -v "^#" | grep -v "^$" || true)

    # Combine existing entries with new maintenance entries
    local new_crontab=""
    if [ -n "$existing_crontab" ]; then
        new_crontab="$existing_crontab"$'\n'
    fi
    new_crontab="${new_crontab}# Maintenance scripts (auto-installed by update-crontab.sh)"$'\n'
    for entry in "${crontab_entries[@]}"; do
        new_crontab="${new_crontab}${entry}"$'\n'
    done

    # Install new crontab
    if [ "$DRY_RUN" -eq 0 ]; then
        echo "$new_crontab" | crontab -u "$user" -
        log_success "User crontab installed for $user"
    else
        echo "[DRY RUN] Would install user crontab for $user:"
        echo "$new_crontab"
    fi
}

# Install root crontab
install_root_crontab() {
    log_info "Installing root crontab..."

    # Check if running as root
    if [ "$EUID" -ne 0 ] && [ "$DRY_RUN" -eq 0 ]; then
        log_error "Root crontab installation requires root privileges"
        log_error "Please run: sudo $0"
        return 1
    fi

    # Backup existing crontab
    backup_crontab "root"

    # Make scripts executable
    make_executable "${MAINTENANCE_DIR}/system-cleanup.sh"
    make_executable "${MAINTENANCE_DIR}/disk-monitor.sh"

    # Build crontab entries
    local crontab_entries=()

    # System cleanup (daily at 3:00 AM)
    crontab_entries+=("0 3 * * * ${REPO_PATH}/scripts/maintenance/system-cleanup.sh >> /tmp/system-cleanup.log 2>&1")

    # Disk monitoring (every 5 minutes)
    crontab_entries+=("*/5 * * * * ${REPO_PATH}/scripts/maintenance/disk-monitor.sh >> /tmp/disk-monitor.log 2>&1")

    # Get existing crontab (excluding our maintenance entries)
    local existing_crontab
    if [ "$DRY_RUN" -eq 0 ]; then
        existing_crontab=$(crontab -u root -l 2>/dev/null | grep -v "system-cleanup.sh" | grep -v "disk-monitor.sh" | grep -v "^#" | grep -v "^$" || true)
    else
        existing_crontab=""
    fi

    # Combine existing entries with new maintenance entries
    local new_crontab=""
    if [ -n "$existing_crontab" ]; then
        new_crontab="$existing_crontab"$'\n'
    fi
    new_crontab="${new_crontab}# Maintenance scripts (auto-installed by update-crontab.sh)"$'\n'
    for entry in "${crontab_entries[@]}"; do
        new_crontab="${new_crontab}${entry}"$'\n'
    done

    # Install new crontab
    if [ "$DRY_RUN" -eq 0 ]; then
        echo "$new_crontab" | crontab -u root -
        log_success "Root crontab installed"
    else
        echo "[DRY RUN] Would install root crontab:"
        echo "$new_crontab"
    fi
}

# Verify scripts exist
verify_scripts() {
    local missing=0

    local scripts=(
        "${MAINTENANCE_DIR}/docker-cleanup.sh"
        "${MAINTENANCE_DIR}/deployment-cleanup.sh"
        "${MAINTENANCE_DIR}/system-cleanup.sh"
        "${MAINTENANCE_DIR}/disk-monitor.sh"
    )

    for script in "${scripts[@]}"; do
        if [ ! -f "$script" ]; then
            log_error "Script not found: $script"
            missing=1
        fi
    done

    if [ "$missing" -eq 1 ]; then
        log_error "Some maintenance scripts are missing. Please ensure all scripts are in ${MAINTENANCE_DIR}"
        return 1
    fi

    log_success "All maintenance scripts found"
    return 0
}

# Main
main() {
    log_info "Starting crontab installation/update..."

    # Verify scripts exist
    if ! verify_scripts; then
        exit 1
    fi

    # Get current user
    local current_user="${SUDO_USER:-$USER}"
    if [ -z "$current_user" ]; then
        current_user="arduino"
    fi

    # Install user crontab
    install_user_crontab "$current_user"

    # Install root crontab (if running as root or with sudo)
    if [ "$EUID" -eq 0 ] || [ -n "$SUDO_USER" ]; then
        install_root_crontab
    else
        log_info "Skipping root crontab installation (not running as root)"
        log_info "To install root crontab, run: sudo $0"
    fi

    log_success "Crontab installation completed"
    echo ""
    echo "Maintenance cronjobs installed:"
    echo "  User crontab: Docker cleanup (every 30min + daily), Deployment cleanup (daily)"
    echo "  Root crontab: System cleanup (daily), Disk monitoring (every 5min)"
    echo ""
    echo "To view installed crontabs:"
    echo "  crontab -l                    # User crontab"
    echo "  sudo crontab -u root -l       # Root crontab"
}

main "$@"
