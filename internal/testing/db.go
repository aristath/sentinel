// Package testing provides testing utilities and helpers for the sentinel project.
package testing

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"testing"

	"github.com/aristath/sentinel/internal/database"
	_ "modernc.org/sqlite"
)

// NewTestDB creates an in-memory SQLite database for testing with automatic schema migration.
// Returns the database instance and a cleanup function that closes the connection.
// The cleanup function is idempotent and can be called multiple times safely.
//
// Supported schema names:
//   - "universe" - applies universe_schema.sql
//   - "config" - applies config_schema.sql
//   - "ledger" - applies ledger_schema.sql
//   - "portfolio" - applies portfolio_schema.sql
//   - "agents" - applies agents_schema.sql
//   - "history" - applies history_schema.sql
//   - "cache" - applies cache_schema.sql
//   - Unknown names - creates empty database (no schema applied)
func NewTestDB(t *testing.T, name string) (*database.DB, func()) {
	t.Helper()

	// Create temporary file for test database to ensure test isolation
	// Using temporary files ensures each test gets its own isolated database
	tmpFile, err := os.CreateTemp("", fmt.Sprintf("test_%s_*.db", name))
	if err != nil {
		t.Fatalf("Failed to create temporary database file: %v", err)
	}
	tmpPath := tmpFile.Name()
	_ = tmpFile.Close()

	// Create database from temporary file
	db, err := database.New(database.Config{
		Path:    tmpPath,
		Profile: database.ProfileStandard,
		Name:    name,
	})
	if err != nil {
		_ = os.Remove(tmpPath)
		t.Fatalf("Failed to create test database %s: %v", name, err)
	}

	// Apply schema migration if schema exists for this database name
	err = db.Migrate()
	if err != nil {
		_ = db.Close()
		_ = os.Remove(tmpPath)
		t.Fatalf("Failed to migrate test database %s: %v", name, err)
	}

	// Return database and cleanup function
	return db, func() {
		if err := db.Close(); err != nil {
			// Log error but don't fail test - cleanup should be idempotent
			t.Logf("Warning: Failed to close test database %s: %v", name, err)
		}
		if err := os.Remove(tmpPath); err != nil {
			t.Logf("Warning: Failed to remove temporary database file %s: %v", tmpPath, err)
		}
	}
}

// NewTestDBWithSchema creates an in-memory SQLite database for testing with a custom schema.
// Returns the database instance and a cleanup function that closes the connection.
// The schema SQL will be executed directly on the database.
func NewTestDBWithSchema(t *testing.T, name string, schema string) (*database.DB, func()) {
	t.Helper()

	// Create temporary file for test database to ensure test isolation
	tmpFile, err := os.CreateTemp("", fmt.Sprintf("test_%s_*.db", name))
	if err != nil {
		t.Fatalf("Failed to create temporary database file: %v", err)
	}
	tmpPath := tmpFile.Name()
	_ = tmpFile.Close()

	// Create database from temporary file
	db, err := database.New(database.Config{
		Path:    tmpPath,
		Profile: database.ProfileStandard,
		Name:    name,
	})
	if err != nil {
		_ = os.Remove(tmpPath)
		t.Fatalf("Failed to create test database %s: %v", name, err)
	}

	// Execute custom schema
	if schema != "" {
		_, err = db.Conn().Exec(schema)
		if err != nil {
			_ = db.Close()
			_ = os.Remove(tmpPath)
			t.Fatalf("Failed to execute custom schema for test database %s: %v", name, err)
		}
	}

	// Return database and cleanup function
	return db, func() {
		if err := db.Close(); err != nil {
			// Log error but don't fail test - cleanup should be idempotent
			t.Logf("Warning: Failed to close test database %s: %v", name, err)
		}
		if err := os.Remove(tmpPath); err != nil {
			t.Logf("Warning: Failed to remove temporary database file %s: %v", tmpPath, err)
		}
	}
}

// findSchemasDir finds the schemas directory relative to the current working directory or test files.
// This is a helper function used by NewTestDB to locate schema files.
func findSchemasDir() (string, error) {
	// Get current working directory
	cwd, err := os.Getwd()
	if err != nil {
		return "", fmt.Errorf("failed to get current working directory: %w", err)
	}

	// Try common paths relative to CWD
	candidates := []string{
		filepath.Join(cwd, "internal/database/schemas"),
		filepath.Join(cwd, "../internal/database/schemas"),
		filepath.Join(cwd, "../../internal/database/schemas"),
	}

	// Also try from executable directory if available
	if execPath, err := os.Executable(); err == nil {
		execDir := filepath.Dir(execPath)
		candidates = append(candidates,
			filepath.Join(execDir, "internal/database/schemas"),
			filepath.Join(filepath.Dir(execDir), "internal/database/schemas"),
		)
	}

	// Find first existing schemas directory
	for _, candidate := range candidates {
		if absPath, err := filepath.Abs(candidate); err == nil {
			if info, err := os.Stat(absPath); err == nil && info.IsDir() {
				return absPath, nil
			}
		}
	}

	return "", fmt.Errorf("schemas directory not found")
}

// readSchemaFile reads a schema file from the schemas directory.
func readSchemaFile(schemaName string) (string, error) {
	schemasDir, err := findSchemasDir()
	if err != nil {
		return "", fmt.Errorf("failed to find schemas directory: %w", err)
	}

	schemaPath := filepath.Join(schemasDir, schemaName)
	content, err := os.ReadFile(schemaPath)
	if err != nil {
		return "", fmt.Errorf("failed to read schema file %s: %w", schemaPath, err)
	}

	return string(content), nil
}

// LoadTestSchema loads a schema file and returns its contents.
// This is a helper function for tests that need to load specific schemas.
func LoadTestSchema(schemaName string) (string, error) {
	return readSchemaFile(schemaName)
}

// CreateTempDBFile creates a temporary database file for testing.
// Returns the file path and a cleanup function that removes the file.
// Useful for tests that need a file-based database instead of in-memory.
func CreateTempDBFile(t *testing.T, name string) (string, func()) {
	t.Helper()

	// Create temporary file
	tmpFile, err := os.CreateTemp("", fmt.Sprintf("%s_*.db", name))
	if err != nil {
		t.Fatalf("Failed to create temporary database file: %v", err)
	}
	tmpPath := tmpFile.Name()
	_ = tmpFile.Close()

	// Return path and cleanup function
	return tmpPath, func() {
		if err := os.Remove(tmpPath); err != nil {
			t.Logf("Warning: Failed to remove temporary database file %s: %v", tmpPath, err)
		}
	}
}

// NewTestDBFromFile creates a test database from a temporary file.
// This is useful for tests that need file-based databases instead of in-memory.
// Returns the database instance and a cleanup function that closes the connection and removes the file.
func NewTestDBFromFile(t *testing.T, name string) (*database.DB, func()) {
	t.Helper()

	tmpPath, cleanupFile := CreateTempDBFile(t, name)

	// Create database from file
	db, err := database.New(database.Config{
		Path:    tmpPath,
		Profile: database.ProfileStandard,
		Name:    name,
	})
	if err != nil {
		cleanupFile()
		t.Fatalf("Failed to create test database %s from file %s: %v", name, tmpPath, err)
	}

	// Apply schema migration
	err = db.Migrate()
	if err != nil {
		_ = db.Close()
		cleanupFile()
		t.Fatalf("Failed to migrate test database %s: %v", name, err)
	}

	// Return database and combined cleanup function
	return db, func() {
		if err := db.Close(); err != nil {
			t.Logf("Warning: Failed to close test database %s: %v", name, err)
		}
		cleanupFile()
	}
}

// GetRawConnection returns the raw *sql.DB connection from a database.DB instance.
// This is useful for tests that need direct access to the underlying connection.
func GetRawConnection(db *database.DB) *sql.DB {
	return db.Conn()
}
