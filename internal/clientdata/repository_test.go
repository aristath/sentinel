package clientdata

import (
	"database/sql"
	"encoding/json"
	"testing"
	"time"

	_ "github.com/mattn/go-sqlite3"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// testSchema creates all tables needed for testing
const testSchema = `
CREATE TABLE alphavantage_overview (isin TEXT PRIMARY KEY, data TEXT NOT NULL, expires_at INTEGER NOT NULL);
CREATE TABLE alphavantage_balance_sheet (isin TEXT PRIMARY KEY, data TEXT NOT NULL, expires_at INTEGER NOT NULL);
CREATE TABLE alphavantage_cash_flow (isin TEXT PRIMARY KEY, data TEXT NOT NULL, expires_at INTEGER NOT NULL);
CREATE TABLE alphavantage_earnings (isin TEXT PRIMARY KEY, data TEXT NOT NULL, expires_at INTEGER NOT NULL);
CREATE TABLE alphavantage_dividends (isin TEXT PRIMARY KEY, data TEXT NOT NULL, expires_at INTEGER NOT NULL);
CREATE TABLE alphavantage_etf_profile (isin TEXT PRIMARY KEY, data TEXT NOT NULL, expires_at INTEGER NOT NULL);
CREATE TABLE alphavantage_insider (isin TEXT PRIMARY KEY, data TEXT NOT NULL, expires_at INTEGER NOT NULL);
CREATE TABLE alphavantage_economic (indicator TEXT PRIMARY KEY, data TEXT NOT NULL, expires_at INTEGER NOT NULL);
CREATE TABLE openfigi (isin TEXT PRIMARY KEY, data TEXT NOT NULL, expires_at INTEGER NOT NULL);
CREATE TABLE yahoo_metadata (isin TEXT PRIMARY KEY, data TEXT NOT NULL, expires_at INTEGER NOT NULL);
CREATE TABLE exchangerate (pair TEXT PRIMARY KEY, data TEXT NOT NULL, expires_at INTEGER NOT NULL);
CREATE TABLE current_prices (isin TEXT PRIMARY KEY, data TEXT NOT NULL, expires_at INTEGER NOT NULL);

CREATE INDEX idx_av_overview_expires ON alphavantage_overview(expires_at);
CREATE INDEX idx_openfigi_expires ON openfigi(expires_at);
CREATE INDEX idx_yahoo_expires ON yahoo_metadata(expires_at);
CREATE INDEX idx_exchangerate_expires ON exchangerate(expires_at);
CREATE INDEX idx_prices_expires ON current_prices(expires_at);
`

func setupTestDB(t *testing.T) *sql.DB {
	db, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)

	_, err = db.Exec(testSchema)
	require.NoError(t, err)

	return db
}

func TestNewRepository(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db)
	assert.NotNil(t, repo)
}

func TestStore(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db)

	// Test storing a simple struct
	data := map[string]interface{}{
		"name":   "Test Company",
		"symbol": "TEST",
		"price":  123.45,
	}

	err := repo.Store("alphavantage_overview", "US0000000001", data, 7*24*time.Hour)
	require.NoError(t, err)

	// Verify data was stored
	var storedData string
	var expiresAt int64
	err = db.QueryRow("SELECT data, expires_at FROM alphavantage_overview WHERE isin = ?", "US0000000001").Scan(&storedData, &expiresAt)
	require.NoError(t, err)

	// Verify JSON was stored correctly
	var parsed map[string]interface{}
	err = json.Unmarshal([]byte(storedData), &parsed)
	require.NoError(t, err)
	assert.Equal(t, "Test Company", parsed["name"])
	assert.Equal(t, "TEST", parsed["symbol"])

	// Verify expiration is roughly 7 days from now
	expectedExpires := time.Now().Add(7 * 24 * time.Hour).Unix()
	assert.InDelta(t, expectedExpires, expiresAt, 5) // Allow 5 second tolerance
}

func TestStoreUpsert(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db)

	// Store initial data
	data1 := map[string]string{"version": "1"}
	err := repo.Store("alphavantage_overview", "US0000000001", data1, time.Hour)
	require.NoError(t, err)

	// Store updated data with same key
	data2 := map[string]string{"version": "2"}
	err = repo.Store("alphavantage_overview", "US0000000001", data2, time.Hour)
	require.NoError(t, err)

	// Verify only one row exists with updated data
	var count int
	err = db.QueryRow("SELECT COUNT(*) FROM alphavantage_overview WHERE isin = ?", "US0000000001").Scan(&count)
	require.NoError(t, err)
	assert.Equal(t, 1, count)

	// Verify data was updated
	result, err := repo.GetIfFresh("alphavantage_overview", "US0000000001")
	require.NoError(t, err)
	require.NotNil(t, result)

	var parsed map[string]string
	err = json.Unmarshal(result, &parsed)
	require.NoError(t, err)
	assert.Equal(t, "2", parsed["version"])
}

func TestGetIfFresh_Fresh(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db)

	// Store data with 1 hour TTL (fresh)
	data := map[string]string{"status": "fresh"}
	err := repo.Store("openfigi", "US0000000001", data, time.Hour)
	require.NoError(t, err)

	// Should return data
	result, err := repo.GetIfFresh("openfigi", "US0000000001")
	require.NoError(t, err)
	require.NotNil(t, result)

	var parsed map[string]string
	err = json.Unmarshal(result, &parsed)
	require.NoError(t, err)
	assert.Equal(t, "fresh", parsed["status"])
}

func TestGetIfFresh_Expired(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db)

	// Insert expired data directly (expired 1 hour ago)
	expiredAt := time.Now().Add(-time.Hour).Unix()
	_, err := db.Exec(
		"INSERT INTO openfigi (isin, data, expires_at) VALUES (?, ?, ?)",
		"US0000000001",
		`{"status":"expired"}`,
		expiredAt,
	)
	require.NoError(t, err)

	// Should return nil for expired data
	result, err := repo.GetIfFresh("openfigi", "US0000000001")
	require.NoError(t, err)
	assert.Nil(t, result, "Expected nil for expired data")
}

func TestGet_ReturnsStaleData(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db)

	// Insert expired data directly (expired 1 hour ago)
	expiredAt := time.Now().Add(-time.Hour).Unix()
	_, err := db.Exec(
		"INSERT INTO openfigi (isin, data, expires_at) VALUES (?, ?, ?)",
		"US0000000001",
		`{"status":"stale_but_useful"}`,
		expiredAt,
	)
	require.NoError(t, err)

	// GetIfFresh should return nil
	result, err := repo.GetIfFresh("openfigi", "US0000000001")
	require.NoError(t, err)
	assert.Nil(t, result, "GetIfFresh should return nil for expired data")

	// Get should return the stale data (useful when API fails)
	result, err = repo.Get("openfigi", "US0000000001")
	require.NoError(t, err)
	require.NotNil(t, result, "Get should return stale data")

	var parsed map[string]string
	err = json.Unmarshal(result, &parsed)
	require.NoError(t, err)
	assert.Equal(t, "stale_but_useful", parsed["status"])
}

func TestGet_NotFound(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db)

	// Get should return nil for non-existent key
	result, err := repo.Get("openfigi", "NONEXISTENT")
	require.NoError(t, err)
	assert.Nil(t, result)
}

func TestGetIfFresh_NotFound(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db)

	// Should return nil for non-existent key
	result, err := repo.GetIfFresh("openfigi", "NONEXISTENT")
	require.NoError(t, err)
	assert.Nil(t, result)
}

func TestDelete(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db)

	// Store data
	data := map[string]string{"to_delete": "true"}
	err := repo.Store("yahoo_metadata", "US0000000001", data, time.Hour)
	require.NoError(t, err)

	// Verify it exists
	result, err := repo.GetIfFresh("yahoo_metadata", "US0000000001")
	require.NoError(t, err)
	require.NotNil(t, result)

	// Delete it
	err = repo.Delete("yahoo_metadata", "US0000000001")
	require.NoError(t, err)

	// Verify it's gone
	result, err = repo.GetIfFresh("yahoo_metadata", "US0000000001")
	require.NoError(t, err)
	assert.Nil(t, result)
}

func TestDeleteNonExistent(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db)

	// Deleting non-existent key should not error
	err := repo.Delete("yahoo_metadata", "NONEXISTENT")
	require.NoError(t, err)
}

func TestDeleteExpired(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db)

	now := time.Now()

	// Insert 3 expired entries and 2 fresh entries
	expiredAt := now.Add(-time.Hour).Unix()
	freshAt := now.Add(time.Hour).Unix()

	_, err := db.Exec("INSERT INTO exchangerate (pair, data, expires_at) VALUES (?, ?, ?)", "EUR:USD", `{}`, expiredAt)
	require.NoError(t, err)
	_, err = db.Exec("INSERT INTO exchangerate (pair, data, expires_at) VALUES (?, ?, ?)", "GBP:USD", `{}`, expiredAt)
	require.NoError(t, err)
	_, err = db.Exec("INSERT INTO exchangerate (pair, data, expires_at) VALUES (?, ?, ?)", "JPY:USD", `{}`, expiredAt)
	require.NoError(t, err)
	_, err = db.Exec("INSERT INTO exchangerate (pair, data, expires_at) VALUES (?, ?, ?)", "CHF:USD", `{}`, freshAt)
	require.NoError(t, err)
	_, err = db.Exec("INSERT INTO exchangerate (pair, data, expires_at) VALUES (?, ?, ?)", "AUD:USD", `{}`, freshAt)
	require.NoError(t, err)

	// Delete expired
	deleted, err := repo.DeleteExpired("exchangerate")
	require.NoError(t, err)
	assert.Equal(t, int64(3), deleted)

	// Verify only 2 remain
	var count int
	err = db.QueryRow("SELECT COUNT(*) FROM exchangerate").Scan(&count)
	require.NoError(t, err)
	assert.Equal(t, 2, count)
}

func TestDeleteExpiredEmptyTable(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db)

	// Delete from empty table should return 0
	deleted, err := repo.DeleteExpired("exchangerate")
	require.NoError(t, err)
	assert.Equal(t, int64(0), deleted)
}

func TestDeleteAllExpired(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db)

	now := time.Now()
	expiredAt := now.Add(-time.Hour).Unix()
	freshAt := now.Add(time.Hour).Unix()

	// Insert expired entries in multiple tables
	_, err := db.Exec("INSERT INTO alphavantage_overview (isin, data, expires_at) VALUES (?, ?, ?)", "US001", `{}`, expiredAt)
	require.NoError(t, err)
	_, err = db.Exec("INSERT INTO alphavantage_overview (isin, data, expires_at) VALUES (?, ?, ?)", "US002", `{}`, freshAt)
	require.NoError(t, err)

	_, err = db.Exec("INSERT INTO openfigi (isin, data, expires_at) VALUES (?, ?, ?)", "US003", `{}`, expiredAt)
	require.NoError(t, err)
	_, err = db.Exec("INSERT INTO openfigi (isin, data, expires_at) VALUES (?, ?, ?)", "US004", `{}`, expiredAt)
	require.NoError(t, err)

	_, err = db.Exec("INSERT INTO yahoo_metadata (isin, data, expires_at) VALUES (?, ?, ?)", "US005", `{}`, freshAt)
	require.NoError(t, err)

	_, err = db.Exec("INSERT INTO exchangerate (pair, data, expires_at) VALUES (?, ?, ?)", "EUR:USD", `{}`, expiredAt)
	require.NoError(t, err)

	// Delete all expired
	results, err := repo.DeleteAllExpired()
	require.NoError(t, err)

	// Verify counts
	assert.Equal(t, int64(1), results["alphavantage_overview"])
	assert.Equal(t, int64(2), results["openfigi"])
	assert.Equal(t, int64(0), results["yahoo_metadata"])
	assert.Equal(t, int64(1), results["exchangerate"])

	// Verify total remaining
	var count int
	db.QueryRow("SELECT COUNT(*) FROM alphavantage_overview").Scan(&count)
	assert.Equal(t, 1, count) // 1 fresh entry

	db.QueryRow("SELECT COUNT(*) FROM openfigi").Scan(&count)
	assert.Equal(t, 0, count) // All expired

	db.QueryRow("SELECT COUNT(*) FROM yahoo_metadata").Scan(&count)
	assert.Equal(t, 1, count) // 1 fresh entry

	db.QueryRow("SELECT COUNT(*) FROM exchangerate").Scan(&count)
	assert.Equal(t, 0, count) // All expired
}

func TestStoreWithDifferentTables(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db)

	// Test storing to different tables
	tables := []struct {
		table string
		key   string
	}{
		{"alphavantage_overview", "US0000000001"},
		{"alphavantage_balance_sheet", "US0000000001"},
		{"alphavantage_cash_flow", "US0000000001"},
		{"alphavantage_earnings", "US0000000001"},
		{"alphavantage_dividends", "US0000000001"},
		{"alphavantage_etf_profile", "US0000000001"},
		{"alphavantage_insider", "US0000000001"},
		{"alphavantage_economic", "GDP"},
		{"openfigi", "US0000000001"},
		{"yahoo_metadata", "US0000000001"},
		{"exchangerate", "EUR:USD"},
		{"current_prices", "US0000000001"},
	}

	for _, tc := range tables {
		t.Run(tc.table, func(t *testing.T) {
			data := map[string]string{"table": tc.table}
			err := repo.Store(tc.table, tc.key, data, time.Hour)
			require.NoError(t, err)

			result, err := repo.GetIfFresh(tc.table, tc.key)
			require.NoError(t, err)
			require.NotNil(t, result)

			var parsed map[string]string
			json.Unmarshal(result, &parsed)
			assert.Equal(t, tc.table, parsed["table"])
		})
	}
}

func TestStoreComplexJSON(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db)

	// Test with complex nested structure (like Alpha Vantage response)
	data := map[string]interface{}{
		"Symbol":               "AAPL",
		"AssetType":            "Common Stock",
		"Name":                 "Apple Inc",
		"Description":          "Apple Inc. designs, manufactures...",
		"MarketCapitalization": 2500000000000,
		"EBITDA":               125000000000,
		"PERatio":              28.5,
		"BookValue":            4.25,
		"DividendYield":        0.0065,
		"QuarterlyEarnings": []map[string]interface{}{
			{"fiscalDateEnding": "2024-03-31", "reportedEPS": "1.52"},
			{"fiscalDateEnding": "2023-12-31", "reportedEPS": "2.18"},
		},
	}

	err := repo.Store("alphavantage_overview", "US0378331005", data, 7*24*time.Hour)
	require.NoError(t, err)

	result, err := repo.GetIfFresh("alphavantage_overview", "US0378331005")
	require.NoError(t, err)
	require.NotNil(t, result)

	var parsed map[string]interface{}
	err = json.Unmarshal(result, &parsed)
	require.NoError(t, err)

	assert.Equal(t, "AAPL", parsed["Symbol"])
	assert.Equal(t, "Apple Inc", parsed["Name"])
	assert.Equal(t, float64(2500000000000), parsed["MarketCapitalization"])

	// Verify nested array
	earnings, ok := parsed["QuarterlyEarnings"].([]interface{})
	require.True(t, ok)
	assert.Len(t, earnings, 2)
}

func TestGetKeyColumn(t *testing.T) {
	// Test the key column mapping
	tests := []struct {
		table    string
		expected string
	}{
		{"alphavantage_overview", "isin"},
		{"alphavantage_economic", "indicator"},
		{"openfigi", "isin"},
		{"exchangerate", "pair"},
		{"current_prices", "isin"},
	}

	for _, tc := range tests {
		t.Run(tc.table, func(t *testing.T) {
			result := getKeyColumn(tc.table)
			assert.Equal(t, tc.expected, result)
		})
	}
}

func TestInvalidTableName(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewRepository(db)

	// All methods should reject invalid table names
	t.Run("Store", func(t *testing.T) {
		err := repo.Store("invalid_table; DROP TABLE openfigi;--", "key", map[string]string{}, time.Hour)
		require.Error(t, err)
		assert.Contains(t, err.Error(), "invalid table name")
	})

	t.Run("GetIfFresh", func(t *testing.T) {
		_, err := repo.GetIfFresh("users", "key")
		require.Error(t, err)
		assert.Contains(t, err.Error(), "invalid table name")
	})

	t.Run("Get", func(t *testing.T) {
		_, err := repo.Get("passwords", "key")
		require.Error(t, err)
		assert.Contains(t, err.Error(), "invalid table name")
	})

	t.Run("Delete", func(t *testing.T) {
		err := repo.Delete("secrets", "key")
		require.Error(t, err)
		assert.Contains(t, err.Error(), "invalid table name")
	})

	t.Run("DeleteExpired", func(t *testing.T) {
		_, err := repo.DeleteExpired("nonexistent")
		require.Error(t, err)
		assert.Contains(t, err.Error(), "invalid table name")
	})
}

func TestValidateTable(t *testing.T) {
	// All tables in AllTables should be valid
	for _, table := range AllTables {
		t.Run(table, func(t *testing.T) {
			err := validateTable(table)
			assert.NoError(t, err)
		})
	}
}
