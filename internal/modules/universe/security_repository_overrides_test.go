package universe

import (
	"database/sql"
	"testing"
	"time"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	_ "github.com/mattn/go-sqlite3"
)

// setupTestDBWithOverrides creates a test database with new schema (without the 4 columns)
// and security_overrides table
func setupTestDBWithOverrides(t *testing.T) *sql.DB {
	// Use a temp file to avoid in-memory database connection isolation issues
	// Each connection to :memory: gets its own database, but temp file is shared
	tmpFile := t.TempDir() + "/test.db"
	db, err := sql.Open("sqlite3", tmpFile)
	require.NoError(t, err)

	// Enable foreign keys
	_, err = db.Exec("PRAGMA foreign_keys = ON")
	require.NoError(t, err)

	// Create securities table with JSON storage (migration 038 schema)
	_, err = db.Exec(`
		CREATE TABLE securities (
			isin TEXT PRIMARY KEY,
			symbol TEXT NOT NULL,
			data TEXT NOT NULL,
			last_synced INTEGER
		) STRICT
	`)
	require.NoError(t, err)

	// Create security_overrides table
	_, err = db.Exec(`
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

	// Create security_tags table (needed by scanSecurity)
	_, err = db.Exec(`
		CREATE TABLE security_tags (
			isin TEXT NOT NULL,
			tag_id TEXT NOT NULL,
			created_at INTEGER NOT NULL,
			updated_at INTEGER NOT NULL,
			PRIMARY KEY (isin, tag_id),
			FOREIGN KEY (isin) REFERENCES securities(isin) ON DELETE CASCADE
		)
	`)
	require.NoError(t, err)

	// Create tags table (referenced by security_tags)
	_, err = db.Exec(`
		CREATE TABLE tags (
			id TEXT PRIMARY KEY,
			name TEXT NOT NULL,
			created_at INTEGER NOT NULL,
			updated_at INTEGER NOT NULL
		)
	`)
	require.NoError(t, err)

	return db
}

func insertSecurityWithoutOverrideColumns(t *testing.T, db *sql.DB, isin, symbol, name string) {
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES (?, ?, json_object('name', ?), NULL)
	`, isin, symbol, name)
	require.NoError(t, err)
}

func insertOverride(t *testing.T, db *sql.DB, isin, field, value string) {
	now := time.Now().Unix()
	_, err := db.Exec(`
		INSERT INTO security_overrides (isin, field, value, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?)
	`, isin, field, value, now, now)
	require.NoError(t, err)
}

// Test ApplyOverrides function

func TestApplyOverrides_StringField(t *testing.T) {
	security := &Security{
		ISIN:      "US0378331005",
		Symbol:    "AAPL.US",
		Name:      "Apple Inc.",
		Geography: "US",
	}

	overrides := map[string]string{
		"geography": "WORLD",
	}

	ApplyOverrides(security, overrides)

	assert.Equal(t, "WORLD", security.Geography)
	assert.Equal(t, "Apple Inc.", security.Name) // Unchanged
}

func TestApplyOverrides_BoolField(t *testing.T) {
	security := &Security{
		ISIN:      "US0378331005",
		AllowBuy:  true,
		AllowSell: true,
	}

	overrides := map[string]string{
		"allow_buy":  "false",
		"allow_sell": "false",
	}

	ApplyOverrides(security, overrides)

	assert.False(t, security.AllowBuy)
	assert.False(t, security.AllowSell)
}

func TestApplyOverrides_IntField(t *testing.T) {
	security := &Security{
		ISIN:   "US0378331005",
		MinLot: 1,
	}

	overrides := map[string]string{
		"min_lot": "100",
	}

	ApplyOverrides(security, overrides)

	assert.Equal(t, 100, security.MinLot)
}

func TestApplyOverrides_FloatField(t *testing.T) {
	security := &Security{
		ISIN:               "US0378331005",
		PriorityMultiplier: 1.0,
	}

	overrides := map[string]string{
		"priority_multiplier": "2.5",
	}

	ApplyOverrides(security, overrides)

	assert.Equal(t, 2.5, security.PriorityMultiplier)
}

func TestApplyOverrides_EmptyValueIgnored(t *testing.T) {
	security := &Security{
		ISIN:      "US0378331005",
		Geography: "US",
	}

	overrides := map[string]string{
		"geography": "", // Empty value should be ignored
	}

	ApplyOverrides(security, overrides)

	assert.Equal(t, "US", security.Geography) // Unchanged
}

func TestApplyOverrides_MultipleFields(t *testing.T) {
	security := &Security{
		ISIN:               "US0378331005",
		Symbol:             "AAPL.US",
		Name:               "Apple Inc.",
		Geography:          "US",
		Industry:           "Technology",
		MinLot:             1,
		AllowBuy:           true,
		AllowSell:          true,
		PriorityMultiplier: 1.0,
	}

	overrides := map[string]string{
		"geography":           "WORLD",
		"industry":            "Consumer Electronics",
		"min_lot":             "50",
		"allow_buy":           "false",
		"priority_multiplier": "1.5",
	}

	ApplyOverrides(security, overrides)

	assert.Equal(t, "WORLD", security.Geography)
	assert.Equal(t, "Consumer Electronics", security.Industry)
	assert.Equal(t, 50, security.MinLot)
	assert.False(t, security.AllowBuy)
	assert.True(t, security.AllowSell) // Not overridden
	assert.Equal(t, 1.5, security.PriorityMultiplier)
	assert.Equal(t, "Apple Inc.", security.Name) // Not overridden
}

func TestApplyOverrides_NilSecurity(t *testing.T) {
	// Should not panic
	ApplyOverrides(nil, map[string]string{"geography": "US"})
}

func TestApplyOverrides_EmptyOverrides(t *testing.T) {
	security := &Security{
		ISIN:      "US0378331005",
		Geography: "US",
	}

	ApplyOverrides(security, map[string]string{})

	assert.Equal(t, "US", security.Geography) // Unchanged
}

func TestApplyOverrides_NilOverrides(t *testing.T) {
	security := &Security{
		ISIN:      "US0378331005",
		Geography: "US",
	}

	ApplyOverrides(security, nil)

	assert.Equal(t, "US", security.Geography) // Unchanged
}

func TestApplyOverrides_UnknownFieldIgnored(t *testing.T) {
	security := &Security{
		ISIN:      "US0378331005",
		Geography: "US",
	}

	overrides := map[string]string{
		"unknown_field": "some_value",
	}

	// Should not panic, unknown fields are just ignored
	ApplyOverrides(security, overrides)

	assert.Equal(t, "US", security.Geography)
}

func TestApplyOverrides_InvalidIntValueIgnored(t *testing.T) {
	security := &Security{
		ISIN:   "US0378331005",
		MinLot: 1,
	}

	overrides := map[string]string{
		"min_lot": "not_a_number",
	}

	ApplyOverrides(security, overrides)

	assert.Equal(t, 1, security.MinLot) // Unchanged due to parse error
}

func TestApplyOverrides_InvalidFloatValueIgnored(t *testing.T) {
	security := &Security{
		ISIN:               "US0378331005",
		PriorityMultiplier: 1.0,
	}

	overrides := map[string]string{
		"priority_multiplier": "not_a_float",
	}

	ApplyOverrides(security, overrides)

	assert.Equal(t, 1.0, security.PriorityMultiplier) // Unchanged due to parse error
}

// Test SecurityRepository with override merging

func TestSecurityRepository_GetByISIN_AppliesDefaults(t *testing.T) {
	db := setupTestDBWithOverrides(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	overrideRepo := NewOverrideRepository(db, log)
	repo := NewSecurityRepositoryWithOverrides(db, overrideRepo, log)

	insertSecurityWithoutOverrideColumns(t, db, "US0378331005", "AAPL.US", "Apple Inc.")

	// Get security - should have defaults applied
	security, err := repo.GetByISIN("US0378331005")
	require.NoError(t, err)
	require.NotNil(t, security)

	// Verify defaults are applied
	assert.True(t, security.AllowBuy, "Default allow_buy should be true")
	assert.True(t, security.AllowSell, "Default allow_sell should be true")
	assert.Equal(t, 1, security.MinLot, "Default min_lot should be 1")
	assert.Equal(t, 1.0, security.PriorityMultiplier, "Default priority_multiplier should be 1.0")
}

func TestSecurityRepository_GetByISIN_MergesOverrides(t *testing.T) {
	db := setupTestDBWithOverrides(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	overrideRepo := NewOverrideRepository(db, log)
	repo := NewSecurityRepositoryWithOverrides(db, overrideRepo, log)

	insertSecurityWithoutOverrideColumns(t, db, "US0378331005", "AAPL.US", "Apple Inc.")
	insertOverride(t, db, "US0378331005", "allow_buy", "false")
	insertOverride(t, db, "US0378331005", "min_lot", "100")
	insertOverride(t, db, "US0378331005", "priority_multiplier", "2.0")

	// Get security - should have overrides applied
	security, err := repo.GetByISIN("US0378331005")
	require.NoError(t, err)
	require.NotNil(t, security)

	// Verify overrides are applied
	assert.False(t, security.AllowBuy, "Override should set allow_buy to false")
	assert.True(t, security.AllowSell, "Default allow_sell should be true (no override)")
	assert.Equal(t, 100, security.MinLot, "Override should set min_lot to 100")
	assert.Equal(t, 2.0, security.PriorityMultiplier, "Override should set priority_multiplier to 2.0")
}

func TestSecurityRepository_GetByISIN_GeographyOverride(t *testing.T) {
	db := setupTestDBWithOverrides(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	overrideRepo := NewOverrideRepository(db, log)
	repo := NewSecurityRepositoryWithOverrides(db, overrideRepo, log)

	// Insert security with geography from Tradernet
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES (?, ?, json_object('name', ?, 'geography', ?), NULL)
	`, "IE00B3RBWM25", "VWCE.EU", "Vanguard FTSE All-World", "EU")
	require.NoError(t, err)

	// Add override for geography
	insertOverride(t, db, "IE00B3RBWM25", "geography", "WORLD")

	// Get security - should have geography override applied
	security, err := repo.GetByISIN("IE00B3RBWM25")
	require.NoError(t, err)
	require.NotNil(t, security)

	assert.Equal(t, "WORLD", security.Geography, "Override should replace Tradernet geography")
}

func TestSecurityRepository_GetBySymbol_MergesOverrides(t *testing.T) {
	db := setupTestDBWithOverrides(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	overrideRepo := NewOverrideRepository(db, log)
	repo := NewSecurityRepositoryWithOverrides(db, overrideRepo, log)

	insertSecurityWithoutOverrideColumns(t, db, "US0378331005", "AAPL.US", "Apple Inc.")
	insertOverride(t, db, "US0378331005", "allow_sell", "false")

	// Get by symbol - should have overrides applied
	security, err := repo.GetBySymbol("AAPL.US")
	require.NoError(t, err)
	require.NotNil(t, security)

	assert.True(t, security.AllowBuy, "Default allow_buy should be true")
	assert.False(t, security.AllowSell, "Override should set allow_sell to false")
}

func TestSecurityRepository_GetAllActive_MergesOverrides(t *testing.T) {
	db := setupTestDBWithOverrides(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	overrideRepo := NewOverrideRepository(db, log)
	repo := NewSecurityRepositoryWithOverrides(db, overrideRepo, log)

	// Insert multiple securities
	insertSecurityWithoutOverrideColumns(t, db, "US0378331005", "AAPL.US", "Apple Inc.")
	insertSecurityWithoutOverrideColumns(t, db, "IE00B3RBWM25", "VWCE.EU", "Vanguard FTSE All-World")

	// Add overrides for different securities
	insertOverride(t, db, "US0378331005", "min_lot", "10")
	insertOverride(t, db, "IE00B3RBWM25", "allow_buy", "false")

	// Get all active - each should have their overrides applied
	securities, err := repo.GetAllActive()
	require.NoError(t, err)
	require.Len(t, securities, 2)

	// Find each security and verify overrides
	var aapl, vwce *Security
	for i := range securities {
		if securities[i].Symbol == "AAPL.US" {
			aapl = &securities[i]
		} else if securities[i].Symbol == "VWCE.EU" {
			vwce = &securities[i]
		}
	}

	require.NotNil(t, aapl)
	require.NotNil(t, vwce)

	assert.Equal(t, 10, aapl.MinLot, "AAPL should have min_lot override")
	assert.True(t, aapl.AllowBuy, "AAPL should have default allow_buy")

	assert.False(t, vwce.AllowBuy, "VWCE should have allow_buy override")
	assert.Equal(t, 1, vwce.MinLot, "VWCE should have default min_lot")
}

func TestSecurityRepository_GetAll_MergesOverrides(t *testing.T) {
	db := setupTestDBWithOverrides(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	overrideRepo := NewOverrideRepository(db, log)
	repo := NewSecurityRepositoryWithOverrides(db, overrideRepo, log)

	insertSecurityWithoutOverrideColumns(t, db, "US0378331005", "AAPL.US", "Apple Inc.")
	insertOverride(t, db, "US0378331005", "priority_multiplier", "1.5")

	securities, err := repo.GetAll()
	require.NoError(t, err)
	require.Len(t, securities, 1)

	assert.Equal(t, 1.5, securities[0].PriorityMultiplier)
}

func TestSecurityRepository_WithoutOverrideRepo_UsesDefaults(t *testing.T) {
	db := setupTestDBWithOverrides(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	// Create repo without override repository (nil)
	repo := NewSecurityRepositoryWithOverrides(db, nil, log)

	insertSecurityWithoutOverrideColumns(t, db, "US0378331005", "AAPL.US", "Apple Inc.")
	// Insert override - but it won't be read because overrideRepo is nil
	insertOverride(t, db, "US0378331005", "allow_buy", "false")

	security, err := repo.GetByISIN("US0378331005")
	require.NoError(t, err)
	require.NotNil(t, security)

	// Should have defaults, overrides are not applied when overrideRepo is nil
	assert.True(t, security.AllowBuy, "Should have default allow_buy when overrideRepo is nil")
}
