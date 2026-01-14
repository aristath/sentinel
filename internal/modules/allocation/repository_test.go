package allocation

import (
	"database/sql"
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	_ "modernc.org/sqlite"
)

// setupTestUniverseDB creates an in-memory SQLite database with test securities
func setupTestUniverseDB(t *testing.T) *sql.DB {
	db, err := sql.Open("sqlite", ":memory:")
	require.NoError(t, err)

	// Create the securities table
	_, err = db.Exec(`
		CREATE TABLE securities (
			id INTEGER PRIMARY KEY,
			isin TEXT UNIQUE NOT NULL,
			symbol TEXT NOT NULL,
			name TEXT NOT NULL,
			geography TEXT,
			industry TEXT,
			active INTEGER DEFAULT 1
		)
	`)
	require.NoError(t, err)

	return db
}

// insertTestSecurity inserts a test security into the database
func insertTestSecurity(t *testing.T, db *sql.DB, isin, symbol, name, geography, industry string, active int) {
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, name, geography, industry, active)
		VALUES (?, ?, ?, ?, ?, ?)
	`, isin, symbol, name, geography, industry, active)
	require.NoError(t, err)
}

func TestGetAvailableIndustries_SingleValues(t *testing.T) {
	db := setupTestUniverseDB(t)
	defer db.Close()

	// Insert securities with single industries
	insertTestSecurity(t, db, "US0000000001", "AAPL", "Apple", "US", "Technology", 1)
	insertTestSecurity(t, db, "US0000000002", "XOM", "Exxon", "US", "Energy", 1)
	insertTestSecurity(t, db, "US0000000003", "JPM", "JPMorgan", "US", "Finance", 1)

	repo := NewRepository(nil, zerolog.Nop())
	repo.SetUniverseDB(db)

	industries, err := repo.GetAvailableIndustries()
	require.NoError(t, err)

	expected := []string{"Energy", "Finance", "Technology"}
	assert.Equal(t, expected, industries)
}

func TestGetAvailableIndustries_CommaSeparatedValues(t *testing.T) {
	db := setupTestUniverseDB(t)
	defer db.Close()

	// Insert securities with comma-separated industries
	insertTestSecurity(t, db, "US0000000001", "GE", "General Electric", "US", "Industrial, Technology, Energy", 1)
	insertTestSecurity(t, db, "US0000000002", "AMZN", "Amazon", "US", "Technology, Consumer Discretionary", 1)

	repo := NewRepository(nil, zerolog.Nop())
	repo.SetUniverseDB(db)

	industries, err := repo.GetAvailableIndustries()
	require.NoError(t, err)

	// Should return unique, sorted individual industries
	expected := []string{"Consumer Discretionary", "Energy", "Industrial", "Technology"}
	assert.Equal(t, expected, industries)
}

func TestGetAvailableIndustries_MixedValues(t *testing.T) {
	db := setupTestUniverseDB(t)
	defer db.Close()

	// Mix of single and comma-separated industries
	insertTestSecurity(t, db, "US0000000001", "AAPL", "Apple", "US", "Technology", 1)
	insertTestSecurity(t, db, "US0000000002", "GE", "General Electric", "US", "Industrial, Technology", 1)
	insertTestSecurity(t, db, "US0000000003", "XOM", "Exxon", "US", "Energy", 1)

	repo := NewRepository(nil, zerolog.Nop())
	repo.SetUniverseDB(db)

	industries, err := repo.GetAvailableIndustries()
	require.NoError(t, err)

	// Technology should appear only once despite being in two securities
	expected := []string{"Energy", "Industrial", "Technology"}
	assert.Equal(t, expected, industries)
}

func TestGetAvailableIndustries_SkipsInactiveSecurities(t *testing.T) {
	db := setupTestUniverseDB(t)
	defer db.Close()

	insertTestSecurity(t, db, "US0000000001", "AAPL", "Apple", "US", "Technology", 1)
	insertTestSecurity(t, db, "US0000000002", "XOM", "Exxon", "US", "Energy", 0) // Inactive

	repo := NewRepository(nil, zerolog.Nop())
	repo.SetUniverseDB(db)

	industries, err := repo.GetAvailableIndustries()
	require.NoError(t, err)

	// Only Technology should appear (Energy is inactive)
	expected := []string{"Technology"}
	assert.Equal(t, expected, industries)
}

func TestGetAvailableIndustries_EmptyAndNull(t *testing.T) {
	db := setupTestUniverseDB(t)
	defer db.Close()

	insertTestSecurity(t, db, "US0000000001", "AAPL", "Apple", "US", "Technology", 1)
	insertTestSecurity(t, db, "US0000000002", "XYZ", "XYZ Corp", "US", "", 1)    // Empty industry
	insertTestSecurity(t, db, "US0000000003", "ABC", "ABC Corp", "US", "   ", 1) // Whitespace only

	repo := NewRepository(nil, zerolog.Nop())
	repo.SetUniverseDB(db)

	industries, err := repo.GetAvailableIndustries()
	require.NoError(t, err)

	// Only Technology should appear
	expected := []string{"Technology"}
	assert.Equal(t, expected, industries)
}

func TestGetAvailableGeographies_SingleValues(t *testing.T) {
	db := setupTestUniverseDB(t)
	defer db.Close()

	insertTestSecurity(t, db, "US0000000001", "AAPL", "Apple", "United States", "Technology", 1)
	insertTestSecurity(t, db, "DE0000000001", "SAP", "SAP", "Germany", "Technology", 1)
	insertTestSecurity(t, db, "JP0000000001", "SONY", "Sony", "Japan", "Technology", 1)

	repo := NewRepository(nil, zerolog.Nop())
	repo.SetUniverseDB(db)

	geographies, err := repo.GetAvailableGeographies()
	require.NoError(t, err)

	expected := []string{"Germany", "Japan", "United States"}
	assert.Equal(t, expected, geographies)
}

func TestGetAvailableGeographies_CommaSeparatedValues(t *testing.T) {
	db := setupTestUniverseDB(t)
	defer db.Close()

	// Multi-geography securities (e.g., global ETFs)
	insertTestSecurity(t, db, "US0000000001", "VT", "Vanguard Total World", "US, Europe, Asia Pacific", "ETF", 1)
	insertTestSecurity(t, db, "US0000000002", "VEA", "Vanguard Developed Markets", "Europe, Japan, Australia", "ETF", 1)

	repo := NewRepository(nil, zerolog.Nop())
	repo.SetUniverseDB(db)

	geographies, err := repo.GetAvailableGeographies()
	require.NoError(t, err)

	// Should return unique, sorted individual geographies
	expected := []string{"Asia Pacific", "Australia", "Europe", "Japan", "US"}
	assert.Equal(t, expected, geographies)
}

func TestGetAvailableGeographies_MixedValues(t *testing.T) {
	db := setupTestUniverseDB(t)
	defer db.Close()

	insertTestSecurity(t, db, "US0000000001", "AAPL", "Apple", "United States", "Technology", 1)
	insertTestSecurity(t, db, "US0000000002", "VT", "Vanguard Total World", "United States, Europe", "ETF", 1)
	insertTestSecurity(t, db, "DE0000000001", "SAP", "SAP", "Europe", "Technology", 1)

	repo := NewRepository(nil, zerolog.Nop())
	repo.SetUniverseDB(db)

	geographies, err := repo.GetAvailableGeographies()
	require.NoError(t, err)

	// United States and Europe should each appear only once
	expected := []string{"Europe", "United States"}
	assert.Equal(t, expected, geographies)
}

func TestGetAvailableGeographies_SkipsInactiveSecurities(t *testing.T) {
	db := setupTestUniverseDB(t)
	defer db.Close()

	insertTestSecurity(t, db, "US0000000001", "AAPL", "Apple", "United States", "Technology", 1)
	insertTestSecurity(t, db, "JP0000000001", "SONY", "Sony", "Japan", "Technology", 0) // Inactive

	repo := NewRepository(nil, zerolog.Nop())
	repo.SetUniverseDB(db)

	geographies, err := repo.GetAvailableGeographies()
	require.NoError(t, err)

	// Only United States should appear (Japan is inactive)
	expected := []string{"United States"}
	assert.Equal(t, expected, geographies)
}

func TestGetAvailableIndustries_NoUniverseDB(t *testing.T) {
	repo := NewRepository(nil, zerolog.Nop())
	// Don't set universeDB

	_, err := repo.GetAvailableIndustries()
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "universe database not configured")
}

func TestGetAvailableGeographies_NoUniverseDB(t *testing.T) {
	repo := NewRepository(nil, zerolog.Nop())
	// Don't set universeDB

	_, err := repo.GetAvailableGeographies()
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "universe database not configured")
}

func TestGetAvailableIndustries_EmptyDatabase(t *testing.T) {
	db := setupTestUniverseDB(t)
	defer db.Close()

	repo := NewRepository(nil, zerolog.Nop())
	repo.SetUniverseDB(db)

	industries, err := repo.GetAvailableIndustries()
	require.NoError(t, err)

	assert.Empty(t, industries)
}

func TestGetAvailableGeographies_EmptyDatabase(t *testing.T) {
	db := setupTestUniverseDB(t)
	defer db.Close()

	repo := NewRepository(nil, zerolog.Nop())
	repo.SetUniverseDB(db)

	geographies, err := repo.GetAvailableGeographies()
	require.NoError(t, err)

	assert.Empty(t, geographies)
}
