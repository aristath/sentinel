package allocation

import (
	"database/sql"
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	_ "modernc.org/sqlite"
)

// testSecurityProvider is defined in repository_overrides_test.go

// setupTestUniverseDB creates an in-memory SQLite database with test securities (migration 038 JSON schema)
func setupTestUniverseDB(t *testing.T) *sql.DB {
	db, err := sql.Open("sqlite", ":memory:")
	require.NoError(t, err)

	// Create the securities table with JSON storage (migration 038 schema)
	_, err = db.Exec(`
		CREATE TABLE securities (
			isin TEXT PRIMARY KEY,
			symbol TEXT NOT NULL,
			data TEXT NOT NULL,
			last_synced INTEGER
		) STRICT
	`)
	require.NoError(t, err)

	return db
}

// insertTestSecurity inserts a test security into the database (JSON storage)
// After migration 038: active parameter is ignored (all securities in database are active)
func insertTestSecurity(t *testing.T, db *sql.DB, isin, symbol, name, geography, industry string, _ int) {
	insertTestSecurityWithType(t, db, isin, symbol, name, "", geography, industry)
}

// insertTestSecurityWithType inserts a test security with explicit product_type (JSON storage)
// After migration 038: active parameter removed (all securities in database are active)
func insertTestSecurityWithType(t *testing.T, db *sql.DB, isin, symbol, name, productType, geography, industry string) {
	// Build JSON object
	jsonParts := []string{}
	if name != "" {
		jsonParts = append(jsonParts, "'name', '"+name+"'")
	}
	if productType != "" {
		jsonParts = append(jsonParts, "'product_type', '"+productType+"'")
	}
	if geography != "" {
		jsonParts = append(jsonParts, "'geography', '"+geography+"'")
	}
	if industry != "" {
		jsonParts = append(jsonParts, "'industry', '"+industry+"'")
	}

	var jsonData string
	if len(jsonParts) > 0 {
		jsonData = "json_object(" + jsonParts[0]
		for i := 1; i < len(jsonParts); i++ {
			jsonData += ", " + jsonParts[i]
		}
		jsonData += ")"
	} else {
		jsonData = "json_object()"
	}

	query := `INSERT INTO securities (isin, symbol, data, last_synced) VALUES (?, ?, ` + jsonData + `, NULL)`
	_, err := db.Exec(query, isin, symbol)
	require.NoError(t, err)
}

func TestGetAvailableIndustries_SingleValues(t *testing.T) {
	db := setupTestUniverseDB(t)
	defer db.Close()

	// Insert securities with single industries
	insertTestSecurity(t, db, "US0000000001", "AAPL", "Apple", "US", "Technology", 1)
	insertTestSecurity(t, db, "US0000000002", "XOM", "Exxon", "US", "Energy", 1)
	insertTestSecurity(t, db, "US0000000003", "JPM", "JPMorgan", "US", "Finance", 1)

	log := zerolog.Nop()
	securityProvider := newTestSecurityProvider(db)
	repo := NewRepository(nil, securityProvider, log)

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

	log := zerolog.Nop()
	securityProvider := newTestSecurityProvider(db)
	repo := NewRepository(nil, securityProvider, log)

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

	log := zerolog.Nop()
	securityProvider := newTestSecurityProvider(db)
	repo := NewRepository(nil, securityProvider, log)

	industries, err := repo.GetAvailableIndustries()
	require.NoError(t, err)

	// Technology should appear only once despite being in two securities
	expected := []string{"Energy", "Industrial", "Technology"}
	assert.Equal(t, expected, industries)
}

func TestGetAvailableIndustries_SkipsInactiveSecurities(t *testing.T) {
	// After migration 038: No soft delete - all securities in database are active
	// This test is no longer relevant since we removed the active column
	// Test renamed to document the change
	t.Skip("After migration 038: No soft delete - all securities in database are active")
}

func TestGetAvailableIndustries_EmptyAndNull(t *testing.T) {
	db := setupTestUniverseDB(t)
	defer db.Close()

	insertTestSecurity(t, db, "US0000000001", "AAPL", "Apple", "US", "Technology", 1)
	insertTestSecurity(t, db, "US0000000002", "XYZ", "XYZ Corp", "US", "", 1)    // Empty industry
	insertTestSecurity(t, db, "US0000000003", "ABC", "ABC Corp", "US", "   ", 1) // Whitespace only

	log := zerolog.Nop()
	securityProvider := newTestSecurityProvider(db)
	repo := NewRepository(nil, securityProvider, log)

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

	log := zerolog.Nop()
	securityProvider := newTestSecurityProvider(db)
	repo := NewRepository(nil, securityProvider, log)

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

	log := zerolog.Nop()
	securityProvider := newTestSecurityProvider(db)
	repo := NewRepository(nil, securityProvider, log)

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

	log := zerolog.Nop()
	securityProvider := newTestSecurityProvider(db)
	repo := NewRepository(nil, securityProvider, log)

	geographies, err := repo.GetAvailableGeographies()
	require.NoError(t, err)

	// United States and Europe should each appear only once
	expected := []string{"Europe", "United States"}
	assert.Equal(t, expected, geographies)
}

func TestGetAvailableGeographies_SkipsInactiveSecurities(t *testing.T) {
	// After migration 038: No soft delete - all securities in database are active
	// This test is no longer relevant since we removed the active column
	// Test renamed to document the change
	t.Skip("After migration 038: No soft delete - all securities in database are active")
}

func TestGetAvailableIndustries_NoUniverseDB(t *testing.T) {
	// After migration 038: SecurityProvider is REQUIRED (no fallback anti-pattern)
	repo := NewRepository(nil, nil, zerolog.Nop())

	_, err := repo.GetAvailableIndustries()
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "security provider not available")
}

func TestGetAvailableGeographies_NoUniverseDB(t *testing.T) {
	// After migration 038: SecurityProvider is REQUIRED (no fallback anti-pattern)
	repo := NewRepository(nil, nil, zerolog.Nop())

	_, err := repo.GetAvailableGeographies()
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "security provider not available")
}

func TestGetAvailableIndustries_EmptyDatabase(t *testing.T) {
	db := setupTestUniverseDB(t)
	defer db.Close()

	log := zerolog.Nop()
	securityProvider := newTestSecurityProvider(db)
	repo := NewRepository(nil, securityProvider, log)

	industries, err := repo.GetAvailableIndustries()
	require.NoError(t, err)

	assert.Empty(t, industries)
}

func TestGetAvailableGeographies_EmptyDatabase(t *testing.T) {
	db := setupTestUniverseDB(t)
	defer db.Close()

	log := zerolog.Nop()
	securityProvider := newTestSecurityProvider(db)
	repo := NewRepository(nil, securityProvider, log)

	geographies, err := repo.GetAvailableGeographies()
	require.NoError(t, err)

	assert.Empty(t, geographies)
}

func TestGetAvailableIndustries_ExcludesIndices(t *testing.T) {
	db := setupTestUniverseDB(t)
	defer db.Close()

	// Insert regular securities
	insertTestSecurityWithType(t, db, "US0000000001", "AAPL", "Apple", "EQUITY", "US", "Technology")
	insertTestSecurityWithType(t, db, "US0000000002", "XOM", "Exxon", "EQUITY", "US", "Energy")

	// Insert market index (should be excluded)
	insertTestSecurityWithType(t, db, "INDEX-SP500.IDX", "SP500.IDX", "S&P 500", "INDEX", "US", "Index")

	log := zerolog.Nop()
	securityProvider := newTestSecurityProvider(db)
	repo := NewRepository(nil, securityProvider, log)

	industries, err := repo.GetAvailableIndustries()
	require.NoError(t, err)

	// Should return Energy, Technology but NOT "Index"
	expected := []string{"Energy", "Technology"}
	assert.Equal(t, expected, industries)
}

func TestGetAvailableGeographies_ExcludesIndices(t *testing.T) {
	db := setupTestUniverseDB(t)
	defer db.Close()

	// Insert regular securities
	insertTestSecurityWithType(t, db, "US0000000001", "AAPL", "Apple", "EQUITY", "United States", "Technology")
	insertTestSecurityWithType(t, db, "DE0000000001", "SAP", "SAP", "EQUITY", "Germany", "Technology")

	// Insert market indices (should be excluded)
	insertTestSecurityWithType(t, db, "INDEX-SP500.IDX", "SP500.IDX", "S&P 500", "INDEX", "United States", "Index")
	insertTestSecurityWithType(t, db, "INDEX-DAX.IDX", "DAX.IDX", "DAX", "INDEX", "Germany", "Index")

	log := zerolog.Nop()
	securityProvider := newTestSecurityProvider(db)
	repo := NewRepository(nil, securityProvider, log)

	geographies, err := repo.GetAvailableGeographies()
	require.NoError(t, err)

	// Should return Germany, United States from regular securities
	// The indices also have these geographies, but they should be excluded
	expected := []string{"Germany", "United States"}
	assert.Equal(t, expected, geographies)
}

func TestGetAvailableIndustries_IncludesNullProductType(t *testing.T) {
	db := setupTestUniverseDB(t)
	defer db.Close()

	// Insert security with NULL product_type (should be included)
	insertTestSecurityWithType(t, db, "US0000000001", "AAPL", "Apple", "", "US", "Technology")
	// Insert security with explicit EQUITY type
	insertTestSecurityWithType(t, db, "US0000000002", "MSFT", "Microsoft", "EQUITY", "US", "Technology")
	// Insert index (should be excluded)
	insertTestSecurityWithType(t, db, "INDEX-SP500.IDX", "SP500.IDX", "S&P 500", "INDEX", "US", "Index")

	log := zerolog.Nop()
	securityProvider := newTestSecurityProvider(db)
	repo := NewRepository(nil, securityProvider, log)

	industries, err := repo.GetAvailableIndustries()
	require.NoError(t, err)

	// Should include Technology from both AAPL (NULL type) and MSFT (EQUITY)
	// Should NOT include Index from SP500.IDX
	expected := []string{"Technology"}
	assert.Equal(t, expected, industries)
}
