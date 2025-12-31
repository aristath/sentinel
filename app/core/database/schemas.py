"""
Database Schemas - CREATE TABLE statements for all databases.

This module contains schema definitions for:
- config.db: Stock universe, allocation targets, settings
- ledger.db: Trades, cash flows (append-only)
- state.db: Positions (current state, rebuildable from ledger)
- cache.db: Ephemeral computed aggregates (can be deleted)
- calculations.db: Pre-computed metrics and scores
- recommendations.db: Trade recommendations (operational)
- dividends.db: Dividend history with DRIP tracking
- rates.db: Exchange rates
- snapshots.db: Portfolio snapshots (daily time-series)
- planner.db: Holistic planner sequences, evaluations, and best results
- history/{isin}.db: Per-stock price data (keyed by ISIN)
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIG.DB - Master data (rarely changes)
# =============================================================================

CONFIG_SCHEMA = """
-- Stock universe
CREATE TABLE IF NOT EXISTS stocks (
    symbol TEXT PRIMARY KEY,
    yahoo_symbol TEXT,
    isin TEXT,                   -- International Securities Identification Number (12 chars)
    name TEXT NOT NULL,
    industry TEXT,
    country TEXT,                -- Country name from Yahoo Finance (e.g., "United States", "Germany")
    fullExchangeName TEXT,       -- Exchange name from Yahoo Finance (e.g., "NASDAQ", "XETR")
    priority_multiplier REAL DEFAULT 1.0,
    min_lot INTEGER DEFAULT 1,
    active INTEGER DEFAULT 1,
    allow_buy INTEGER DEFAULT 1,
    allow_sell INTEGER DEFAULT 0,
    currency TEXT,
    last_synced TEXT,           -- When stock data was last fully synced (daily pipeline)
    min_portfolio_target REAL,  -- Minimum target portfolio allocation percentage (0-20)
    max_portfolio_target REAL,  -- Maximum target portfolio allocation percentage (0-30)
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stocks_active ON stocks(active);
CREATE INDEX IF NOT EXISTS idx_stocks_country ON stocks(country);
-- Note: idx_stocks_isin is created in migration or init_config_schema for new databases

-- Allocation targets (group-based weightings)
CREATE TABLE IF NOT EXISTS allocation_targets (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL,      -- 'country_group' or 'industry_group'
    name TEXT NOT NULL,
    target_pct REAL NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(type, name)
);

-- Custom grouping for countries (e.g., EU, US, ASIA)
CREATE TABLE IF NOT EXISTS country_groups (
    id INTEGER PRIMARY KEY,
    group_name TEXT NOT NULL,  -- e.g., 'EU', 'US', 'ASIA'
    country_name TEXT NOT NULL,  -- e.g., 'Germany', 'France'
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(group_name, country_name)
);

CREATE INDEX IF NOT EXISTS idx_country_groups_group ON country_groups(group_name);
CREATE INDEX IF NOT EXISTS idx_country_groups_country ON country_groups(country_name);

-- Custom grouping for industries (e.g., Technology, Industrials, Energy)
CREATE TABLE IF NOT EXISTS industry_groups (
    id INTEGER PRIMARY KEY,
    group_name TEXT NOT NULL,  -- e.g., 'Technology', 'Industrials'
    industry_name TEXT NOT NULL,  -- e.g., 'Software', 'Semiconductors'
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(group_name, industry_name)
);

CREATE INDEX IF NOT EXISTS idx_industry_groups_group ON industry_groups(group_name);
CREATE INDEX IF NOT EXISTS idx_industry_groups_industry ON industry_groups(industry_name);

-- Application settings (key-value store)
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TEXT NOT NULL
);

-- Trade recommendations (stored with UUIDs for dismissal tracking)
-- Uses portfolio_hash to identify same recommendations for same portfolio state
CREATE TABLE IF NOT EXISTS recommendations (
    uuid TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    side TEXT NOT NULL,  -- 'BUY' or 'SELL'
    amount REAL,  -- Display only, not part of uniqueness
    quantity INTEGER,
    estimated_price REAL,
    estimated_value REAL,
    reason TEXT NOT NULL,
    country TEXT,                -- Country name from Yahoo Finance (replaces geography)
    industry TEXT,
    currency TEXT DEFAULT 'EUR',
    priority REAL,
    current_portfolio_score REAL,
    new_portfolio_score REAL,
    score_change REAL,
    status TEXT DEFAULT 'pending',  -- 'pending', 'executed', 'dismissed'
    portfolio_hash TEXT NOT NULL DEFAULT '',  -- Hash of portfolio state when recommendation was made
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,  -- Updated when recommendation is regenerated
    executed_at TEXT,
    dismissed_at TEXT,
    UNIQUE(symbol, side, reason, portfolio_hash)  -- Same rec for same portfolio state
);

CREATE INDEX IF NOT EXISTS idx_recommendations_symbol ON recommendations(symbol);
CREATE INDEX IF NOT EXISTS idx_recommendations_status ON recommendations(status);
CREATE INDEX IF NOT EXISTS idx_recommendations_created_at ON recommendations(created_at);
-- Note: portfolio_hash indexes are created in migration v2->v3 for existing databases
-- For new installs, they're created below after initial data setup

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    description TEXT
);
"""

# Default allocation targets removed - use group-based allocations instead
# Users should set up country_groups and industry_groups first, then set group targets
DEFAULT_ALLOCATION_TARGETS: list[tuple[str, str, float]] = []

# Default settings for new database installations
# NOTE: min_trade_size and recommendation_depth replaced by optimizer-based settings
DEFAULT_SETTINGS = [
    ("min_cash_threshold", "500", "Minimum EUR cash reserve"),
    ("max_trades_per_cycle", "5", "Maximum trades per rebalance cycle"),
    ("min_stock_score", "0.5", "Minimum score to consider buying"),
    ("min_hold_days", "90", "Minimum days before selling"),
    ("sell_cooldown_days", "180", "Days between sells of same stock"),
    ("max_loss_threshold", "-0.20", "Don't sell if loss exceeds this"),
    ("target_annual_return", "0.11", "Target CAGR for scoring (11%)"),
    # Optimizer settings
    ("optimizer_blend", "0.5", "0.0 = pure Mean-Variance, 1.0 = pure HRP"),
    ("optimizer_target_return", "0.11", "Target annual return for optimizer"),
    # Transaction costs (Freedom24)
    ("transaction_cost_fixed", "2.0", "Fixed cost per trade in EUR"),
    ("transaction_cost_percent", "0.002", "Variable cost as fraction (0.2%)"),
    # Cash management
    ("min_cash_reserve", "500.0", "Minimum cash to keep (never fully deploy)"),
    # Job scheduling (simplified - only 2 configurable settings)
    (
        "job_sync_cycle_minutes",
        "15",
        "Sync cycle interval in minutes (trades, prices, recommendations)",
    ),
    ("job_maintenance_hour", "3", "Daily maintenance hour (0-23)"),
    ("max_actions", "5", "Maximum automated actions per cycle"),
    ("dry_run", "false", "Disable actual trading (simulation mode)"),
]


async def init_config_schema(db):
    """Initialize config database schema."""
    await db.executescript(CONFIG_SCHEMA)

    # Check schema version
    row = await db.fetchone("SELECT MAX(version) as v FROM schema_version")
    current_version = row["v"] if row and row["v"] else 0

    if current_version == 0:
        now = datetime.now().isoformat()

        # Insert default allocation targets
        for type_, name, target in DEFAULT_ALLOCATION_TARGETS:
            await db.execute(
                """INSERT OR IGNORE INTO allocation_targets
                   (type, name, target_pct, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (type_, name, target, now, now),
            )

        # Insert default settings
        for key, value, desc in DEFAULT_SETTINGS:
            await db.execute(
                """INSERT OR IGNORE INTO settings
                   (key, value, description, updated_at)
                   VALUES (?, ?, ?, ?)""",
                (key, value, desc, now),
            )

        # Create portfolio_hash indexes for new installs
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_recommendations_portfolio_hash ON recommendations(portfolio_hash)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_recommendations_unique_match "
            "ON recommendations(symbol, side, reason, portfolio_hash)"
        )

        # Create isin index for new installs
        await db.execute("CREATE INDEX IF NOT EXISTS idx_stocks_isin ON stocks(isin)")

        # Record schema version
        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (
                8,
                now,
                "Initial config schema with portfolio_hash recommendations, last_synced, country, fullExchangeName, portfolio targets, custom grouping, and isin",
            ),
        )

        await db.commit()
        logger.info(
            "Config database initialized with schema version 8 (includes portfolio_hash, last_synced, portfolio targets, custom grouping, and isin)"
        )
    elif current_version == 1:
        # Migration: Add recommendations table (version 1 -> 2)
        now = datetime.now().isoformat()
        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (2, now, "Added recommendations table for storage and dismissal tracking"),
        )
        await db.commit()
        logger.info(
            "Config database migrated to schema version 2 (recommendations table)"
        )
        current_version = 2  # Continue to next migration

    if current_version == 2:
        # Migration: Add portfolio_hash, change unique constraint (version 2 -> 3)
        now = datetime.now().isoformat()
        logger.info("Migrating config database to schema version 3 (portfolio_hash)...")

        # Check if portfolio_hash column exists
        cursor = await db.execute("PRAGMA table_info(recommendations)")
        columns = [row[1] for row in await cursor.fetchall()]

        if "portfolio_hash" not in columns:
            # SQLite doesn't support DROP CONSTRAINT, need table recreation
            # Create new table with correct schema
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS recommendations_new (
                    uuid TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    name TEXT NOT NULL,
                    side TEXT NOT NULL,
                    amount REAL,
                    quantity INTEGER,
                    estimated_price REAL,
                    estimated_value REAL,
                    reason TEXT NOT NULL,
                    country TEXT,                -- Country name from Yahoo Finance
                    industry TEXT,
                    currency TEXT DEFAULT 'EUR',
                    priority REAL,
                    current_portfolio_score REAL,
                    new_portfolio_score REAL,
                    score_change REAL,
                    status TEXT DEFAULT 'pending',
                    portfolio_hash TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    executed_at TEXT,
                    dismissed_at TEXT,
                    UNIQUE(symbol, side, reason, portfolio_hash)
                )
            """
            )

            # Copy data (old recommendations get empty hash, will be regenerated)
            await db.execute(
                """
                INSERT OR IGNORE INTO recommendations_new
                SELECT uuid, symbol, name, side, amount, quantity, estimated_price,
                       estimated_value, reason, geography as country, industry, currency, priority,
                       current_portfolio_score, new_portfolio_score, score_change,
                       status, '', created_at, updated_at, executed_at, dismissed_at
                FROM recommendations
            """
            )

            # Swap tables
            await db.execute("DROP TABLE recommendations")
            await db.execute(
                "ALTER TABLE recommendations_new RENAME TO recommendations"
            )

            # Recreate indexes
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_recommendations_symbol ON recommendations(symbol)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_recommendations_status ON recommendations(status)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_recommendations_created_at ON recommendations(created_at)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_recommendations_portfolio_hash ON recommendations(portfolio_hash)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_recommendations_unique_match "
                "ON recommendations(symbol, side, reason, portfolio_hash)"
            )

        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (
                3,
                now,
                "Added portfolio_hash, changed unique constraint to (symbol, side, reason, portfolio_hash)",
            ),
        )
        await db.commit()
        logger.info("Config database migrated to schema version 3 (portfolio_hash)")
        current_version = 3  # Continue to next migration

    if current_version == 3:
        # Migration: Add last_synced column to stocks (version 3 -> 4)
        now = datetime.now().isoformat()
        logger.info("Migrating config database to schema version 4 (last_synced)...")

        # Check if last_synced column exists
        cursor = await db.execute("PRAGMA table_info(stocks)")
        columns = [row[1] for row in await cursor.fetchall()]

        if "last_synced" not in columns:
            await db.execute("ALTER TABLE stocks ADD COLUMN last_synced TEXT")
            logger.info("Added last_synced column to stocks table")

        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (4, now, "Added last_synced column to stocks for daily pipeline tracking"),
        )
        await db.commit()
        logger.info("Config database migrated to schema version 4 (last_synced)")
        current_version = 4  # Continue to next migration

    if current_version == 4:
        # Migration: Add country and fullExchangeName columns to stocks, update recommendations (version 4 -> 5)
        now = datetime.now().isoformat()
        logger.info(
            "Migrating config database to schema version 5 (country and fullExchangeName)..."
        )

        # Check if country column exists
        cursor = await db.execute("PRAGMA table_info(stocks)")
        columns = [row[1] for row in await cursor.fetchall()]

        if "country" not in columns:
            await db.execute("ALTER TABLE stocks ADD COLUMN country TEXT")
            logger.info("Added country column to stocks table")

        if "fullExchangeName" not in columns:
            await db.execute("ALTER TABLE stocks ADD COLUMN fullExchangeName TEXT")
            logger.info("Added fullExchangeName column to stocks table")

        # Create index on country
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_stocks_country ON stocks(country)"
        )

        # Update recommendations table: add country column (migration from geography)
        cursor = await db.execute("PRAGMA table_info(recommendations)")
        rec_columns = [row[1] for row in await cursor.fetchall()]

        if "country" not in rec_columns:
            await db.execute("ALTER TABLE recommendations ADD COLUMN country TEXT")
            logger.info("Added country column to recommendations table")

        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (
                5,
                now,
                "Added country and fullExchangeName columns to stocks, added country to recommendations",
            ),
        )
        await db.commit()
        logger.info(
            "Config database migrated to schema version 5 (country and fullExchangeName)"
        )
        current_version = 5  # Continue to next migration

    if current_version == 5:
        # Migration: Add min_portfolio_target and max_portfolio_target columns to stocks (version 5 -> 6)
        now = datetime.now().isoformat()
        logger.info(
            "Migrating config database to schema version 6 (portfolio targets)..."
        )

        # Check if min_portfolio_target column exists
        cursor = await db.execute("PRAGMA table_info(stocks)")
        columns = [row[1] for row in await cursor.fetchall()]

        if "min_portfolio_target" not in columns:
            await db.execute("ALTER TABLE stocks ADD COLUMN min_portfolio_target REAL")
            logger.info("Added min_portfolio_target column to stocks table")

        if "max_portfolio_target" not in columns:
            await db.execute("ALTER TABLE stocks ADD COLUMN max_portfolio_target REAL")
            logger.info("Added max_portfolio_target column to stocks table")

        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (
                6,
                now,
                "Added min_portfolio_target and max_portfolio_target columns to stocks",
            ),
        )
        await db.commit()
        logger.info("Config database migrated to schema version 6 (portfolio targets)")
        current_version = 6

    if current_version == 6:
        # Migration: Add country_groups and industry_groups tables (version 6 -> 7)
        now = datetime.now().isoformat()
        logger.info(
            "Migrating config database to schema version 7 (custom grouping)..."
        )

        # Check if country_groups table exists
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='country_groups'"
        )
        if not await cursor.fetchone():
            await db.execute(
                """
                CREATE TABLE country_groups (
                    id INTEGER PRIMARY KEY,
                    group_name TEXT NOT NULL,
                    country_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(group_name, country_name)
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_country_groups_group ON country_groups(group_name)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_country_groups_country ON country_groups(country_name)"
            )
            logger.info("Created country_groups table")

        # Check if industry_groups table exists
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='industry_groups'"
        )
        if not await cursor.fetchone():
            await db.execute(
                """
                CREATE TABLE industry_groups (
                    id INTEGER PRIMARY KEY,
                    group_name TEXT NOT NULL,
                    industry_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(group_name, industry_name)
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_industry_groups_group ON industry_groups(group_name)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_industry_groups_industry ON industry_groups(industry_name)"
            )
            logger.info("Created industry_groups table")

        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (
                7,
                now,
                "Added country_groups and industry_groups tables for custom grouping",
            ),
        )
        await db.commit()
        logger.info("Config database migrated to schema version 7 (custom grouping)")
        current_version = 7

    if current_version == 7:
        # Migration: Add isin column to stocks table (version 7 -> 8)
        now = datetime.now().isoformat()
        logger.info("Migrating config database to schema version 8 (isin column)...")

        # Check if isin column exists
        cursor = await db.execute("PRAGMA table_info(stocks)")
        columns = [row[1] for row in await cursor.fetchall()]

        if "isin" not in columns:
            await db.execute("ALTER TABLE stocks ADD COLUMN isin TEXT")
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_stocks_isin ON stocks(isin)"
            )
            logger.info("Added isin column to stocks table")

        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (
                8,
                now,
                "Added isin column to stocks for ISIN-based symbol resolution",
            ),
        )
        await db.commit()
        logger.info("Config database migrated to schema version 8 (isin column)")


# =============================================================================
# LEDGER.DB - Immutable audit trail (append-only)
# =============================================================================

LEDGER_SCHEMA = """
-- Trade history (append-only, never modified)
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    isin TEXT,                   -- ISIN for broker-agnostic identification
    side TEXT NOT NULL,          -- 'BUY' or 'SELL'
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    executed_at TEXT NOT NULL,
    order_id TEXT UNIQUE,        -- Broker order ID for deduplication
    currency TEXT,
    currency_rate REAL,
    value_eur REAL,              -- Calculated trade value in EUR
    source TEXT DEFAULT 'tradernet',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_executed_at ON trades(executed_at);
CREATE INDEX IF NOT EXISTS idx_trades_order_id ON trades(order_id);
CREATE INDEX IF NOT EXISTS idx_trades_symbol_side ON trades(symbol, side);

-- Cash flow transactions (append-only)
CREATE TABLE IF NOT EXISTS cash_flows (
    id INTEGER PRIMARY KEY,
    transaction_id TEXT UNIQUE NOT NULL,
    type_doc_id INTEGER NOT NULL,
    transaction_type TEXT,       -- 'DEPOSIT', 'WITHDRAWAL', 'DIVIDEND', etc.
    date TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL,
    amount_eur REAL NOT NULL,
    status TEXT,
    status_c INTEGER,
    description TEXT,
    params_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cash_flows_date ON cash_flows(date);
CREATE INDEX IF NOT EXISTS idx_cash_flows_type ON cash_flows(transaction_type);

-- Dividend history with DRIP tracking
-- Tracks dividend payments and whether they were reinvested.
-- pending_bonus: If dividend couldn't be reinvested (too small), store a bonus
-- that the optimizer will apply to that stock's expected return.
CREATE TABLE IF NOT EXISTS dividend_history (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    cash_flow_id INTEGER,            -- Link to cash_flows table (optional)
    amount REAL NOT NULL,            -- Original dividend amount
    currency TEXT NOT NULL,
    amount_eur REAL NOT NULL,        -- Converted amount in EUR
    payment_date TEXT NOT NULL,
    reinvested INTEGER DEFAULT 0,    -- 0 = not reinvested, 1 = reinvested
    reinvested_at TEXT,              -- When reinvestment trade executed
    reinvested_quantity INTEGER,     -- Shares bought with dividend
    pending_bonus REAL DEFAULT 0,    -- Bonus to apply to expected return (0.0 to 1.0)
    bonus_cleared INTEGER DEFAULT 0, -- 1 when bonus has been used
    cleared_at TEXT,                 -- When bonus was cleared
    created_at TEXT NOT NULL,
    FOREIGN KEY (cash_flow_id) REFERENCES cash_flows(id)
);

CREATE INDEX IF NOT EXISTS idx_dividend_history_symbol ON dividend_history(symbol);
CREATE INDEX IF NOT EXISTS idx_dividend_history_date ON dividend_history(payment_date);
CREATE INDEX IF NOT EXISTS idx_dividend_history_pending ON dividend_history(pending_bonus) WHERE pending_bonus > 0;

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    description TEXT
);
"""


async def init_ledger_schema(db):
    """Initialize ledger database schema."""
    await db.executescript(LEDGER_SCHEMA)

    row = await db.fetchone("SELECT MAX(version) as v FROM schema_version")
    current_version = row["v"] if row and row["v"] else 0

    if current_version == 0:
        now = datetime.now().isoformat()
        # Create ISIN index for new databases
        await db.execute("CREATE INDEX IF NOT EXISTS idx_trades_isin ON trades(isin)")
        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (3, now, "Initial ledger schema with ISIN column"),
        )
        await db.commit()
        logger.info("Ledger database initialized with schema version 3")
    elif current_version == 1:
        # Migration: Add dividend_history table (version 1 -> 2)
        now = datetime.now().isoformat()
        logger.info(
            "Migrating ledger database to schema version 2 (dividend_history)..."
        )

        # Table is created by executescript above (CREATE IF NOT EXISTS)
        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (2, now, "Added dividend_history table for DRIP tracking"),
        )
        await db.commit()
        logger.info("Ledger database migrated to schema version 2")
        current_version = 2  # Continue to next migration

    if current_version == 2:
        # Migration: Add ISIN column to trades (version 2 -> 3)
        now = datetime.now().isoformat()
        logger.info("Migrating ledger database to schema version 3 (ISIN)...")

        cursor = await db.execute("PRAGMA table_info(trades)")
        columns = [row[1] for row in await cursor.fetchall()]

        if "isin" not in columns:
            await db.execute("ALTER TABLE trades ADD COLUMN isin TEXT")
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_trades_isin ON trades(isin)"
            )
            logger.info("Added isin column to trades table")

        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (3, now, "Added ISIN column to trades"),
        )
        await db.commit()
        logger.info("Ledger database migrated to schema version 3")


# =============================================================================
# STATE.DB - Current state (rebuildable from ledger)
# =============================================================================

STATE_SCHEMA = """
-- Current positions (derived from ledger, can be rebuilt)
CREATE TABLE IF NOT EXISTS positions (
    symbol TEXT PRIMARY KEY,
    isin TEXT,                   -- ISIN for broker-agnostic identification
    quantity REAL NOT NULL,
    avg_price REAL NOT NULL,
    current_price REAL,
    currency TEXT DEFAULT 'EUR',
    currency_rate REAL DEFAULT 1.0,
    market_value_eur REAL,
    cost_basis_eur REAL,
    unrealized_pnl REAL,
    unrealized_pnl_pct REAL,
    last_updated TEXT,
    first_bought_at TEXT,
    last_sold_at TEXT
);

-- Note: idx_positions_isin is created in migration or init_state_schema for new databases

-- Stock scores (cached calculations)
CREATE TABLE IF NOT EXISTS scores (
    symbol TEXT PRIMARY KEY,

    -- Component scores (0-1 range)
    quality_score REAL,
    opportunity_score REAL,
    analyst_score REAL,
    allocation_fit_score REAL,

    -- Sub-components for debugging
    cagr_score REAL,
    consistency_score REAL,
    financial_strength_score REAL,
    sharpe_score REAL,
    drawdown_score REAL,
    dividend_bonus REAL,

    -- Technical indicators
    rsi REAL,
    ema_200 REAL,
    below_52w_high_pct REAL,

    -- Combined scores
    total_score REAL,
    sell_score REAL,

    -- Metadata
    history_years REAL,
    calculated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_scores_total ON scores(total_score);

-- Portfolio snapshots (daily summary)
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    date TEXT PRIMARY KEY,
    total_value REAL NOT NULL,
    cash_balance REAL NOT NULL,
    invested_value REAL,
    unrealized_pnl REAL,
    geo_eu_pct REAL,
    geo_asia_pct REAL,
    geo_us_pct REAL,
    position_count INTEGER,
    annual_turnover REAL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_snapshots_date ON portfolio_snapshots(date);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    description TEXT
);
"""


async def init_state_schema(db):
    """Initialize state database schema."""
    await db.executescript(STATE_SCHEMA)

    row = await db.fetchone("SELECT MAX(version) as v FROM schema_version")
    current_version = row["v"] if row and row["v"] else 0

    if current_version == 0:
        now = datetime.now().isoformat()
        # Create ISIN index for new databases
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_positions_isin ON positions(isin)"
        )
        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (2, now, "Initial state schema with ISIN column"),
        )
        await db.commit()
        logger.info("State database initialized with schema version 2")
    elif current_version == 1:
        # Migration: Add ISIN column to positions (version 1 -> 2)
        now = datetime.now().isoformat()
        logger.info("Migrating state database to schema version 2 (ISIN)...")

        cursor = await db.execute("PRAGMA table_info(positions)")
        columns = [row[1] for row in await cursor.fetchall()]

        if "isin" not in columns:
            await db.execute("ALTER TABLE positions ADD COLUMN isin TEXT")
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_positions_isin ON positions(isin)"
            )
            logger.info("Added isin column to positions table")

        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (2, now, "Added ISIN column to positions"),
        )
        await db.commit()
        logger.info("State database migrated to schema version 2")

    # Migration: Add annual_turnover column to portfolio_snapshots (version 2 -> 3)
    if current_version == 2:
        now = datetime.now().isoformat()
        logger.info("Migrating state database to schema version 3 (annual_turnover)...")

        try:
            # Check if column already exists
            cursor = await db.execute("PRAGMA table_info(portfolio_snapshots)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

            if "annual_turnover" not in column_names:
                await db.execute(
                    "ALTER TABLE portfolio_snapshots ADD COLUMN annual_turnover REAL"
                )
                logger.info("Added annual_turnover column to portfolio_snapshots")

            await db.execute(
                "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
                (
                    3,
                    now,
                    "Added annual_turnover column to portfolio_snapshots",
                ),
            )
            await db.commit()
            logger.info("State database migrated to schema version 3")
        except Exception as e:
            logger.error(f"Failed to migrate state schema to version 3: {e}")
            await db.rollback()


# =============================================================================
# CACHE.DB - Computed aggregates (ephemeral, can be rebuilt)
# =============================================================================

CACHE_SCHEMA = """
-- Generic cache entries with TTL
CREATE TABLE IF NOT EXISTS cache_entries (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,         -- JSON serialized
    expires_at TEXT,             -- NULL = never expires
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache_entries(expires_at);

-- Yahoo Finance data cache
CREATE TABLE IF NOT EXISTS yahoo_cache (
    symbol TEXT NOT NULL,
    data_type TEXT NOT NULL,     -- 'quote', 'fundamentals', 'history'
    data TEXT NOT NULL,          -- JSON serialized
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (symbol, data_type)
);

CREATE INDEX IF NOT EXISTS idx_yahoo_cache_expires ON yahoo_cache(expires_at);

-- Recommendation cache keyed by portfolio hash
CREATE TABLE IF NOT EXISTS recommendation_cache (
    portfolio_hash TEXT NOT NULL,
    cache_type TEXT NOT NULL,  -- 'buy', 'sell', 'multi_step', 'strategic'
    data TEXT NOT NULL,        -- JSON serialized
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (portfolio_hash, cache_type)
);

CREATE INDEX IF NOT EXISTS idx_rec_cache_expires ON recommendation_cache(expires_at);

-- Analytics cache for expensive computations (performance weights, risk metrics)
CREATE TABLE IF NOT EXISTS analytics_cache (
    cache_key TEXT PRIMARY KEY,
    data TEXT NOT NULL,        -- JSON serialized
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_analytics_cache_expires ON analytics_cache(expires_at);

-- Exchange rates cache (1 hour TTL, single source of truth for currency conversion)
CREATE TABLE IF NOT EXISTS exchange_rates (
    from_currency TEXT NOT NULL,
    to_currency TEXT NOT NULL,
    rate REAL NOT NULL,
    fetched_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    PRIMARY KEY (from_currency, to_currency)
);

CREATE INDEX IF NOT EXISTS idx_exchange_rates_expires ON exchange_rates(expires_at);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    description TEXT
);
"""


async def init_cache_schema(db):
    """Initialize cache database schema."""
    await db.executescript(CACHE_SCHEMA)

    row = await db.fetchone("SELECT MAX(version) as v FROM schema_version")
    current_version = row["v"] if row and row["v"] else 0

    if current_version == 0:
        now = datetime.now().isoformat()
        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (2, now, "Initial cache schema with recommendation and analytics cache"),
        )
        await db.commit()
        logger.info("Cache database initialized with schema version 2")
    elif current_version == 1:
        # Migration: Add recommendation_cache and analytics_cache tables
        now = datetime.now().isoformat()
        logger.info("Migrating cache database to version 2 (recommendation cache)...")

        # Tables are created by executescript above (CREATE IF NOT EXISTS)
        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (2, now, "Added recommendation_cache and analytics_cache tables"),
        )
        await db.commit()
        logger.info("Cache database migrated to schema version 2")


# =============================================================================
# HISTORY/{SYMBOL}.DB - Per-symbol price data
# =============================================================================

HISTORY_SCHEMA = """
-- Daily price data
CREATE TABLE IF NOT EXISTS daily_prices (
    date TEXT PRIMARY KEY,
    open_price REAL,
    high_price REAL,
    low_price REAL,
    close_price REAL NOT NULL,
    volume INTEGER,
    source TEXT DEFAULT 'yahoo',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_daily_date ON daily_prices(date);

-- Monthly aggregates (for CAGR calculations)
CREATE TABLE IF NOT EXISTS monthly_prices (
    year_month TEXT PRIMARY KEY,  -- 'YYYY-MM' format
    avg_close REAL NOT NULL,
    avg_adj_close REAL,
    min_price REAL,
    max_price REAL,
    source TEXT DEFAULT 'calculated',
    created_at TEXT NOT NULL
);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    description TEXT
);
"""


async def init_history_schema(db):
    """Initialize per-symbol history database schema."""
    await db.executescript(HISTORY_SCHEMA)

    row = await db.fetchone("SELECT MAX(version) as v FROM schema_version")
    current_version = row["v"] if row and row["v"] else 0

    if current_version == 0:
        now = datetime.now().isoformat()
        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (1, now, "Initial history schema"),
        )
        await db.commit()
        logger.info("History database initialized with schema version 1")


# =============================================================================
# CALCULATIONS.DB - Pre-computed raw metrics
# =============================================================================

CALCULATIONS_SCHEMA = """
-- Pre-computed raw metrics for all stocks
CREATE TABLE IF NOT EXISTS calculated_metrics (
    symbol TEXT NOT NULL,
    isin TEXT,                      -- ISIN for broker-agnostic identification
    metric TEXT NOT NULL,           -- e.g., 'RSI_14', 'EMA_200', 'BB_LOWER', 'CAGR_5Y', 'SHARPE'
    value REAL NOT NULL,
    calculated_at TEXT NOT NULL,    -- ISO datetime
    expires_at TEXT,                -- Optional TTL for cache invalidation
    source TEXT DEFAULT 'calculated', -- 'calculated', 'yahoo', 'pyfolio'
    PRIMARY KEY (symbol, metric)
);

CREATE INDEX IF NOT EXISTS idx_calculations_symbol ON calculated_metrics(symbol);
CREATE INDEX IF NOT EXISTS idx_calculations_metric ON calculated_metrics(metric);
CREATE INDEX IF NOT EXISTS idx_calculations_expires ON calculated_metrics(expires_at);
-- Note: idx_calculations_isin is created in migration or init_calculations_schema

-- Stock scores (cached composite calculations)
-- Moved from state.db as these are calculated values, not state
CREATE TABLE IF NOT EXISTS scores (
    symbol TEXT PRIMARY KEY,
    isin TEXT,                      -- ISIN for broker-agnostic identification

    -- Component scores (0-1 range)
    quality_score REAL,
    opportunity_score REAL,
    analyst_score REAL,
    allocation_fit_score REAL,

    -- Sub-components for debugging
    cagr_score REAL,
    consistency_score REAL,
    financial_strength_score REAL,
    sharpe_score REAL,
    drawdown_score REAL,
    dividend_bonus REAL,

    -- Technical indicators
    rsi REAL,
    ema_200 REAL,
    below_52w_high_pct REAL,

    -- Combined scores
    total_score REAL,
    sell_score REAL,

    -- Metadata
    history_years REAL,
    calculated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_scores_total ON scores(total_score);
-- Note: idx_scores_isin is created in migration or init_calculations_schema

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    description TEXT
);
"""


async def init_calculations_schema(db):
    """Initialize calculations database schema."""
    await db.executescript(CALCULATIONS_SCHEMA)

    row = await db.fetchone("SELECT MAX(version) as v FROM schema_version")
    current_version = row["v"] if row and row["v"] else 0

    if current_version == 0:
        now = datetime.now().isoformat()
        # Create ISIN indexes for new databases
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_calculations_isin ON calculated_metrics(isin)"
        )
        await db.execute("CREATE INDEX IF NOT EXISTS idx_scores_isin ON scores(isin)")
        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (3, now, "Initial calculations schema with ISIN columns"),
        )
        await db.commit()
        logger.info("Calculations database initialized with schema version 3")
    elif current_version == 1:
        # Migration: Add scores table (version 1 -> 2)
        now = datetime.now().isoformat()
        logger.info("Migrating calculations database to schema version 2 (scores)...")

        # Table is created by executescript above (CREATE IF NOT EXISTS)
        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (2, now, "Added scores table (moved from state.db)"),
        )
        await db.commit()
        logger.info("Calculations database migrated to schema version 2")
        current_version = 2  # Continue to next migration

    if current_version == 2:
        # Migration: Add ISIN columns (version 2 -> 3)
        now = datetime.now().isoformat()
        logger.info("Migrating calculations database to schema version 3 (ISIN)...")

        # Add isin column to calculated_metrics
        cursor = await db.execute("PRAGMA table_info(calculated_metrics)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "isin" not in columns:
            await db.execute("ALTER TABLE calculated_metrics ADD COLUMN isin TEXT")
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_calculations_isin ON calculated_metrics(isin)"
            )
            logger.info("Added isin column to calculated_metrics table")

        # Add isin column to scores
        cursor = await db.execute("PRAGMA table_info(scores)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "isin" not in columns:
            await db.execute("ALTER TABLE scores ADD COLUMN isin TEXT")
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_scores_isin ON scores(isin)"
            )
            logger.info("Added isin column to scores table")

        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (3, now, "Added ISIN columns to calculated_metrics and scores"),
        )
        await db.commit()
        logger.info("Calculations database migrated to schema version 3")


# =============================================================================
# RECOMMENDATIONS.DB - Trade recommendations (operational data)
# =============================================================================

RECOMMENDATIONS_SCHEMA = """
-- Trade recommendations (stored with UUIDs for dismissal tracking)
-- Uses portfolio_hash to identify same recommendations for same portfolio state
CREATE TABLE IF NOT EXISTS recommendations (
    uuid TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    isin TEXT,                       -- ISIN for broker-agnostic identification
    name TEXT NOT NULL,
    side TEXT NOT NULL,  -- 'BUY' or 'SELL'
    amount REAL,  -- Display only, not part of uniqueness
    quantity INTEGER,
    estimated_price REAL,
    estimated_value REAL,
    reason TEXT NOT NULL,
    country TEXT,
    industry TEXT,
    currency TEXT DEFAULT 'EUR',
    priority REAL,
    current_portfolio_score REAL,
    new_portfolio_score REAL,
    score_change REAL,
    status TEXT DEFAULT 'pending',  -- 'pending', 'executed', 'dismissed'
    portfolio_hash TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    executed_at TEXT,
    dismissed_at TEXT,
    UNIQUE(symbol, side, reason, portfolio_hash)
);

CREATE INDEX IF NOT EXISTS idx_recommendations_symbol ON recommendations(symbol);
-- Note: idx_recommendations_isin is created in migration or init_recommendations_schema
CREATE INDEX IF NOT EXISTS idx_recommendations_status ON recommendations(status);
CREATE INDEX IF NOT EXISTS idx_recommendations_created_at ON recommendations(created_at);
CREATE INDEX IF NOT EXISTS idx_recommendations_portfolio_hash ON recommendations(portfolio_hash);
CREATE INDEX IF NOT EXISTS idx_recommendations_unique_match
    ON recommendations(symbol, side, reason, portfolio_hash);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    description TEXT
);
"""


async def init_recommendations_schema(db):
    """Initialize recommendations database schema."""
    await db.executescript(RECOMMENDATIONS_SCHEMA)

    row = await db.fetchone("SELECT MAX(version) as v FROM schema_version")
    current_version = row["v"] if row and row["v"] else 0

    if current_version == 0:
        now = datetime.now().isoformat()
        # Create ISIN index for new databases
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_recommendations_isin ON recommendations(isin)"
        )
        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (2, now, "Initial recommendations schema with ISIN column"),
        )
        await db.commit()
        logger.info("Recommendations database initialized with schema version 2")
    elif current_version == 1:
        # Migration: Add ISIN column (version 1 -> 2)
        now = datetime.now().isoformat()
        logger.info("Migrating recommendations database to schema version 2 (ISIN)...")

        cursor = await db.execute("PRAGMA table_info(recommendations)")
        columns = [row[1] for row in await cursor.fetchall()]

        if "isin" not in columns:
            await db.execute("ALTER TABLE recommendations ADD COLUMN isin TEXT")
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_recommendations_isin ON recommendations(isin)"
            )
            logger.info("Added isin column to recommendations table")

        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (2, now, "Added ISIN column to recommendations"),
        )
        await db.commit()
        logger.info("Recommendations database migrated to schema version 2")


# =============================================================================
# DIVIDENDS.DB - Dividend history with DRIP tracking
# =============================================================================

DIVIDENDS_SCHEMA = """
-- Dividend history with DRIP tracking
-- Tracks dividend payments and whether they were reinvested.
-- pending_bonus: If dividend couldn't be reinvested (too small), store a bonus
-- that the optimizer will apply to that stock's expected return.
CREATE TABLE IF NOT EXISTS dividend_history (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    isin TEXT,                       -- ISIN for broker-agnostic identification
    cash_flow_id INTEGER,            -- Link to cash_flows table in ledger.db (optional)
    amount REAL NOT NULL,            -- Original dividend amount
    currency TEXT NOT NULL,
    amount_eur REAL NOT NULL,        -- Converted amount in EUR
    payment_date TEXT NOT NULL,
    reinvested INTEGER DEFAULT 0,    -- 0 = not reinvested, 1 = reinvested
    reinvested_at TEXT,              -- When reinvestment trade executed
    reinvested_quantity INTEGER,     -- Shares bought with dividend
    pending_bonus REAL DEFAULT 0,    -- Bonus to apply to expected return (0.0 to 1.0)
    bonus_cleared INTEGER DEFAULT 0, -- 1 when bonus has been used
    cleared_at TEXT,                 -- When bonus was cleared
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_dividend_history_symbol ON dividend_history(symbol);
-- Note: idx_dividend_history_isin is created in migration or init_dividends_schema
CREATE INDEX IF NOT EXISTS idx_dividend_history_date ON dividend_history(payment_date);
CREATE INDEX IF NOT EXISTS idx_dividend_history_pending ON dividend_history(pending_bonus)
    WHERE pending_bonus > 0;

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    description TEXT
);
"""


async def init_dividends_schema(db):
    """Initialize dividends database schema."""
    await db.executescript(DIVIDENDS_SCHEMA)

    row = await db.fetchone("SELECT MAX(version) as v FROM schema_version")
    current_version = row["v"] if row and row["v"] else 0

    if current_version == 0:
        now = datetime.now().isoformat()
        # Create ISIN index for new databases
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_dividend_history_isin ON dividend_history(isin)"
        )
        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (2, now, "Initial dividends schema with ISIN column"),
        )
        await db.commit()
        logger.info("Dividends database initialized with schema version 2")
    elif current_version == 1:
        # Migration: Add ISIN column (version 1 -> 2)
        now = datetime.now().isoformat()
        logger.info("Migrating dividends database to schema version 2 (ISIN)...")

        cursor = await db.execute("PRAGMA table_info(dividend_history)")
        columns = [row[1] for row in await cursor.fetchall()]

        if "isin" not in columns:
            await db.execute("ALTER TABLE dividend_history ADD COLUMN isin TEXT")
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_dividend_history_isin ON dividend_history(isin)"
            )
            logger.info("Added isin column to dividend_history table")

        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (2, now, "Added ISIN column to dividend_history"),
        )
        await db.commit()
        logger.info("Dividends database migrated to schema version 2")


# =============================================================================
# RATES.DB - Exchange rates (persistent, not ephemeral cache)
# =============================================================================

RATES_SCHEMA = """
-- Exchange rates (single source of truth for currency conversion)
CREATE TABLE IF NOT EXISTS exchange_rates (
    from_currency TEXT NOT NULL,
    to_currency TEXT NOT NULL,
    rate REAL NOT NULL,
    fetched_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    PRIMARY KEY (from_currency, to_currency)
);

CREATE INDEX IF NOT EXISTS idx_exchange_rates_expires ON exchange_rates(expires_at);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    description TEXT
);
"""


async def init_rates_schema(db):
    """Initialize rates database schema."""
    await db.executescript(RATES_SCHEMA)

    row = await db.fetchone("SELECT MAX(version) as v FROM schema_version")
    current_version = row["v"] if row and row["v"] else 0

    if current_version == 0:
        now = datetime.now().isoformat()
        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (1, now, "Initial rates schema"),
        )
        await db.commit()
        logger.info("Rates database initialized with schema version 1")


# =============================================================================
# SNAPSHOTS.DB - Portfolio snapshots (daily time-series)
# =============================================================================

SNAPSHOTS_SCHEMA = """
-- Portfolio snapshots (daily summary)
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    date TEXT PRIMARY KEY,
    total_value REAL NOT NULL,
    cash_balance REAL NOT NULL,
    invested_value REAL,
    unrealized_pnl REAL,
    geo_eu_pct REAL,
    geo_asia_pct REAL,
    geo_us_pct REAL,
    position_count INTEGER,
    annual_turnover REAL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_snapshots_date ON portfolio_snapshots(date);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    description TEXT
);
"""


async def init_snapshots_schema(db):
    """Initialize snapshots database schema."""
    await db.executescript(SNAPSHOTS_SCHEMA)

    row = await db.fetchone("SELECT MAX(version) as v FROM schema_version")
    current_version = row["v"] if row and row["v"] else 0

    if current_version == 0:
        now = datetime.now().isoformat()
        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (1, now, "Initial snapshots schema"),
        )
        await db.commit()
        logger.info("Snapshots database initialized with schema version 1")
        current_version = 1

    # Migration: Add annual_turnover column (version 1 -> 2)
    if current_version == 1:
        try:
            # Check if column already exists
            cursor = await db.execute("PRAGMA table_info(portfolio_snapshots)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

            if "annual_turnover" not in column_names:
                await db.execute(
                    "ALTER TABLE portfolio_snapshots ADD COLUMN annual_turnover REAL"
                )
                logger.info("Added annual_turnover column to portfolio_snapshots")

            now = datetime.now().isoformat()
            await db.execute(
                "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
                (
                    2,
                    now,
                    "Added annual_turnover column for portfolio turnover tracking",
                ),
            )
            await db.commit()
            logger.info("Snapshots database migrated to schema version 2")
        except Exception as e:
            logger.error(f"Failed to migrate snapshots schema to version 2: {e}")
            await db.rollback()


# =============================================================================
# PLANNER.DB - Holistic planner sequences and evaluations
# =============================================================================

# Planner schema initialization is now in app.modules.planning.database.schemas
# Imported directly in manager.py to avoid circular dependencies
