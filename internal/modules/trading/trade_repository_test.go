package trading

import (
	"database/sql"
	"testing"
	"time"

	_ "github.com/mattn/go-sqlite3"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

// TestCreate_ValidatesPrice tests that Create() validates price before insertion
func TestCreate_ValidatesPrice(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Create in-memory SQLite database for testing
	db, err := sql.Open("sqlite3", ":memory:")
	if err != nil {
		t.Fatalf("Failed to open test database: %v", err)
	}
	defer db.Close()

	// Create trades table
	_, err = db.Exec(`
		CREATE TABLE trades (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			symbol TEXT NOT NULL,
			isin TEXT,
			side TEXT NOT NULL,
			quantity REAL NOT NULL,
			price REAL NOT NULL CHECK(price > 0),
			executed_at TEXT NOT NULL,
			order_id TEXT UNIQUE,
			currency TEXT,
			value_eur REAL,
			source TEXT NOT NULL,
			mode TEXT NOT NULL,
			created_at TEXT NOT NULL
		)
	`)
	if err != nil {
		t.Fatalf("Failed to create test table: %v", err)
	}

	repo := NewTradeRepository(db, nil, log)

	testCases := []struct {
		name        string
		price       float64
		shouldError bool
		errorMsg    string
	}{
		{
			name:        "Valid positive price",
			price:       100.0,
			shouldError: false,
		},
		{
			name:        "Zero price should fail",
			price:       0.0,
			shouldError: true,
			errorMsg:    "price must be positive",
		},
		{
			name:        "Negative price should fail",
			price:       -10.0,
			shouldError: true,
			errorMsg:    "price must be positive",
		},
		{
			name:        "Small positive price should pass",
			price:       0.01,
			shouldError: false,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			trade := Trade{
				OrderID:    "ORDER-" + tc.name,
				Symbol:     "AAPL",
				Side:       TradeSideBuy,
				Quantity:   10,
				Price:      tc.price,
				ExecutedAt: time.Now(),
				Source:     "test",
				Currency:   "EUR",
				Mode:       "test",
			}

			err := repo.Create(trade)

			if tc.shouldError {
				assert.Error(t, err, "Create should return error for invalid price")
				if tc.errorMsg != "" {
					// Validation should catch it before database constraint
					assert.Contains(t, err.Error(), tc.errorMsg, "Error should mention price validation: %s", err.Error())
				}
			} else {
				assert.NoError(t, err, "Create should succeed for valid price")
			}
		})
	}
}

// setupTestDB creates an in-memory database with both trades and securities tables
func setupTestDB(t *testing.T) (*sql.DB, *sql.DB) {
	t.Helper()

	// Create ledger database (trades table)
	ledgerDB, err := sql.Open("sqlite3", ":memory:")
	if err != nil {
		t.Fatalf("Failed to open ledger test database: %v", err)
	}

	// Create trades table
	_, err = ledgerDB.Exec(`
		CREATE TABLE trades (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			symbol TEXT NOT NULL,
			isin TEXT,
			side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
			quantity REAL NOT NULL CHECK (quantity > 0),
			price REAL NOT NULL CHECK (price > 0),
			executed_at INTEGER NOT NULL,
			order_id TEXT,
			currency TEXT NOT NULL,
			value_eur REAL NOT NULL,
			source TEXT DEFAULT 'manual',
			mode TEXT DEFAULT 'normal',
			created_at INTEGER NOT NULL
		)
	`)
	if err != nil {
		t.Fatalf("Failed to create trades table: %v", err)
	}

	// Create universe database (securities table)
	universeDB, err := sql.Open("sqlite3", ":memory:")
	if err != nil {
		t.Fatalf("Failed to open universe test database: %v", err)
	}

	// Create securities table
	_, err = universeDB.Exec(`
		CREATE TABLE securities (
			isin TEXT PRIMARY KEY,
			symbol TEXT NOT NULL UNIQUE,
			name TEXT NOT NULL,
			created_at INTEGER NOT NULL,
			updated_at INTEGER NOT NULL
		)
	`)
	if err != nil {
		t.Fatalf("Failed to create securities table: %v", err)
	}

	return ledgerDB, universeDB
}

// TestGetRecentlyBoughtISINs_ReturnsISINsNotSymbols tests that the method returns ISINs, not Symbols
func TestGetRecentlyBoughtISINs_ReturnsISINsNotSymbols(t *testing.T) {
	ledgerDB, universeDB := setupTestDB(t)
	defer ledgerDB.Close()
	defer universeDB.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Insert test security
	now := time.Now().Unix()
	_, err := universeDB.Exec(`
		INSERT INTO securities (isin, symbol, name, created_at, updated_at) VALUES
		('US0378331005', 'AAPL.US', 'Apple Inc.', ?, ?)
	`, now, now)
	assert.NoError(t, err)

	// Insert recent buy trade
	_, err = ledgerDB.Exec(`
		INSERT INTO trades (symbol, isin, side, quantity, price, executed_at, order_id, currency, value_eur, created_at) VALUES
		('AAPL.US', 'US0378331005', 'BUY', 10, 150.0, ?, 'ORDER123', 'USD', 1500.0, ?)
	`, now, now)
	assert.NoError(t, err)

	// Test
	repo := NewTradeRepository(ledgerDB, universeDB, log)
	isins, err := repo.GetRecentlyBoughtISINs(30)

	// Assertions
	assert.NoError(t, err)
	assert.Contains(t, isins, "US0378331005", "Should return ISIN")
	assert.NotContains(t, isins, "AAPL.US", "Should NOT return Symbol")
	assert.Len(t, isins, 1)
	assert.True(t, isins["US0378331005"], "ISIN should map to true")
}

// TestGetRecentlySoldISINs_ReturnsISINsNotSymbols tests that the method returns ISINs for SELL trades
func TestGetRecentlySoldISINs_ReturnsISINsNotSymbols(t *testing.T) {
	ledgerDB, universeDB := setupTestDB(t)
	defer ledgerDB.Close()
	defer universeDB.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Insert test security
	now := time.Now().Unix()
	_, err := universeDB.Exec(`
		INSERT INTO securities (isin, symbol, name, created_at, updated_at) VALUES
		('US5949181045', 'MSFT.US', 'Microsoft Corp.', ?, ?)
	`, now, now)
	assert.NoError(t, err)

	// Insert recent sell trade
	_, err = ledgerDB.Exec(`
		INSERT INTO trades (symbol, isin, side, quantity, price, executed_at, order_id, currency, value_eur, created_at) VALUES
		('MSFT.US', 'US5949181045', 'SELL', 5, 300.0, ?, 'ORDER456', 'USD', 1500.0, ?)
	`, now, now)
	assert.NoError(t, err)

	// Test
	repo := NewTradeRepository(ledgerDB, universeDB, log)
	isins, err := repo.GetRecentlySoldISINs(30)

	// Assertions
	assert.NoError(t, err)
	assert.Contains(t, isins, "US5949181045", "Should return ISIN")
	assert.NotContains(t, isins, "MSFT.US", "Should NOT return Symbol")
	assert.Len(t, isins, 1)
	assert.True(t, isins["US5949181045"], "ISIN should map to true")
}

// TestGetRecentlyBoughtISINs_ExcludesResearchTrades tests that RESEARCH_ trades are excluded
func TestGetRecentlyBoughtISINs_ExcludesResearchTrades(t *testing.T) {
	ledgerDB, universeDB := setupTestDB(t)
	defer ledgerDB.Close()
	defer universeDB.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Insert test securities
	now := time.Now().Unix()
	_, err := universeDB.Exec(`
		INSERT INTO securities (isin, symbol, name, created_at, updated_at) VALUES
		('US0378331005', 'AAPL.US', 'Apple Inc.', ?, ?),
		('US5949181045', 'MSFT.US', 'Microsoft Corp.', ?, ?)
	`, now, now, now, now)
	assert.NoError(t, err)

	// Insert regular buy trade
	_, err = ledgerDB.Exec(`
		INSERT INTO trades (symbol, isin, side, quantity, price, executed_at, order_id, currency, value_eur, created_at) VALUES
		('AAPL.US', 'US0378331005', 'BUY', 10, 150.0, ?, 'ORDER123', 'USD', 1500.0, ?)
	`, now, now)
	assert.NoError(t, err)

	// Insert RESEARCH buy trade (should be excluded)
	_, err = ledgerDB.Exec(`
		INSERT INTO trades (symbol, isin, side, quantity, price, executed_at, order_id, currency, value_eur, created_at) VALUES
		('MSFT.US', 'US5949181045', 'BUY', 5, 300.0, ?, 'RESEARCH_001', 'USD', 1500.0, ?)
	`, now, now)
	assert.NoError(t, err)

	// Test
	repo := NewTradeRepository(ledgerDB, universeDB, log)
	isins, err := repo.GetRecentlyBoughtISINs(30)

	// Assertions
	assert.NoError(t, err)
	assert.Contains(t, isins, "US0378331005", "Should include regular buy trade")
	assert.NotContains(t, isins, "US5949181045", "Should exclude RESEARCH trade")
	assert.Len(t, isins, 1)
}

// TestGetRecentlyBoughtISINs_OnlyRecentTrades tests that old trades are not included
func TestGetRecentlyBoughtISINs_OnlyRecentTrades(t *testing.T) {
	ledgerDB, universeDB := setupTestDB(t)
	defer ledgerDB.Close()
	defer universeDB.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Insert test security
	now := time.Now().Unix()
	_, err := universeDB.Exec(`
		INSERT INTO securities (isin, symbol, name, created_at, updated_at) VALUES
		('US0378331005', 'AAPL.US', 'Apple Inc.', ?, ?),
		('US5949181045', 'MSFT.US', 'Microsoft Corp.', ?, ?)
	`, now, now, now, now)
	assert.NoError(t, err)

	// Insert recent buy trade (within 30 days)
	recentTime := time.Now().AddDate(0, 0, -10).Unix()
	_, err = ledgerDB.Exec(`
		INSERT INTO trades (symbol, isin, side, quantity, price, executed_at, order_id, currency, value_eur, created_at) VALUES
		('AAPL.US', 'US0378331005', 'BUY', 10, 150.0, ?, 'ORDER123', 'USD', 1500.0, ?)
	`, recentTime, now)
	assert.NoError(t, err)

	// Insert old buy trade (> 30 days)
	oldTime := time.Now().AddDate(0, 0, -40).Unix()
	_, err = ledgerDB.Exec(`
		INSERT INTO trades (symbol, isin, side, quantity, price, executed_at, order_id, currency, value_eur, created_at) VALUES
		('MSFT.US', 'US5949181045', 'BUY', 5, 300.0, ?, 'ORDER456', 'USD', 1500.0, ?)
	`, oldTime, now)
	assert.NoError(t, err)

	// Test
	repo := NewTradeRepository(ledgerDB, universeDB, log)
	isins, err := repo.GetRecentlyBoughtISINs(30)

	// Assertions
	assert.NoError(t, err)
	assert.Contains(t, isins, "US0378331005", "Should include recent trade")
	assert.NotContains(t, isins, "US5949181045", "Should exclude old trade")
	assert.Len(t, isins, 1)
}

// TestGetRecentlySoldISINs_OnlyRecentTrades tests that old sell trades are not included
func TestGetRecentlySoldISINs_OnlyRecentTrades(t *testing.T) {
	ledgerDB, universeDB := setupTestDB(t)
	defer ledgerDB.Close()
	defer universeDB.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Insert test securities
	now := time.Now().Unix()
	_, err := universeDB.Exec(`
		INSERT INTO securities (isin, symbol, name, created_at, updated_at) VALUES
		('US0378331005', 'AAPL.US', 'Apple Inc.', ?, ?),
		('US5949181045', 'MSFT.US', 'Microsoft Corp.', ?, ?)
	`, now, now, now, now)
	assert.NoError(t, err)

	// Insert recent sell trade (within 30 days)
	recentTime := time.Now().AddDate(0, 0, -15).Unix()
	_, err = ledgerDB.Exec(`
		INSERT INTO trades (symbol, isin, side, quantity, price, executed_at, currency, value_eur, created_at) VALUES
		('AAPL.US', 'US0378331005', 'SELL', 10, 150.0, ?, 'USD', 1500.0, ?)
	`, recentTime, now)
	assert.NoError(t, err)

	// Insert old sell trade (> 30 days)
	oldTime := time.Now().AddDate(0, 0, -50).Unix()
	_, err = ledgerDB.Exec(`
		INSERT INTO trades (symbol, isin, side, quantity, price, executed_at, currency, value_eur, created_at) VALUES
		('MSFT.US', 'US5949181045', 'SELL', 5, 300.0, ?, 'USD', 1500.0, ?)
	`, oldTime, now)
	assert.NoError(t, err)

	// Test
	repo := NewTradeRepository(ledgerDB, universeDB, log)
	isins, err := repo.GetRecentlySoldISINs(30)

	// Assertions
	assert.NoError(t, err)
	assert.Contains(t, isins, "US0378331005", "Should include recent sell trade")
	assert.NotContains(t, isins, "US5949181045", "Should exclude old sell trade")
	assert.Len(t, isins, 1)
}

// TestGetRecentlyBoughtISINs_EmptyResult tests behavior when no recent buys exist
func TestGetRecentlyBoughtISINs_EmptyResult(t *testing.T) {
	ledgerDB, universeDB := setupTestDB(t)
	defer ledgerDB.Close()
	defer universeDB.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Test with empty database
	repo := NewTradeRepository(ledgerDB, universeDB, log)
	isins, err := repo.GetRecentlyBoughtISINs(30)

	// Assertions
	assert.NoError(t, err)
	assert.NotNil(t, isins, "Should return non-nil map")
	assert.Len(t, isins, 0, "Should return empty map")
}

// TestGetRecentlySoldISINs_EmptyResult tests behavior when no recent sells exist
func TestGetRecentlySoldISINs_EmptyResult(t *testing.T) {
	ledgerDB, universeDB := setupTestDB(t)
	defer ledgerDB.Close()
	defer universeDB.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Test with empty database
	repo := NewTradeRepository(ledgerDB, universeDB, log)
	isins, err := repo.GetRecentlySoldISINs(30)

	// Assertions
	assert.NoError(t, err)
	assert.NotNil(t, isins, "Should return non-nil map")
	assert.Len(t, isins, 0, "Should return empty map")
}
