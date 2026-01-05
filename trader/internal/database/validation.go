package database

import (
	"database/sql"
	"fmt"
	"strings"
)

// ISINValidator validates ISIN requirements before migration
type ISINValidator struct {
	db *sql.DB
}

// ValidationResult contains the results of all validation checks
type ValidationResult struct {
	IsValid            bool
	MissingISINs       []string // Securities without ISIN
	DuplicateISINs     []string // Duplicate ISIN values found
	OrphanedReferences []string // Foreign key references to non-existent securities
}

// NewISINValidator creates a new ISIN validator
func NewISINValidator(db *sql.DB) *ISINValidator {
	return &ISINValidator{
		db: db,
	}
}

// ValidateAllSecuritiesHaveISIN checks that all securities have a non-empty ISIN
// Returns list of symbols that are missing ISIN
func (v *ISINValidator) ValidateAllSecuritiesHaveISIN() ([]string, error) {
	query := `
		SELECT symbol
		FROM securities
		WHERE isin IS NULL OR isin = '' OR TRIM(isin) = ''
	`

	rows, err := v.db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query securities: %w", err)
	}
	defer rows.Close()

	var missingISINs []string
	for rows.Next() {
		var symbol string
		if err := rows.Scan(&symbol); err != nil {
			return nil, fmt.Errorf("failed to scan symbol: %w", err)
		}
		missingISINs = append(missingISINs, symbol)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating rows: %w", err)
	}

	return missingISINs, nil
}

// ValidateNoDuplicateISINs checks that no two securities share the same ISIN
// Returns list of duplicate ISIN values
func (v *ISINValidator) ValidateNoDuplicateISINs() ([]string, error) {
	query := `
		SELECT isin, COUNT(*) as count
		FROM securities
		WHERE isin IS NOT NULL AND isin != '' AND TRIM(isin) != ''
		GROUP BY isin
		HAVING COUNT(*) > 1
	`

	rows, err := v.db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query duplicate ISINs: %w", err)
	}
	defer rows.Close()

	var duplicateISINs []string
	for rows.Next() {
		var isin string
		var count int
		if err := rows.Scan(&isin, &count); err != nil {
			return nil, fmt.Errorf("failed to scan duplicate ISIN: %w", err)
		}
		duplicateISINs = append(duplicateISINs, isin)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating rows: %w", err)
	}

	return duplicateISINs, nil
}

// ValidateForeignKeys checks that all foreign key references point to existing securities
// This validates that scores, positions, trades, etc. reference valid securities
// Returns list of orphaned references (format: "table:column:value")
func (v *ISINValidator) ValidateForeignKeys() ([]string, error) {
	var errors []string

	// Check scores table (now uses isin as PRIMARY KEY)
	scoreQuery := `
		SELECT s.isin
		FROM scores s
		LEFT JOIN securities sec ON s.isin = sec.isin
		WHERE sec.isin IS NULL
	`
	rows, err := v.db.Query(scoreQuery)
	if err != nil {
		return nil, fmt.Errorf("failed to query orphaned scores: %w", err)
	}
	for rows.Next() {
		var isin string
		if err := rows.Scan(&isin); err != nil {
			rows.Close()
			return nil, fmt.Errorf("failed to scan orphaned score: %w", err)
		}
		errors = append(errors, fmt.Sprintf("scores:isin:%s", isin))
	}
	rows.Close()

	// Check positions table (now uses isin as PRIMARY KEY)
	positionQuery := `
		SELECT p.isin
		FROM positions p
		LEFT JOIN securities sec ON p.isin = sec.isin
		WHERE sec.isin IS NULL
	`
	rows, err = v.db.Query(positionQuery)
	if err != nil {
		return nil, fmt.Errorf("failed to query orphaned positions: %w", err)
	}
	for rows.Next() {
		var isin string
		if err := rows.Scan(&isin); err != nil {
			rows.Close()
			return nil, fmt.Errorf("failed to scan orphaned position: %w", err)
		}
		errors = append(errors, fmt.Sprintf("positions:isin:%s", isin))
	}
	rows.Close()

	return errors, nil
}

// ValidateAll runs all validation checks and returns a comprehensive result
func (v *ISINValidator) ValidateAll() (*ValidationResult, error) {
	result := &ValidationResult{
		IsValid:            true,
		MissingISINs:       []string{},
		DuplicateISINs:     []string{},
		OrphanedReferences: []string{},
	}

	// Check for missing ISINs
	missingISINs, err := v.ValidateAllSecuritiesHaveISIN()
	if err != nil {
		return nil, fmt.Errorf("failed to validate ISIN presence: %w", err)
	}
	result.MissingISINs = missingISINs
	if len(missingISINs) > 0 {
		result.IsValid = false
	}

	// Check for duplicate ISINs
	duplicateISINs, err := v.ValidateNoDuplicateISINs()
	if err != nil {
		return nil, fmt.Errorf("failed to validate duplicate ISINs: %w", err)
	}
	result.DuplicateISINs = duplicateISINs
	if len(duplicateISINs) > 0 {
		result.IsValid = false
	}

	// Check foreign keys
	orphanedRefs, err := v.ValidateForeignKeys()
	if err != nil {
		return nil, fmt.Errorf("failed to validate foreign keys: %w", err)
	}
	result.OrphanedReferences = orphanedRefs
	if len(orphanedRefs) > 0 {
		result.IsValid = false
	}

	return result, nil
}

// FormatValidationErrors formats validation errors for display
func (r *ValidationResult) FormatErrors() string {
	if r.IsValid {
		return "All validations passed"
	}

	var parts []string

	if len(r.MissingISINs) > 0 {
		parts = append(parts, fmt.Sprintf("Missing ISINs (%d): %s", len(r.MissingISINs), strings.Join(r.MissingISINs, ", ")))
	}

	if len(r.DuplicateISINs) > 0 {
		parts = append(parts, fmt.Sprintf("Duplicate ISINs (%d): %s", len(r.DuplicateISINs), strings.Join(r.DuplicateISINs, ", ")))
	}

	if len(r.OrphanedReferences) > 0 {
		parts = append(parts, fmt.Sprintf("Orphaned references (%d): %s", len(r.OrphanedReferences), strings.Join(r.OrphanedReferences, ", ")))
	}

	return strings.Join(parts, "\n")
}
