// Package config provides repositories for configuration data stored in config.db.
// This includes market indices, which are distinct from settings (key-value pairs).
package config

import (
	"database/sql"
	"fmt"

	"github.com/rs/zerolog"
)

// MarketIndex represents a market index configuration entry
type MarketIndex struct {
	Symbol    string
	ISIN      string // Looked up from securities table
	Region    string
	IndexType string
	Enabled   bool
}

// MarketIndexRepository provides access to market indices configuration
type MarketIndexRepository struct {
	configDB *sql.DB
	log      zerolog.Logger
}

// NewMarketIndexRepository creates a new market index repository
func NewMarketIndexRepository(configDB *sql.DB, log zerolog.Logger) *MarketIndexRepository {
	return &MarketIndexRepository{
		configDB: configDB,
		log:      log.With().Str("repository", "market_index").Logger(),
	}
}

// GetEnabledPriceIndices returns all enabled PRICE-type market indices
// Returns only symbol and region (ISIN must be looked up separately via SecurityProvider)
func (r *MarketIndexRepository) GetEnabledPriceIndices() ([]MarketIndex, error) {
	if r.configDB == nil {
		return nil, fmt.Errorf("configDB is nil")
	}

	query := `
		SELECT symbol, region
		FROM market_indices
		WHERE enabled = 1 AND index_type = 'PRICE'
	`

	rows, err := r.configDB.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query market indices: %w", err)
	}
	defer rows.Close()

	var indices []MarketIndex
	for rows.Next() {
		var idx MarketIndex
		if err := rows.Scan(&idx.Symbol, &idx.Region); err != nil {
			return nil, fmt.Errorf("failed to scan market index: %w", err)
		}
		idx.IndexType = "PRICE"
		idx.Enabled = true
		indices = append(indices, idx)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating market indices: %w", err)
	}

	return indices, nil
}
