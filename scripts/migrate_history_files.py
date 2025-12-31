#!/usr/bin/env python3
"""
History Database File Migration Script.

Renames per-stock history database files from symbol-based names to ISIN-based names.
For example: AAPL_US.db -> US0378331005.db

Run this script on the Arduino device AFTER deploying new code:
    python scripts/migrate_history_files.py

The script will:
1. Load symbol->ISIN mapping from stocks table
2. Rename history files from symbol to ISIN format
3. Keep backup of old files (.bak) for rollback
4. Report success/failure for each file
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def symbol_to_filename(symbol: str) -> str:
    """Convert symbol to filename format (same logic as old history method)."""
    return symbol.replace(".", "_").replace("-", "_") + ".db"


async def get_symbol_isin_mapping(config_db) -> dict[str, str]:
    """Get mapping of symbol -> ISIN from stocks table."""
    rows = await config_db.fetchall(
        "SELECT symbol, isin FROM securities WHERE isin IS NOT NULL AND isin != ''"
    )
    return {row["symbol"]: row["isin"] for row in rows}


async def migrate_history_files():
    """Migrate history database files from symbol to ISIN naming."""
    from app.config import settings
    from app.core.database.manager import init_databases

    logger.info("=" * 60)
    logger.info("History File Migration")
    logger.info("=" * 60)
    logger.info(f"Data directory: {settings.data_dir}")

    history_dir = settings.data_dir / "history"
    if not history_dir.exists():
        logger.info("No history directory found, nothing to migrate")
        return 0

    # Initialize database manager to access stocks table
    db_manager = await init_databases(settings.data_dir)

    # Get symbol -> ISIN mapping
    symbol_isin_map = await get_symbol_isin_mapping(db_manager.config)
    logger.info(f"Found {len(symbol_isin_map)} stocks with ISIN")

    # Get all existing history files
    history_files = list(history_dir.glob("*.db"))
    history_files = [f for f in history_files if not f.name.endswith(".bak")]
    logger.info(f"Found {len(history_files)} history files")

    # Build filename -> symbol mapping (reverse of symbol_to_filename)
    filename_symbol_map = {}
    for symbol in symbol_isin_map.keys():
        filename = symbol_to_filename(symbol)
        filename_symbol_map[filename] = symbol

    migrated = 0
    skipped = 0
    errors = 0

    for file_path in history_files:
        filename = file_path.name
        symbol = filename_symbol_map.get(filename)

        if not symbol:
            # Try to guess symbol from filename
            potential_symbol = filename[:-3]  # Remove .db
            potential_symbol = potential_symbol.replace("_", ".")
            if potential_symbol not in symbol_isin_map:
                logger.warning(f"Cannot determine symbol for {filename}, skipping")
                skipped += 1
                continue
            symbol = potential_symbol

        isin = symbol_isin_map.get(symbol)
        if not isin:
            logger.warning(f"No ISIN for symbol {symbol}, skipping {filename}")
            skipped += 1
            continue

        new_filename = f"{isin}.db"
        new_path = history_dir / new_filename

        if new_path.exists():
            if new_path == file_path:
                logger.info(f"Already migrated: {filename}")
                skipped += 1
            else:
                logger.warning(
                    f"Target {new_filename} already exists, skipping {filename}"
                )
                skipped += 1
            continue

        # Create backup
        backup_path = file_path.with_suffix(".db.bak")
        try:
            # Copy to new name
            import shutil

            shutil.copy2(file_path, new_path)

            # Rename old to backup
            file_path.rename(backup_path)

            logger.info(f"Migrated: {filename} -> {new_filename}")
            migrated += 1

        except Exception as e:
            logger.error(f"Failed to migrate {filename}: {e}")
            errors += 1

    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("Migration Summary")
    logger.info("=" * 60)
    logger.info(f"Migrated: {migrated}")
    logger.info(f"Skipped:  {skipped}")
    logger.info(f"Errors:   {errors}")

    if errors == 0:
        logger.info("")
        logger.info("Migration completed successfully!")
        logger.info("")
        logger.info("The old files have been renamed to .bak for safety.")
        logger.info("You can delete them after verifying the migration:")
        logger.info(f"  rm {history_dir}/*.bak")
    else:
        logger.error("Migration had errors - please review and retry")
        return 1

    await db_manager.close_all()
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(migrate_history_files())
    sys.exit(exit_code)
