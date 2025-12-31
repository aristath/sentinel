# Scripts

Utility scripts for Arduino Trader.

## import_freedom24.py

Imports trade history and cash flows from Freedom24 JSON exports into the database.

### Exporting Data from Freedom24

1. Log in to your Freedom24 account
2. Go to Reports > Account Statement
3. Select the date range you want to export
4. Export as JSON format
5. Save the file to your computer

### Usage

```bash
# Stop the service first (database locking)
sudo systemctl stop arduino-trader

# Import one or more export files
python3 scripts/import_freedom24.py /path/to/export1.json /path/to/export2.json

# Restart the service
sudo systemctl start arduino-trader
```

### Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Show what would be imported without making changes |
| `--db PATH` | Use a custom database path (default: `data/trader.db`) |

### Examples

```bash
# Dry run to preview import
python3 scripts/import_freedom24.py --dry-run /tmp/freedom24_export.json

# Import multiple files
python3 scripts/import_freedom24.py /tmp/export_2024.json /tmp/export_2025.json

# Use custom database
python3 scripts/import_freedom24.py --db /path/to/custom.db /tmp/export.json
```

### What Gets Imported

**Trades:**
- Security buy/sell transactions (instrument type 1)
- Skips forex conversions, options, and other non-security instruments

**Cash Flows:**
- Card deposits
- Dividends
- Taxes
- Withdrawals (card_payout)
- Block/unblock transactions

**Stocks:**
- New stocks are automatically added to the universe with:
  - Geography derived from symbol suffix (.US, .GR, .EU)
  - Industry set to "Other" (update manually later)

### Duplicate Handling

- **Trades:** Checked by (symbol, side, quantity, price, executed_at)
- **Cash flows:** Checked by transaction_id (unique constraint)

Duplicates are skipped, so it's safe to re-import the same file.

### Data Mapping

| Freedom24 Field | Database Column | Notes |
|-----------------|-----------------|-------|
| `trades.detailed[].instr_nm` | `trades.symbol` | e.g., "WU.US" |
| `trades.detailed[].operation` | `trades.side` | "buy" or "sell" |
| `trades.detailed[].q` | `trades.quantity` | |
| `trades.detailed[].p` | `trades.price` | |
| `trades.detailed[].short_date` | `trades.executed_at` | |
| `cash_in_outs[].id` | `cash_flows.transaction_id` | |
| `cash_in_outs[].type` | `cash_flows.transaction_type` | |
| `cash_in_outs[].datetime` | `cash_flows.date` | |
| `cash_in_outs[].amount` | `cash_flows.amount` | |
| `cash_in_outs[].currency` | `cash_flows.currency` | |
