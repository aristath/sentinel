package portfolio

import (
	"database/sql"
	"fmt"
	"strings"
	"time"

	"github.com/rs/zerolog"
)

// SecurityInfo represents security information needed for positions
type SecurityInfo struct {
	ISIN             string
	Symbol           string
	Name             string
	Geography        string
	FullExchangeName string
	Industry         string
	Currency         string
	AllowSell        bool
}

// SecurityProvider defines the contract for getting security information
// Defined here to avoid import cycle with universe package
type SecurityProvider interface {
	GetAllActive() ([]SecurityInfo, error)
	GetAllActiveTradable() ([]SecurityInfo, error)
	GetISINBySymbol(symbol string) (string, error)
}

// PositionRepository handles position database operations
// Faithful translation from Python: app/modules/portfolio/database/position_repository.py
type PositionRepository struct {
	portfolioDB      *sql.DB          // portfolio.db - positions
	universeDB       *sql.DB          // universe.db - securities
	securityProvider SecurityProvider // Optional: for override support
	log              zerolog.Logger
}

// NewPositionRepository creates a new position repository
func NewPositionRepository(
	portfolioDB, universeDB *sql.DB,
	securityProvider SecurityProvider,
	log zerolog.Logger,
) *PositionRepository {
	return &PositionRepository{
		portfolioDB:      portfolioDB,
		universeDB:       universeDB,
		securityProvider: securityProvider,
		log:              log.With().Str("repo", "position").Logger(),
	}
}

// GetAll returns all positions
// Faithful translation of Python: async def get_all(self) -> List[Position]
// Column order after migration: isin, symbol, quantity, avg_price, ...
func (r *PositionRepository) GetAll() ([]Position, error) {
	query := `SELECT isin, symbol, quantity, avg_price, current_price, currency,
		currency_rate, market_value_eur, cost_basis_eur, unrealized_pnl,
		unrealized_pnl_pct, last_updated, first_bought, last_sold
		FROM positions`

	rows, err := r.portfolioDB.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query positions: %w", err)
	}
	defer rows.Close()

	var positions []Position
	for rows.Next() {
		pos, err := r.scanPosition(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan position: %w", err)
		}
		positions = append(positions, pos)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating positions: %w", err)
	}

	return positions, nil
}

// GetWithSecurityInfo returns all positions with security info joined
// Faithful translation of Python: async def get_with_security_info(self) -> List[Dict]
// Note: This method accesses both state.db (positions) and config.db (securities)
func (r *PositionRepository) GetWithSecurityInfo() ([]PositionWithSecurity, error) {
	// Get positions from portfolio.db
	// Column order after migration: isin, symbol, quantity, avg_price, ...
	positionRows, err := r.portfolioDB.Query(`SELECT isin, symbol, quantity, avg_price, current_price, currency,
		currency_rate, market_value_eur, cost_basis_eur, unrealized_pnl,
		unrealized_pnl_pct, last_updated, first_bought, last_sold
		FROM positions`)
	if err != nil {
		return nil, fmt.Errorf("failed to query positions: %w", err)
	}
	defer positionRows.Close()

	// Read all positions into map (use ISIN as key)
	positionsByISIN := make(map[string]Position)
	for positionRows.Next() {
		pos, err := r.scanPosition(positionRows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan position: %w", err)
		}
		// Use ISIN as map key (primary identifier)
		if pos.ISIN != "" {
			positionsByISIN[pos.ISIN] = pos
		} else {
			// Fallback to symbol if ISIN is missing (shouldn't happen after migration)
			r.log.Warn().Str("symbol", pos.Symbol).Msg("Position has no ISIN, using symbol as key")
			positionsByISIN[pos.Symbol] = pos
		}
	}

	if err := positionRows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating positions: %w", err)
	}

	if len(positionsByISIN) == 0 {
		return []PositionWithSecurity{}, nil
	}

	// Get securities with overrides applied (SecurityProvider is required)
	securities, err := r.securityProvider.GetAllActive()
	if err != nil {
		return nil, fmt.Errorf("failed to get securities with overrides: %w", err)
	}

	// Build lookup map
	securitiesByISIN := make(map[string]SecurityInfo)
	for _, sec := range securities {
		securitiesByISIN[sec.ISIN] = sec
	}

	// Merge position and security data
	var result []PositionWithSecurity
	for isin, pos := range positionsByISIN {
		sec, found := securitiesByISIN[isin]

		merged := PositionWithSecurity{
			Symbol:         pos.Symbol,
			Quantity:       pos.Quantity,
			AvgPrice:       pos.AvgPrice,
			CurrentPrice:   pos.CurrentPrice,
			Currency:       pos.Currency,
			CurrencyRate:   pos.CurrencyRate,
			MarketValueEUR: pos.MarketValueEUR,
			LastUpdated:    pos.LastUpdated,
		}

		if found {
			merged.StockName = sec.Name      // Respects name overrides
			merged.AllowSell = sec.AllowSell // Respects allow_sell overrides
			merged.Geography = sec.Geography // Respects geography overrides
			merged.Industry = sec.Industry   // Respects industry overrides
			merged.FullExchangeName = sec.FullExchangeName
		} else {
			// Fallback: use symbol as name if security not found
			merged.StockName = pos.Symbol
			merged.AllowSell = true // Default to allowing sell (system default)
		}

		result = append(result, merged)
	}

	return result, nil
}

// GetBySymbol returns a position by symbol (helper method - looks up ISIN first)
// This requires securityProvider to lookup ISIN from securities table
func (r *PositionRepository) GetBySymbol(symbol string) (*Position, error) {
	// Lookup ISIN from securities via provider
	if r.securityProvider == nil {
		return nil, fmt.Errorf("security provider not available for ISIN lookup")
	}

	isin, err := r.securityProvider.GetISINBySymbol(symbol)
	if err != nil {
		// Security not found
		return nil, nil
	}

	if isin == "" {
		return nil, nil // No ISIN found
	}

	// Query position by ISIN
	return r.GetByISIN(isin)
}

// GetByISIN returns a position by ISIN (primary method)
// After migration: isin is PRIMARY KEY
func (r *PositionRepository) GetByISIN(isin string) (*Position, error) {
	// Column order after migration: isin, symbol, quantity, avg_price, ...
	query := `SELECT isin, symbol, quantity, avg_price, current_price, currency,
		currency_rate, market_value_eur, cost_basis_eur, unrealized_pnl,
		unrealized_pnl_pct, last_updated, first_bought, last_sold
		FROM positions WHERE isin = ?`

	rows, err := r.portfolioDB.Query(query, strings.ToUpper(strings.TrimSpace(isin)))
	if err != nil {
		return nil, fmt.Errorf("failed to query position by ISIN: %w", err)
	}
	defer rows.Close()

	if !rows.Next() {
		return nil, nil // Position not found
	}

	pos, err := r.scanPosition(rows)
	if err != nil {
		return nil, fmt.Errorf("failed to scan position: %w", err)
	}

	return &pos, nil
}

// GetByIdentifier returns a position by symbol or ISIN (smart lookup)
// Faithful translation of Python: async def get_by_identifier(self, identifier: str) -> Optional[Position]
func (r *PositionRepository) GetByIdentifier(identifier string) (*Position, error) {
	identifier = strings.ToUpper(strings.TrimSpace(identifier))

	// Check if it looks like an ISIN (12 chars, starts with 2 letters)
	if len(identifier) == 12 && len(identifier) >= 2 {
		firstTwo := identifier[:2]
		if (firstTwo[0] >= 'A' && firstTwo[0] <= 'Z') && (firstTwo[1] >= 'A' && firstTwo[1] <= 'Z') {
			// Try ISIN lookup first
			pos, err := r.GetByISIN(identifier)
			if err != nil {
				return nil, err
			}
			if pos != nil {
				return pos, nil
			}
		}
	}

	// Fall back to symbol lookup
	return r.GetBySymbol(identifier)
}

// GetCount returns the total number of positions
// Faithful translation of Python: async def get_count(self) -> int
func (r *PositionRepository) GetCount() (int, error) {
	query := "SELECT COUNT(*) as count FROM positions"

	var count int
	err := r.portfolioDB.QueryRow(query).Scan(&count)
	if err != nil {
		return 0, fmt.Errorf("failed to get position count: %w", err)
	}

	return count, nil
}

// GetTotalValue returns the total portfolio value in EUR
// Faithful translation of Python: async def get_total_value(self) -> float
func (r *PositionRepository) GetTotalValue() (float64, error) {
	query := "SELECT COALESCE(SUM(market_value_eur), 0) as total FROM positions"

	var total float64
	err := r.portfolioDB.QueryRow(query).Scan(&total)
	if err != nil {
		return 0.0, fmt.Errorf("failed to get total value: %w", err)
	}

	return total, nil
}

// scanPosition scans a database row into a Position struct
// Column order after migration: isin, symbol, quantity, avg_price, ...
func (r *PositionRepository) scanPosition(rows *sql.Rows) (Position, error) {
	var pos Position
	var isin sql.NullString
	var currentPrice, marketValueEUR, costBasisEUR sql.NullFloat64
	var unrealizedPnL, unrealizedPnLPct sql.NullFloat64
	var lastUpdatedUnix, firstBoughtAtUnix, lastSoldAtUnix sql.NullInt64

	// Column order after migration: isin, symbol, quantity, avg_price, current_price, currency,
	// currency_rate, market_value_eur, cost_basis_eur, unrealized_pnl, unrealized_pnl_pct,
	// last_updated, first_bought, last_sold
	err := rows.Scan(
		&isin,              // 1: isin (PRIMARY KEY)
		&pos.Symbol,        // 2: symbol
		&pos.Quantity,      // 3: quantity
		&pos.AvgPrice,      // 4: avg_price
		&currentPrice,      // 5: current_price
		&pos.Currency,      // 6: currency
		&pos.CurrencyRate,  // 7: currency_rate
		&marketValueEUR,    // 8: market_value_eur
		&costBasisEUR,      // 9: cost_basis_eur
		&unrealizedPnL,     // 10: unrealized_pnl
		&unrealizedPnLPct,  // 11: unrealized_pnl_pct
		&lastUpdatedUnix,   // 12: last_updated (Unix timestamp)
		&firstBoughtAtUnix, // 13: first_bought (Unix timestamp)
		&lastSoldAtUnix,    // 14: last_sold (Unix timestamp)
	)
	if err != nil {
		return pos, err
	}

	// Handle nullable fields
	if currentPrice.Valid {
		pos.CurrentPrice = currentPrice.Float64
	}
	if marketValueEUR.Valid {
		pos.MarketValueEUR = marketValueEUR.Float64
	}
	if costBasisEUR.Valid {
		pos.CostBasisEUR = costBasisEUR.Float64
	}
	if unrealizedPnL.Valid {
		pos.UnrealizedPnL = unrealizedPnL.Float64
	}
	if unrealizedPnLPct.Valid {
		pos.UnrealizedPnLPct = unrealizedPnLPct.Float64
	}
	if lastUpdatedUnix.Valid {
		pos.LastUpdated = &lastUpdatedUnix.Int64
	}
	if firstBoughtAtUnix.Valid {
		pos.FirstBoughtAt = &firstBoughtAtUnix.Int64
	}
	if lastSoldAtUnix.Valid {
		pos.LastSoldAt = &lastSoldAtUnix.Int64
	}
	if isin.Valid {
		pos.ISIN = isin.String
	}

	// Normalize symbol
	pos.Symbol = strings.ToUpper(strings.TrimSpace(pos.Symbol))

	// Default currency if empty
	if pos.Currency == "" {
		pos.Currency = "EUR"
	}

	// Default currency rate if zero
	if pos.CurrencyRate == 0 {
		pos.CurrencyRate = 1.0
	}

	return pos, nil
}

// Upsert inserts or updates a position
// After migration: isin is PRIMARY KEY
func (r *PositionRepository) Upsert(position Position) error {
	now := time.Now().Unix()

	// Normalize symbol
	position.Symbol = strings.ToUpper(strings.TrimSpace(position.Symbol))

	// ISIN is required (PRIMARY KEY)
	if position.ISIN == "" {
		return fmt.Errorf("ISIN is required for position upsert")
	}
	position.ISIN = strings.ToUpper(strings.TrimSpace(position.ISIN))

	// Use Unix timestamps directly - no string parsing needed
	var lastUpdatedUnix int64
	if position.LastUpdated != nil {
		lastUpdatedUnix = *position.LastUpdated
	} else {
		lastUpdatedUnix = now
	}

	var firstBoughtUnix sql.NullInt64
	if position.FirstBoughtAt != nil {
		firstBoughtUnix = sql.NullInt64{Int64: *position.FirstBoughtAt, Valid: true}
	}

	var lastSoldUnix sql.NullInt64
	if position.LastSoldAt != nil {
		lastSoldUnix = sql.NullInt64{Int64: *position.LastSoldAt, Valid: true}
	}

	// Begin transaction
	tx, err := r.portfolioDB.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	// Column order after migration: isin, symbol, quantity, avg_price, ...
	query := `
		INSERT OR REPLACE INTO positions
		(isin, symbol, quantity, avg_price, current_price, currency,
		 currency_rate, market_value_eur, cost_basis_eur,
		 unrealized_pnl, unrealized_pnl_pct, last_updated,
		 first_bought, last_sold)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	_, err = tx.Exec(query,
		position.ISIN,
		position.Symbol,
		position.Quantity,
		position.AvgPrice,
		nullFloat64(position.CurrentPrice),
		position.Currency,
		position.CurrencyRate,
		nullFloat64(position.MarketValueEUR),
		nullFloat64(position.CostBasisEUR),
		nullFloat64(position.UnrealizedPnL),
		nullFloat64(position.UnrealizedPnLPct),
		lastUpdatedUnix,
		firstBoughtUnix,
		lastSoldUnix,
	)
	if err != nil {
		return fmt.Errorf("failed to upsert position: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	r.log.Info().Str("isin", position.ISIN).Str("symbol", position.Symbol).Msg("Position upserted")
	return nil
}

// Delete deletes a specific position by ISIN
// Changed from symbol to ISIN as primary identifier
func (r *PositionRepository) Delete(isin string) error {
	isin = strings.ToUpper(strings.TrimSpace(isin))

	// Begin transaction
	tx, err := r.portfolioDB.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	query := "DELETE FROM positions WHERE isin = ?"
	result, err := tx.Exec(query, isin)
	if err != nil {
		return fmt.Errorf("failed to delete position: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	r.log.Info().Str("isin", isin).Int64("rows_affected", rowsAffected).Msg("Position deleted")
	return nil
}

// DeleteAll deletes all positions (used during sync)
// Faithful translation of Python: async def delete_all(self) -> None
func (r *PositionRepository) DeleteAll() error {
	// Begin transaction
	tx, err := r.portfolioDB.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	query := "DELETE FROM positions"
	result, err := tx.Exec(query)
	if err != nil {
		return fmt.Errorf("failed to delete all positions: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	r.log.Warn().Int64("rows_affected", rowsAffected).Msg("All positions deleted")
	return nil
}

// UpdatePrice updates current price and recalculates market value and P&L by ISIN
// Changed from symbol to ISIN as primary identifier
func (r *PositionRepository) UpdatePrice(isin string, price float64, currencyRate float64) error {
	isin = strings.ToUpper(strings.TrimSpace(isin))
	now := time.Now().Unix()

	if currencyRate == 0 {
		currencyRate = 1.0
	}

	// Begin transaction
	tx, err := r.portfolioDB.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	// SQL matches Python exactly - calculates market_value_eur, unrealized_pnl, unrealized_pnl_pct
	query := `
		UPDATE positions SET
			current_price = ?,
			market_value_eur = quantity * ? / ?,
			unrealized_pnl = (? - avg_price) * quantity / ?,
			unrealized_pnl_pct = CASE
				WHEN avg_price > 0 THEN ((? / avg_price) - 1) * 100
				ELSE 0
			END,
			last_updated = ?
		WHERE isin = ?
	`

	result, err := tx.Exec(query,
		price,        // current_price
		price,        // for market_value_eur calculation
		currencyRate, // for market_value_eur calculation
		price,        // for unrealized_pnl calculation
		currencyRate, // for unrealized_pnl calculation
		price,        // for unrealized_pnl_pct calculation
		now,          // last_updated
		isin,         // WHERE isin
	)
	if err != nil {
		return fmt.Errorf("failed to update price: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	r.log.Debug().
		Str("isin", isin).
		Float64("price", price).
		Float64("currency_rate", currencyRate).
		Int64("rows_affected", rowsAffected).
		Msg("Position price updated")

	return nil
}

// UpdateLastSoldAt updates the last_sold_at timestamp after a sell by ISIN
// Changed from symbol to ISIN as primary identifier
func (r *PositionRepository) UpdateLastSoldAt(isin string) error {
	isin = strings.ToUpper(strings.TrimSpace(isin))
	// Store as Unix timestamp at midnight UTC (date only)
	now := time.Date(time.Now().Year(), time.Now().Month(), time.Now().Day(), 0, 0, 0, 0, time.UTC).Unix()

	// Begin transaction
	tx, err := r.portfolioDB.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	query := "UPDATE positions SET last_sold = ? WHERE isin = ?"
	result, err := tx.Exec(query, now, isin)
	if err != nil {
		return fmt.Errorf("failed to update last_sold_at: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	r.log.Debug().Str("isin", isin).Int64("rows_affected", rowsAffected).Msg("Position last_sold_at updated")
	return nil
}

// Helper functions for nullable types

func nullFloat64(val float64) sql.NullFloat64 {
	if val == 0 {
		return sql.NullFloat64{Valid: false}
	}
	return sql.NullFloat64{Float64: val, Valid: true}
}

func nullString(val string) sql.NullString {
	if val == "" {
		return sql.NullString{Valid: false}
	}
	return sql.NullString{String: val, Valid: true}
}
