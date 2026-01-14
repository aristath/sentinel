package allocation

import (
	"database/sql"
	"fmt"
	"sort"
	"time"

	"github.com/aristath/sentinel/internal/utils"
	"github.com/rs/zerolog"
)

// Repository handles allocation target database operations
// Database: config.db (allocation_targets table), universe.db (securities table for lookups)
type Repository struct {
	db         *sql.DB // config.db
	universeDB *sql.DB // universe.db (optional, for GetAvailableGeographies/Industries)
	log        zerolog.Logger
}

// NewRepository creates a new allocation repository
// db parameter should be config.db connection
func NewRepository(db *sql.DB, log zerolog.Logger) *Repository {
	return &Repository{
		db:  db,
		log: log.With().Str("repo", "allocation").Logger(),
	}
}

// SetUniverseDB sets the universe database connection for querying securities
func (r *Repository) SetUniverseDB(universeDB *sql.DB) {
	r.universeDB = universeDB
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
		var createdAtUnix, updatedAtUnix sql.NullInt64

		if err := rows.Scan(
			&target.ID,
			&target.Type,
			&target.Name,
			&target.TargetPct,
			&createdAtUnix,
			&updatedAtUnix,
		); err != nil {
			return nil, fmt.Errorf("failed to scan allocation target: %w", err)
		}

		// Convert Unix timestamps to time.Time
		if createdAtUnix.Valid {
			target.CreatedAt = time.Unix(createdAtUnix.Int64, 0).UTC()
		}
		if updatedAtUnix.Valid {
			target.UpdatedAt = time.Unix(updatedAtUnix.Int64, 0).UTC()
		}

		targets = append(targets, target)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating allocation targets: %w", err)
	}

	return targets, nil
}

// GetGeographyTargets returns geography allocation targets as raw weights.
// The returned weights are NOT normalized - call NormalizeWeights() when needed for calculations.
func (r *Repository) GetGeographyTargets() (map[string]float64, error) {
	targets, err := r.GetByType("geography")
	if err != nil {
		return nil, err
	}

	result := make(map[string]float64)
	for _, t := range targets {
		result[t.Name] = t.TargetPct
	}

	return result, nil
}

// GetIndustryTargets returns industry allocation targets as raw weights.
// The returned weights are NOT normalized - call NormalizeWeights() when needed for calculations.
func (r *Repository) GetIndustryTargets() (map[string]float64, error) {
	targets, err := r.GetByType("industry")
	if err != nil {
		return nil, err
	}

	result := make(map[string]float64)
	for _, t := range targets {
		result[t.Name] = t.TargetPct
	}

	return result, nil
}

// Upsert inserts or updates an allocation target
// Faithful translation of Python: async def upsert(self, target: AllocationTarget) -> None
func (r *Repository) Upsert(target AllocationTarget) error {
	now := time.Now().Unix()

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

// GetAvailableGeographies returns distinct geographies from active securities.
// Parses comma-separated geography values and returns unique, sorted individual geographies.
func (r *Repository) GetAvailableGeographies() ([]string, error) {
	if r.universeDB == nil {
		return nil, fmt.Errorf("universe database not configured")
	}

	query := "SELECT geography FROM securities WHERE active = 1 AND geography IS NOT NULL AND geography != ''"
	rows, err := r.universeDB.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query geographies: %w", err)
	}
	defer rows.Close()

	seen := make(map[string]bool)
	var result []string
	for rows.Next() {
		var geoRaw string
		if err := rows.Scan(&geoRaw); err != nil {
			return nil, fmt.Errorf("failed to scan geography: %w", err)
		}
		// Parse comma-separated values and deduplicate
		for _, geo := range utils.ParseCSV(geoRaw) {
			if !seen[geo] {
				seen[geo] = true
				result = append(result, geo)
			}
		}
	}

	if err := rows.Err(); err != nil {
		return nil, err
	}

	sort.Strings(result)
	return result, nil
}

// GetAvailableIndustries returns distinct industries from active securities.
// Parses comma-separated industry values and returns unique, sorted individual industries.
func (r *Repository) GetAvailableIndustries() ([]string, error) {
	if r.universeDB == nil {
		return nil, fmt.Errorf("universe database not configured")
	}

	query := "SELECT industry FROM securities WHERE active = 1 AND industry IS NOT NULL AND industry != ''"
	rows, err := r.universeDB.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query industries: %w", err)
	}
	defer rows.Close()

	seen := make(map[string]bool)
	var result []string
	for rows.Next() {
		var industryRaw string
		if err := rows.Scan(&industryRaw); err != nil {
			return nil, fmt.Errorf("failed to scan industry: %w", err)
		}
		// Parse comma-separated values and deduplicate
		for _, industry := range utils.ParseCSV(industryRaw) {
			if !seen[industry] {
				seen[industry] = true
				result = append(result, industry)
			}
		}
	}

	if err := rows.Err(); err != nil {
		return nil, err
	}

	sort.Strings(result)
	return result, nil
}

// SetGeographyTargets sets multiple geography allocation targets at once
func (r *Repository) SetGeographyTargets(targets map[string]float64) error {
	for name, weight := range targets {
		target := AllocationTarget{
			Type:      "geography",
			Name:      name,
			TargetPct: weight,
		}
		if err := r.Upsert(target); err != nil {
			return fmt.Errorf("failed to set geography target %s: %w", name, err)
		}
	}
	return nil
}

// SetIndustryTargets sets multiple industry allocation targets at once
func (r *Repository) SetIndustryTargets(targets map[string]float64) error {
	for name, weight := range targets {
		target := AllocationTarget{
			Type:      "industry",
			Name:      name,
			TargetPct: weight,
		}
		if err := r.Upsert(target); err != nil {
			return fmt.Errorf("failed to set industry target %s: %w", name, err)
		}
	}
	return nil
}
