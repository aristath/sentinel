// Package allocation provides repository implementations for managing allocation targets.
// This file implements the Repository, which handles allocation targets stored in config.db.
// Allocation targets define target percentages for geography and industry diversification.
package allocation

import (
	"database/sql"
	"fmt"
	"sort"
	"time"

	"github.com/aristath/sentinel/internal/utils"
	"github.com/rs/zerolog"
)

// SecurityInfo represents security information needed for allocation calculations.
// This is a simplified view of security data used when determining available
// geographies and industries from the investment universe.
type SecurityInfo struct {
	ISIN      string // Primary identifier
	Symbol    string // Trading symbol
	Name      string // Company name
	Geography string // Country/region (may be comma-separated)
	Industry  string // Industry sector (may be comma-separated)
}

// SecurityProvider defines the contract for getting security information.
// This interface is used to avoid circular dependencies with the universe module.
// It provides access to active tradable securities for determining available
// geographies and industries.
type SecurityProvider interface {
	GetAllActiveTradable() ([]SecurityInfo, error) // Get all tradable securities
}

// Repository handles allocation target database operations.
// Allocation targets are stored in config.db and define target percentages for
// geography and industry diversification. The repository can optionally use a
// SecurityProvider to determine available geographies and industries from the
// investment universe.
//
// Database: config.db (allocation_targets table), universe.db (securities table for lookups)
type Repository struct {
	db               *sql.DB          // config.db - allocation_targets table
	universeDB       *sql.DB          // universe.db (optional, for GetAvailableGeographies/Industries)
	securityProvider SecurityProvider // Optional provider for security lookups
	log              zerolog.Logger   // Structured logger
}

// NewRepository creates a new allocation repository.
// The securityProvider is optional but recommended for full functionality
// (determining available geographies and industries).
//
// Parameters:
//   - db: Database connection to config.db
//   - securityProvider: Provider for security lookups (can be nil, but limits functionality)
//   - log: Structured logger
//
// Returns:
//   - *Repository: Initialized repository instance
func NewRepository(db *sql.DB, securityProvider SecurityProvider, log zerolog.Logger) *Repository {
	return &Repository{
		db:               db,
		securityProvider: securityProvider,
		log:              log.With().Str("repo", "allocation").Logger(),
	}
}

// SetUniverseDB sets the universe database connection for querying securities.
// This is used by methods that need direct access to the securities table
// (e.g., GetAvailableGeographies, GetAvailableIndustries).
//
// Parameters:
//   - universeDB: Database connection to universe.db
func (r *Repository) SetUniverseDB(universeDB *sql.DB) {
	r.universeDB = universeDB
}

// GetAll returns all allocation targets as a map with key 'type:name'.
// The key format is "type:name" (e.g., "geography:US", "industry:Technology").
// This is useful for quick lookups of target percentages.
//
// Returns:
//   - map[string]float64: Map of "type:name" -> target percentage
//   - error: Error if query fails
//
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

// GetByType returns allocation targets filtered by type.
// Types include "geography" and "industry".
//
// Parameters:
//   - targetType: Target type ("geography" or "industry")
//
// Returns:
//   - []AllocationTarget: List of allocation targets of the specified type
//   - error: Error if query fails
//
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
// This is a convenience method that filters GetByType("geography") and converts to a map.
//
// Returns:
//   - map[string]float64: Map of geography name -> target percentage (raw, not normalized)
//   - error: Error if query fails
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
// This is a convenience method that filters GetByType("industry") and converts to a map.
//
// Returns:
//   - map[string]float64: Map of industry name -> target percentage (raw, not normalized)
//   - error: Error if query fails
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

// Upsert inserts or updates an allocation target.
// Uses INSERT OR REPLACE to handle both insert and update in a single operation.
// The (type, name) combination is unique - updating an existing target replaces its target_pct.
//
// Parameters:
//   - target: AllocationTarget object to upsert
//
// Returns:
//   - error: Error if database operation fails
//
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

// Delete removes an allocation target.
// This operation is idempotent - it does not error if the target doesn't exist.
//
// Parameters:
//   - targetType: Target type ("geography" or "industry")
//   - name: Target name (e.g., "US", "Technology")
//
// Returns:
//   - error: Error if database operation fails
//
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

// GetAvailableGeographies returns distinct geographies from active tradable securities (excludes indices).
// This method queries the security universe to determine which geographies are available
// for allocation targeting. It parses comma-separated geography values and returns unique,
// sorted individual geographies.
//
// Requires securityProvider to be configured.
//
// Returns:
//   - []string: Sorted list of available geography names
//   - error: Error if securityProvider is missing or query fails
func (r *Repository) GetAvailableGeographies() ([]string, error) {
	// SecurityProvider is required - no fallback
	if r.securityProvider == nil {
		return nil, fmt.Errorf("security provider not available")
	}

	securities, err := r.securityProvider.GetAllActiveTradable()
	if err != nil {
		return nil, fmt.Errorf("failed to get securities: %w", err)
	}

	seen := make(map[string]bool)
	for _, sec := range securities {
		if sec.Geography != "" {
			geos := utils.ParseCSV(sec.Geography)
			for _, geo := range geos {
				seen[geo] = true
			}
		}
	}

	// Convert to sorted slice
	var result []string
	for geo := range seen {
		result = append(result, geo)
	}
	sort.Strings(result)
	return result, nil
}

// GetAvailableIndustries returns distinct industries from active tradable securities (excludes indices).
// This method queries the security universe to determine which industries are available
// for allocation targeting. It parses comma-separated industry values and returns unique,
// sorted individual industries.
//
// Requires securityProvider to be configured.
//
// Returns:
//   - []string: Sorted list of available industry names
//   - error: Error if securityProvider is missing or query fails
func (r *Repository) GetAvailableIndustries() ([]string, error) {
	// SecurityProvider is required - no fallback
	if r.securityProvider == nil {
		return nil, fmt.Errorf("security provider not available")
	}

	securities, err := r.securityProvider.GetAllActiveTradable()
	if err != nil {
		return nil, fmt.Errorf("failed to get securities: %w", err)
	}

	seen := make(map[string]bool)
	for _, sec := range securities {
		if sec.Industry != "" {
			inds := utils.ParseCSV(sec.Industry)
			for _, ind := range inds {
				seen[ind] = true
			}
		}
	}

	// Convert to sorted slice
	var result []string
	for industry := range seen {
		result = append(result, industry)
	}
	sort.Strings(result)
	return result, nil
}

// SetGeographyTargets sets multiple geography allocation targets at once.
// This is a convenience method for bulk updates. Each target is upserted individually.
//
// Parameters:
//   - targets: Map of geography name -> target percentage
//
// Returns:
//   - error: Error if any target upsert fails (partial update may have occurred)
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

// SetIndustryTargets sets multiple industry allocation targets at once.
// This is a convenience method for bulk updates. Each target is upserted individually.
//
// Parameters:
//   - targets: Map of industry name -> target percentage
//
// Returns:
//   - error: Error if any target upsert fails (partial update may have occurred)
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
