// Package database provides database connection and initialization functionality.
package database

import (
	"context"
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	_ "modernc.org/sqlite" // Pure Go SQLite driver
)

// DatabaseProfile defines different configuration profiles for databases
type DatabaseProfile string

const (
	// ProfileLedger - Maximum safety for immutable audit trail
	ProfileLedger DatabaseProfile = "ledger"
	// ProfileCache - Maximum speed for ephemeral data
	ProfileCache DatabaseProfile = "cache"
	// ProfileStandard - Balanced configuration for most databases
	ProfileStandard DatabaseProfile = "standard"
)

// DB wraps the database connection with production-grade configuration
type DB struct {
	conn    *sql.DB
	path    string
	profile DatabaseProfile
	name    string // Database name for logging
}

// Config holds database configuration
type Config struct {
	Path    string
	Profile DatabaseProfile
	Name    string // Friendly name for logging (e.g., "universe", "ledger")
}

// New creates a new database connection with production-grade configuration
func New(cfg Config) (*DB, error) {
	// Ensure directory exists - resolve to absolute path to avoid relative path issues
	absPath, err := filepath.Abs(cfg.Path)
	if err != nil {
		return nil, fmt.Errorf("failed to resolve database path to absolute: %w", err)
	}
	dir := filepath.Dir(absPath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create database directory: %w", err)
	}
	// Use absolute path for database operations
	cfg.Path = absPath

	// Default to standard profile if not specified
	if cfg.Profile == "" {
		cfg.Profile = ProfileStandard
	}

	// Build connection string with appropriate PRAGMAs
	connStr := buildConnectionString(cfg.Path, cfg.Profile)

	// Open database connection
	conn, err := sql.Open("sqlite", connStr)
	if err != nil {
		return nil, fmt.Errorf("failed to open database %s: %w", cfg.Name, err)
	}

	// Configure connection pool for long-term operation
	configureConnectionPool(conn, cfg.Profile)

	// Test connection with timeout
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := conn.PingContext(ctx); err != nil {
		return nil, fmt.Errorf("failed to ping database %s: %w", cfg.Name, err)
	}

	db := &DB{
		conn:    conn,
		path:    cfg.Path,
		profile: cfg.Profile,
		name:    cfg.Name,
	}

	// Apply additional PRAGMAs that can't be set via connection string
	if err := db.applyRuntimePragmas(); err != nil {
		return nil, fmt.Errorf("failed to apply runtime PRAGMAs for %s: %w", cfg.Name, err)
	}

	return db, nil
}

// buildConnectionString creates SQLite connection string with profile-specific PRAGMAs
func buildConnectionString(path string, profile DatabaseProfile) string {
	// Base connection string with WAL mode (all databases)
	connStr := path + "?_pragma=journal_mode(WAL)"

	// Profile-specific PRAGMAs
	switch profile {
	case ProfileLedger:
		// Maximum safety - audit trail for real money
		connStr += "&_pragma=synchronous(FULL)" // Fsync after every write
		connStr += "&_pragma=auto_vacuum(NONE)" // Never shrink (append-only)

	case ProfileCache:
		// Maximum speed - ephemeral data
		connStr += "&_pragma=synchronous(OFF)"   // No fsync (it's cache!)
		connStr += "&_pragma=auto_vacuum(FULL)"  // Auto-reclaim space
		connStr += "&_pragma=temp_store(MEMORY)" // Temp tables in RAM

	case ProfileStandard:
		// Balanced - most databases
		connStr += "&_pragma=synchronous(NORMAL)"      // Fsync at checkpoints
		connStr += "&_pragma=auto_vacuum(INCREMENTAL)" // Gradual space reclamation
		connStr += "&_pragma=temp_store(MEMORY)"       // Temp tables in RAM
	}

	// Common PRAGMAs for all profiles
	connStr += "&_pragma=foreign_keys(1)"          // Enable foreign key constraints
	connStr += "&_pragma=wal_autocheckpoint(1000)" // Checkpoint every 1000 pages
	connStr += "&_pragma=cache_size(-64000)"       // 64MB cache (negative = KB)

	return connStr
}

// configureConnectionPool sets up connection pool for long-term operation
func configureConnectionPool(conn *sql.DB, profile DatabaseProfile) {
	// Connection pool limits
	conn.SetMaxOpenConns(25) // Max concurrent connections
	conn.SetMaxIdleConns(5)  // Keep some connections warm

	// Connection lifecycle management (prevent stale connections)
	conn.SetConnMaxLifetime(1 * time.Hour)    // Recycle connections after 1 hour
	conn.SetConnMaxIdleTime(10 * time.Minute) // Close idle connections after 10 minutes

	// Cache database can have fewer connections (less frequently accessed)
	if profile == ProfileCache {
		conn.SetMaxOpenConns(10)
		conn.SetMaxIdleConns(2)
	}
}

// applyRuntimePragmas applies PRAGMAs that require a query execution
func (db *DB) applyRuntimePragmas() error {
	// These PRAGMAs don't work via connection string, must be executed
	// Currently all critical PRAGMAs are handled via connection string
	// This method is here for future runtime-only PRAGMAs if needed
	return nil
}

// Close closes the database connection
func (db *DB) Close() error {
	return db.conn.Close()
}

// Conn returns the underlying sql.DB connection
// Used by repositories to execute queries
func (db *DB) Conn() *sql.DB {
	return db.conn
}

// Name returns the database name for logging
func (db *DB) Name() string {
	return db.name
}

// Profile returns the database profile
func (db *DB) Profile() DatabaseProfile {
	return db.profile
}

// Path returns the database file path
func (db *DB) Path() string {
	return db.path
}

// Migrate applies the database schema from the schemas directory
// This is the single source of truth for each database's schema
func (db *DB) Migrate() error {
	// Map database names to their schema files
	schemaFiles := map[string]string{
		"universe":  "universe_schema.sql",
		"config":    "config_schema.sql",
		"ledger":    "ledger_schema.sql",
		"portfolio": "portfolio_schema.sql",
		"agents":    "agents_schema.sql",
		"history":   "history_schema.sql",
		"cache":     "cache_schema.sql",
	}

	schemaFile, ok := schemaFiles[db.name]
	if !ok {
		// Unknown database name, skip migration
		return nil
	}
	// Try multiple paths to find schemas directory
	var schemasDir string

	// 1. Try relative to database path (for absolute paths)
	dbDir := filepath.Dir(db.path)
	candidates := []string{
		filepath.Join(dbDir, "../trader/internal/database/schemas"),      // From ../data to trader/internal/...
		filepath.Join(dbDir, "../repo/trader/internal/database/schemas"), // From ../data to repo/trader/internal/...
		filepath.Join(dbDir, "../internal/database/schemas"),             // From ../data to internal/...
		filepath.Join(dbDir, "internal/database/schemas"),                // Same directory
		"internal/database/schemas",                                      // Relative to CWD
		"./internal/database/schemas",                                    // Explicit relative
	}

	// Also try from executable directory if available
	if execPath, err := os.Executable(); err == nil {
		execDir := filepath.Dir(execPath)
		candidates = append(candidates,
			filepath.Join(execDir, "internal/database/schemas"),
			filepath.Join(filepath.Dir(execDir), "internal/database/schemas"),
			filepath.Join(execDir, "../repo/trader/internal/database/schemas"),            // From bin/ to repo/trader/internal/...
			filepath.Join(filepath.Dir(execDir), "repo/trader/internal/database/schemas"), // From app/ to repo/trader/internal/...
		)
	}

	// Find first existing schemas directory
	for _, candidate := range candidates {
		if absPath, err := filepath.Abs(candidate); err == nil {
			if info, err := os.Stat(absPath); err == nil && info.IsDir() {
				schemasDir = absPath
				break
			}
		}
	}

	// Check if schemas directory exists
	if schemasDir == "" {
		// Schemas directory doesn't exist, skip (tables may already exist)
		return nil
	}

	// Read and execute the schema file
	schemaPath := filepath.Join(schemasDir, schemaFile)
	content, err := os.ReadFile(schemaPath)
	if err != nil {
		// Schema file doesn't exist, skip (tables may already exist)
		return nil
	}

	// Execute schema within a transaction
	tx, err := db.conn.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction for schema %s: %w", schemaFile, err)
	}

	if _, err := tx.Exec(string(content)); err != nil {
		_ = tx.Rollback()

		// If error indicates schema already applied, skip it
		errStr := err.Error()
		if strings.Contains(errStr, "duplicate column") ||
			strings.Contains(errStr, "already exists") {
			// Schema already applied, commit and continue
			_ = tx.Commit()
			return nil
		}

		return fmt.Errorf("failed to execute schema %s for %s: %w", schemaFile, db.name, err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit schema %s for %s: %w", schemaFile, db.name, err)
	}

	return nil
}

// Begin starts a new transaction
func (db *DB) Begin() (*sql.Tx, error) {
	return db.conn.Begin()
}

// BeginTx starts a new transaction with options
func (db *DB) BeginTx(ctx context.Context, opts *sql.TxOptions) (*sql.Tx, error) {
	return db.conn.BeginTx(ctx, opts)
}

// Exec executes a query without returning rows
func (db *DB) Exec(query string, args ...interface{}) (sql.Result, error) {
	return db.conn.Exec(query, args...)
}

// ExecContext executes a query with context
func (db *DB) ExecContext(ctx context.Context, query string, args ...interface{}) (sql.Result, error) {
	return db.conn.ExecContext(ctx, query, args...)
}

// Query executes a query that returns rows
func (db *DB) Query(query string, args ...interface{}) (*sql.Rows, error) {
	return db.conn.Query(query, args...)
}

// QueryContext executes a query with context
func (db *DB) QueryContext(ctx context.Context, query string, args ...interface{}) (*sql.Rows, error) {
	return db.conn.QueryContext(ctx, query, args...)
}

// QueryRow executes a query that returns at most one row
func (db *DB) QueryRow(query string, args ...interface{}) *sql.Row {
	return db.conn.QueryRow(query, args...)
}

// QueryRowContext executes a query with context
func (db *DB) QueryRowContext(ctx context.Context, query string, args ...interface{}) *sql.Row {
	return db.conn.QueryRowContext(ctx, query, args...)
}

// HealthCheck performs a comprehensive health check on the database
func (db *DB) HealthCheck(ctx context.Context) error {
	// 1. Test connection
	if err := db.conn.PingContext(ctx); err != nil {
		return fmt.Errorf("ping failed for %s: %w", db.name, err)
	}

	// 2. Integrity check (comprehensive but expensive)
	var integrityResult string
	err := db.conn.QueryRowContext(ctx, "PRAGMA integrity_check").Scan(&integrityResult)
	if err != nil {
		return fmt.Errorf("integrity check query failed for %s: %w", db.name, err)
	}

	if integrityResult != "ok" {
		return fmt.Errorf("integrity check failed for %s: %s", db.name, integrityResult)
	}

	return nil
}

// QuickCheck performs a quick health check (just ping, no integrity check)
func (db *DB) QuickCheck(ctx context.Context) error {
	return db.conn.PingContext(ctx)
}

// WALCheckpoint forces a WAL checkpoint to prevent bloat
func (db *DB) WALCheckpoint(mode string) error {
	// Modes: PASSIVE, FULL, RESTART, TRUNCATE
	// TRUNCATE is recommended for maintenance (resets WAL file to minimal size)
	if mode == "" {
		mode = "TRUNCATE"
	}

	query := fmt.Sprintf("PRAGMA wal_checkpoint(%s)", mode)
	_, err := db.conn.Exec(query)
	if err != nil {
		return fmt.Errorf("WAL checkpoint failed for %s: %w", db.name, err)
	}

	return nil
}

// Vacuum runs VACUUM to reclaim space and reduce fragmentation
func (db *DB) Vacuum() error {
	// Note: VACUUM can be expensive on large databases
	// Should only be run during maintenance windows
	if _, err := db.conn.Exec("VACUUM"); err != nil {
		return fmt.Errorf("vacuum failed for %s: %w", db.name, err)
	}

	return nil
}

// Stats returns database statistics
type Stats struct {
	SizeBytes     int64 // Database file size
	WALSizeBytes  int64 // WAL file size
	PageCount     int64 // Total pages
	PageSize      int64 // Page size in bytes
	FreelistCount int64 // Number of free pages
}

// GetStats retrieves database statistics
func (db *DB) GetStats() (*Stats, error) {
	stats := &Stats{}

	// Get file size
	if fileInfo, err := os.Stat(db.path); err == nil {
		stats.SizeBytes = fileInfo.Size()
	}

	// Get WAL file size
	walPath := db.path + "-wal"
	if fileInfo, err := os.Stat(walPath); err == nil {
		stats.WALSizeBytes = fileInfo.Size()
	}

	// Get page count
	if err := db.conn.QueryRow("PRAGMA page_count").Scan(&stats.PageCount); err != nil {
		return nil, fmt.Errorf("failed to get page count: %w", err)
	}

	// Get page size
	if err := db.conn.QueryRow("PRAGMA page_size").Scan(&stats.PageSize); err != nil {
		return nil, fmt.Errorf("failed to get page size: %w", err)
	}

	// Get freelist count
	if err := db.conn.QueryRow("PRAGMA freelist_count").Scan(&stats.FreelistCount); err != nil {
		return nil, fmt.Errorf("failed to get freelist count: %w", err)
	}

	return stats, nil
}
