package portfolio

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"testing"
	"time"

	_ "github.com/mattn/go-sqlite3"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// testSecurityProvider provides securities with overrides for tests
type testSecurityProvider struct {
	db  *sql.DB
	log zerolog.Logger
}

func newTestSecurityProvider(db *sql.DB, log zerolog.Logger) *testSecurityProvider {
	return &testSecurityProvider{db: db, log: log}
}

func (p *testSecurityProvider) GetAllActive() ([]SecurityInfo, error) {
	// Query securities using JSON storage schema (after migration 038)
	query := `SELECT isin, symbol, data, last_synced FROM securities`
	rows, err := p.db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query securities: %w", err)
	}
	defer rows.Close()

	var securities []SecurityInfo
	for rows.Next() {
		var isin, symbol, jsonData string
		var lastSynced sql.NullInt64

		if err := rows.Scan(&isin, &symbol, &jsonData, &lastSynced); err != nil {
			return nil, fmt.Errorf("failed to scan security: %w", err)
		}

		// Parse JSON data
		var data struct {
			Name             string `json:"name"`
			Geography        string `json:"geography"`
			FullExchangeName string `json:"fullExchangeName"`
			Industry         string `json:"industry"`
			Currency         string `json:"currency"`
		}
		if err := json.Unmarshal([]byte(jsonData), &data); err != nil {
			p.log.Warn().Str("isin", isin).Err(err).Msg("Failed to parse JSON data")
			continue
		}

		sec := SecurityInfo{
			ISIN:             isin,
			Symbol:           symbol,
			Name:             data.Name,
			Geography:        data.Geography,
			FullExchangeName: data.FullExchangeName,
			Industry:         data.Industry,
			Currency:         data.Currency,
			AllowSell:        true, // default
		}

		securities = append(securities, sec)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating securities: %w", err)
	}

	// Apply overrides
	for i := range securities {
		overrides, err := p.getOverrides(securities[i].ISIN)
		if err != nil {
			p.log.Warn().Str("isin", securities[i].ISIN).Err(err).Msg("Failed to fetch overrides")
			continue
		}

		if len(overrides) > 0 {
			p.applyOverrides(&securities[i], overrides)
		}
	}

	return securities, nil
}

func (p *testSecurityProvider) GetAllActiveTradable() ([]SecurityInfo, error) {
	// Query securities excluding INDEX product_type (after migration 038)
	query := `SELECT isin, symbol, data, last_synced FROM securities
		WHERE json_extract(data, '$.product_type') IS NULL
		OR json_extract(data, '$.product_type') != 'INDEX'`
	rows, err := p.db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query tradable securities: %w", err)
	}
	defer rows.Close()

	var securities []SecurityInfo
	for rows.Next() {
		var isin, symbol, jsonData string
		var lastSynced sql.NullInt64

		if err := rows.Scan(&isin, &symbol, &jsonData, &lastSynced); err != nil {
			return nil, fmt.Errorf("failed to scan security: %w", err)
		}

		// Parse JSON data
		var data struct {
			Name             string `json:"name"`
			Geography        string `json:"geography"`
			FullExchangeName string `json:"fullExchangeName"`
			Industry         string `json:"industry"`
			Currency         string `json:"currency"`
		}
		if err := json.Unmarshal([]byte(jsonData), &data); err != nil {
			p.log.Warn().Str("isin", isin).Err(err).Msg("Failed to parse JSON data")
			continue
		}

		sec := SecurityInfo{
			ISIN:             isin,
			Symbol:           symbol,
			Name:             data.Name,
			Geography:        data.Geography,
			FullExchangeName: data.FullExchangeName,
			Industry:         data.Industry,
			Currency:         data.Currency,
			AllowSell:        true, // default
		}

		securities = append(securities, sec)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating securities: %w", err)
	}

	// Apply overrides
	for i := range securities {
		overrides, err := p.getOverrides(securities[i].ISIN)
		if err != nil {
			p.log.Warn().Str("isin", securities[i].ISIN).Err(err).Msg("Failed to fetch overrides")
			continue
		}

		if len(overrides) > 0 {
			p.applyOverrides(&securities[i], overrides)
		}
	}

	return securities, nil
}

func (p *testSecurityProvider) GetISINBySymbol(symbol string) (string, error) {
	var isin string
	query := `SELECT isin FROM securities WHERE symbol = ?`
	err := p.db.QueryRow(query, symbol).Scan(&isin)
	if err == sql.ErrNoRows {
		return "", fmt.Errorf("security not found: %s", symbol)
	}
	return isin, err
}

func (p *testSecurityProvider) getOverrides(isin string) (map[string]string, error) {
	overrides := make(map[string]string)
	query := "SELECT field, value FROM security_overrides WHERE isin = ?"

	rows, err := p.db.Query(query, isin)
	if err != nil {
		return nil, fmt.Errorf("failed to query overrides: %w", err)
	}
	defer rows.Close()

	for rows.Next() {
		var field, value string
		if err := rows.Scan(&field, &value); err != nil {
			return nil, fmt.Errorf("failed to scan override: %w", err)
		}
		overrides[field] = value
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating overrides: %w", err)
	}

	return overrides, nil
}

func (p *testSecurityProvider) applyOverrides(sec *SecurityInfo, overrides map[string]string) {
	for field, value := range overrides {
		switch field {
		case "name":
			sec.Name = value
		case "geography":
			sec.Geography = value
		case "industry":
			sec.Industry = value
		case "currency":
			sec.Currency = value
		case "allow_sell":
			sec.AllowSell = value == "true" || value == "1"
		}
	}
}

// setupTestDBWithOverrides creates test databases with security_overrides table
func setupTestDBWithOverrides(t *testing.T) (*sql.DB, *sql.DB) {
	t.Helper()

	// Create portfolio database
	portfolioDB, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)
	t.Cleanup(func() { portfolioDB.Close() })

	// Create positions table
	_, err = portfolioDB.Exec(`
		CREATE TABLE positions (
			isin TEXT PRIMARY KEY,
			symbol TEXT NOT NULL,
			quantity REAL NOT NULL,
			avg_price REAL NOT NULL,
			current_price REAL,
			currency TEXT NOT NULL DEFAULT 'EUR',
			currency_rate REAL NOT NULL DEFAULT 1.0,
			market_value_eur REAL,
			cost_basis_eur REAL,
			unrealized_pnl REAL,
			unrealized_pnl_pct REAL,
			last_updated INTEGER,
			first_bought INTEGER,
			last_sold INTEGER
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
			PRIMARY KEY (isin, field),
			FOREIGN KEY (isin) REFERENCES securities(isin) ON DELETE CASCADE
		)
	`)
	require.NoError(t, err)

	return portfolioDB, universeDB
}

// insertSecurityWithoutOverrideColumns inserts a security using JSON storage schema
func insertSecurityWithoutOverrideColumns(t *testing.T, db *sql.DB, isin, symbol, name string) {
	t.Helper()

	now := time.Now().Unix()
	// Create JSON data with basic fields
	jsonData := fmt.Sprintf(`{"name":"%s","product_type":"STOCK"}`, name)
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES (?, ?, ?, ?)
	`, isin, symbol, jsonData, now)
	require.NoError(t, err)
}

// insertOverride inserts an override record
func insertOverride(t *testing.T, db *sql.DB, isin, field, value string) {
	t.Helper()

	now := time.Now().Unix()
	_, err := db.Exec(`
		INSERT INTO security_overrides (isin, field, value, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?)
		ON CONFLICT(isin, field) DO UPDATE SET
			value = excluded.value,
			updated_at = excluded.updated_at
	`, isin, field, value, now, now)
	require.NoError(t, err)
}

func TestGetWithSecurityInfo_AppliesGeographyOverride(t *testing.T) {
	portfolioDB, universeDB := setupTestDBWithOverrides(t)

	// Insert security with US geography
	insertSecurityWithoutOverrideColumns(t, universeDB, "US0378331005", "AAPL.US", "Apple Inc.")
	// Update JSON data to add geography field
	_, err := universeDB.Exec(`
		UPDATE securities
		SET data = json_set(data, '$.geography', ?)
		WHERE isin = ?`, "US", "US0378331005")
	require.NoError(t, err)

	// Override geography to WORLD
	insertOverride(t, universeDB, "US0378331005", "geography", "WORLD")

	// Insert position for this security
	now := time.Now().Unix()
	_, err = portfolioDB.Exec(`INSERT INTO positions (isin, symbol, quantity, avg_price, currency, currency_rate, last_updated)
		VALUES (?, ?, ?, ?, ?, ?, ?)`, "US0378331005", "AAPL.US", 100.0, 150.0, "USD", 1.1, now)
	require.NoError(t, err)

	// Create repos with override support
	securityProvider := newTestSecurityProvider(universeDB, zerolog.Nop())
	positionRepo := NewPositionRepository(portfolioDB, universeDB, securityProvider, zerolog.Nop())

	// Execute
	positions, err := positionRepo.GetWithSecurityInfo()
	require.NoError(t, err)
	require.Len(t, positions, 1)

	// Assert override applied
	assert.Equal(t, "WORLD", positions[0].Geography, "Geography override not applied")
}

func TestGetWithSecurityInfo_AppliesIndustryOverride(t *testing.T) {
	portfolioDB, universeDB := setupTestDBWithOverrides(t)

	// Insert security with Technology industry
	insertSecurityWithoutOverrideColumns(t, universeDB, "US0378331005", "AAPL.US", "Apple Inc.")
	// Update JSON data to add industry field
	_, err := universeDB.Exec(`
		UPDATE securities
		SET data = json_set(data, '$.industry', ?)
		WHERE isin = ?`, "Technology", "US0378331005")
	require.NoError(t, err)

	// Override industry to Finance
	insertOverride(t, universeDB, "US0378331005", "industry", "Finance")

	// Insert position for this security
	now := time.Now().Unix()
	_, err = portfolioDB.Exec(`INSERT INTO positions (isin, symbol, quantity, avg_price, currency, currency_rate, last_updated)
		VALUES (?, ?, ?, ?, ?, ?, ?)`, "US0378331005", "AAPL.US", 100.0, 150.0, "USD", 1.1, now)
	require.NoError(t, err)

	// Create repos with override support
	securityProvider := newTestSecurityProvider(universeDB, zerolog.Nop())
	positionRepo := NewPositionRepository(portfolioDB, universeDB, securityProvider, zerolog.Nop())

	// Execute
	positions, err := positionRepo.GetWithSecurityInfo()
	require.NoError(t, err)
	require.Len(t, positions, 1)

	// Assert override applied
	assert.Equal(t, "Finance", positions[0].Industry, "Industry override not applied")
}

func TestGetWithSecurityInfo_AppliesNameOverride(t *testing.T) {
	portfolioDB, universeDB := setupTestDBWithOverrides(t)

	// Insert security with original name
	insertSecurityWithoutOverrideColumns(t, universeDB, "US0378331005", "AAPL.US", "Apple Inc.")

	// Override name to custom name
	insertOverride(t, universeDB, "US0378331005", "name", "Apple Custom Name")

	// Insert position for this security
	now := time.Now().Unix()
	_, err := portfolioDB.Exec(`INSERT INTO positions (isin, symbol, quantity, avg_price, currency, currency_rate, last_updated)
		VALUES (?, ?, ?, ?, ?, ?, ?)`, "US0378331005", "AAPL.US", 100.0, 150.0, "USD", 1.1, now)
	require.NoError(t, err)

	// Create repos with override support
	securityProvider := newTestSecurityProvider(universeDB, zerolog.Nop())
	positionRepo := NewPositionRepository(portfolioDB, universeDB, securityProvider, zerolog.Nop())

	// Execute
	positions, err := positionRepo.GetWithSecurityInfo()
	require.NoError(t, err)
	require.Len(t, positions, 1)

	// Assert override applied
	assert.Equal(t, "Apple Custom Name", positions[0].StockName, "Name override not applied")
}

// Note: TestGetWithSecurityInfo_WithoutSecurityRepo_UsesFallback was removed
// because the fallback anti-pattern has been eliminated. SecurityProvider is now
// a required dependency with no fallbacks to mask DI failures.
