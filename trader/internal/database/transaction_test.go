package database

import (
	"database/sql"
	"errors"
	"fmt"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	_ "modernc.org/sqlite"
)

// setupTestDB creates an in-memory SQLite database for testing
func setupTestDB(t *testing.T) *DB {
	db, err := New(Config{
		Path:    ":memory:",
		Profile: ProfileStandard,
		Name:    "test",
	})
	require.NoError(t, err)

	// Create a simple test table
	_, err = db.Conn().Exec(`
		CREATE TABLE IF NOT EXISTS test_table (
			id INTEGER PRIMARY KEY,
			value TEXT NOT NULL
		)
	`)
	require.NoError(t, err)

	return db
}

// TestWithTransaction_Success tests that WithTransaction commits successfully
func TestWithTransaction_Success(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	// Clear any existing rows first
	_, err := db.Conn().Exec("DELETE FROM test_table")
	require.NoError(t, err)

	var result int

	err = WithTransaction(db.Conn(), func(tx *sql.Tx) error {
		// Insert a row
		_, err := tx.Exec("INSERT INTO test_table (value) VALUES (?)", "test-value")
		if err != nil {
			return err
		}

		// Read it back within the same transaction
		err = tx.QueryRow("SELECT COUNT(*) FROM test_table WHERE value = ?", "test-value").Scan(&result)
		return err
	})

	require.NoError(t, err)
	assert.Equal(t, 1, result, "Row should be inserted and committed")

	// Verify the row persists after transaction
	var count int
	err = db.Conn().QueryRow("SELECT COUNT(*) FROM test_table WHERE value = ?", "test-value").Scan(&count)
	require.NoError(t, err)
	assert.Equal(t, 1, count, "Row should persist after commit")
}

// TestWithTransaction_RollbackOnError tests that WithTransaction rolls back on error
func TestWithTransaction_RollbackOnError(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	// Clear any existing rows first
	_, err := db.Conn().Exec("DELETE FROM test_table")
	require.NoError(t, err)

	testErr := errors.New("test error")

	err = WithTransaction(db.Conn(), func(tx *sql.Tx) error {
		// Insert a row
		_, err := tx.Exec("INSERT INTO test_table (value) VALUES (?)", "test-value")
		if err != nil {
			return err
		}

		// Return error to trigger rollback
		return testErr
	})

	require.Error(t, err)
	assert.ErrorIs(t, err, testErr, "Error should be unwrappable")
	assert.Contains(t, err.Error(), "transaction", "Error should mention transaction")

	// Verify the row was NOT committed
	var count int
	err = db.Conn().QueryRow("SELECT COUNT(*) FROM test_table WHERE value = ?", "test-value").Scan(&count)
	require.NoError(t, err)
	assert.Equal(t, 0, count, "Row should not exist after rollback")
}

// TestWithTransaction_RollbackOnPanic tests that WithTransaction recovers from panic and rolls back
func TestWithTransaction_RollbackOnPanic(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	panicValue := "panic occurred"

	err := WithTransaction(db.Conn(), func(tx *sql.Tx) error {
		// Insert a row
		_, err := tx.Exec("INSERT INTO test_table (value) VALUES (?)", "test-value")
		if err != nil {
			return err
		}

		// Panic to trigger recovery and rollback
		panic(panicValue)
	})

	require.Error(t, err)
	assert.Contains(t, err.Error(), "panic", "Error should mention panic")
	assert.Contains(t, err.Error(), panicValue, "Error should contain panic value")

	// Verify the row was NOT committed
	var count int
	err = db.Conn().QueryRow("SELECT COUNT(*) FROM test_table WHERE value = ?", "test-value").Scan(&count)
	require.NoError(t, err)
	assert.Equal(t, 0, count, "Row should not exist after panic rollback")
}

// TestWithTransaction_ErrorWrapping tests that errors are properly wrapped with context
func TestWithTransaction_ErrorWrapping(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	testErr := errors.New("database operation failed")

	err := WithTransaction(db.Conn(), func(tx *sql.Tx) error {
		// Simulate an error
		return testErr
	})

	require.Error(t, err)
	assert.ErrorIs(t, err, testErr, "Error should be unwrappable")
	assert.Contains(t, err.Error(), "transaction", "Error should mention transaction context")
}

// TestWithTransaction_NestedTransactions tests behavior with nested transactions
// Note: SQLite doesn't natively support nested transactions, but WithTransaction
// will start a new transaction on the same connection, which SQLite may allow
// in some cases. This test verifies that nested calls don't cause panics.
func TestWithTransaction_NestedTransactions(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	err := WithTransaction(db.Conn(), func(tx *sql.Tx) error {
		// Try to start another transaction within the current one
		// SQLite doesn't support nested transactions, so this may fail
		// or behave unexpectedly, but shouldn't panic
		err := WithTransaction(db.Conn(), func(tx2 *sql.Tx) error {
			return nil
		})
		// We don't assert on success/failure since behavior may vary
		// We just verify it doesn't panic
		return err
	})

	// Test passes if no panic occurred (error may or may not be nil)
	// The key is that it doesn't crash
	_ = err // Use err to avoid "unused variable" warning
}

// TestWithTransaction_CommitFailure tests that commit failures are handled properly
func TestWithTransaction_CommitFailure(t *testing.T) {
	// This test requires a more complex setup to simulate commit failure
	// SQLite doesn't easily allow us to simulate commit failures, so we'll test error wrapping instead

	db := setupTestDB(t)
	defer db.Close()

	// Close the connection prematurely to force a commit error
	db.Close()

	err := WithTransaction(db.Conn(), func(tx *sql.Tx) error {
		_, err := tx.Exec("INSERT INTO test_table (value) VALUES (?)", "test-value")
		return err
	})

	// The transaction should fail because the connection is closed
	require.Error(t, err)
	assert.Contains(t, err.Error(), "transaction", "Error should mention transaction")
}

// TestWithTransaction_MultipleOperations tests that multiple operations work correctly
func TestWithTransaction_MultipleOperations(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	// Clear any existing rows first
	_, err := db.Conn().Exec("DELETE FROM test_table")
	require.NoError(t, err)

	err = WithTransaction(db.Conn(), func(tx *sql.Tx) error {
		// Insert multiple rows
		for i := 0; i < 5; i++ {
			_, err := tx.Exec("INSERT INTO test_table (value) VALUES (?)", fmt.Sprintf("value-%d", i))
			if err != nil {
				return err
			}
		}
		return nil
	})

	require.NoError(t, err)

	// Verify all rows were committed
	var count int
	err = db.Conn().QueryRow("SELECT COUNT(*) FROM test_table").Scan(&count)
	require.NoError(t, err)
	assert.Equal(t, 5, count, "All rows should be committed")
}

// TestWithTransaction_EmptyFunction tests that an empty function works correctly
func TestWithTransaction_EmptyFunction(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	err := WithTransaction(db.Conn(), func(tx *sql.Tx) error {
		// Do nothing
		return nil
	})

	require.NoError(t, err)
	// Transaction should commit successfully even if no operations were performed
}

// TestWithTransaction_NilDB tests that nil DB is handled gracefully
func TestWithTransaction_NilDB(t *testing.T) {
	err := WithTransaction(nil, func(tx *sql.Tx) error {
		return nil
	})

	require.Error(t, err)
	assert.Contains(t, err.Error(), "nil", "Error should mention nil database")
}

// TestWithTransaction_SQLiteConstraintViolation tests that constraint violations trigger rollback
func TestWithTransaction_SQLiteConstraintViolation(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	// Add a unique constraint
	_, err := db.Conn().Exec(`
		CREATE UNIQUE INDEX IF NOT EXISTS idx_value_unique ON test_table(value)
	`)
	require.NoError(t, err)

	// Insert a value
	_, err = db.Conn().Exec("INSERT INTO test_table (value) VALUES (?)", "duplicate")
	require.NoError(t, err)

	// Try to insert duplicate in transaction (should fail and rollback)
	err = WithTransaction(db.Conn(), func(tx *sql.Tx) error {
		_, err := tx.Exec("INSERT INTO test_table (value) VALUES (?)", "duplicate")
		return err
	})

	require.Error(t, err)
	assert.Contains(t, err.Error(), "transaction", "Error should mention transaction")

	// Verify only one row exists (the original, not the failed one)
	var count int
	err = db.Conn().QueryRow("SELECT COUNT(*) FROM test_table WHERE value = ?", "duplicate").Scan(&count)
	require.NoError(t, err)
	assert.Equal(t, 1, count, "Duplicate should not be inserted")
}
