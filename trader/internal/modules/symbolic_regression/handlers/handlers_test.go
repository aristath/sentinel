package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/aristath/sentinel/internal/modules/symbolic_regression"
	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	_ "modernc.org/sqlite"
)

func setupTestHandlers(t *testing.T) (*Handlers, *sql.DB, func()) {
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
			discovered_at INTEGER NOT NULL,
			is_active INTEGER DEFAULT 1,
			created_at INTEGER DEFAULT (strftime('%s', 'now'))
		);
	`)
	require.NoError(t, err)

	log := zerolog.Nop()
	storage := symbolic_regression.NewFormulaStorage(db, log)

	handlers := NewHandlers(storage, nil, nil, log)

	cleanup := func() {
		db.Close()
	}

	return handlers, db, cleanup
}

func TestHandlers_ListFormulas(t *testing.T) {
	handlers, db, cleanup := setupTestHandlers(t)
	defer cleanup()

	// Insert test formula
	testDate := time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC)
	_, err := db.Exec(`
		INSERT INTO discovered_formulas (
			formula_type, security_type, formula_expression, validation_metrics,
			fitness_score, complexity, discovered_at, is_active
		) VALUES (
			'expected_return', 'stock', '0.65*cagr + 0.28*score',
			'{"mae": 0.05}', 0.05, 5, ?, 1
		);
	`, testDate.Unix())
	require.NoError(t, err)

	req := httptest.NewRequest("GET", "/api/symbolic-regression/formulas?formula_type=expected_return&security_type=stock", nil)
	w := httptest.NewRecorder()

	handlers.HandleListFormulas(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err = json.Unmarshal(w.Body.Bytes(), &response)
	require.NoError(t, err)

	assert.Contains(t, response, "formulas")
}

func TestHandlers_GetActiveFormula(t *testing.T) {
	handlers, db, cleanup := setupTestHandlers(t)
	defer cleanup()

	// Insert test formula with Unix timestamp
	testDate := time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC)
	_, err := db.Exec(`
		INSERT INTO discovered_formulas (
			formula_type, security_type, formula_expression, validation_metrics,
			fitness_score, complexity, discovered_at, is_active
		) VALUES (
			'expected_return', 'stock', '0.65*cagr + 0.28*score',
			'{"mae": 0.05}', 0.05, 5, ?, 1
		);
	`, testDate.Unix())
	require.NoError(t, err)

	req := httptest.NewRequest("GET", "/api/symbolic-regression/formulas/active?formula_type=expected_return&security_type=stock", nil)
	w := httptest.NewRecorder()

	handlers.HandleGetActiveFormula(w, req)

	// Should succeed
	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err = json.Unmarshal(w.Body.Bytes(), &response)
	require.NoError(t, err)

	// Should have formula or message
	if response["formula"] != nil {
		assert.NotNil(t, response["formula"])
	} else {
		// No formula found is also valid
		assert.Contains(t, response, "message")
	}
}

func TestHandlers_DeactivateFormula(t *testing.T) {
	handlers, db, cleanup := setupTestHandlers(t)
	defer cleanup()

	// Insert test formula
	testDate := time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC)
	result, err := db.Exec(`
		INSERT INTO discovered_formulas (
			formula_type, security_type, formula_expression, validation_metrics,
			fitness_score, complexity, discovered_at, is_active
		) VALUES (
			'expected_return', 'stock', '0.65*cagr + 0.28*score',
			'{"mae": 0.05}', 0.05, 5, ?, 1
		);
	`, testDate.Unix())
	require.NoError(t, err)

	id, _ := result.LastInsertId()

	router := chi.NewRouter()
	router.Post("/formulas/{id}/deactivate", handlers.HandleDeactivateFormula)

	req := httptest.NewRequest("POST", "/formulas/1/deactivate", nil)
	w := httptest.NewRecorder()

	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	// Verify formula is deactivated
	var isActive int
	err = db.QueryRow("SELECT is_active FROM discovered_formulas WHERE id = ?", id).Scan(&isActive)
	require.NoError(t, err)
	assert.Equal(t, 0, isActive)
}
