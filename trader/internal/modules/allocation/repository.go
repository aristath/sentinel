package allocation

import (
	"database/sql"
	"fmt"
	"time"

	"github.com/rs/zerolog"
)

// Repository handles allocation target database operations
// Faithful translation from Python: app/modules/allocation/database/allocation_repository.py
// Database: config.db (allocation_targets table)
type Repository struct {
	db  *sql.DB // config.db
	log zerolog.Logger
}

// NewRepository creates a new allocation repository
// db parameter should be config.db connection
func NewRepository(db *sql.DB, log zerolog.Logger) *Repository {
	return &Repository{
		db:  db,
		log: log.With().Str("repo", "allocation").Logger(),
	}
}

// GetAll returns all allocation targets as map with key 'type:name'
// Faithful translation of Python: async def get_all(self) -> Dict[str, float]
func (r *Repository) GetAll() (map[string]float64, error) {
	query := "SELECT type, name, target_pct FROM allocation_targets"

	rows, err := r.db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query allocation targets: %w", err)
	}
	defer rows.Close()

	result := make(map[string]float64)
	for rows.Next() {
		var targetType, name string
		var targetPct float64

		if err := rows.Scan(&targetType, &name, &targetPct); err != nil {
			return nil, fmt.Errorf("failed to scan allocation target: %w", err)
		}

		key := fmt.Sprintf("%s:%s", targetType, name)
		result[key] = targetPct
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating allocation targets: %w", err)
	}

	return result, nil
}

// GetByType returns allocation targets filtered by type
// Faithful translation of Python: async def get_by_type(self, target_type: str) -> List[AllocationTarget]
func (r *Repository) GetByType(targetType string) ([]AllocationTarget, error) {
	query := "SELECT id, type, name, target_pct, created_at, updated_at FROM allocation_targets WHERE type = ?"

	rows, err := r.db.Query(query, targetType)
	if err != nil {
		return nil, fmt.Errorf("failed to query allocation targets by type: %w", err)
	}
	defer rows.Close()

	var targets []AllocationTarget
	for rows.Next() {
		var target AllocationTarget
		var createdAt, updatedAt string

		if err := rows.Scan(
			&target.ID,
			&target.Type,
			&target.Name,
			&target.TargetPct,
			&createdAt,
			&updatedAt,
		); err != nil {
			return nil, fmt.Errorf("failed to scan allocation target: %w", err)
		}

		// Parse timestamps
		target.CreatedAt, _ = time.Parse(time.RFC3339, createdAt)
		target.UpdatedAt, _ = time.Parse(time.RFC3339, updatedAt)

		targets = append(targets, target)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating allocation targets: %w", err)
	}

	return targets, nil
}

// GetCountryGroupTargets returns country group allocation targets
// Faithful translation of Python: async def get_country_group_targets(self) -> Dict[str, float]
func (r *Repository) GetCountryGroupTargets() (map[string]float64, error) {
	targets, err := r.GetByType("country_group")
	if err != nil {
		return nil, err
	}

	rawWeights := make(map[string]float64)
	for _, t := range targets {
		rawWeights[t.Name] = t.TargetPct
	}

	// Normalize weights to sum to 1.0 (100%)
	totalWeight := 0.0
	for _, weight := range rawWeights {
		totalWeight += weight
	}

	if totalWeight > 0 {
		result := make(map[string]float64)
		for name, weight := range rawWeights {
			result[name] = weight / totalWeight
		}
		return result, nil
	}

	return rawWeights, nil
}

// GetIndustryGroupTargets returns industry group allocation targets
// Faithful translation of Python: async def get_industry_group_targets(self) -> Dict[str, float]
func (r *Repository) GetIndustryGroupTargets() (map[string]float64, error) {
	targets, err := r.GetByType("industry_group")
	if err != nil {
		return nil, err
	}

	rawWeights := make(map[string]float64)
	for _, t := range targets {
		rawWeights[t.Name] = t.TargetPct
	}

	// Normalize weights to sum to 1.0 (100%)
	totalWeight := 0.0
	for _, weight := range rawWeights {
		totalWeight += weight
	}

	if totalWeight > 0 {
		result := make(map[string]float64)
		for name, weight := range rawWeights {
			result[name] = weight / totalWeight
		}
		return result, nil
	}

	return rawWeights, nil
}

// Upsert inserts or updates an allocation target
// Faithful translation of Python: async def upsert(self, target: AllocationTarget) -> None
func (r *Repository) Upsert(target AllocationTarget) error {
	now := time.Now().Format(time.RFC3339)

	query := `
		INSERT INTO allocation_targets (type, name, target_pct, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?)
		ON CONFLICT(type, name) DO UPDATE SET
			target_pct = excluded.target_pct,
			updated_at = excluded.updated_at
	`

	_, err := r.db.Exec(query, target.Type, target.Name, target.TargetPct, now, now)
	if err != nil {
		return fmt.Errorf("failed to upsert allocation target: %w", err)
	}

	r.log.Debug().
		Str("type", target.Type).
		Str("name", target.Name).
		Float64("target_pct", target.TargetPct).
		Msg("Allocation target upserted")

	return nil
}

// Delete removes an allocation target
// Faithful translation of Python: async def delete(self, target_type: str, name: str) -> None
func (r *Repository) Delete(targetType, name string) error {
	query := "DELETE FROM allocation_targets WHERE type = ? AND name = ?"

	result, err := r.db.Exec(query, targetType, name)
	if err != nil {
		return fmt.Errorf("failed to delete allocation target: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	r.log.Debug().
		Str("type", targetType).
		Str("name", name).
		Int64("rows_affected", rowsAffected).
		Msg("Allocation target deleted")

	return nil
}
