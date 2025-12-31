#!/usr/bin/env python3
"""Restore corrupted securities data from backup.

After migration v10, columns were misaligned because product_type was inserted
at position 5, shifting all subsequent columns. This script restores the correct
values from the pre-migration backup.

Fields to restore:
- industry (currently has country values)
- country (currently has fullExchangeName values)
- fullExchangeName (currently has priority_multiplier values)
- currency (currently has last_synced timestamps)
- priority_multiplier (currently has min_lot values)
- min_lot (currently has active values)

The original industry values were lost (went to product_type column which was
manually fixed). We'll restore them from backup.
"""

import sqlite3
import sys
from pathlib import Path

# Paths
BACKUP_DB = Path.home() / "Downloads" / "data-backup" / "config.db"
REMOTE_HOST = "arduino@192.168.1.11"
REMOTE_DB = "/home/arduino/arduino-trader/data/config.db"


def main():
    """Restore corrupted fields from backup."""

    # Read backup data
    print("Reading backup database...")
    backup_conn = sqlite3.connect(BACKUP_DB)
    backup_cursor = backup_conn.cursor()

    backup_cursor.execute("""
        SELECT
            symbol,
            industry,
            country,
            fullExchangeName,
            currency,
            priority_multiplier,
            min_lot
        FROM securities
        ORDER BY symbol
    """)

    backup_data = {}
    for row in backup_cursor.fetchall():
        symbol, industry, country, exchange, currency, priority, min_lot = row
        backup_data[symbol] = {
            'industry': industry,
            'country': country,
            'fullExchangeName': exchange,
            'currency': currency,
            'priority_multiplier': priority,
            'min_lot': min_lot,
        }

    backup_conn.close()

    print(f"Loaded {len(backup_data)} securities from backup")

    # Generate UPDATE statements for remote execution
    print("\nGenerating UPDATE statements...")

    update_statements = []
    for symbol, data in backup_data.items():
        # Escape single quotes in string values
        industry = data['industry'].replace("'", "''") if data['industry'] else None
        country = data['country'].replace("'", "''") if data['country'] else None
        exchange = data['fullExchangeName'].replace("'", "''") if data['fullExchangeName'] else None
        currency = data['currency'].replace("'", "''") if data['currency'] else None

        update_sql = f"""UPDATE securities SET
            industry = {f"'{industry}'" if industry else 'NULL'},
            country = {f"'{country}'" if country else 'NULL'},
            fullExchangeName = {f"'{exchange}'" if exchange else 'NULL'},
            currency = {f"'{currency}'" if currency else 'NULL'},
            priority_multiplier = {data['priority_multiplier']},
            min_lot = {data['min_lot']}
        WHERE symbol = '{symbol}';"""

        update_statements.append(update_sql)

    # Write to file for remote execution
    script_path = Path("/tmp/restore_securities.sql")
    with open(script_path, 'w') as f:
        f.write("BEGIN TRANSACTION;\n")
        for stmt in update_statements:
            f.write(stmt + "\n")
        f.write("COMMIT;\n")

    print(f"Generated {len(update_statements)} UPDATE statements")
    print(f"Saved to {script_path}")
    print("\nTo apply on Arduino device, run:")
    print(f"scp {script_path} arduino@192.168.1.11:/tmp/")
    print(f"ssh arduino@192.168.1.11 'echo \"aristath\" | sudo -S sqlite3 /home/arduino/arduino-trader/data/config.db < /tmp/restore_securities.sql'")

    # Show sample of what will be restored
    print("\n=== Sample Restorations ===")
    for symbol in list(backup_data.keys())[:5]:
        data = backup_data[symbol]
        print(f"{symbol}:")
        print(f"  industry: {data['industry']}")
        print(f"  country: {data['country']}")
        print(f"  fullExchangeName: {data['fullExchangeName']}")
        print(f"  currency: {data['currency']}")
        print(f"  priority_multiplier: {data['priority_multiplier']}")
        print(f"  min_lot: {data['min_lot']}")


if __name__ == "__main__":
    main()
