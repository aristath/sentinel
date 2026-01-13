# Database Schemas

This directory contains the **single source of truth** for each database's schema.

## Schema Files

Each database has one schema file that represents its complete, final state:

- `universe_schema.sql` - Investment universe (securities, tags, country/industry groups)
- `config_schema.sql` - Application configuration (settings, allocation targets, planner settings)
- `ledger_schema.sql` - Immutable financial audit trail (trades, cash flows, dividends, DRIP tracking)
- `portfolio_schema.sql` - Current portfolio state (positions, scores, calculated metrics)
- `history_schema.sql` - Historical time-series data (daily/monthly prices, exchange rates)
- `cache_schema.sql` - Ephemeral operational data (job history)
- `client_data_schema.sql` - External API response cache (Alpha Vantage, Yahoo, OpenFIGI)

## How It Works

When a database is initialized via `database.New()`, the `Migrate()` method is automatically called. This method:

1. Maps the database name to its schema file
2. Finds the `schemas/` directory (tries multiple paths for flexibility)
3. Reads and executes the schema file in a transaction
4. Handles errors gracefully (skips if schema already applied)

## Making Schema Changes

To modify a database schema:

1. Edit the appropriate schema file in this directory
2. The changes will be applied automatically on the next application start
3. For existing databases, SQLite will handle `CREATE TABLE IF NOT EXISTS` and similar statements gracefully
