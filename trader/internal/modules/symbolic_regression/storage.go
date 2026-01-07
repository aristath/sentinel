package symbolic_regression

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"time"

	"github.com/rs/zerolog"
)

// FormulaStorage handles storage and retrieval of discovered formulas
type FormulaStorage struct {
	db  *sql.DB
	log zerolog.Logger
}

// NewFormulaStorage creates a new formula storage
func NewFormulaStorage(db *sql.DB, log zerolog.Logger) *FormulaStorage {
	return &FormulaStorage{
		db:  db,
		log: log.With().Str("component", "formula_storage").Logger(),
	}
}

// SaveFormula saves a discovered formula to the database
// isActive is optional variadic parameter - if not provided, defaults to false
func (fs *FormulaStorage) SaveFormula(formula *DiscoveredFormula, isActive ...bool) (int64, error) {
	// Serialize validation metrics to JSON
	metricsJSON, err := json.Marshal(formula.ValidationMetrics)
	if err != nil {
		return 0, fmt.Errorf("failed to marshal validation metrics: %w", err)
	}

	// Determine is_active value: default to false if not provided
	isActiveValue := 0
	if len(isActive) > 0 && isActive[0] {
		isActiveValue = 1
	}

	query := `
		INSERT INTO discovered_formulas (
			formula_type, security_type, regime_range_min, regime_range_max,
			formula_expression, validation_metrics, fitness_score, complexity,
			training_examples_count, discovered_at, is_active
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	var regimeMin, regimeMax interface{}
	if formula.RegimeRangeMin != nil {
		regimeMin = *formula.RegimeRangeMin
	}
	if formula.RegimeRangeMax != nil {
		regimeMax = *formula.RegimeRangeMax
	}

	// Extract fitness and complexity from validation metrics if not set
	fitness := 0.0
	complexity := 0
	if val, ok := formula.ValidationMetrics["fitness"]; ok {
		fitness = val
	}
	if val, ok := formula.ValidationMetrics["complexity"]; ok {
		complexity = int(val)
	}

	result, err := fs.db.Exec(
		query,
		string(formula.FormulaType),
		string(formula.SecurityType),
		regimeMin,
		regimeMax,
		formula.FormulaExpression,
		string(metricsJSON),
		fitness,
		complexity,
		0, // training_examples_count (can be added later)
		formula.DiscoveredAt.Unix(),
		isActiveValue,
	)
	if err != nil {
		return 0, fmt.Errorf("failed to insert formula: %w", err)
	}

	id, err := result.LastInsertId()
	if err != nil {
		return 0, fmt.Errorf("failed to get insert ID: %w", err)
	}

	fs.log.Info().
		Int64("id", id).
		Str("formula_type", string(formula.FormulaType)).
		Str("security_type", string(formula.SecurityType)).
		Msg("Saved discovered formula")

	return id, nil
}

// GetActiveFormula retrieves the active formula for a given type and security type
// regimeScore is optional - if provided, will match formulas with regime ranges
func (fs *FormulaStorage) GetActiveFormula(
	formulaType FormulaType,
	securityType SecurityType,
	regimeScore *float64,
) (*DiscoveredFormula, error) {
	var query string
	var args []interface{}

	if regimeScore != nil {
		// Match formulas with regime ranges that include this score
		query = `
			SELECT id, formula_type, security_type, regime_range_min, regime_range_max,
			       formula_expression, validation_metrics, fitness_score, complexity,
			       training_examples_count, discovered_at
			FROM discovered_formulas
			WHERE formula_type = ? AND security_type = ? AND is_active = 1
			  AND (regime_range_min IS NULL OR regime_range_min <= ?)
			  AND (regime_range_max IS NULL OR regime_range_max >= ?)
			ORDER BY discovered_at DESC
			LIMIT 1
		`
		args = []interface{}{string(formulaType), string(securityType), *regimeScore, *regimeScore}
	} else {
		// No regime filtering
		query = `
			SELECT id, formula_type, security_type, regime_range_min, regime_range_max,
			       formula_expression, validation_metrics, fitness_score, complexity,
			       training_examples_count, discovered_at
			FROM discovered_formulas
			WHERE formula_type = ? AND security_type = ? AND is_active = 1
			ORDER BY discovered_at DESC
			LIMIT 1
		`
		args = []interface{}{string(formulaType), string(securityType)}
	}

	var formula DiscoveredFormula
	var regimeMin, regimeMax sql.NullFloat64
	var metricsJSON string
	var discoveredAtUnix sql.NullInt64
	var fitnessScore float64
	var complexity int
	var trainingExamplesCount sql.NullInt64

	err := fs.db.QueryRow(query, args...).Scan(
		&formula.ID,
		&formula.FormulaType,
		&formula.SecurityType,
		&regimeMin,
		&regimeMax,
		&formula.FormulaExpression,
		&metricsJSON,
		&fitnessScore,
		&complexity,
		&trainingExamplesCount,
		&discoveredAtUnix,
	)
	if err == sql.ErrNoRows {
		return nil, nil // No active formula found
	}
	if err != nil {
		return nil, fmt.Errorf("failed to query formula: %w", err)
	}

	// Parse regime ranges
	if regimeMin.Valid {
		formula.RegimeRangeMin = &regimeMin.Float64
	}
	if regimeMax.Valid {
		formula.RegimeRangeMax = &regimeMax.Float64
	}

	// Parse validation metrics
	if err := json.Unmarshal([]byte(metricsJSON), &formula.ValidationMetrics); err != nil {
		return nil, fmt.Errorf("failed to unmarshal validation metrics: %w", err)
	}

	// Convert Unix timestamp to time.Time
	if discoveredAtUnix.Valid {
		formula.DiscoveredAt = time.Unix(discoveredAtUnix.Int64, 0).UTC()
	}

	return &formula, nil
}

// DeactivateFormula deactivates a formula (sets is_active = 0)
func (fs *FormulaStorage) DeactivateFormula(id int64) error {
	query := `UPDATE discovered_formulas SET is_active = 0 WHERE id = ?`

	_, err := fs.db.Exec(query, id)
	if err != nil {
		return fmt.Errorf("failed to deactivate formula: %w", err)
	}

	fs.log.Info().Int64("id", id).Msg("Deactivated formula")

	return nil
}

// GetAllFormulas retrieves all formulas (active and inactive) for a given type
func (fs *FormulaStorage) GetAllFormulas(
	formulaType FormulaType,
	securityType SecurityType,
) ([]*DiscoveredFormula, error) {
	query := `
		SELECT id, formula_type, security_type, regime_range_min, regime_range_max,
		       formula_expression, validation_metrics, fitness_score, complexity,
		       training_examples_count, discovered_at
		FROM discovered_formulas
		WHERE formula_type = ? AND security_type = ?
		ORDER BY discovered_at DESC
	`

	rows, err := fs.db.Query(query, string(formulaType), string(securityType))
	if err != nil {
		return nil, fmt.Errorf("failed to query formulas: %w", err)
	}
	defer rows.Close()

	var formulas []*DiscoveredFormula
	for rows.Next() {
		var formula DiscoveredFormula
		var regimeMin, regimeMax sql.NullFloat64
		var metricsJSON string
		var discoveredAtUnix sql.NullInt64
		var fitnessScore float64
		var complexity int
		var trainingExamplesCount sql.NullInt64

		err := rows.Scan(
			&formula.ID,
			&formula.FormulaType,
			&formula.SecurityType,
			&regimeMin,
			&regimeMax,
			&formula.FormulaExpression,
			&metricsJSON,
			&fitnessScore,
			&complexity,
			&trainingExamplesCount,
			&discoveredAtUnix,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan formula: %w", err)
		}

		// Parse regime ranges
		if regimeMin.Valid {
			formula.RegimeRangeMin = &regimeMin.Float64
		}
		if regimeMax.Valid {
			formula.RegimeRangeMax = &regimeMax.Float64
		}

		// Parse validation metrics
		formula.ValidationMetrics = make(map[string]float64)
		if metricsJSON != "" {
			if err := json.Unmarshal([]byte(metricsJSON), &formula.ValidationMetrics); err != nil {
				return nil, fmt.Errorf("failed to unmarshal validation metrics: %w", err)
			}
		}

		// Convert Unix timestamp to time.Time
		if discoveredAtUnix.Valid {
			formula.DiscoveredAt = time.Unix(discoveredAtUnix.Int64, 0).UTC()
		}

		formulas = append(formulas, &formula)
	}

	return formulas, nil
}
