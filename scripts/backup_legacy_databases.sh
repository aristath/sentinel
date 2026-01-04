#!/bin/bash
# Backup legacy Python app databases before migration

set -e

PYTHON_DATA_DIR="${1:-~/arduino-trader/data}"
BACKUP_DIR="${2:-~/arduino-trader/data/backups/legacy_pre_migration_$(date +%Y%m%d_%H%M%S)}"

echo "Creating backup of legacy Python databases..."
echo "Source: ${PYTHON_DATA_DIR}"
echo "Backup: ${BACKUP_DIR}"

# Create backup directory
mkdir -p "${BACKUP_DIR}"

# Backup all database files
echo "Backing up database files..."
for db in config.db state.db ledger.db calculations.db snapshots.db dividends.db satellites.db planner.db recommendations.db rates.db cache.db trader.db; do
    if [ -f "${PYTHON_DATA_DIR}/${db}" ]; then
        echo "  Backing up ${db}..."
        cp "${PYTHON_DATA_DIR}/${db}" "${BACKUP_DIR}/"
        # Also backup WAL and SHM files if they exist
        [ -f "${PYTHON_DATA_DIR}/${db}-wal" ] && cp "${PYTHON_DATA_DIR}/${db}-wal" "${BACKUP_DIR}/" || true
        [ -f "${PYTHON_DATA_DIR}/${db}-shm" ] && cp "${PYTHON_DATA_DIR}/${db}-shm" "${BACKUP_DIR}/" || true
    fi
done

# Backup history directory if it exists
if [ -d "${PYTHON_DATA_DIR}/history" ]; then
    echo "  Backing up history directory..."
    cp -r "${PYTHON_DATA_DIR}/history" "${BACKUP_DIR}/"
fi

# Create a tar archive for easier storage
echo "Creating compressed archive..."
cd "$(dirname "${BACKUP_DIR}")"
tar -czf "$(basename "${BACKUP_DIR}").tar.gz" "$(basename "${BACKUP_DIR}")"

echo ""
echo "Backup completed!"
echo "Backup location: ${BACKUP_DIR}"
echo "Compressed archive: $(dirname "${BACKUP_DIR}")/$(basename "${BACKUP_DIR}").tar.gz"
echo ""
echo "To restore from backup:"
echo "  cd ~/arduino-trader/data"
echo "  tar -xzf backups/$(basename "${BACKUP_DIR}").tar.gz"
echo "  cp backups/$(basename "${BACKUP_DIR}")/*.db ."
