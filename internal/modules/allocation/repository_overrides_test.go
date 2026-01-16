package allocation

import (
	"database/sql"
	"encoding/json"
	"testing"
	"time"

	"github.com/aristath/sentinel/internal/domain"
	_ "github.com/mattn/go-sqlite3"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// testSecurityProvider provides securities with overrides for allocation tests
type testSecurityProvider struct {
	db *sql.DB
}

func newTestSecurityProvider(db *sql.DB) *testSecurityProvider {
	return &testSecurityProvider{db: db}
}

func (p *testSecurityProvider) GetAllActiveTradable() ([]SecurityInfo, error) {
	// Query securities using JSON storage schema (migration 038)
	// Filter out indices using JSON extraction
	query := `SELECT isin, symbol, data, last_synced FROM securities
		WHERE json_extract(data, '$.product_type') IS NULL
		OR json_extract(data, '$.product_type') != ?`

	rows, err := p.db.Query(query, string(domain.ProductTypeIndex))
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var securities []SecurityInfo
	for rows.Next() {
		var isin, symbol, jsonData string
		var lastSynced sql.NullInt64

		if err := rows.Scan(&isin, &symbol, &jsonData, &lastSynced); err != nil {
			return nil, err
		}

		// Parse JSON data
		var data struct {
			Name      string `json:"name"`
			Geography string `json:"geography"`
			Industry  string `json:"industry"`
		}
		if err := json.Unmarshal([]byte(jsonData), &data); err != nil {
			continue // Skip malformed JSON
		}

		sec := SecurityInfo{
			ISIN:      isin,
			Symbol:    symbol,
			Name:      data.Name,
			Geography: data.Geography,
			Industry:  data.Industry,
		}

		securities = append(securities, sec)
	}

	// Apply overrides
	for i := range securities {
		overrides, err := p.getOverrides(securities[i].ISIN)
		if err != nil {
			continue
		}
		if len(overrides) > 0 {
			p.applyOverrides(&securities[i], overrides)
		}
	}

	return securities, nil
}

func (p *testSecurityProvider) getOverrides(isin string) (map[string]string, error) {
	overrides := make(map[string]string)
	query := "SELECT field, value FROM security_overrides WHERE isin = ?"

	rows, err := p.db.Query(query, isin)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	for rows.Next() {
		var field, value string
		if err := rows.Scan(&field, &value); err != nil {
			return nil, err
		}
		overrides[field] = value
	}

	return overrides, nil
}

func (p *testSecurityProvider) applyOverrides(sec *SecurityInfo, overrides map[string]string) {
	for field, value := range overrides {
		switch field {
		case "geography":
			sec.Geography = value
		case "industry":
			sec.Industry = value
		}
	}
}

func setupTestDBsForAllocation(t *testing.T) (*sql.DB, *sql.DB) {
	t.Helper()

	// Create config database
	configDB, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)
	t.Cleanup(func() { configDB.Close() })

	// Create allocation_targets table
	_, err = configDB.Exec(`
		CREATE TABLE allocation_targets (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			type TEXT NOT NULL,
			name TEXT NOT NULL,
			target_pct REAL NOT NULL,
			created_at INTEGER NOT NULL,
			updated_at INTEGER NOT NULL,
			UNIQUE(type, name)
		)
	`)
	require.NoError(t, err)

	// Create universe database
	universeDB, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)
	t.Cleanup(func() { universeDB.Close() })

	// Create securities table (migration 038 JSON storage schema)
	_, err = universeDB.Exec(`
		CREATE TABLE securities (
			isin TEXT PRIMARY KEY,
			symbol TEXT NOT NULL,
			data TEXT NOT NULL,
			last_synced INTEGER
		) STRICT
	`)
	require.NoError(t, err)

	// Create security_overrides table
	_, err = universeDB.Exec(`
		CREATE TABLE security_overrides (
			isin TEXT NOT NULL,
			field TEXT NOT NULL,
			value TEXT NOT NULL,
			created_at INTEGER NOT NULL,
			updated_at INTEGER NOT NULL,
			PRIMARY KEY (isin, field)
		)
	`)
	require.NoError(t, err)

	return configDB, universeDB
}

func TestGetAvailableGeographies_RespectsOverrides(t *testing.T) {
	configDB, universeDB := setupTestDBsForAllocation(t)

	now := time.Now().Unix()

	// Security 1: US geography, override to WORLD
	jsonData1 := `{"name":"Apple","geography":"US"}`
	_, err := universeDB.Exec(`INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES (?, ?, ?, ?)`, "US0378331005", "AAPL.US", jsonData1, now)
	require.NoError(t, err)
	_, err = universeDB.Exec(`INSERT INTO security_overrides (isin, field, value, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?)`, "US0378331005", "geography", "WORLD", now, now)
	require.NoError(t, err)

	// Security 2: EU geography, no override
	jsonData2 := `{"name":"IWDA","geography":"EU"}`
	_, err = universeDB.Exec(`INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES (?, ?, ?, ?)`, "IE00B4L5Y983", "IWDA.EU", jsonData2, now)
	require.NoError(t, err)

	// Create repo with override support
	securityProvider := newTestSecurityProvider(universeDB)
	repo := NewRepository(configDB, securityProvider, zerolog.Nop())
	repo.SetUniverseDB(universeDB)

	// Execute
	geographies, err := repo.GetAvailableGeographies()
	require.NoError(t, err)

	// Assert: WORLD (from override), EU (from base), NOT US (overridden)
	assert.Contains(t, geographies, "WORLD")
	assert.Contains(t, geographies, "EU")
	assert.NotContains(t, geographies, "US", "US should not appear (overridden to WORLD)")
}

func TestGetAvailableIndustries_RespectsOverrides(t *testing.T) {
	configDB, universeDB := setupTestDBsForAllocation(t)

	now := time.Now().Unix()

	// Security 1: Technology industry, override to Finance
	jsonData1 := `{"name":"Apple","industry":"Technology"}`
	_, err := universeDB.Exec(`INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES (?, ?, ?, ?)`, "US0378331005", "AAPL.US", jsonData1, now)
	require.NoError(t, err)
	_, err = universeDB.Exec(`INSERT INTO security_overrides (isin, field, value, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?)`, "US0378331005", "industry", "Finance", now, now)
	require.NoError(t, err)

	// Security 2: Healthcare industry, no override
	jsonData2 := `{"name":"Microsoft","industry":"Healthcare"}`
	_, err = universeDB.Exec(`INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES (?, ?, ?, ?)`, "US5949181045", "MSFT.US", jsonData2, now)
	require.NoError(t, err)

	// Create repo with override support
	securityProvider := newTestSecurityProvider(universeDB)
	repo := NewRepository(configDB, securityProvider, zerolog.Nop())
	repo.SetUniverseDB(universeDB)

	// Execute
	industries, err := repo.GetAvailableIndustries()
	require.NoError(t, err)

	// Assert: Finance (from override), Healthcare (from base), NOT Technology (overridden)
	assert.Contains(t, industries, "Finance")
	assert.Contains(t, industries, "Healthcare")
	assert.NotContains(t, industries, "Technology", "Technology should not appear (overridden to Finance)")
}

func TestGetAvailableGeographies_HandlesCSV(t *testing.T) {
	configDB, universeDB := setupTestDBsForAllocation(t)

	now := time.Now().Unix()

	// Security with CSV override "US, EU"
	jsonData := `{"name":"Apple","geography":"WORLD"}`
	_, err := universeDB.Exec(`INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES (?, ?, ?, ?)`, "US0378331005", "AAPL.US", jsonData, now)
	require.NoError(t, err)
	_, err = universeDB.Exec(`INSERT INTO security_overrides (isin, field, value, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?)`, "US0378331005", "geography", "US, EU", now, now)
	require.NoError(t, err)

	// Create repo with override support
	securityProvider := newTestSecurityProvider(universeDB)
	repo := NewRepository(configDB, securityProvider, zerolog.Nop())
	repo.SetUniverseDB(universeDB)

	// Execute
	geographies, err := repo.GetAvailableGeographies()
	require.NoError(t, err)

	// Assert: Both US and EU should appear
	assert.Contains(t, geographies, "US")
	assert.Contains(t, geographies, "EU")
	assert.NotContains(t, geographies, "WORLD", "WORLD should not appear (overridden to US, EU)")
}
