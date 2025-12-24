"""
Database Schemas - CREATE TABLE statements for all databases.

This module contains schema definitions for:
- config.db: Stock universe, allocation targets, settings
- ledger.db: Trades, cash flows (append-only)
- state.db: Positions, scores, snapshots (current state)
- cache.db: Computed aggregates
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

DEFAULT_SETTINGS = [
    ("min_cash_threshold", "400", "Minimum EUR cash to trigger rebalance"),
    ("min_trade_size", "400", "Minimum EUR trade size (keeps commission at 0.5%)"),
    ("max_trades_per_cycle", "5", "Maximum trades per rebalance cycle"),
    ("min_stock_score", "0.5", "Minimum score to consider buying"),
    ("recommendation_depth", "1", "Number of steps in multi-step recommendations (1-5)"),
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
                (type_, name, target, now, now)
            )

        # Insert default settings
        for key, value, desc in DEFAULT_SETTINGS:
            await db.execute(
                """INSERT OR IGNORE INTO settings
                   (key, value, description, updated_at)
                   VALUES (?, ?, ?, ?)""",
                (key, value, desc, now)
            )

        # Record schema version
        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (1, now, "Initial config schema")
        )

        await db.commit()
        logger.info("Config database initialized with schema version 1")


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
            (1, now, "Initial ledger schema")
        )
        await db.commit()
        logger.info("Ledger database initialized with schema version 1")


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
            (1, now, "Initial state schema")
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
            (1, now, "Initial cache schema")
        )
        await db.commit()
        logger.info("Cache database initialized with schema version 1")


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
            (1, now, "Initial history schema")
        )
        await db.commit()
