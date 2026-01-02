package allocation

import (
	"database/sql"
	"fmt"
	"time"

	"github.com/rs/zerolog"
)

// GroupingRepository handles country and industry grouping operations
// Faithful translation from Python: app/repositories/grouping.py
type GroupingRepository struct {
	db  *sql.DB
	log zerolog.Logger
}

// NewGroupingRepository creates a new grouping repository
func NewGroupingRepository(db *sql.DB, log zerolog.Logger) *GroupingRepository {
	return &GroupingRepository{
		db:  db,
		log: log.With().Str("repo", "grouping").Logger(),
	}
}

// GetCountryGroups returns all country groups as map: group_name -> [country_names]
// Faithful translation of Python: async def get_country_groups(self) -> Dict[str, List[str]]
func (r *GroupingRepository) GetCountryGroups() (map[string][]string, error) {
	query := "SELECT group_name, country_name FROM country_groups ORDER BY group_name, country_name"

	rows, err := r.db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query country groups: %w", err)
	}
	defer rows.Close()

	groups := make(map[string][]string)
	for rows.Next() {
		var groupName, countryName string
		if err := rows.Scan(&groupName, &countryName); err != nil {
			return nil, fmt.Errorf("failed to scan country group: %w", err)
		}

		// Filter out __EMPTY__ marker (used to indicate group exists but is empty)
		if countryName != "__EMPTY__" {
			groups[groupName] = append(groups[groupName], countryName)
		} else {
			// Ensure group exists in map even if empty
			if _, exists := groups[groupName]; !exists {
				groups[groupName] = []string{}
			}
		}
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating country groups: %w", err)
	}

	return groups, nil
}

// GetIndustryGroups returns all industry groups as map: group_name -> [industry_names]
// Faithful translation of Python: async def get_industry_groups(self) -> Dict[str, List[str]]
func (r *GroupingRepository) GetIndustryGroups() (map[string][]string, error) {
	query := "SELECT group_name, industry_name FROM industry_groups ORDER BY group_name, industry_name"

	rows, err := r.db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query industry groups: %w", err)
	}
	defer rows.Close()

	groups := make(map[string][]string)
	for rows.Next() {
		var groupName, industryName string
		if err := rows.Scan(&groupName, &industryName); err != nil {
			return nil, fmt.Errorf("failed to scan industry group: %w", err)
		}

		// Filter out __EMPTY__ marker (special marker for empty groups)
		if industryName != "__EMPTY__" {
			groups[groupName] = append(groups[groupName], industryName)
		} else {
			// Ensure group exists in map even if empty
			if _, exists := groups[groupName]; !exists {
				groups[groupName] = []string{}
			}
		}
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating industry groups: %w", err)
	}

	return groups, nil
}

// SetCountryGroup sets countries for a country group (replaces existing)
// Faithful translation of Python: async def set_country_group(self, group_name: str, country_names: List[str])
func (r *GroupingRepository) SetCountryGroup(groupName string, countryNames []string) error {
	now := time.Now().Format(time.RFC3339)

	// Start transaction
	tx, err := r.db.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	// Delete existing mappings for this group
	_, err = tx.Exec("DELETE FROM country_groups WHERE group_name = ?", groupName)
	if err != nil {
		return fmt.Errorf("failed to delete existing country groups: %w", err)
	}

	// Insert new mappings
	// If empty list, insert a special marker to indicate group exists but is empty
	// This allows us to distinguish "deleted hardcoded group" from "never existed"
	if len(countryNames) == 0 {
		_, err = tx.Exec(
			"INSERT INTO country_groups (group_name, country_name, created_at, updated_at) VALUES (?, ?, ?, ?)",
			groupName, "__EMPTY__", now, now,
		)
		if err != nil {
			return fmt.Errorf("failed to insert empty country group marker: %w", err)
		}
	} else {
		for _, countryName := range countryNames {
			_, err = tx.Exec(
				"INSERT INTO country_groups (group_name, country_name, created_at, updated_at) VALUES (?, ?, ?, ?)",
				groupName, countryName, now, now,
			)
			if err != nil {
				return fmt.Errorf("failed to insert country group: %w", err)
			}
		}
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	r.log.Debug().
		Str("group_name", groupName).
		Int("country_count", len(countryNames)).
		Msg("Country group updated")

	return nil
}

// SetIndustryGroup sets industries for an industry group (replaces existing)
// Faithful translation of Python: async def set_industry_group(self, group_name: str, industry_names: List[str])
func (r *GroupingRepository) SetIndustryGroup(groupName string, industryNames []string) error {
	now := time.Now().Format(time.RFC3339)

	// Start transaction
	tx, err := r.db.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	// Delete existing mappings for this group
	_, err = tx.Exec("DELETE FROM industry_groups WHERE group_name = ?", groupName)
	if err != nil {
		return fmt.Errorf("failed to delete existing industry groups: %w", err)
	}

	// Insert new mappings
	// If empty list, insert a special marker to indicate group exists but is empty
	if len(industryNames) == 0 {
		_, err = tx.Exec(
			"INSERT INTO industry_groups (group_name, industry_name, created_at, updated_at) VALUES (?, ?, ?, ?)",
			groupName, "__EMPTY__", now, now,
		)
		if err != nil {
			return fmt.Errorf("failed to insert empty industry group marker: %w", err)
		}
	} else {
		for _, industryName := range industryNames {
			_, err = tx.Exec(
				"INSERT INTO industry_groups (group_name, industry_name, created_at, updated_at) VALUES (?, ?, ?, ?)",
				groupName, industryName, now, now,
			)
			if err != nil {
				return fmt.Errorf("failed to insert industry group: %w", err)
			}
		}
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	r.log.Debug().
		Str("group_name", groupName).
		Int("industry_count", len(industryNames)).
		Msg("Industry group updated")

	return nil
}

// DeleteCountryGroup deletes a country group
// Faithful translation of Python: async def delete_country_group(self, group_name: str)
func (r *GroupingRepository) DeleteCountryGroup(groupName string) error {
	result, err := r.db.Exec("DELETE FROM country_groups WHERE group_name = ?", groupName)
	if err != nil {
		return fmt.Errorf("failed to delete country group: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	r.log.Debug().
		Str("group_name", groupName).
		Int64("rows_affected", rowsAffected).
		Msg("Country group deleted")

	return nil
}

// DeleteIndustryGroup deletes an industry group
// Faithful translation of Python: async def delete_industry_group(self, group_name: str)
func (r *GroupingRepository) DeleteIndustryGroup(groupName string) error {
	result, err := r.db.Exec("DELETE FROM industry_groups WHERE group_name = ?", groupName)
	if err != nil {
		return fmt.Errorf("failed to delete industry group: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	r.log.Debug().
		Str("group_name", groupName).
		Int64("rows_affected", rowsAffected).
		Msg("Industry group deleted")

	return nil
}

// GetAvailableCountries returns list of all unique countries from securities table
// Faithful translation of Python: async def get_available_countries(self) -> List[str]
func (r *GroupingRepository) GetAvailableCountries() ([]string, error) {
	query := "SELECT DISTINCT country FROM securities WHERE country IS NOT NULL AND country != '' ORDER BY country"

	rows, err := r.db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query available countries: %w", err)
	}
	defer rows.Close()

	var countries []string
	for rows.Next() {
		var country string
		if err := rows.Scan(&country); err != nil {
			return nil, fmt.Errorf("failed to scan country: %w", err)
		}
		countries = append(countries, country)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating countries: %w", err)
	}

	return countries, nil
}

// GetAvailableIndustries returns list of all unique industries from securities table
// Faithful translation of Python: async def get_available_industries(self) -> List[str]
func (r *GroupingRepository) GetAvailableIndustries() ([]string, error) {
	query := "SELECT DISTINCT industry FROM securities WHERE industry IS NOT NULL AND industry != '' ORDER BY industry"

	rows, err := r.db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query available industries: %w", err)
	}
	defer rows.Close()

	var industries []string
	for rows.Next() {
		var industry string
		if err := rows.Scan(&industry); err != nil {
			return nil, fmt.Errorf("failed to scan industry: %w", err)
		}
		industries = append(industries, industry)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating industries: %w", err)
	}

	return industries, nil
}
