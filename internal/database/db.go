// Package database provides database connection and initialization functionality.
package database

import (
	"context"
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
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
	// Handle file: URIs (used for in-memory databases) - skip filepath operations
	if strings.HasPrefix(cfg.Path, "file:") {
		// For file: URIs, use as-is without filepath operations
		// This is used for in-memory databases in tests
	} else {
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
	}

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

// findSchemasDirectory locates the schemas directory using the source code location.
// This is the architecturally correct approach because:
// 1. Schemas are part of the source code, not the database file
// 2. Works regardless of where the database file is located (tests, CI, production)
// 3. Works regardless of working directory
// 4. Works regardless of executable location
//
// It uses runtime.Caller to find the db.go file location, then derives the schemas
// directory as a sibling directory (internal/database/schemas/).
func findSchemasDirectory() (string, error) {
	// Get this function's file path (db.go)
	// Caller(0) = this function (findSchemasDirectory)
	_, currentFile, _, ok := runtime.Caller(0)
	if !ok {
		return "", fmt.Errorf("failed to get caller information")
	}

	// Get the absolute path of this source file
	absFile, err := filepath.Abs(currentFile)
	if err != nil {
		return "", fmt.Errorf("failed to get absolute path of source file: %w", err)
	}

	// This file is at internal/database/db.go
	// Schemas are at internal/database/schemas/
	// So we go from db.go's directory to schemas/
	dbDir := filepath.Dir(absFile)
	schemasDir := filepath.Join(dbDir, "schemas")

	// Verify the schemas directory exists
	if info, err := os.Stat(schemasDir); err != nil {
		return "", fmt.Errorf("schemas directory not found at %s: %w", schemasDir, err)
	} else if !info.IsDir() {
		return "", fmt.Errorf("schemas path exists but is not a directory: %s", schemasDir)
	}

	return schemasDir, nil
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

	// Connection lifecycle management (tuned for long-running embedded device)
	// Extended lifetimes prevent unnecessary reconnection during long operations
	conn.SetConnMaxLifetime(24 * time.Hour)   // Recycle connections after 24 hours
	conn.SetConnMaxIdleTime(30 * time.Minute) // Close idle connections after 30 minutes

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

	// Find schemas directory using source code location
	// This is architecturally correct: schemas are always relative to the source code,
	// not the database file location. This works in tests, CI, and production.
	schemasDir, err := findSchemasDirectory()
	if err != nil {
		// If we can't find schemas directory, skip migration (tables may already exist)
		// This allows the system to work even if schemas aren't available
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

// WithTransaction executes a function within a database transaction.
// It handles begin, commit, rollback, panic recovery, and error wrapping automatically.
// If the function returns an error or panics, the transaction is rolled back.
// If the function succeeds, the transaction is committed.
func WithTransaction(db *sql.DB, fn func(*sql.Tx) error) (err error) {
	if db == nil {
		return fmt.Errorf("database connection is nil")
	}

	// Start transaction
	tx, err := db.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}

	// Defer rollback with panic recovery
	// Use named return variable to capture panic value
	defer func() {
		if p := recover(); p != nil {
			// Panic occurred - rollback and convert panic to error
			_ = tx.Rollback()
			err = fmt.Errorf("panic in transaction: %v", p)
		} else if err != nil {
			// Function returned error - rollback
			rollbackErr := tx.Rollback()
			if rollbackErr != nil {
				err = fmt.Errorf("transaction failed: %w (rollback also failed: %v)", err, rollbackErr)
			} else {
				err = fmt.Errorf("transaction failed: %w", err)
			}
		} else {
			// Function succeeded - commit
			if commitErr := tx.Commit(); commitErr != nil {
				err = fmt.Errorf("failed to commit transaction: %w", commitErr)
			}
		}
	}()

	// Execute function within transaction
	err = fn(tx)
	return err
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
