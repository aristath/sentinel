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

// securitiesColumns is the list of columns for the securities table
// Used to avoid SELECT * which can break when schema changes
// Column order must match the table schema (matches SELECT * order)
// Note: allow_buy, allow_sell, min_lot, priority_multiplier are stored in security_overrides table
const securitiesColumns = `isin, symbol, name, product_type, industry, geography, fullExchangeName,
market_code, active, currency, last_synced,
min_portfolio_target, max_portfolio_target, created_at, updated_at`

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
func (r *SecurityRepository) GetAllActive() ([]Security, error) {
	query := "SELECT " + securitiesColumns + " FROM securities WHERE active = 1 AND (product_type IS NULL OR product_type != ?)"

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
	query := `SELECT DISTINCT fullExchangeName FROM securities
		WHERE fullExchangeName IS NOT NULL AND fullExchangeName != '' AND active = 1
		AND (product_type IS NULL OR product_type != ?)
		ORDER BY fullExchangeName`

	rows, err := r.universeDB.Query(query, string(ProductTypeIndex))
	if err != nil {
		return nil, fmt.Errorf("failed to query distinct exchanges: %w", err)
	}
	defer rows.Close()

	var exchanges []string
	for rows.Next() {
		var exchange sql.NullString
		if err := rows.Scan(&exchange); err != nil {
			return nil, fmt.Errorf("failed to scan exchange: %w", err)
		}
		if exchange.Valid && exchange.String != "" {
			exchanges = append(exchanges, exchange.String)
		}
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating exchanges: %w", err)
	}

	return exchanges, nil
}

// GetAllActiveTradable returns all active tradable securities (excludes indices and cash)
// Used for scoring and trading operations
func (r *SecurityRepository) GetAllActiveTradable() ([]Security, error) {
	query := "SELECT " + securitiesColumns + " FROM securities WHERE active = 1 AND (product_type IS NULL OR product_type != ?)"

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
	query := "SELECT " + securitiesColumns + " FROM securities WHERE market_code = ? AND active = 1 AND (product_type IS NULL OR product_type != ?)"

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
	now := time.Now().Unix()

	// Normalize symbol
	security.Symbol = strings.ToUpper(strings.TrimSpace(security.Symbol))

	// Begin transaction
	tx, err := r.universeDB.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	query := `
		INSERT INTO securities
		(isin, symbol, name, product_type, industry, geography, fullExchangeName,
		 market_code, active, currency, min_portfolio_target, max_portfolio_target,
		 created_at, updated_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	// ISIN is required (PRIMARY KEY)
	if security.ISIN == "" {
		return fmt.Errorf("ISIN is required for security creation")
	}

	_, err = tx.Exec(query,
		strings.ToUpper(strings.TrimSpace(security.ISIN)),
		security.Symbol,
		security.Name,
		nullString(security.ProductType),
		nullString(security.Industry),
		nullString(security.Geography),
		nullString(security.FullExchangeName),
		nullString(security.MarketCode),
		boolToInt(security.Active),
		nullString(security.Currency),
		nullFloat64(security.MinPortfolioTarget),
		nullFloat64(security.MaxPortfolioTarget),
		now,
		now,
	)
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
// Note: allow_buy, allow_sell, min_lot, priority_multiplier should be set via security_overrides using the OverrideRepository
func (r *SecurityRepository) Update(isin string, updates map[string]interface{}) error {
	if len(updates) == 0 {
		return nil
	}

	// Whitelist of allowed update fields
	// Note: allow_buy, allow_sell, priority_multiplier are NOT allowed here
	// They should be set via security_overrides table
	allowedFields := map[string]bool{
		"active": true,
		"name":   true, "product_type": true, "sector": true, "industry": true,
		"geography": true, "fullExchangeName": true, "currency": true,
		"exchange":             true,
		"market_code":          true, // Tradernet market code for region mapping
		"min_portfolio_target": true, "max_portfolio_target": true,
		"isin":        true,
		"symbol":      true,
		"last_synced": true, // Unix timestamp
		"min_lot":     true, // Minimum lot size from broker
	}

	// Validate all keys are in whitelist
	for key := range updates {
		if !allowedFields[key] {
			return fmt.Errorf("invalid update field: %s", key)
		}
	}

	// Add updated_at
	now := time.Now().Unix()
	updates["updated_at"] = now

	// Convert booleans to integers
	for _, boolField := range []string{"active"} {
		if val, ok := updates[boolField]; ok {
			if boolVal, isBool := val.(bool); isBool {
				updates[boolField] = boolToInt(boolVal)
			}
		}
	}

	// Build SET clause
	var setClauses []string
	var values []interface{}
	for key, val := range updates {
		setClauses = append(setClauses, fmt.Sprintf("%s = ?", key))
		values = append(values, val)
	}
	values = append(values, strings.ToUpper(strings.TrimSpace(isin)))

	// Begin transaction
	tx, err := r.universeDB.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	// Safe: all keys are validated against whitelist above, values use parameterized query
	//nolint:gosec // G201: Field names are whitelisted, values are parameterized
	query := fmt.Sprintf("UPDATE securities SET %s WHERE isin = ?", strings.Join(setClauses, ", "))
	result, err := tx.Exec(query, values...)
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

// Delete soft deletes a security by ISIN (sets active=0)
// Changed from symbol to ISIN as primary identifier
func (r *SecurityRepository) Delete(isin string) error {
	return r.Update(isin, map[string]interface{}{"active": false})
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

	_, err = tx.Exec("DELETE FROM broker_symbols WHERE isin = ?", isin)
	if err != nil {
		return fmt.Errorf("failed to delete broker_symbols: %w", err)
	}

	_, err = tx.Exec("DELETE FROM client_symbols WHERE isin = ?", isin)
	if err != nil {
		return fmt.Errorf("failed to delete client_symbols: %w", err)
	}

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
	securityRows, err := r.universeDB.Query("SELECT "+securitiesColumns+" FROM securities WHERE active = 1 AND (product_type IS NULL OR product_type != ?)", string(ProductTypeIndex))
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
			Active:             security.Active,
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
	var security Security
	var isin, productType, geography, fullExchangeName sql.NullString
	var marketCode sql.NullString
	var industry, currency sql.NullString
	var lastSynced sql.NullInt64
	var minPortfolioTarget, maxPortfolioTarget sql.NullFloat64
	var active sql.NullInt64
	var createdAt, updatedAt sql.NullInt64

	// Table schema: isin, symbol, name, product_type, industry, geography, fullExchangeName,
	// market_code, active, currency, last_synced, min_portfolio_target, max_portfolio_target, created_at, updated_at
	// Note: allow_buy, allow_sell, min_lot, priority_multiplier are in security_overrides table
	var symbol sql.NullString
	err := rows.Scan(
		&isin,               // isin (PRIMARY KEY)
		&symbol,             // symbol
		&security.Name,      // name
		&productType,        // product_type
		&industry,           // industry
		&geography,          // geography
		&fullExchangeName,   // fullExchangeName
		&marketCode,         // market_code
		&active,             // active
		&currency,           // currency
		&lastSynced,         // last_synced
		&minPortfolioTarget, // min_portfolio_target
		&maxPortfolioTarget, // max_portfolio_target
		&createdAt,          // created_at
		&updatedAt,          // updated_at
	)
	if err != nil {
		return security, err
	}

	// Handle nullable fields
	if isin.Valid {
		security.ISIN = isin.String
	}
	if symbol.Valid {
		security.Symbol = symbol.String
	}
	if productType.Valid {
		security.ProductType = productType.String
	}
	if geography.Valid {
		security.Geography = geography.String
	}
	if fullExchangeName.Valid {
		security.FullExchangeName = fullExchangeName.String
	}
	if marketCode.Valid {
		security.MarketCode = marketCode.String
	}
	if industry.Valid {
		security.Industry = industry.String
	}
	if currency.Valid {
		security.Currency = currency.String
	}
	if lastSynced.Valid {
		security.LastSynced = &lastSynced.Int64
	}
	if minPortfolioTarget.Valid {
		security.MinPortfolioTarget = minPortfolioTarget.Float64
	}
	if maxPortfolioTarget.Valid {
		security.MaxPortfolioTarget = maxPortfolioTarget.Float64
	}

	// Handle boolean field (stored as integer in SQLite)
	if active.Valid {
		security.Active = active.Int64 != 0
	}

	// Timestamps are read but not stored in Security model
	// (created_at and updated_at are database fields but not part of the domain model)

	// Normalize symbol
	security.Symbol = strings.ToUpper(strings.TrimSpace(security.Symbol))

	// Apply defaults for fields moved to security_overrides
	// These will be overridden by actual overrides in the calling method
	ApplyDefaults(&security)

	// Load tags for the security
	// Use ISIN as primary identifier (security_tags table uses isin, not symbol)
	if security.ISIN != "" {
		tagIDs, err := r.getTagsForSecurity(security.ISIN)
		if err != nil {
			// Log error but don't fail - tags are optional
			// Note: In test environments, this error might be silently ignored if logger is disabled
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

	return security, nil
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
		SELECT DISTINCT s.isin, s.symbol, s.name, s.product_type, s.industry, s.geography, s.fullExchangeName,
			s.market_code, s.active, s.currency, s.last_synced,
			s.min_portfolio_target, s.max_portfolio_target, s.created_at, s.updated_at
		FROM securities s
		INNER JOIN security_tags st ON s.isin = st.isin
		WHERE st.tag_id IN (%s)
		AND s.active = 1
		AND (s.product_type IS NULL OR s.product_type != ?)
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
		SELECT DISTINCT s.isin, s.symbol, s.name, s.product_type, s.industry, s.geography, s.fullExchangeName,
			s.market_code, s.active, s.currency, s.last_synced,
			s.min_portfolio_target, s.max_portfolio_target, s.created_at, s.updated_at
		FROM securities s
		INNER JOIN security_tags st ON s.isin = st.isin
		WHERE s.symbol IN (%s)
		AND st.tag_id IN (%s)
		AND s.active = 1
		AND (s.product_type IS NULL OR s.product_type != ?)
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
