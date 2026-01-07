package symbolic_regression

import (
	"database/sql"
	"testing"
	"time"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	_ "modernc.org/sqlite"
)

func setupStorageTestDB(t *testing.T) (*sql.DB, func()) {
	db, err := sql.Open("sqlite", ":memory:")
	require.NoError(t, err)

	// Create schema
	_, err = db.Exec(`
		CREATE TABLE IF NOT EXISTS discovered_formulas (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			formula_type TEXT NOT NULL,
			security_type TEXT NOT NULL,
			regime_range_min REAL,
			regime_range_max REAL,
			formula_expression TEXT NOT NULL,
			validation_metrics TEXT NOT NULL,
			fitness_score REAL NOT NULL,
			complexity INTEGER NOT NULL,
			training_examples_count INTEGER,
			discovered_at TEXT NOT NULL,
			is_active INTEGER DEFAULT 1,
			created_at TEXT DEFAULT CURRENT_TIMESTAMP
		);
	`)
	require.NoError(t, err)

	cleanup := func() {
		db.Close()
	}

	return db, cleanup
}

func TestFormulaStorage_SaveFormula(t *testing.T) {
	db, cleanup := setupStorageTestDB(t)
	defer cleanup()

	log := zerolog.Nop()
	storage := NewFormulaStorage(db, log)

	formula := &DiscoveredFormula{
		FormulaType:       FormulaTypeExpectedReturn,
		SecurityType:      SecurityTypeStock,
		RegimeRangeMin:    floatPtr(-1.0),
		RegimeRangeMax:    floatPtr(0.0),
		FormulaExpression: "0.65*cagr + 0.28*score",
		ValidationMetrics: map[string]float64{
			"mae":      0.05,
			"rmse":     0.08,
			"spearman": 0.75,
		},
		DiscoveredAt: time.Now(),
	}

	id, err := storage.SaveFormula(formula, true) // Use explicit true for backward compatibility in test
	require.NoError(t, err)
	assert.Greater(t, id, int64(0))
}

func TestFormulaStorage_GetActiveFormula(t *testing.T) {
	db, cleanup := setupStorageTestDB(t)
	defer cleanup()

	log := zerolog.Nop()
	storage := NewFormulaStorage(db, log)

	// Save a formula
	formula := &DiscoveredFormula{
		FormulaType:       FormulaTypeExpectedReturn,
		SecurityType:      SecurityTypeStock,
		FormulaExpression: "0.65*cagr + 0.28*score",
		ValidationMetrics: map[string]float64{"mae": 0.05},
		DiscoveredAt:      time.Now(),
	}

	id, err := storage.SaveFormula(formula, true) // Use explicit true to make it active
	require.NoError(t, err)

	// Retrieve it
	retrieved, err := storage.GetActiveFormula(FormulaTypeExpectedReturn, SecurityTypeStock, nil)
	require.NoError(t, err)
	require.NotNil(t, retrieved)

	assert.Equal(t, id, retrieved.ID)
	assert.Equal(t, FormulaTypeExpectedReturn, retrieved.FormulaType)
	assert.Equal(t, SecurityTypeStock, retrieved.SecurityType)
	assert.Equal(t, "0.65*cagr + 0.28*score", retrieved.FormulaExpression)
}

func TestFormulaStorage_DeactivateFormula(t *testing.T) {
	db, cleanup := setupStorageTestDB(t)
	defer cleanup()

	log := zerolog.Nop()
	storage := NewFormulaStorage(db, log)

	// Save a formula
	formula := &DiscoveredFormula{
		FormulaType:       FormulaTypeExpectedReturn,
		SecurityType:      SecurityTypeStock,
		FormulaExpression: "0.65*cagr + 0.28*score",
		ValidationMetrics: map[string]float64{"mae": 0.05},
		DiscoveredAt:      time.Now(),
	}

	id, err := storage.SaveFormula(formula, true) // Use explicit true to make it active
	require.NoError(t, err)

	// Deactivate it
	err = storage.DeactivateFormula(id)
	require.NoError(t, err)

	// Should not be retrievable as active
	retrieved, err := storage.GetActiveFormula(FormulaTypeExpectedReturn, SecurityTypeStock, nil)
	require.NoError(t, err)
	assert.Nil(t, retrieved)
}

func TestFormulaStorage_SaveFormulaWithIsActive(t *testing.T) {
	db, cleanup := setupStorageTestDB(t)
	defer cleanup()

	log := zerolog.Nop()
	storage := NewFormulaStorage(db, log)

	formula := &DiscoveredFormula{
		FormulaType:       FormulaTypeExpectedReturn,
		SecurityType:      SecurityTypeStock,
		FormulaExpression: "0.65*cagr + 0.28*score",
		ValidationMetrics: map[string]float64{"mae": 0.05},
		DiscoveredAt:      time.Now(),
	}

	t.Run("Save with isActive=true", func(t *testing.T) {
		id, err := storage.SaveFormula(formula, true)
		require.NoError(t, err)
		assert.Greater(t, id, int64(0))

		// Verify is_active = 1 in database
		var isActive int
		err = db.QueryRow("SELECT is_active FROM discovered_formulas WHERE id = ?", id).Scan(&isActive)
		require.NoError(t, err)
		assert.Equal(t, 1, isActive)
	})

	t.Run("Save with isActive=false", func(t *testing.T) {
		id, err := storage.SaveFormula(formula, false)
		require.NoError(t, err)
		assert.Greater(t, id, int64(0))

		// Verify is_active = 0 in database
		var isActive int
		err = db.QueryRow("SELECT is_active FROM discovered_formulas WHERE id = ?", id).Scan(&isActive)
		require.NoError(t, err)
		assert.Equal(t, 0, isActive)
	})

	t.Run("Save without isActive parameter (default to false)", func(t *testing.T) {
		id, err := storage.SaveFormula(formula)
		require.NoError(t, err)
		assert.Greater(t, id, int64(0))

		// Verify is_active = 0 in database (default)
		var isActive int
		err = db.QueryRow("SELECT is_active FROM discovered_formulas WHERE id = ?", id).Scan(&isActive)
		require.NoError(t, err)
		assert.Equal(t, 0, isActive)
	})
}
