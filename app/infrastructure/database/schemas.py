"""
Database Schemas - CREATE TABLE statements for all databases.

This module contains schema definitions for:
- config.db: Stock universe, allocation targets, settings
- ledger.db: Trades, cash flows (append-only)
- state.db: Positions, scores, snapshots (current state)
- cache.db: Computed aggregates
- calculations.db: Pre-computed raw metrics (RSI, EMA, Sharpe, CAGR, etc.)
- history/{symbol}.db: Per-symbol price data
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
    name TEXT NOT NULL,
    industry TEXT,
    geography TEXT NOT NULL,
    priority_multiplier REAL DEFAULT 1.0,
    min_lot INTEGER DEFAULT 1,
    active INTEGER DEFAULT 1,
    allow_buy INTEGER DEFAULT 1,
    allow_sell INTEGER DEFAULT 0,
    currency TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stocks_active ON stocks(active);
CREATE INDEX IF NOT EXISTS idx_stocks_geography ON stocks(geography);

-- Allocation targets (geography and industry weightings)
CREATE TABLE IF NOT EXISTS allocation_targets (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL,      -- 'geography' or 'industry'
    name TEXT NOT NULL,
    target_pct REAL NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(type, name)
);

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
    geography TEXT,
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

DEFAULT_ALLOCATION_TARGETS = [
    ("geography", "EU", 0.50),
    ("geography", "ASIA", 0.30),
    ("geography", "US", 0.20),
    ("industry", "Technology", 0.20),
    ("industry", "Healthcare", 0.20),
    ("industry", "Finance", 0.20),
    ("industry", "Consumer", 0.20),
    ("industry", "Industrial", 0.20),
]

# Default settings for new database installations
# NOTE: min_trade_size and recommendation_depth removed - optimizer handles this now
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
    # Job scheduling
    ("job_portfolio_sync_minutes", "15", "Portfolio sync interval in minutes"),
    ("job_trade_sync_minutes", "5", "Trade sync interval in minutes"),
    ("job_price_sync_minutes", "5", "Price sync interval in minutes"),
    ("job_score_refresh_minutes", "30", "Score refresh interval in minutes"),
    ("job_rebalance_check_minutes", "15", "Rebalance check interval in minutes"),
    ("job_cash_flow_sync_hour", "18", "Cash flow sync hour (0-23)"),
    ("job_historical_sync_hour", "22", "Historical sync hour (0-23)"),
    ("job_maintenance_hour", "3", "Maintenance job hour (0-23)"),
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

        # Record schema version
        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (3, now, "Initial config schema with portfolio_hash recommendations"),
        )

        await db.commit()
        logger.info(
            "Config database initialized with schema version 3 (includes portfolio_hash recommendations)"
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
                    geography TEXT,
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
                       estimated_value, reason, geography, industry, currency, priority,
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


# =============================================================================
# LEDGER.DB - Immutable audit trail (append-only)
# =============================================================================

LEDGER_SCHEMA = """
-- Trade history (append-only, never modified)
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
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
        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (2, now, "Initial ledger schema with dividend_history"),
        )
        await db.commit()
        logger.info(
            "Ledger database initialized with schema version 2 (includes dividend_history)"
        )
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


# =============================================================================
# STATE.DB - Current state (rebuildable from ledger)
# =============================================================================

STATE_SCHEMA = """
-- Current positions (derived from ledger, can be rebuilt)
CREATE TABLE IF NOT EXISTS positions (
    symbol TEXT PRIMARY KEY,
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
        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (1, now, "Initial state schema"),
        )
        await db.commit()
        logger.info("State database initialized with schema version 1")


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
        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (1, now, "Initial calculations schema"),
        )
        await db.commit()
        logger.info("Calculations database initialized with schema version 1")
