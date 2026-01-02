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
	configDB *sql.DB // config.db - securities table
	log      zerolog.Logger
}

// NewSecurityRepository creates a new security repository
func NewSecurityRepository(configDB *sql.DB, log zerolog.Logger) *SecurityRepository {
	return &SecurityRepository{
		configDB: configDB,
		log:      log.With().Str("repo", "security").Logger(),
	}
}

// GetBySymbol returns a security by symbol
// Faithful translation of Python: async def get_by_symbol(self, symbol: str) -> Optional[Security]
func (r *SecurityRepository) GetBySymbol(symbol string) (*Security, error) {
	query := "SELECT * FROM securities WHERE symbol = ?"

	rows, err := r.configDB.Query(query, strings.ToUpper(strings.TrimSpace(symbol)))
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

	return &security, nil
}

// GetByISIN returns a security by ISIN
// Faithful translation of Python: async def get_by_isin(self, isin: str) -> Optional[Security]
func (r *SecurityRepository) GetByISIN(isin string) (*Security, error) {
	query := "SELECT * FROM securities WHERE isin = ?"

	rows, err := r.configDB.Query(query, strings.ToUpper(strings.TrimSpace(isin)))
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

// GetAllActive returns all active securities
// Faithful translation of Python: async def get_all_active(self) -> List[Security]
func (r *SecurityRepository) GetAllActive() ([]Security, error) {
	query := "SELECT * FROM securities WHERE active = 1"

	rows, err := r.configDB.Query(query)
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

	return securities, nil
}

// GetAll returns all securities (active and inactive)
// Faithful translation of Python: async def get_all(self) -> List[Security]
func (r *SecurityRepository) GetAll() ([]Security, error) {
	query := "SELECT * FROM securities"

	rows, err := r.configDB.Query(query)
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

	return securities, nil
}

// GetByBucket returns all securities assigned to a specific bucket
// Faithful translation of Python: async def get_by_bucket(self, bucket_id: str, active_only: bool = True)
func (r *SecurityRepository) GetByBucket(bucketID string, activeOnly bool) ([]Security, error) {
	var query string
	if activeOnly {
		query = "SELECT * FROM securities WHERE bucket_id = ? AND active = 1"
	} else {
		query = "SELECT * FROM securities WHERE bucket_id = ?"
	}

	rows, err := r.configDB.Query(query, bucketID)
	if err != nil {
		return nil, fmt.Errorf("failed to query securities by bucket: %w", err)
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

	return securities, nil
}

// Create creates a new security
// Faithful translation of Python: async def create(self, security: Security) -> None
func (r *SecurityRepository) Create(security Security) error {
	now := time.Now().Format(time.RFC3339)

	// Normalize symbol
	security.Symbol = strings.ToUpper(strings.TrimSpace(security.Symbol))

	// Begin transaction
	tx, err := r.configDB.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	query := `
		INSERT INTO securities
		(symbol, yahoo_symbol, isin, name, product_type, industry, country, fullExchangeName,
		 priority_multiplier, min_lot, active, allow_buy, allow_sell,
		 currency, min_portfolio_target, max_portfolio_target, bucket_id,
		 created_at, updated_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	_, err = tx.Exec(query,
		security.Symbol,
		nullString(security.YahooSymbol),
		nullString(security.ISIN),
		security.Name,
		nullString(security.ProductType),
		nullString(security.Industry),
		nullString(security.Country),
		nullString(security.FullExchangeName),
		security.PriorityMultiplier,
		security.MinLot,
		boolToInt(security.Active),
		boolToInt(security.AllowBuy),
		boolToInt(security.AllowSell),
		nullString(security.Currency),
		nullFloat64(security.MinPortfolioTarget),
		nullFloat64(security.MaxPortfolioTarget),
		security.BucketID,
		now,
		now,
	)
	if err != nil {
		return fmt.Errorf("failed to insert security: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	r.log.Info().Str("symbol", security.Symbol).Msg("Security created")
	return nil
}

// Update updates security fields
// Faithful translation of Python: async def update(self, symbol: str, **updates) -> None
func (r *SecurityRepository) Update(symbol string, updates map[string]interface{}) error {
	if len(updates) == 0 {
		return nil
	}

	// Whitelist of allowed update fields
	allowedFields := map[string]bool{
		"active": true, "allow_buy": true, "allow_sell": true,
		"name": true, "product_type": true, "sector": true, "industry": true,
		"country": true, "fullExchangeName": true, "currency": true,
		"exchange": true, "market_cap": true, "pe_ratio": true,
		"dividend_yield": true, "beta": true, "52w_high": true, "52w_low": true,
		"min_portfolio_target": true, "max_portfolio_target": true,
		"isin": true, "min_lot": true, "priority_multiplier": true,
		"yahoo_symbol": true, "bucket_id": true, "symbol": true,
	}

	// Validate all keys are in whitelist
	for key := range updates {
		if !allowedFields[key] {
			return fmt.Errorf("invalid update field: %s", key)
		}
	}

	// Add updated_at
	now := time.Now().Format(time.RFC3339)
	updates["updated_at"] = now

	// Convert booleans to integers
	for _, boolField := range []string{"active", "allow_buy", "allow_sell"} {
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
	values = append(values, strings.ToUpper(strings.TrimSpace(symbol)))

	// Begin transaction
	tx, err := r.configDB.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	query := fmt.Sprintf("UPDATE securities SET %s WHERE symbol = ?", strings.Join(setClauses, ", "))
	result, err := tx.Exec(query, values...)
	if err != nil {
		return fmt.Errorf("failed to update security: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	r.log.Info().Str("symbol", symbol).Int64("rows_affected", rowsAffected).Msg("Security updated")
	return nil
}

// Delete soft deletes a security (sets active=0)
// Faithful translation of Python: async def delete(self, symbol: str) -> None
func (r *SecurityRepository) Delete(symbol string) error {
	return r.Update(symbol, map[string]interface{}{"active": false})
}

// GetWithScores returns all active securities with their scores and positions
// Faithful translation of Python: async def get_with_scores(self) -> List[dict]
// Note: This method accesses multiple databases (config.db and state.db) - architecture violation
func (r *SecurityRepository) GetWithScores(stateDB *sql.DB) ([]SecurityWithScore, error) {
	// Fetch securities from config.db
	securityRows, err := r.configDB.Query("SELECT * FROM securities WHERE active = 1")
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
		sws := SecurityWithScore{
			Symbol:             security.Symbol,
			Name:               security.Name,
			ISIN:               security.ISIN,
			YahooSymbol:        security.YahooSymbol,
			ProductType:        security.ProductType,
			Country:            security.Country,
			FullExchangeName:   security.FullExchangeName,
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
			BucketID:           security.BucketID,
		}
		securitiesMap[security.Symbol] = sws
	}

	if err := securityRows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating securities: %w", err)
	}

	// Fetch scores from state.db
	scoreRows, err := stateDB.Query("SELECT * FROM scores")
	if err != nil {
		return nil, fmt.Errorf("failed to query scores: %w", err)
	}
	defer scoreRows.Close()

	scoresMap := make(map[string]SecurityScore)
	scoreRepo := NewScoreRepository(stateDB, r.log)
	for scoreRows.Next() {
		score, err := scoreRepo.scanScore(scoreRows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan score: %w", err)
		}
		scoresMap[score.Symbol] = score
	}

	if err := scoreRows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating scores: %w", err)
	}

	// Fetch positions from state.db
	positionRows, err := stateDB.Query("SELECT * FROM positions")
	if err != nil {
		return nil, fmt.Errorf("failed to query positions: %w", err)
	}
	defer positionRows.Close()

	positionsMap := make(map[string]struct {
		marketValueEUR float64
		quantity       float64
	})

	for positionRows.Next() {
		var symbol string
		var quantity, marketValueEUR sql.NullFloat64
		// We only need symbol, quantity, and market_value_eur - scan minimal fields
		var avgPrice, currentPrice, currencyRate sql.NullFloat64
		var currency, lastUpdated sql.NullString
		var costBasis, unrealizedPnL, unrealizedPnLPct sql.NullFloat64
		var firstBought, lastSold, isin, bucketID sql.NullString

		err := positionRows.Scan(
			&symbol, &quantity, &avgPrice, &currentPrice, &currency, &currencyRate,
			&marketValueEUR, &costBasis, &unrealizedPnL, &unrealizedPnLPct,
			&lastUpdated, &firstBought, &lastSold, &isin, &bucketID,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan position: %w", err)
		}

		positionsMap[symbol] = struct {
			marketValueEUR float64
			quantity       float64
		}{
			marketValueEUR: marketValueEUR.Float64,
			quantity:       quantity.Float64,
		}
	}

	if err := positionRows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating positions: %w", err)
	}

	// Merge data
	var result []SecurityWithScore
	for symbol, sws := range securitiesMap {
		// Add score data
		if score, found := scoresMap[symbol]; found {
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
			sws.FundamentalScore = &score.FundamentalScore
		}

		// Add position data
		if pos, found := positionsMap[symbol]; found {
			sws.PositionValue = &pos.marketValueEUR
			sws.PositionQuantity = &pos.quantity
		} else {
			zero := 0.0
			sws.PositionValue = &zero
			sws.PositionQuantity = &zero
		}

		result = append(result, sws)
	}

	return result, nil
}

// scanSecurity scans a database row into a Security struct
func (r *SecurityRepository) scanSecurity(rows *sql.Rows) (Security, error) {
	var security Security
	var yahooSymbol, isin, productType, country, fullExchangeName sql.NullString
	var industry, currency, lastSynced, bucketID sql.NullString
	var minPortfolioTarget, maxPortfolioTarget sql.NullFloat64
	var active, allowBuy, allowSell sql.NullInt64
	var createdAt, updatedAt sql.NullString

	err := rows.Scan(
		&security.Symbol,
		&yahooSymbol,
		&isin,
		&security.Name,
		&productType,
		&industry,
		&country,
		&fullExchangeName,
		&security.PriorityMultiplier,
		&security.MinLot,
		&active,
		&allowBuy,
		&allowSell,
		&currency,
		&lastSynced,
		&minPortfolioTarget,
		&maxPortfolioTarget,
		&createdAt,
		&updatedAt,
		&bucketID,
	)
	if err != nil {
		return security, err
	}

	// Handle nullable fields
	if yahooSymbol.Valid {
		security.YahooSymbol = yahooSymbol.String
	}
	if isin.Valid {
		security.ISIN = isin.String
	}
	if productType.Valid {
		security.ProductType = productType.String
	}
	if country.Valid {
		security.Country = country.String
	}
	if fullExchangeName.Valid {
		security.FullExchangeName = fullExchangeName.String
	}
	if industry.Valid {
		security.Industry = industry.String
	}
	if currency.Valid {
		security.Currency = currency.String
	}
	if lastSynced.Valid {
		security.LastSynced = lastSynced.String
	}
	if minPortfolioTarget.Valid {
		security.MinPortfolioTarget = minPortfolioTarget.Float64
	}
	if maxPortfolioTarget.Valid {
		security.MaxPortfolioTarget = maxPortfolioTarget.Float64
	}
	if bucketID.Valid {
		security.BucketID = bucketID.String
	} else {
		security.BucketID = "core"
	}

	// Handle boolean fields (stored as integers in SQLite)
	if active.Valid {
		security.Active = active.Int64 != 0
	}
	if allowBuy.Valid {
		security.AllowBuy = allowBuy.Int64 != 0
	} else {
		security.AllowBuy = true // Default
	}
	if allowSell.Valid {
		security.AllowSell = allowSell.Int64 != 0
	}

	// Normalize symbol
	security.Symbol = strings.ToUpper(strings.TrimSpace(security.Symbol))

	// Default values
	if security.PriorityMultiplier == 0 {
		security.PriorityMultiplier = 1.0
	}
	if security.MinLot == 0 {
		security.MinLot = 1
	}
	if security.BucketID == "" {
		security.BucketID = "core"
	}

	return security, nil
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
