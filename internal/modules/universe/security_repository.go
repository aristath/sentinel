package universe

import (
	"database/sql"
	"fmt"
	"strings"
	"time"

	"github.com/rs/zerolog"
)

// SecurityRepository handles security database operations
// Faithful translation from Python: app/modules/universe/database/security_repository.py
type SecurityRepository struct {
	universeDB   *sql.DB // universe.db - securities table
	tagRepo      *TagRepository
	overrideRepo OverrideRepositoryInterface
	log          zerolog.Logger
}

// securitiesColumns is the list of columns for the securities table (JSON storage schema)
// After migration 038: Only 4 columns - isin, symbol, data (JSON blob), last_synced
// All security data is stored as JSON in the 'data' column
// Note: allow_buy, allow_sell, min_lot, priority_multiplier are stored in security_overrides table
const securitiesColumns = `isin, symbol, data, last_synced`

// NewSecurityRepository creates a new security repository (backward compatible, no override support)
func NewSecurityRepository(universeDB *sql.DB, log zerolog.Logger) *SecurityRepository {
	return &SecurityRepository{
		universeDB:   universeDB,
		tagRepo:      NewTagRepository(universeDB, log),
		overrideRepo: nil,
		log:          log.With().Str("repo", "security").Logger(),
	}
}

// NewSecurityRepositoryWithOverrides creates a new security repository with override support
func NewSecurityRepositoryWithOverrides(universeDB *sql.DB, overrideRepo OverrideRepositoryInterface, log zerolog.Logger) *SecurityRepository {
	return &SecurityRepository{
		universeDB:   universeDB,
		tagRepo:      NewTagRepository(universeDB, log),
		overrideRepo: overrideRepo,
		log:          log.With().Str("repo", "security").Logger(),
	}
}

// GetBySymbol returns a security by symbol
// Faithful translation of Python: async def get_by_symbol(self, symbol: str) -> Optional[Security]
func (r *SecurityRepository) GetBySymbol(symbol string) (*Security, error) {
	query := "SELECT " + securitiesColumns + " FROM securities WHERE symbol = ?"

	rows, err := r.universeDB.Query(query, strings.ToUpper(strings.TrimSpace(symbol)))
	if err != nil {
		return nil, fmt.Errorf("failed to query security by symbol: %w", err)
	}
	defer rows.Close()

	if !rows.Next() {
		return nil, nil // Security not found
	}

	security, err := r.scanSecurity(rows)
	if err != nil {
		return nil, fmt.Errorf("failed to scan security: %w", err)
	}

	// Apply overrides if override repository is available
	if r.overrideRepo != nil && security.ISIN != "" {
		overrides, err := r.overrideRepo.GetOverrides(security.ISIN)
		if err != nil {
			r.log.Warn().Str("isin", security.ISIN).Err(err).Msg("Failed to fetch overrides")
		} else if len(overrides) > 0 {
			ApplyOverrides(&security, overrides)
		}
	}

	return &security, nil
}

// GetByISIN returns a security by ISIN
// Faithful translation of Python: async def get_by_isin(self, isin: str) -> Optional[Security]
func (r *SecurityRepository) GetByISIN(isin string) (*Security, error) {
	query := "SELECT " + securitiesColumns + " FROM securities WHERE isin = ?"

	normalizedISIN := strings.ToUpper(strings.TrimSpace(isin))
	rows, err := r.universeDB.Query(query, normalizedISIN)
	if err != nil {
		return nil, fmt.Errorf("failed to query security by ISIN: %w", err)
	}
	defer rows.Close()

	if !rows.Next() {
		return nil, nil // Security not found
	}

	security, err := r.scanSecurity(rows)
	if err != nil {
		return nil, fmt.Errorf("failed to scan security: %w", err)
	}

	// Apply overrides if override repository is available
	if r.overrideRepo != nil {
		overrides, err := r.overrideRepo.GetOverrides(normalizedISIN)
		if err != nil {
			r.log.Warn().Str("isin", normalizedISIN).Err(err).Msg("Failed to fetch overrides")
		} else if len(overrides) > 0 {
			ApplyOverrides(&security, overrides)
		}
	}

	return &security, nil
}

// GetByIdentifier returns a security by symbol or ISIN (smart lookup)
// Faithful translation of Python: async def get_by_identifier(self, identifier: str) -> Optional[Security]
func (r *SecurityRepository) GetByIdentifier(identifier string) (*Security, error) {
	identifier = strings.ToUpper(strings.TrimSpace(identifier))

	// Check if it looks like an ISIN (12 chars, starts with 2 letters)
	if len(identifier) == 12 && len(identifier) >= 2 {
		firstTwo := identifier[:2]
		if (firstTwo[0] >= 'A' && firstTwo[0] <= 'Z') && (firstTwo[1] >= 'A' && firstTwo[1] <= 'Z') {
			// Try ISIN lookup first
			sec, err := r.GetByISIN(identifier)
			if err != nil {
				return nil, err
			}
			if sec != nil {
				return sec, nil
			}
		}
	}

	// Fall back to symbol lookup
	return r.GetBySymbol(identifier)
}

// GetAllActive returns all active tradable securities (excludes indices)
// Faithful translation of Python: async def get_all_active(self) -> List[Security]
// GetAllActive returns all active securities (excludes indices)
// After migration 038: All securities in table are active (no soft delete)
func (r *SecurityRepository) GetAllActive() ([]Security, error) {
	// Filter out indices using JSON extraction
	query := `SELECT ` + securitiesColumns + ` FROM securities
		WHERE json_extract(data, '$.product_type') IS NULL
		OR json_extract(data, '$.product_type') != ?`

	rows, err := r.universeDB.Query(query, string(ProductTypeIndex))
	if err != nil {
		return nil, fmt.Errorf("failed to query active securities: %w", err)
	}
	defer rows.Close()

	var securities []Security
	for rows.Next() {
		security, err := r.scanSecurity(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan security: %w", err)
		}
		securities = append(securities, security)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating securities: %w", err)
	}

	// Apply overrides if override repository is available (batch mode for efficiency)
	if r.overrideRepo != nil && len(securities) > 0 {
		allOverrides, err := r.overrideRepo.GetAllOverrides()
		if err != nil {
			r.log.Warn().Err(err).Msg("Failed to fetch all overrides")
		} else {
			for i := range securities {
				if overrides, exists := allOverrides[securities[i].ISIN]; exists && len(overrides) > 0 {
					ApplyOverrides(&securities[i], overrides)
				}
			}
		}
	}

	return securities, nil
}

// GetDistinctExchanges returns a list of distinct exchange names from active tradable securities (excludes indices)
func (r *SecurityRepository) GetDistinctExchanges() ([]string, error) {
	query := `SELECT DISTINCT json_extract(data, '$.fullExchangeName') as fullExchangeName
		FROM securities
		WHERE json_extract(data, '$.fullExchangeName') IS NOT NULL
		AND json_extract(data, '$.fullExchangeName') != ''
		AND (json_extract(data, '$.product_type') IS NULL OR json_extract(data, '$.product_type') != ?)
		ORDER BY fullExchangeName`

	rows, err := r.universeDB.Query(query, string(ProductTypeIndex))
	if err != nil {
		return nil, fmt.Errorf("failed to query distinct exchanges: %w", err)
	}
	defer rows.Close()

	var exchanges []string
	for rows.Next() {
		var exchange string
		if err := rows.Scan(&exchange); err != nil {
			return nil, fmt.Errorf("failed to scan exchange: %w", err)
		}
		if exchange != "" {
			exchanges = append(exchanges, exchange)
		}
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating exchanges: %w", err)
	}

	return exchanges, nil
}

// GetAllActiveTradable returns all active tradable securities (excludes indices and cash)
// Used for scoring and trading operations
// After migration 038: Same as GetAllActive() (all securities in table are active)
func (r *SecurityRepository) GetAllActiveTradable() ([]Security, error) {
	// Filter out indices using JSON extraction
	query := `SELECT ` + securitiesColumns + ` FROM securities
		WHERE json_extract(data, '$.product_type') IS NULL
		OR json_extract(data, '$.product_type') != ?`

	rows, err := r.universeDB.Query(query, string(ProductTypeIndex))
	if err != nil {
		return nil, fmt.Errorf("failed to query tradable securities: %w", err)
	}
	defer rows.Close()

	var securities []Security
	for rows.Next() {
		security, err := r.scanSecurity(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan security: %w", err)
		}
		securities = append(securities, security)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating securities: %w", err)
	}

	// Apply overrides if override repository is available (batch mode for efficiency)
	if r.overrideRepo != nil && len(securities) > 0 {
		allOverrides, err := r.overrideRepo.GetAllOverrides()
		if err != nil {
			r.log.Warn().Err(err).Msg("Failed to fetch all overrides")
		} else {
			for i := range securities {
				if overrides, exists := allOverrides[securities[i].ISIN]; exists && len(overrides) > 0 {
					ApplyOverrides(&securities[i], overrides)
				}
			}
		}
	}

	return securities, nil
}

// GetAll returns all securities (active and inactive)
// Faithful translation of Python: async def get_all(self) -> List[Security]
func (r *SecurityRepository) GetAll() ([]Security, error) {
	query := "SELECT " + securitiesColumns + " FROM securities"

	rows, err := r.universeDB.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query all securities: %w", err)
	}
	defer rows.Close()

	var securities []Security
	for rows.Next() {
		security, err := r.scanSecurity(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan security: %w", err)
		}
		securities = append(securities, security)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating securities: %w", err)
	}

	// Apply overrides if override repository is available (batch mode for efficiency)
	if r.overrideRepo != nil && len(securities) > 0 {
		allOverrides, err := r.overrideRepo.GetAllOverrides()
		if err != nil {
			r.log.Warn().Err(err).Msg("Failed to fetch all overrides")
		} else {
			for i := range securities {
				if overrides, exists := allOverrides[securities[i].ISIN]; exists && len(overrides) > 0 {
					ApplyOverrides(&securities[i], overrides)
				}
			}
		}
	}

	return securities, nil
}

// GetByMarketCode returns all active tradable securities with the specified market code (excludes indices)
// Used for per-region regime detection and grouping securities by market
func (r *SecurityRepository) GetByMarketCode(marketCode string) ([]Security, error) {
	query := `SELECT ` + securitiesColumns + ` FROM securities
		WHERE json_extract(data, '$.market_code') = ?
		AND (json_extract(data, '$.product_type') IS NULL OR json_extract(data, '$.product_type') != ?)`

	rows, err := r.universeDB.Query(query, marketCode, string(ProductTypeIndex))
	if err != nil {
		return nil, fmt.Errorf("failed to query securities by market code: %w", err)
	}
	defer rows.Close()

	var securities []Security
	for rows.Next() {
		security, err := r.scanSecurity(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan security: %w", err)
		}
		securities = append(securities, security)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating securities: %w", err)
	}

	// Apply overrides if override repository is available (batch mode for efficiency)
	if r.overrideRepo != nil && len(securities) > 0 {
		allOverrides, err := r.overrideRepo.GetAllOverrides()
		if err != nil {
			r.log.Warn().Err(err).Msg("Failed to fetch all overrides")
		} else {
			for i := range securities {
				if overrides, exists := allOverrides[securities[i].ISIN]; exists && len(overrides) > 0 {
					ApplyOverrides(&securities[i], overrides)
				}
			}
		}
	}

	return securities, nil
}

// Create creates a new security in the repository
// Note: allow_buy, allow_sell, min_lot, priority_multiplier should be set via security_overrides using the OverrideRepository
func (r *SecurityRepository) Create(security Security) error {
	// ISIN is required (PRIMARY KEY)
	if security.ISIN == "" {
		return fmt.Errorf("ISIN is required for security creation")
	}

	// Normalize symbol
	security.Symbol = strings.ToUpper(strings.TrimSpace(security.Symbol))
	security.ISIN = strings.ToUpper(strings.TrimSpace(security.ISIN))

	// Serialize security data to JSON
	jsonData, err := SecurityToJSON(&security)
	if err != nil {
		return fmt.Errorf("failed to serialize security to JSON: %w", err)
	}

	// Begin transaction
	tx, err := r.universeDB.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	// Insert into JSON storage schema: isin, symbol, data, last_synced
	query := `INSERT INTO securities (isin, symbol, data, last_synced) VALUES (?, ?, ?, ?)`

	var lastSynced interface{}
	if security.LastSynced != nil {
		lastSynced = *security.LastSynced
	}

	_, err = tx.Exec(query, security.ISIN, security.Symbol, jsonData, lastSynced)
	if err != nil {
		return fmt.Errorf("failed to insert security: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	r.log.Info().Str("isin", security.ISIN).Str("symbol", security.Symbol).Msg("Security created")
	return nil
}

// Update updates security fields by ISIN
// For JSON storage schema, this method:
// 1. Reads the current JSON data
// 2. Parses and updates the specified fields
// 3. Serializes back to JSON
// 4. Updates the database
// Note: allow_buy, allow_sell, min_lot, priority_multiplier should be set via security_overrides
func (r *SecurityRepository) Update(isin string, updates map[string]any) error {
	if len(updates) == 0 {
		return nil
	}

	isin = strings.ToUpper(strings.TrimSpace(isin))

	// Special case: if "data" field is provided as complete JSON string, just update it directly
	if dataStr, ok := updates["data"].(string); ok {
		return r.updateJSONDirectly(isin, dataStr, updates)
	}

	// Otherwise, read current data, modify fields, and write back
	// Begin transaction
	tx, err := r.universeDB.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	// Read current security data
	var symbol, jsonData string
	var lastSynced sql.NullInt64
	query := `SELECT symbol, data, last_synced FROM securities WHERE isin = ?`
	err = tx.QueryRow(query, isin).Scan(&symbol, &jsonData, &lastSynced)
	if err == sql.ErrNoRows {
		return fmt.Errorf("security not found: %s", isin)
	}
	if err != nil {
		return fmt.Errorf("failed to read security: %w", err)
	}

	// Parse current JSON
	data, err := ParseSecurityJSON(jsonData)
	if err != nil {
		return fmt.Errorf("failed to parse existing JSON: %w", err)
	}

	// Apply updates to JSON fields
	if val, ok := updates["name"]; ok {
		if strVal, ok := val.(string); ok {
			data.Name = strVal
		}
	}
	if val, ok := updates["product_type"]; ok {
		if strVal, ok := val.(string); ok {
			data.ProductType = strVal
		}
	}
	if val, ok := updates["industry"]; ok {
		if strVal, ok := val.(string); ok {
			data.Industry = strVal
		}
	}
	if val, ok := updates["geography"]; ok {
		if strVal, ok := val.(string); ok {
			data.Geography = strVal
		}
	}
	if val, ok := updates["fullExchangeName"]; ok {
		if strVal, ok := val.(string); ok {
			data.FullExchangeName = strVal
		}
	}
	if val, ok := updates["market_code"]; ok {
		if strVal, ok := val.(string); ok {
			data.MarketCode = strVal
		}
	}
	if val, ok := updates["currency"]; ok {
		if strVal, ok := val.(string); ok {
			data.Currency = strVal
		}
	}
	if val, ok := updates["min_lot"]; ok {
		if intVal, ok := val.(int); ok {
			data.MinLot = intVal
		}
	}
	if val, ok := updates["min_portfolio_target"]; ok {
		if floatVal, ok := val.(float64); ok {
			data.MinPortfolioTarget = floatVal
		}
	}
	if val, ok := updates["max_portfolio_target"]; ok {
		if floatVal, ok := val.(float64); ok {
			data.MaxPortfolioTarget = floatVal
		}
	}

	// Serialize back to JSON
	updatedJSON, err := SerializeSecurityJSON(data)
	if err != nil {
		return fmt.Errorf("failed to serialize updated JSON: %w", err)
	}

	// Build UPDATE statement
	var setClauses []string
	var values []interface{}

	// Always update data column
	setClauses = append(setClauses, "data = ?")
	values = append(values, updatedJSON)

	// Handle symbol update separately (it's its own column)
	if val, ok := updates["symbol"]; ok {
		if strVal, ok := val.(string); ok {
			setClauses = append(setClauses, "symbol = ?")
			values = append(values, strings.ToUpper(strings.TrimSpace(strVal)))
		}
	}

	// Handle last_synced separately (it's its own column)
	if val, ok := updates["last_synced"]; ok {
		setClauses = append(setClauses, "last_synced = ?")
		values = append(values, val)
	}

	// Add ISIN to WHERE clause
	values = append(values, isin)

	// Execute update
	updateQuery := fmt.Sprintf("UPDATE securities SET %s WHERE isin = ?", strings.Join(setClauses, ", "))
	result, err := tx.Exec(updateQuery, values...)
	if err != nil {
		return fmt.Errorf("failed to update security: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	r.log.Info().Str("isin", isin).Int64("rows_affected", rowsAffected).Msg("Security updated")
	return nil
}

// updateJSONDirectly updates the data column directly with provided JSON string
func (r *SecurityRepository) updateJSONDirectly(isin string, jsonData string, updates map[string]any) error {
	// Begin transaction
	tx, err := r.universeDB.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	// Build UPDATE statement
	var setClauses []string
	var values []interface{}

	// Update data column
	setClauses = append(setClauses, "data = ?")
	values = append(values, jsonData)

	// Handle last_synced if provided
	if val, ok := updates["last_synced"]; ok {
		setClauses = append(setClauses, "last_synced = ?")
		values = append(values, val)
	}

	// Add ISIN to WHERE clause
	values = append(values, isin)

	// Execute update
	query := fmt.Sprintf("UPDATE securities SET %s WHERE isin = ?", strings.Join(setClauses, ", "))
	result, err := tx.Exec(query, values...)
	if err != nil {
		return fmt.Errorf("failed to update security: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	r.log.Info().Str("isin", isin).Int64("rows_affected", rowsAffected).Msg("Security updated (direct JSON)")
	return nil
}

// Delete is deprecated after migration 038 - no soft delete with JSON storage
// Only HardDelete is supported (actual removal from database)
// This method is kept for interface compatibility but should not be used
func (r *SecurityRepository) Delete(isin string) error {
	r.log.Warn().Str("isin", isin).Msg("Delete() called but soft delete not supported with JSON storage - use HardDelete() instead")
	return fmt.Errorf("soft delete not supported after migration 038 - use HardDelete() to permanently remove security")
}

// HardDelete permanently removes a security and all related data from universe.db
// This includes: security_tags, broker_symbols, client_symbols, and the security itself
func (r *SecurityRepository) HardDelete(isin string) error {
	isin = strings.ToUpper(strings.TrimSpace(isin))

	// Begin transaction
	tx, err := r.universeDB.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	// Delete related data first (security_tags has CASCADE but be explicit)
	_, err = tx.Exec("DELETE FROM security_tags WHERE isin = ?", isin)
	if err != nil {
		return fmt.Errorf("failed to delete security_tags: %w", err)
	}

	// Note: security_overrides will be deleted automatically via CASCADE foreign key

	// Delete the security itself
	result, err := tx.Exec("DELETE FROM securities WHERE isin = ?", isin)
	if err != nil {
		return fmt.Errorf("failed to delete security: %w", err)
	}

	rows, _ := result.RowsAffected()
	if rows == 0 {
		return fmt.Errorf("security not found: %s", isin)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	r.log.Info().Str("isin", isin).Msg("Security hard deleted from universe.db")
	return nil
}

// GetWithScores returns all active tradable securities with their scores and positions (excludes indices)
// Faithful translation of Python: async def get_with_scores(self) -> List[dict]
// Note: This method accesses multiple databases (universe.db and portfolio.db) - architecture violation
func (r *SecurityRepository) GetWithScores(portfolioDB *sql.DB) ([]SecurityWithScore, error) {
	// Fetch securities from universe.db (exclude indices)
	query := `SELECT ` + securitiesColumns + ` FROM securities
		WHERE json_extract(data, '$.product_type') IS NULL
		OR json_extract(data, '$.product_type') != ?`
	securityRows, err := r.universeDB.Query(query, string(ProductTypeIndex))
	if err != nil {
		return nil, fmt.Errorf("failed to query securities: %w", err)
	}
	defer securityRows.Close()

	securitiesMap := make(map[string]SecurityWithScore)
	for securityRows.Next() {
		security, err := r.scanSecurity(securityRows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan security: %w", err)
		}

		// Convert to SecurityWithScore
		// Explicitly copy tags slice to avoid potential sharing issues
		var tagsCopy []string
		if len(security.Tags) > 0 {
			tagsCopy = make([]string, len(security.Tags))
			copy(tagsCopy, security.Tags)
		} else {
			tagsCopy = []string{}
		}
		sws := SecurityWithScore{
			Symbol:             security.Symbol,
			Name:               security.Name,
			ISIN:               security.ISIN,
			ProductType:        security.ProductType,
			Geography:          security.Geography,
			FullExchangeName:   security.FullExchangeName,
			MarketCode:         security.MarketCode,
			Industry:           security.Industry,
			PriorityMultiplier: security.PriorityMultiplier,
			MinLot:             security.MinLot,
			AllowBuy:           security.AllowBuy,
			AllowSell:          security.AllowSell,
			Currency:           security.Currency,
			LastSynced:         security.LastSynced,
			MinPortfolioTarget: security.MinPortfolioTarget,
			MaxPortfolioTarget: security.MaxPortfolioTarget,
			Tags:               tagsCopy,
		}
		// Use normalized ISIN as map key (primary identifier) for consistent matching
		normalizedISIN := strings.ToUpper(strings.TrimSpace(security.ISIN))
		if normalizedISIN != "" {
			securitiesMap[normalizedISIN] = sws
		} else {
			r.log.Warn().Str("symbol", security.Symbol).Msg("Security missing ISIN, skipping")
		}
	}

	if err := securityRows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating securities: %w", err)
	}

	// Apply overrides to securities (batch mode for efficiency)
	if r.overrideRepo != nil && len(securitiesMap) > 0 {
		allOverrides, err := r.overrideRepo.GetAllOverrides()
		if err != nil {
			r.log.Warn().Err(err).Msg("Failed to fetch all overrides")
		} else {
			for isin, sws := range securitiesMap {
				if overrides, exists := allOverrides[isin]; exists && len(overrides) > 0 {
					ApplyOverridesToSecurityWithScore(&sws, overrides)
					securitiesMap[isin] = sws
				}
			}
		}
	}

	// Fetch scores from portfolio.db
	scoreRows, err := portfolioDB.Query("SELECT " + scoresColumns + " FROM scores")
	if err != nil {
		return nil, fmt.Errorf("failed to query scores: %w", err)
	}
	defer scoreRows.Close()

	scoresMap := make(map[string]SecurityScore)
	scoreRepo := NewScoreRepository(portfolioDB, r.log)
	for scoreRows.Next() {
		score, err := scoreRepo.scanScore(scoreRows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan score: %w", err)
		}
		// After migration: scores table uses ISIN as PRIMARY KEY
		// Use ISIN directly as map key (no lookup needed)
		// Normalize ISIN to uppercase for consistent matching
		normalizedISIN := strings.ToUpper(strings.TrimSpace(score.ISIN))
		if normalizedISIN != "" {
			scoresMap[normalizedISIN] = score
		} else {
			// Fallback: if ISIN is missing (shouldn't happen), skip this score
			r.log.Warn().Str("score_data", fmt.Sprintf("%+v", score)).Msg("Score missing ISIN, skipping")
		}
	}

	if err := scoreRows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating scores: %w", err)
	}

	// Fetch positions from portfolio.db
	positionRows, err := portfolioDB.Query(`SELECT symbol, quantity, avg_price, current_price, currency,
		currency_rate, market_value_eur, cost_basis_eur, unrealized_pnl,
		unrealized_pnl_pct, last_updated, first_bought, last_sold, isin
		FROM positions`)
	if err != nil {
		return nil, fmt.Errorf("failed to query positions: %w", err)
	}
	defer positionRows.Close()

	positionsMap := make(map[string]struct {
		marketValueEUR float64
		quantity       float64
		currentPrice   *float64
	})

	for positionRows.Next() {
		var symbol string
		var quantity, marketValueEUR sql.NullFloat64
		// We only need symbol, quantity, and market_value_eur - scan minimal fields
		var avgPrice, currentPrice, currencyRate sql.NullFloat64
		var currency, lastUpdated sql.NullString
		var costBasis, unrealizedPnL, unrealizedPnLPct sql.NullFloat64
		var firstBought, lastSold, isin sql.NullString

		err := positionRows.Scan(
			&symbol, &quantity, &avgPrice, &currentPrice, &currency, &currencyRate,
			&marketValueEUR, &costBasis, &unrealizedPnL, &unrealizedPnLPct,
			&lastUpdated, &firstBought, &lastSold, &isin,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan position: %w", err)
		}

		// Convert symbol to ISIN for map key
		// Use ISIN from position if available, otherwise lookup
		var mapKey string
		if isin.Valid && isin.String != "" {
			mapKey = isin.String
		} else {
			// Lookup ISIN from securities table using symbol
			security, err := r.GetBySymbol(symbol)
			if err == nil && security != nil && security.ISIN != "" {
				mapKey = security.ISIN
			} else {
				// Fallback to symbol if ISIN lookup fails (for CASH positions)
				mapKey = symbol
			}
		}

		// Calculate market value EUR if not set in database
		var finalMarketValueEUR float64
		if marketValueEUR.Valid {
			finalMarketValueEUR = marketValueEUR.Float64
		} else if quantity.Valid && currentPrice.Valid && currencyRate.Valid && currencyRate.Float64 > 0 {
			// Calculate from quantity * current_price / currency_rate
			finalMarketValueEUR = quantity.Float64 * currentPrice.Float64 / currencyRate.Float64
		} else {
			// No valid data, skip this position but log a warning
			r.log.Warn().
				Str("symbol", symbol).
				Bool("has_quantity", quantity.Valid).
				Bool("has_price", currentPrice.Valid).
				Bool("has_rate", currencyRate.Valid).
				Msg("Skipping position with invalid data (missing market_value_eur and unable to calculate)")
			continue
		}

		var currentPricePtr *float64
		if currentPrice.Valid {
			currentPricePtr = &currentPrice.Float64
		}

		positionsMap[mapKey] = struct {
			marketValueEUR float64
			quantity       float64
			currentPrice   *float64
		}{
			marketValueEUR: finalMarketValueEUR,
			quantity:       quantity.Float64,
			currentPrice:   currentPricePtr,
		}
	}

	if err := positionRows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating positions: %w", err)
	}

	// Merge data
	var result []SecurityWithScore
	for isin, sws := range securitiesMap {
		// Normalize ISIN to uppercase for consistent matching
		normalizedISIN := strings.ToUpper(strings.TrimSpace(isin))
		// Add score data (scoresMap now uses ISIN as key)
		if score, found := scoresMap[normalizedISIN]; found {
			sws.TotalScore = &score.TotalScore
			sws.QualityScore = &score.QualityScore
			sws.OpportunityScore = &score.OpportunityScore
			sws.AnalystScore = &score.AnalystScore
			sws.AllocationFitScore = &score.AllocationFitScore
			sws.Volatility = &score.Volatility
			sws.CAGRScore = &score.CAGRScore
			sws.ConsistencyScore = &score.ConsistencyScore
			sws.HistoryYears = &score.HistoryYears
			sws.TechnicalScore = &score.TechnicalScore
			sws.StabilityScore = &score.StabilityScore
		} else {
			// Debug: Log when score not found for a security
			r.log.Debug().
				Str("isin", isin).
				Str("normalized_isin", normalizedISIN).
				Str("symbol", sws.Symbol).
				Int("scores_map_size", len(scoresMap)).
				Msg("Score not found for security in scoresMap")
		}

		// Add position data (positionsMap now uses ISIN as key)
		if pos, found := positionsMap[isin]; found {
			sws.PositionValue = &pos.marketValueEUR
			sws.PositionQuantity = &pos.quantity
			sws.CurrentPrice = pos.currentPrice
		} else {
			zero := 0.0
			sws.PositionValue = &zero
			sws.PositionQuantity = &zero
			// CurrentPrice remains nil if no position
		}

		result = append(result, sws)
	}

	return result, nil
}

// scanSecurity scans a database row into a Security struct
// Note: allow_buy, allow_sell, min_lot, priority_multiplier are stored in security_overrides table
func (r *SecurityRepository) scanSecurity(rows *sql.Rows) (Security, error) {
	var isin, symbol, jsonData string
	var lastSynced sql.NullInt64

	// Scan from JSON storage schema: isin, symbol, data, last_synced
	err := rows.Scan(&isin, &symbol, &jsonData, &lastSynced)
	if err != nil {
		return Security{}, fmt.Errorf("failed to scan row: %w", err)
	}

	// Convert lastSynced to pointer
	var ls *int64
	if lastSynced.Valid {
		ls = &lastSynced.Int64
	}

	// Parse JSON data to Security struct
	security, err := SecurityFromJSON(isin, symbol, jsonData, ls)
	if err != nil {
		r.log.Error().
			Err(err).
			Str("isin", isin).
			Str("symbol", symbol).
			Msg("Failed to parse security JSON")
		return Security{}, fmt.Errorf("failed to parse security JSON for %s: %w", isin, err)
	}

	// Apply defaults for fields moved to security_overrides
	// These will be overridden by actual overrides in the calling method
	ApplyDefaults(security)

	// Load tags for the security
	// Use ISIN as primary identifier (security_tags table uses isin, not symbol)
	if security.ISIN != "" {
		tagIDs, err := r.getTagsForSecurity(security.ISIN)
		if err != nil {
			// Log error but don't fail - tags are optional
			r.log.Warn().Str("isin", security.ISIN).Str("symbol", security.Symbol).Err(err).Msg("Failed to load tags for security")
			security.Tags = []string{} // Initialize to empty slice
		} else if len(tagIDs) > 0 {
			// Make a copy of the slice to avoid potential issues with shared underlying array
			security.Tags = make([]string, len(tagIDs))
			copy(security.Tags, tagIDs)
		} else {
			// Empty result - no tags found (this is valid, not an error)
			security.Tags = []string{}
		}
	} else {
		security.Tags = []string{}
	}

	return *security, nil
}

// getTagsForSecurity loads tag IDs for a security by ISIN
func (r *SecurityRepository) getTagsForSecurity(isin string) ([]string, error) {
	query := "SELECT tag_id FROM security_tags WHERE isin = ? ORDER BY tag_id"

	rows, err := r.universeDB.Query(query, strings.ToUpper(strings.TrimSpace(isin)))
	if err != nil {
		return nil, fmt.Errorf("failed to query tags for security: %w", err)
	}
	defer rows.Close()

	var tagIDs []string
	for rows.Next() {
		var tagID string
		err := rows.Scan(&tagID)
		if err != nil {
			return nil, fmt.Errorf("failed to scan tag ID: %w", err)
		}
		tagIDs = append(tagIDs, tagID)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating tags: %w", err)
	}

	return tagIDs, nil
}

// SetTagsForSecurity replaces all tags for a security (deletes existing, inserts new)
// symbol parameter is kept for backward compatibility, but we look up ISIN internally
func (r *SecurityRepository) SetTagsForSecurity(symbol string, tagIDs []string) error {
	// Normalize symbol
	symbol = strings.ToUpper(strings.TrimSpace(symbol))

	// Look up ISIN from symbol (security_tags table uses isin, not symbol)
	security, err := r.GetBySymbol(symbol)
	if err != nil {
		return fmt.Errorf("failed to lookup security by symbol: %w", err)
	}
	if security == nil || security.ISIN == "" {
		return fmt.Errorf("security not found or missing ISIN: %s", symbol)
	}
	isin := security.ISIN

	// Ensure all tag IDs exist (create with default names if missing)
	if err := r.tagRepo.EnsureTagsExist(tagIDs); err != nil {
		return fmt.Errorf("failed to ensure tags exist: %w", err)
	}

	// Begin transaction
	tx, err := r.universeDB.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	// Delete all existing tags for this security (using ISIN)
	_, err = tx.Exec("DELETE FROM security_tags WHERE isin = ?", isin)
	if err != nil {
		return fmt.Errorf("failed to delete existing tags: %w", err)
	}

	// Insert new tags (using ISIN)
	now := time.Now().Unix()
	for _, tagID := range tagIDs {
		// Skip empty tag IDs
		tagID = strings.ToLower(strings.TrimSpace(tagID))
		if tagID == "" {
			continue
		}

		_, err = tx.Exec(`
			INSERT INTO security_tags (isin, tag_id, created_at, updated_at)
			VALUES (?, ?, ?, ?)
		`, isin, tagID, now, now)
		if err != nil {
			return fmt.Errorf("failed to insert tag %s: %w", tagID, err)
		}
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	r.log.Debug().Str("isin", isin).Str("symbol", symbol).Int("tag_count", len(tagIDs)).Msg("Tags updated for security")
	return nil
}

// GetTagsForSecurity returns all tag IDs for a security (public method)
// symbol parameter is kept for backward compatibility, but we look up ISIN internally
func (r *SecurityRepository) GetTagsForSecurity(symbol string) ([]string, error) {
	// Look up ISIN from symbol (security_tags table uses isin, not symbol)
	security, err := r.GetBySymbol(symbol)
	if err != nil {
		return nil, fmt.Errorf("failed to lookup security by symbol: %w", err)
	}
	if security == nil || security.ISIN == "" {
		return nil, fmt.Errorf("security not found or missing ISIN: %s", symbol)
	}
	return r.getTagsForSecurity(security.ISIN)
}

// GetTagsWithUpdateTimes returns all tags for a security with their last update times
// symbol parameter is kept for backward compatibility, but we look up ISIN internally
func (r *SecurityRepository) GetTagsWithUpdateTimes(symbol string) (map[string]time.Time, error) {
	// Normalize symbol
	symbol = strings.ToUpper(strings.TrimSpace(symbol))

	// Look up ISIN from symbol (security_tags table uses isin, not symbol)
	security, err := r.GetBySymbol(symbol)
	if err != nil {
		return nil, fmt.Errorf("failed to lookup security by symbol: %w", err)
	}
	if security == nil || security.ISIN == "" {
		return nil, fmt.Errorf("security not found or missing ISIN: %s", symbol)
	}
	isin := security.ISIN

	query := "SELECT tag_id, updated_at FROM security_tags WHERE isin = ? ORDER BY tag_id"

	rows, err := r.universeDB.Query(query, isin)
	if err != nil {
		return nil, fmt.Errorf("failed to query tags with update times: %w", err)
	}
	defer rows.Close()

	tags := make(map[string]time.Time)
	for rows.Next() {
		var tagID string
		var updatedAtUnix sql.NullInt64
		err := rows.Scan(&tagID, &updatedAtUnix)
		if err != nil {
			return nil, fmt.Errorf("failed to scan tag update time: %w", err)
		}

		// Convert Unix timestamp to time.Time
		if updatedAtUnix.Valid {
			tags[tagID] = time.Unix(updatedAtUnix.Int64, 0).UTC()
		} else {
			// If NULL, use zero time (will force update)
			tags[tagID] = time.Time{}
		}
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating tags: %w", err)
	}

	return tags, nil
}

// UpdateSpecificTags updates only the specified tags for a security, preserving other tags
// symbol parameter is kept for backward compatibility, but we look up ISIN internally
func (r *SecurityRepository) UpdateSpecificTags(symbol string, tagIDs []string) error {
	// Normalize symbol
	symbol = strings.ToUpper(strings.TrimSpace(symbol))

	if len(tagIDs) == 0 {
		return nil // Nothing to update
	}

	// Look up ISIN from symbol (security_tags table uses isin, not symbol)
	security, err := r.GetBySymbol(symbol)
	if err != nil {
		return fmt.Errorf("failed to lookup security by symbol: %w", err)
	}
	if security == nil || security.ISIN == "" {
		return fmt.Errorf("security not found or missing ISIN: %s", symbol)
	}
	isin := security.ISIN

	// Ensure all tag IDs exist
	if err := r.tagRepo.EnsureTagsExist(tagIDs); err != nil {
		return fmt.Errorf("failed to ensure tags exist: %w", err)
	}

	// Begin transaction
	tx, err := r.universeDB.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	// Get current tags to determine which to delete and which to insert/update (using ISIN)
	currentTags, err := r.getTagsForSecurity(isin)
	if err != nil {
		return fmt.Errorf("failed to get current tags: %w", err)
	}

	currentTagSet := make(map[string]bool)
	for _, tagID := range currentTags {
		currentTagSet[tagID] = true
	}

	now := time.Now().Unix()
	newTagSet := make(map[string]bool)

	// Process each tag
	for _, tagID := range tagIDs {
		// Normalize tag ID
		tagID = strings.ToLower(strings.TrimSpace(tagID))
		if tagID == "" {
			continue
		}

		newTagSet[tagID] = true

		if currentTagSet[tagID] {
			// Tag exists - update its updated_at timestamp (using ISIN)
			_, err = tx.Exec(`
				UPDATE security_tags
				SET updated_at = ?
				WHERE isin = ? AND tag_id = ?
			`, now, isin, tagID)
			if err != nil {
				return fmt.Errorf("failed to update tag %s: %w", tagID, err)
			}
		} else {
			// Tag doesn't exist - insert it (using ISIN)
			// Use INSERT OR IGNORE to handle race conditions where tag might be inserted between check and insert
			_, err = tx.Exec(`
				INSERT OR IGNORE INTO security_tags (isin, tag_id, created_at, updated_at)
				VALUES (?, ?, ?, ?)
			`, isin, tagID, now, now)
			if err != nil {
				return fmt.Errorf("failed to insert tag %s: %w", tagID, err)
			}
		}
	}

	// Note: We don't delete tags that aren't in the new set - we only update the ones specified
	// This allows partial updates while preserving other tags

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	r.log.Debug().
		Str("symbol", symbol).
		Int("tag_count", len(tagIDs)).
		Msg("Specific tags updated for security")

	return nil
}

// GetByTags returns active securities matching any of the provided tags
// Uses indexed security_tags table for fast querying
func (r *SecurityRepository) GetByTags(tagIDs []string) ([]Security, error) {
	if len(tagIDs) == 0 {
		return []Security{}, nil
	}

	// Normalize tag IDs
	normalizedTags := make([]string, 0, len(tagIDs))
	for _, tagID := range tagIDs {
		normalized := strings.ToLower(strings.TrimSpace(tagID))
		if normalized != "" {
			normalizedTags = append(normalizedTags, normalized)
		}
	}

	if len(normalizedTags) == 0 {
		return []Security{}, nil
	}

	// Build query with placeholders
	placeholders := strings.Repeat("?,", len(normalizedTags))
	placeholders = placeholders[:len(placeholders)-1] // Remove trailing comma

	query := fmt.Sprintf(`
		SELECT DISTINCT s.isin, s.symbol, s.data, s.last_synced
		FROM securities s
		INNER JOIN security_tags st ON s.isin = st.isin
		WHERE st.tag_id IN (%s)
		AND (json_extract(s.data, '$.product_type') IS NULL OR json_extract(s.data, '$.product_type') != ?)
		ORDER BY s.symbol ASC
	`, placeholders)

	// Build args slice (tag IDs + ProductTypeIndex filter)
	args := make([]interface{}, len(normalizedTags)+1)
	for i, tagID := range normalizedTags {
		args[i] = tagID
	}
	args[len(normalizedTags)] = string(ProductTypeIndex)

	rows, err := r.universeDB.Query(query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to query securities by tags: %w", err)
	}
	defer rows.Close()

	var securities []Security
	for rows.Next() {
		security, err := r.scanSecurity(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan security: %w", err)
		}

		// Ensure tags are loaded (scanSecurity should load them, but reload to be safe)
		// Use ISIN as primary identifier
		if security.ISIN != "" {
			tagIDs, tagErr := r.getTagsForSecurity(security.ISIN)
			if tagErr == nil {
				security.Tags = make([]string, len(tagIDs))
				copy(security.Tags, tagIDs)
			} else {
				// If error, initialize to empty slice
				security.Tags = []string{}
			}
		} else {
			security.Tags = []string{}
		}

		securities = append(securities, security)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating securities: %w", err)
	}

	// Apply overrides if override repository is available (batch mode for efficiency)
	if r.overrideRepo != nil && len(securities) > 0 {
		allOverrides, err := r.overrideRepo.GetAllOverrides()
		if err != nil {
			r.log.Warn().Err(err).Msg("Failed to fetch all overrides")
		} else {
			for i := range securities {
				if overrides, exists := allOverrides[securities[i].ISIN]; exists && len(overrides) > 0 {
					ApplyOverrides(&securities[i], overrides)
				}
			}
		}
	}

	r.log.Debug().
		Int("tag_count", len(normalizedTags)).
		Int("securities_found", len(securities)).
		Msg("Queried securities by tags")

	return securities, nil
}

// GetPositionsByTags returns securities that are in the provided position symbols AND have the specified tags
// This is useful for filtering portfolio positions by tags
func (r *SecurityRepository) GetPositionsByTags(positionSymbols []string, tagIDs []string) ([]Security, error) {
	if len(positionSymbols) == 0 || len(tagIDs) == 0 {
		return []Security{}, nil
	}

	// Normalize symbols
	normalizedSymbols := make([]string, 0, len(positionSymbols))
	for _, symbol := range positionSymbols {
		normalized := strings.ToUpper(strings.TrimSpace(symbol))
		if normalized != "" {
			normalizedSymbols = append(normalizedSymbols, normalized)
		}
	}

	// Normalize tag IDs
	normalizedTags := make([]string, 0, len(tagIDs))
	for _, tagID := range tagIDs {
		normalized := strings.ToLower(strings.TrimSpace(tagID))
		if normalized != "" {
			normalizedTags = append(normalizedTags, normalized)
		}
	}

	if len(normalizedSymbols) == 0 || len(normalizedTags) == 0 {
		return []Security{}, nil
	}

	// Build query with placeholders
	symbolPlaceholders := strings.Repeat("?,", len(normalizedSymbols))
	symbolPlaceholders = symbolPlaceholders[:len(symbolPlaceholders)-1]

	tagPlaceholders := strings.Repeat("?,", len(normalizedTags))
	tagPlaceholders = tagPlaceholders[:len(tagPlaceholders)-1]

	query := fmt.Sprintf(`
		SELECT DISTINCT s.isin, s.symbol, s.data, s.last_synced
		FROM securities s
		INNER JOIN security_tags st ON s.isin = st.isin
		WHERE s.symbol IN (%s)
		AND st.tag_id IN (%s)
		AND (json_extract(s.data, '$.product_type') IS NULL OR json_extract(s.data, '$.product_type') != ?)
		ORDER BY s.symbol ASC
	`, symbolPlaceholders, tagPlaceholders)

	// Build args slice (symbols first, then tags, then ProductTypeIndex filter)
	args := make([]interface{}, 0, len(normalizedSymbols)+len(normalizedTags)+1)
	for _, symbol := range normalizedSymbols {
		args = append(args, symbol)
	}
	for _, tagID := range normalizedTags {
		args = append(args, tagID)
	}
	args = append(args, string(ProductTypeIndex))

	rows, err := r.universeDB.Query(query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to query positions by tags: %w", err)
	}
	defer rows.Close()

	var securities []Security
	for rows.Next() {
		security, err := r.scanSecurity(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan security: %w", err)
		}

		// Ensure tags are loaded (scanSecurity should load them, but reload to be safe)
		// Use ISIN as primary identifier (security_tags table uses isin, not symbol)
		if security.ISIN != "" {
			tagIDs, tagErr := r.getTagsForSecurity(security.ISIN)
			if tagErr != nil {
				// Log error but don't fail - tags are optional
				r.log.Warn().Str("isin", security.ISIN).Str("symbol", security.Symbol).Err(tagErr).Msg("Failed to load tags for security in GetPositionsByTags")
				security.Tags = []string{}
			} else {
				security.Tags = make([]string, len(tagIDs))
				copy(security.Tags, tagIDs)
			}
		} else {
			security.Tags = []string{}
		}

		securities = append(securities, security)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating securities: %w", err)
	}

	// Apply overrides if override repository is available (batch mode for efficiency)
	if r.overrideRepo != nil && len(securities) > 0 {
		allOverrides, err := r.overrideRepo.GetAllOverrides()
		if err != nil {
			r.log.Warn().Err(err).Msg("Failed to fetch all overrides")
		} else {
			for i := range securities {
				if overrides, exists := allOverrides[securities[i].ISIN]; exists && len(overrides) > 0 {
					ApplyOverrides(&securities[i], overrides)
				}
			}
		}
	}

	r.log.Debug().
		Int("position_count", len(normalizedSymbols)).
		Int("tag_count", len(normalizedTags)).
		Int("securities_found", len(securities)).
		Msg("Queried positions by tags")

	return securities, nil
}

// GetISINBySymbol returns just the ISIN for a given symbol
// This is more efficient than GetBySymbol when you only need the ISIN
func (r *SecurityRepository) GetISINBySymbol(symbol string) (string, error) {
	var isin string
	query := `SELECT isin FROM securities WHERE symbol = ?`
	err := r.universeDB.QueryRow(query, strings.ToUpper(strings.TrimSpace(symbol))).Scan(&isin)
	if err == sql.ErrNoRows {
		return "", fmt.Errorf("security not found: %s", symbol)
	}
	if err != nil {
		return "", fmt.Errorf("failed to query ISIN by symbol: %w", err)
	}
	return isin, nil
}

// GetSymbolByISIN returns just the symbol for a given ISIN
// This is more efficient than GetByISIN when you only need the symbol
func (r *SecurityRepository) GetSymbolByISIN(isin string) (string, error) {
	var symbol string
	query := `SELECT symbol FROM securities WHERE isin = ?`
	err := r.universeDB.QueryRow(query, strings.ToUpper(strings.TrimSpace(isin))).Scan(&symbol)
	if err == sql.ErrNoRows {
		return "", fmt.Errorf("security not found: %s", isin)
	}
	if err != nil {
		return "", fmt.Errorf("failed to query symbol by ISIN: %w", err)
	}
	return symbol, nil
}

// BatchGetISINsBySymbols returns a map of symbol → ISIN for multiple symbols
// This is much more efficient than calling GetISINBySymbol in a loop
func (r *SecurityRepository) BatchGetISINsBySymbols(symbols []string) (map[string]string, error) {
	if len(symbols) == 0 {
		return make(map[string]string), nil
	}

	// Normalize symbols
	normalizedSymbols := make([]string, len(symbols))
	for i, sym := range symbols {
		normalizedSymbols[i] = strings.ToUpper(strings.TrimSpace(sym))
	}

	// Build query with placeholders
	placeholders := strings.Repeat("?,", len(normalizedSymbols)-1) + "?"
	query := fmt.Sprintf(`SELECT symbol, isin FROM securities WHERE symbol IN (%s)`, placeholders)

	// Convert to []interface{} for Query
	args := make([]interface{}, len(normalizedSymbols))
	for i, sym := range normalizedSymbols {
		args[i] = sym
	}

	rows, err := r.universeDB.Query(query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to batch query ISINs: %w", err)
	}
	defer rows.Close()

	mapping := make(map[string]string)
	for rows.Next() {
		var symbol, isin string
		if err := rows.Scan(&symbol, &isin); err != nil {
			return nil, fmt.Errorf("failed to scan symbol/ISIN: %w", err)
		}
		mapping[symbol] = isin
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating symbol/ISIN results: %w", err)
	}

	return mapping, nil
}

// GetByISINs returns multiple securities by their ISINs (batch lookup)
func (r *SecurityRepository) GetByISINs(isins []string) ([]Security, error) {
	if len(isins) == 0 {
		return []Security{}, nil
	}

	// Normalize ISINs
	normalizedISINs := make([]string, len(isins))
	for i, isin := range isins {
		normalizedISINs[i] = strings.ToUpper(strings.TrimSpace(isin))
	}

	// Build query with placeholders
	placeholders := strings.Repeat("?,", len(normalizedISINs)-1) + "?"
	query := fmt.Sprintf(`SELECT %s FROM securities WHERE isin IN (%s)`, securitiesColumns, placeholders)

	// Convert to []interface{} for Query
	args := make([]interface{}, len(normalizedISINs))
	for i, isin := range normalizedISINs {
		args[i] = isin
	}

	rows, err := r.universeDB.Query(query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to batch query securities by ISIN: %w", err)
	}
	defer rows.Close()

	var securities []Security
	for rows.Next() {
		security, err := r.scanSecurity(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan security: %w", err)
		}
		securities = append(securities, security)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating securities: %w", err)
	}

	// Apply overrides if override repository is available (batch mode for efficiency)
	if r.overrideRepo != nil && len(securities) > 0 {
		allOverrides, err := r.overrideRepo.GetAllOverrides()
		if err != nil {
			r.log.Warn().Err(err).Msg("Failed to fetch all overrides")
		} else {
			for i := range securities {
				if overrides, exists := allOverrides[securities[i].ISIN]; exists && len(overrides) > 0 {
					ApplyOverrides(&securities[i], overrides)
				}
			}
		}
	}

	return securities, nil
}

// GetBySymbols returns multiple securities by their symbols (batch lookup)
func (r *SecurityRepository) GetBySymbols(symbols []string) ([]Security, error) {
	if len(symbols) == 0 {
		return []Security{}, nil
	}

	// Normalize symbols
	normalizedSymbols := make([]string, len(symbols))
	for i, sym := range symbols {
		normalizedSymbols[i] = strings.ToUpper(strings.TrimSpace(sym))
	}

	// Build query with placeholders
	placeholders := strings.Repeat("?,", len(normalizedSymbols)-1) + "?"
	query := fmt.Sprintf(`SELECT %s FROM securities WHERE symbol IN (%s)`, securitiesColumns, placeholders)

	// Convert to []interface{} for Query
	args := make([]interface{}, len(normalizedSymbols))
	for i, sym := range normalizedSymbols {
		args[i] = sym
	}

	rows, err := r.universeDB.Query(query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to batch query securities by symbol: %w", err)
	}
	defer rows.Close()

	var securities []Security
	for rows.Next() {
		security, err := r.scanSecurity(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan security: %w", err)
		}
		securities = append(securities, security)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating securities: %w", err)
	}

	// Apply overrides if override repository is available (batch mode for efficiency)
	if r.overrideRepo != nil && len(securities) > 0 {
		allOverrides, err := r.overrideRepo.GetAllOverrides()
		if err != nil {
			r.log.Warn().Err(err).Msg("Failed to fetch all overrides")
		} else {
			for i := range securities {
				if overrides, exists := allOverrides[securities[i].ISIN]; exists && len(overrides) > 0 {
					ApplyOverrides(&securities[i], overrides)
				}
			}
		}
	}

	return securities, nil
}

// GetTradable returns all tradable securities (excludes indices)
// Replaces GetAllActive and GetAllActiveTradable (active column will be removed)
func (r *SecurityRepository) GetTradable() ([]Security, error) {
	// After migration: no active column, use JSON extraction for product_type
	query := `SELECT ` + securitiesColumns + ` FROM securities
		WHERE json_extract(data, '$.product_type') IS NULL
		OR json_extract(data, '$.product_type') != ?`

	rows, err := r.universeDB.Query(query, string(ProductTypeIndex))
	if err != nil {
		return nil, fmt.Errorf("failed to query tradable securities: %w", err)
	}
	defer rows.Close()

	var securities []Security
	for rows.Next() {
		security, err := r.scanSecurity(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan security: %w", err)
		}
		securities = append(securities, security)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating securities: %w", err)
	}

	// Apply overrides if override repository is available (batch mode for efficiency)
	if r.overrideRepo != nil && len(securities) > 0 {
		allOverrides, err := r.overrideRepo.GetAllOverrides()
		if err != nil {
			r.log.Warn().Err(err).Msg("Failed to fetch all overrides")
		} else {
			for i := range securities {
				if overrides, exists := allOverrides[securities[i].ISIN]; exists && len(overrides) > 0 {
					ApplyOverrides(&securities[i], overrides)
				}
			}
		}
	}

	return securities, nil
}

// GetByGeography returns securities filtered by geography
func (r *SecurityRepository) GetByGeography(geography string) ([]Security, error) {
	query := `SELECT ` + securitiesColumns + ` FROM securities
		WHERE json_extract(data, '$.geography') = ?`

	rows, err := r.universeDB.Query(query, geography)
	if err != nil {
		return nil, fmt.Errorf("failed to query securities by geography: %w", err)
	}
	defer rows.Close()

	var securities []Security
	for rows.Next() {
		security, err := r.scanSecurity(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan security: %w", err)
		}
		securities = append(securities, security)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating securities: %w", err)
	}

	// Apply overrides if override repository is available
	if r.overrideRepo != nil && len(securities) > 0 {
		allOverrides, err := r.overrideRepo.GetAllOverrides()
		if err != nil {
			r.log.Warn().Err(err).Msg("Failed to fetch all overrides")
		} else {
			for i := range securities {
				if overrides, exists := allOverrides[securities[i].ISIN]; exists && len(overrides) > 0 {
					ApplyOverrides(&securities[i], overrides)
				}
			}
		}
	}

	return securities, nil
}

// GetByIndustry returns securities filtered by industry
func (r *SecurityRepository) GetByIndustry(industry string) ([]Security, error) {
	query := `SELECT ` + securitiesColumns + ` FROM securities
		WHERE json_extract(data, '$.industry') = ?`

	rows, err := r.universeDB.Query(query, industry)
	if err != nil {
		return nil, fmt.Errorf("failed to query securities by industry: %w", err)
	}
	defer rows.Close()

	var securities []Security
	for rows.Next() {
		security, err := r.scanSecurity(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan security: %w", err)
		}
		securities = append(securities, security)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating securities: %w", err)
	}

	// Apply overrides if override repository is available
	if r.overrideRepo != nil && len(securities) > 0 {
		allOverrides, err := r.overrideRepo.GetAllOverrides()
		if err != nil {
			r.log.Warn().Err(err).Msg("Failed to fetch all overrides")
		} else {
			for i := range securities {
				if overrides, exists := allOverrides[securities[i].ISIN]; exists && len(overrides) > 0 {
					ApplyOverrides(&securities[i], overrides)
				}
			}
		}
	}

	return securities, nil
}

// GetDistinctGeographies returns a list of distinct geographies from active securities (excludes indices)
func (r *SecurityRepository) GetDistinctGeographies() ([]string, error) {
	query := `SELECT DISTINCT json_extract(data, '$.geography') as geography
		FROM securities
		WHERE json_extract(data, '$.geography') IS NOT NULL
		AND json_extract(data, '$.geography') != ''
		AND json_extract(data, '$.geography') != '0'
		AND (json_extract(data, '$.product_type') IS NULL OR json_extract(data, '$.product_type') != ?)
		ORDER BY geography`

	rows, err := r.universeDB.Query(query, string(ProductTypeIndex))
	if err != nil {
		return nil, fmt.Errorf("failed to query distinct geographies: %w", err)
	}
	defer rows.Close()

	var geographies []string
	for rows.Next() {
		var geography string
		if err := rows.Scan(&geography); err != nil {
			return nil, fmt.Errorf("failed to scan geography: %w", err)
		}
		geographies = append(geographies, geography)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating geographies: %w", err)
	}

	return geographies, nil
}

// GetDistinctIndustries returns a list of distinct industries from active securities (excludes indices)
func (r *SecurityRepository) GetDistinctIndustries() ([]string, error) {
	query := `SELECT DISTINCT json_extract(data, '$.industry') as industry
		FROM securities
		WHERE json_extract(data, '$.industry') IS NOT NULL
		AND json_extract(data, '$.industry') != ''
		AND (json_extract(data, '$.product_type') IS NULL OR json_extract(data, '$.product_type') != ?)
		ORDER BY industry`

	rows, err := r.universeDB.Query(query, string(ProductTypeIndex))
	if err != nil {
		return nil, fmt.Errorf("failed to query distinct industries: %w", err)
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

// GetGeographiesAndIndustries returns a map of geography → list of industries
func (r *SecurityRepository) GetGeographiesAndIndustries() (map[string][]string, error) {
	query := `SELECT DISTINCT
		json_extract(data, '$.geography') as geography,
		json_extract(data, '$.industry') as industry
		FROM securities
		WHERE json_extract(data, '$.geography') IS NOT NULL
		AND json_extract(data, '$.geography') != ''
		AND json_extract(data, '$.geography') != '0'
		AND json_extract(data, '$.industry') IS NOT NULL
		AND json_extract(data, '$.industry') != ''
		AND (json_extract(data, '$.product_type') IS NULL OR json_extract(data, '$.product_type') != ?)
		ORDER BY geography, industry`

	rows, err := r.universeDB.Query(query, string(ProductTypeIndex))
	if err != nil {
		return nil, fmt.Errorf("failed to query geographies and industries: %w", err)
	}
	defer rows.Close()

	result := make(map[string][]string)
	for rows.Next() {
		var geography, industry string
		if err := rows.Scan(&geography, &industry); err != nil {
			return nil, fmt.Errorf("failed to scan geography/industry: %w", err)
		}

		if _, exists := result[geography]; !exists {
			result[geography] = []string{}
		}
		result[geography] = append(result[geography], industry)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating geographies/industries: %w", err)
	}

	return result, nil
}

// GetSecuritiesForOptimization returns minimal data needed for portfolio optimization
func (r *SecurityRepository) GetSecuritiesForOptimization() ([]SecurityOptimizationData, error) {
	query := `SELECT isin, symbol,
		json_extract(data, '$.product_type') as product_type,
		json_extract(data, '$.geography') as geography,
		json_extract(data, '$.industry') as industry,
		json_extract(data, '$.min_portfolio_target') as min_portfolio_target,
		json_extract(data, '$.max_portfolio_target') as max_portfolio_target
		FROM securities`

	rows, err := r.universeDB.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query securities for optimization: %w", err)
	}
	defer rows.Close()

	var result []SecurityOptimizationData
	for rows.Next() {
		var data SecurityOptimizationData
		var productType, geography, industry sql.NullString
		var minTarget, maxTarget sql.NullFloat64

		err := rows.Scan(&data.ISIN, &data.Symbol, &productType, &geography, &industry, &minTarget, &maxTarget)
		if err != nil {
			return nil, fmt.Errorf("failed to scan optimization data: %w", err)
		}

		if productType.Valid {
			data.ProductType = productType.String
		}
		if geography.Valid {
			data.Geography = geography.String
		}
		if industry.Valid {
			data.Industry = industry.String
		}
		if minTarget.Valid {
			data.MinPortfolioTarget = minTarget.Float64
		}
		if maxTarget.Valid {
			data.MaxPortfolioTarget = maxTarget.Float64
		}

		result = append(result, data)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating optimization data: %w", err)
	}

	return result, nil
}

// GetSecuritiesForCharts returns minimal data needed for chart generation
func (r *SecurityRepository) GetSecuritiesForCharts() ([]SecurityChartData, error) {
	query := `SELECT isin, symbol FROM securities
		WHERE json_extract(data, '$.product_type') IS NULL
		OR json_extract(data, '$.product_type') != ?`

	rows, err := r.universeDB.Query(query, string(ProductTypeIndex))
	if err != nil {
		return nil, fmt.Errorf("failed to query securities for charts: %w", err)
	}
	defer rows.Close()

	var result []SecurityChartData
	for rows.Next() {
		var data SecurityChartData
		err := rows.Scan(&data.ISIN, &data.Symbol)
		if err != nil {
			return nil, fmt.Errorf("failed to scan chart data: %w", err)
		}
		result = append(result, data)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating chart data: %w", err)
	}

	return result, nil
}

// Exists checks if a security exists by ISIN
func (r *SecurityRepository) Exists(isin string) (bool, error) {
	var count int
	query := `SELECT COUNT(*) FROM securities WHERE isin = ?`
	err := r.universeDB.QueryRow(query, strings.ToUpper(strings.TrimSpace(isin))).Scan(&count)
	if err != nil {
		return false, fmt.Errorf("failed to check security existence: %w", err)
	}
	return count > 0, nil
}

// ExistsBySymbol checks if a security exists by symbol
func (r *SecurityRepository) ExistsBySymbol(symbol string) (bool, error) {
	var count int
	query := `SELECT COUNT(*) FROM securities WHERE symbol = ?`
	err := r.universeDB.QueryRow(query, strings.ToUpper(strings.TrimSpace(symbol))).Scan(&count)
	if err != nil {
		return false, fmt.Errorf("failed to check security existence by symbol: %w", err)
	}
	return count > 0, nil
}

// CountTradable returns the count of tradable securities (excludes indices)
func (r *SecurityRepository) CountTradable() (int, error) {
	var count int
	query := `SELECT COUNT(*) FROM securities
		WHERE json_extract(data, '$.product_type') IS NULL
		OR json_extract(data, '$.product_type') != ?`
	err := r.universeDB.QueryRow(query, string(ProductTypeIndex)).Scan(&count)
	if err != nil {
		return 0, fmt.Errorf("failed to count tradable securities: %w", err)
	}
	return count, nil
}

// Helper functions

func nullString(s string) sql.NullString {
	if s == "" {
		return sql.NullString{Valid: false}
	}
	return sql.NullString{String: s, Valid: true}
}

func nullFloat64(f float64) sql.NullFloat64 {
	if f == 0 {
		return sql.NullFloat64{Valid: false}
	}
	return sql.NullFloat64{Float64: f, Valid: true}
}

func boolToInt(b bool) int {
	if b {
		return 1
	}
	return 0
}
