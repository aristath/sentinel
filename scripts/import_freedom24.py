#!/usr/bin/env python3
"""
Import Freedom24 exported JSON data into the Arduino Trader database.

Usage:
    python3 scripts/import_freedom24.py /path/to/export1.json /path/to/export2.json
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Default database path (relative to arduino-trader root)
DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "trader.db"


def get_geography_from_symbol(symbol: str) -> str:
    """Derive geography from symbol suffix."""
    if symbol.endswith(".US"):
        return "US"
    elif symbol.endswith(".GR"):
        return "EU"
    elif symbol.endswith(".EU"):
        return "EU"
    elif symbol.endswith(".DE"):
        return "EU"
    elif symbol.endswith(".HK"):
        return "ASIA"
    else:
        return "EU"  # Default to EU


def import_trades(conn: sqlite3.Connection, data: dict, dry_run: bool = False) -> int:
    """Import trades from Freedom24 export."""
    trades = data.get("trades", {}).get("detailed", [])
    imported = 0
    skipped = 0

    cursor = conn.cursor()

    for trade in trades:
        symbol = trade.get("instr_nm")
        operation = trade.get("operation")
        quantity = trade.get("q")
        price = trade.get("p")
        date = trade.get("short_date")
        order_id = trade.get("id")
        instr_type = trade.get("instr_type")

        # Skip non-stock instruments (options, forex conversions)
        # instr_type 1 = stocks, 6 = forex, 4 = options, 16 = option exercise
        if instr_type not in [1]:
            print(f"  Skipping non-stock: {symbol} (type {instr_type})")
            continue

        # Skip if missing required fields
        if not all([symbol, operation, quantity, price, date]):
            print(f"  Skipping incomplete trade: {trade}")
            continue

        # Check for duplicate
        cursor.execute(
            """
            SELECT id FROM trades
            WHERE symbol = ? AND side = ? AND quantity = ? AND price = ? AND executed_at = ?
        """,
            (symbol, operation, quantity, price, date),
        )

        if cursor.fetchone():
            skipped += 1
            continue

        # Ensure stock exists
        ensure_stock_exists(conn, symbol, trade, dry_run)

        if not dry_run:
            cursor.execute(
                """
                INSERT INTO trades (symbol, side, quantity, price, executed_at, order_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    symbol,
                    operation,
                    quantity,
                    price,
                    date,
                    order_id if order_id != "Grouped" else None,
                ),
            )

        imported += 1
        print(f"  Imported trade: {operation} {quantity} {symbol} @ {price} on {date}")

    if not dry_run:
        conn.commit()

    print(f"  Trades: {imported} imported, {skipped} skipped (duplicates)")
    return imported


def import_cash_flows(
    conn: sqlite3.Connection, data: dict, dry_run: bool = False
) -> int:
    """Import cash flows from Freedom24 export."""
    cash_in_outs = data.get("cash_in_outs", [])
    imported = 0
    skipped = 0

    cursor = conn.cursor()

    for cf in cash_in_outs:
        transaction_id = str(cf.get("id"))
        transaction_type = cf.get("type")
        date = cf.get("datetime")
        amount = float(cf.get("amount", 0))
        currency = cf.get("currency")
        description = cf.get("comment")
        details = cf.get("details")

        # Calculate amount in EUR
        if currency == "EUR":
            amount_eur = amount
        elif currency == "USD":
            # Convert USD to EUR (approximate - use stored rate if available)
            amount_eur = (
                amount * 0.93
            )  # Rough conversion, will be updated by actual rate
        else:
            amount_eur = amount

        # Check for duplicate using transaction_id
        cursor.execute(
            "SELECT id FROM cash_flows WHERE transaction_id = ?", (transaction_id,)
        )
        if cursor.fetchone():
            skipped += 1
            continue

        if not dry_run:
            now = datetime.now().isoformat()
            cursor.execute(
                """
                INSERT INTO cash_flows
                (transaction_id, type_doc_id, transaction_type, date, amount, currency, amount_eur,
                 status, description, params_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    transaction_id,
                    0,  # type_doc_id - not available in Freedom24 export
                    transaction_type,
                    date,
                    amount,
                    currency,
                    amount_eur,
                    "completed",
                    description,
                    (
                        details
                        if isinstance(details, str)
                        else json.dumps(details) if details else None
                    ),
                    now,
                    now,
                ),
            )

        imported += 1
        type_str = transaction_type or "unknown"
        print(f"  Imported cash flow: {type_str} {amount} {currency} on {date}")

    if not dry_run:
        conn.commit()

    print(f"  Cash flows: {imported} imported, {skipped} skipped (duplicates)")
    return imported


def ensure_stock_exists(
    conn: sqlite3.Connection, symbol: str, trade: dict, dry_run: bool = False
) -> None:
    """Ensure a stock exists in the stocks table, creating if needed."""
    cursor = conn.cursor()
    cursor.execute("SELECT symbol FROM stocks WHERE symbol = ?", (symbol,))

    if cursor.fetchone():
        return  # Stock already exists

    # Get stock info from trade data
    name = symbol  # Default to symbol if name not available
    geography = get_geography_from_symbol(symbol)

    # Try to get yahoo symbol (usually same but with different format)
    yahoo_symbol = symbol.replace(".US", "").replace(".GR", ".AT").replace(".EU", "")

    # Default industry (can be updated later)
    industry = "Other"

    if not dry_run:
        cursor.execute(
            """
            INSERT INTO stocks (symbol, yahoo_symbol, name, industry, geography, active)
            VALUES (?, ?, ?, ?, ?, 1)
        """,
            (symbol, yahoo_symbol, name, industry, geography),
        )
        conn.commit()

    print(f"  Created stock: {symbol} ({geography})")


def import_file(
    conn: sqlite3.Connection, filepath: str, dry_run: bool = False
) -> tuple[int, int]:
    """Import a single Freedom24 export file."""
    print(f"\nImporting: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Get date range from export
    date_start = data.get("date_start", "unknown")
    date_end = data.get("date_end", "unknown")
    print(f"  Date range: {date_start} to {date_end}")

    trades_count = import_trades(conn, data, dry_run)
    cash_flows_count = import_cash_flows(conn, data, dry_run)

    return trades_count, cash_flows_count


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 import_freedom24.py <json_file1> [json_file2] ...")
        print("\nOptions:")
        print("  --dry-run    Show what would be imported without making changes")
        print("  --db PATH    Use custom database path")
        sys.exit(1)

    # Parse arguments
    files = []
    db_path = DEFAULT_DB_PATH
    dry_run = False

    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--dry-run":
            dry_run = True
        elif arg == "--db":
            i += 1
            db_path = Path(sys.argv[i])
        else:
            files.append(arg)
        i += 1

    if not files:
        print("Error: No input files specified")
        sys.exit(1)

    # Connect to database
    print(f"Database: {db_path}")
    if dry_run:
        print("DRY RUN - no changes will be made")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    total_trades = 0
    total_cash_flows = 0

    try:
        for filepath in files:
            trades, cash_flows = import_file(conn, filepath, dry_run)
            total_trades += trades
            total_cash_flows += cash_flows
    finally:
        conn.close()

    print(f"\n{'Would import' if dry_run else 'Imported'}:")
    print(f"  Total trades: {total_trades}")
    print(f"  Total cash flows: {total_cash_flows}")


if __name__ == "__main__":
    main()
