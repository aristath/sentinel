package clientdata

import (
	"database/sql"
	"testing"
	"time"

	_ "github.com/mattn/go-sqlite3"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNewCleanupJob(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db)
	job := NewCleanupJob(repo, zerolog.Nop())

	assert.NotNil(t, job)
}

func TestCleanupJobName(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db)
	job := NewCleanupJob(repo, zerolog.Nop())

	assert.Equal(t, "client_data_cleanup", job.Name())
}

func TestCleanupJobRun(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db)
	job := NewCleanupJob(repo, zerolog.Nop())

	now := time.Now()
	expiredAt := now.Add(-time.Hour).Unix()
	freshAt := now.Add(time.Hour).Unix()

	// Insert expired and fresh entries across multiple tables
	insertExpiredAndFresh(t, db, "alphavantage_overview", "isin", expiredAt, freshAt)
	insertExpiredAndFresh(t, db, "openfigi", "isin", expiredAt, freshAt)
	insertExpiredAndFresh(t, db, "exchangerate", "pair", expiredAt, freshAt)

	// Count before cleanup
	var countBefore int
	db.QueryRow("SELECT (SELECT COUNT(*) FROM alphavantage_overview) + (SELECT COUNT(*) FROM openfigi) + (SELECT COUNT(*) FROM exchangerate)").Scan(&countBefore)
	assert.Equal(t, 6, countBefore) // 2 per table (1 expired + 1 fresh)

	// Run cleanup
	err := job.Run()
	require.NoError(t, err)

	// Count after cleanup - should only have fresh entries
	var countAfter int
	db.QueryRow("SELECT (SELECT COUNT(*) FROM alphavantage_overview) + (SELECT COUNT(*) FROM openfigi) + (SELECT COUNT(*) FROM exchangerate)").Scan(&countAfter)
	assert.Equal(t, 3, countAfter) // 1 fresh per table
}

func TestCleanupJobRunEmptyTables(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db)
	job := NewCleanupJob(repo, zerolog.Nop())

	// Run cleanup on empty tables - should not error
	err := job.Run()
	require.NoError(t, err)
}

func TestCleanupJobRunAllExpired(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db)
	job := NewCleanupJob(repo, zerolog.Nop())

	expiredAt := time.Now().Add(-time.Hour).Unix()

	// Insert only expired entries
	_, err := db.Exec("INSERT INTO alphavantage_overview (isin, data, expires_at) VALUES (?, ?, ?)", "US001", `{}`, expiredAt)
	require.NoError(t, err)
	_, err = db.Exec("INSERT INTO alphavantage_overview (isin, data, expires_at) VALUES (?, ?, ?)", "US002", `{}`, expiredAt)
	require.NoError(t, err)
	_, err = db.Exec("INSERT INTO openfigi (isin, data, expires_at) VALUES (?, ?, ?)", "US003", `{}`, expiredAt)
	require.NoError(t, err)

	// Run cleanup
	err = job.Run()
	require.NoError(t, err)

	// Verify all entries removed
	var count int
	db.QueryRow("SELECT COUNT(*) FROM alphavantage_overview").Scan(&count)
	assert.Equal(t, 0, count)
	db.QueryRow("SELECT COUNT(*) FROM openfigi").Scan(&count)
	assert.Equal(t, 0, count)
}

func TestCleanupJobRunAllFresh(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db)
	job := NewCleanupJob(repo, zerolog.Nop())

	freshAt := time.Now().Add(time.Hour).Unix()

	// Insert only fresh entries
	_, err := db.Exec("INSERT INTO alphavantage_overview (isin, data, expires_at) VALUES (?, ?, ?)", "US001", `{}`, freshAt)
	require.NoError(t, err)
	_, err = db.Exec("INSERT INTO alphavantage_overview (isin, data, expires_at) VALUES (?, ?, ?)", "US002", `{}`, freshAt)
	require.NoError(t, err)
	_, err = db.Exec("INSERT INTO openfigi (isin, data, expires_at) VALUES (?, ?, ?)", "US003", `{}`, freshAt)
	require.NoError(t, err)

	// Run cleanup
	err = job.Run()
	require.NoError(t, err)

	// Verify no entries removed
	var count int
	db.QueryRow("SELECT COUNT(*) FROM alphavantage_overview").Scan(&count)
	assert.Equal(t, 2, count)
	db.QueryRow("SELECT COUNT(*) FROM openfigi").Scan(&count)
	assert.Equal(t, 1, count)
}

func TestCleanupJobSetJob(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db)
	job := NewCleanupJob(repo, zerolog.Nop())

	// SetJob should not panic
	job.SetJob(nil)
	job.SetJob(struct{}{})
}

// Helper function to insert one expired and one fresh entry per table
func insertExpiredAndFresh(t *testing.T, db *sql.DB, table, keyCol string, expiredAt, freshAt int64) {
	t.Helper()

	var key1, key2 string
	if keyCol == "pair" {
		key1 = "EUR:USD"
		key2 = "GBP:USD"
	} else {
		key1 = "US_EXPIRED_" + table
		key2 = "US_FRESH_" + table
	}

	_, err := db.Exec(
		"INSERT INTO "+table+" ("+keyCol+", data, expires_at) VALUES (?, ?, ?)",
		key1, `{"status":"expired"}`, expiredAt,
	)
	require.NoError(t, err)

	_, err = db.Exec(
		"INSERT INTO "+table+" ("+keyCol+", data, expires_at) VALUES (?, ?, ?)",
		key2, `{"status":"fresh"}`, freshAt,
	)
	require.NoError(t, err)
}
