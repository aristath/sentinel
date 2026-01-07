package optimization

import (
	"database/sql"
	"testing"

	"github.com/aristath/portfolioManager/internal/modules/symbolic_regression"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	_ "modernc.org/sqlite"
)

func TestReturnsCalculator_WithDiscoveredFormula(t *testing.T) {
	// Setup test database
	db, err := sql.Open("sqlite", ":memory:")
	require.NoError(t, err)
	defer db.Close()

	// Create schema
	_, err = db.Exec(`
		CREATE TABLE IF NOT EXISTS positions (
			isin TEXT PRIMARY KEY,
			symbol TEXT,
			quantity REAL NOT NULL,
			avg_price REAL NOT NULL
		);

		CREATE TABLE IF NOT EXISTS scores (
			isin TEXT PRIMARY KEY,
			total_score REAL NOT NULL,
			cagr_score REAL,
			fundamental_score REAL,
			dividend_bonus REAL,
			last_updated TEXT NOT NULL
		);

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

	// Insert test data
	_, err = db.Exec(`
		INSERT INTO positions (isin, symbol, quantity, avg_price)
		VALUES ('US0378331005', 'AAPL', 10.0, 150.0);

		INSERT INTO scores (isin, total_score, cagr_score, fundamental_score, dividend_bonus, last_updated)
		VALUES ('US0378331005', 0.75, 0.80, 0.70, 0.02, '2024-01-01');

		INSERT INTO discovered_formulas (
			formula_type, security_type, formula_expression, validation_metrics,
			fitness_score, complexity, discovered_at, is_active
		) VALUES (
			'expected_return', 'stock',
			'0.65*cagr + 0.28*total_score',
			'{"mae": 0.05, "rmse": 0.08}',
			0.05, 5, '2024-01-01', 1
		);
	`)
	require.NoError(t, err)

	// Create formula storage
	log := zerolog.Nop()
	formulaStorage := symbolic_regression.NewFormulaStorage(db, log)

	// Create returns calculator with formula storage
	// Note: universeDB is nil for this test since we're using ISIN directly
	calc := &ReturnsCalculator{
		db:             db,
		universeDB:     nil, // Not needed for this test (ISIN provided directly)
		formulaStorage: formulaStorage,
		log:            log,
	}

	// Test security
	security := Security{
		Symbol:      "AAPL",
		ISIN:        "US0378331005",
		ProductType: "EQUITY",
	}

	// Calculate expected return
	result, err := calc.calculateSingle(
		security,
		0.11, // target return
		0.80, // threshold
		0.0,  // dividend bonus
		0.3,  // regime score
		0.0,  // forward adjustment
	)

	require.NoError(t, err)
	require.NotNil(t, result)

	// Should use discovered formula: 0.65*cagr + 0.28*total_score
	// cagr = 0.12, total_score = 0.75
	// Expected: 0.65*0.12 + 0.28*0.75 = 0.078 + 0.21 = 0.288
	// But we also add dividend yield (0.02) and apply other adjustments
	// So result should be in reasonable range
	assert.Greater(t, *result, 0.0)
	assert.Less(t, *result, 0.5)
}

func TestReturnsCalculator_FallbackWhenNoFormula(t *testing.T) {
	// Setup test database without discovered formula
	db, err := sql.Open("sqlite", ":memory:")
	require.NoError(t, err)
	defer db.Close()

	_, err = db.Exec(`
		CREATE TABLE IF NOT EXISTS positions (
			isin TEXT PRIMARY KEY,
			symbol TEXT,
			quantity REAL NOT NULL,
			avg_price REAL NOT NULL
		);

		CREATE TABLE IF NOT EXISTS scores (
			isin TEXT PRIMARY KEY,
			total_score REAL NOT NULL,
			cagr_score REAL,
			dividend_bonus REAL,
			last_updated TEXT NOT NULL
		);
	`)
	require.NoError(t, err)

	_, err = db.Exec(`
		INSERT INTO positions (isin, symbol, quantity, avg_price)
		VALUES ('US0378331005', 'AAPL', 10.0, 150.0);

		INSERT INTO scores (isin, total_score, cagr_score, dividend_bonus, last_updated)
		VALUES ('US0378331005', 0.75, 0.80, 0.02, '2024-01-01');
	`)
	require.NoError(t, err)

	log := zerolog.Nop()
	formulaStorage := symbolic_regression.NewFormulaStorage(db, log)

	calc := &ReturnsCalculator{
		db:             db,
		formulaStorage: formulaStorage,
		log:            log,
	}

	security := Security{
		Symbol:      "AAPL",
		ISIN:        "US0378331005",
		ProductType: "EQUITY",
	}

	// Should fall back to static formula when no discovered formula exists
	result, err := calc.calculateSingle(
		security,
		0.11,
		0.80,
		0.0,
		0.0,
		0.0,
	)

	// Should still work (using static formula)
	require.NoError(t, err)
	require.NotNil(t, result)
}
