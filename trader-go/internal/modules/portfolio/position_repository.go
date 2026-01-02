package portfolio

import (
	"database/sql"
	"fmt"
	"strings"
	"time"

	"github.com/rs/zerolog"
)

// PositionRepository handles position database operations
// Faithful translation from Python: app/modules/portfolio/database/position_repository.py
type PositionRepository struct {
	stateDB  *sql.DB // state.db - positions
	configDB *sql.DB // config.db - securities
	log      zerolog.Logger
}

// NewPositionRepository creates a new position repository
func NewPositionRepository(stateDB, configDB *sql.DB, log zerolog.Logger) *PositionRepository {
	return &PositionRepository{
		stateDB:  stateDB,
		configDB: configDB,
		log:      log.With().Str("repo", "position").Logger(),
	}
}

// GetAll returns all positions
// Faithful translation of Python: async def get_all(self) -> List[Position]
func (r *PositionRepository) GetAll() ([]Position, error) {
	query := "SELECT * FROM positions"

	rows, err := r.stateDB.Query(query)
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
	// Get positions from state.db
	positionRows, err := r.stateDB.Query("SELECT * FROM positions")
	if err != nil {
		return nil, fmt.Errorf("failed to query positions: %w", err)
	}
	defer positionRows.Close()

	// Read all positions into map
	positionsBySymbol := make(map[string]Position)
	for positionRows.Next() {
		pos, err := r.scanPosition(positionRows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan position: %w", err)
		}
		positionsBySymbol[pos.Symbol] = pos
	}

	if err := positionRows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating positions: %w", err)
	}

	if len(positionsBySymbol) == 0 {
		return []PositionWithSecurity{}, nil
	}

	// Get securities from config.db
	securityRows, err := r.configDB.Query(`
		SELECT symbol, name, country, fullExchangeName, industry, currency
		FROM securities
		WHERE active = 1
	`)
	if err != nil {
		return nil, fmt.Errorf("failed to query securities: %w", err)
	}
	defer securityRows.Close()

	// Read securities into map
	type SecurityInfo struct {
		Symbol           string
		Name             string
		Country          sql.NullString
		FullExchangeName sql.NullString
		Industry         sql.NullString
		Currency         sql.NullString
	}

	securitiesBySymbol := make(map[string]SecurityInfo)
	for securityRows.Next() {
		var sec SecurityInfo
		if err := securityRows.Scan(
			&sec.Symbol,
			&sec.Name,
			&sec.Country,
			&sec.FullExchangeName,
			&sec.Industry,
			&sec.Currency,
		); err != nil {
			return nil, fmt.Errorf("failed to scan security: %w", err)
		}
		securitiesBySymbol[sec.Symbol] = sec
	}

	if err := securityRows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating securities: %w", err)
	}

	// Merge position and security data
	var result []PositionWithSecurity
	for symbol, pos := range positionsBySymbol {
		sec, found := securitiesBySymbol[symbol]

		merged := PositionWithSecurity{
			Symbol:         pos.Symbol,
			Quantity:       pos.Quantity,
			AvgPrice:       pos.AvgPrice,
			CurrentPrice:   pos.CurrentPrice,
			Currency:       pos.Currency,
			CurrencyRate:   pos.CurrencyRate,
			MarketValueEUR: pos.MarketValueEUR,
			LastUpdated:    pos.LastUpdated,
			BucketID:       pos.BucketID,
		}

		if found {
			merged.StockName = sec.Name
			if sec.Country.Valid {
				merged.Country = sec.Country.String
			}
			if sec.FullExchangeName.Valid {
				merged.FullExchangeName = sec.FullExchangeName.String
			}
			if sec.Industry.Valid {
				merged.Industry = sec.Industry.String
			}
		} else {
			// Fallback: use symbol as name if security not found
			merged.StockName = symbol
		}

		result = append(result, merged)
	}

	return result, nil
}

// GetBySymbol returns a position by symbol
// Faithful translation of Python: async def get_by_symbol(self, symbol: str) -> Optional[Position]
func (r *PositionRepository) GetBySymbol(symbol string) (*Position, error) {
	query := "SELECT * FROM positions WHERE symbol = ?"

	rows, err := r.stateDB.Query(query, strings.ToUpper(strings.TrimSpace(symbol)))
	if err != nil {
		return nil, fmt.Errorf("failed to query position by symbol: %w", err)
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

// GetByISIN returns a position by ISIN
// Faithful translation of Python: async def get_by_isin(self, isin: str) -> Optional[Position]
func (r *PositionRepository) GetByISIN(isin string) (*Position, error) {
	query := "SELECT * FROM positions WHERE isin = ?"

	rows, err := r.stateDB.Query(query, strings.ToUpper(strings.TrimSpace(isin)))
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
	err := r.stateDB.QueryRow(query).Scan(&count)
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
	err := r.stateDB.QueryRow(query).Scan(&total)
	if err != nil {
		return 0.0, fmt.Errorf("failed to get total value: %w", err)
	}

	return total, nil
}

// scanPosition scans a database row into a Position struct
func (r *PositionRepository) scanPosition(rows *sql.Rows) (Position, error) {
	var pos Position
	var currentPrice, marketValueEUR, costBasisEUR sql.NullFloat64
	var unrealizedPnL, unrealizedPnLPct sql.NullFloat64
	var lastUpdated, firstBoughtAt, lastSoldAt sql.NullString
	var isin sql.NullString
	var bucketID sql.NullString

	err := rows.Scan(
		&pos.Symbol,       // 1
		&pos.Quantity,     // 2
		&pos.AvgPrice,     // 3
		&currentPrice,     // 4
		&pos.Currency,     // 5
		&pos.CurrencyRate, // 6
		&marketValueEUR,   // 7
		&costBasisEUR,     // 8
		&unrealizedPnL,    // 9
		&unrealizedPnLPct, // 10
		&lastUpdated,      // 11
		&firstBoughtAt,    // 12
		&lastSoldAt,       // 13
		&isin,             // 14
		&bucketID,         // 15
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
	if lastUpdated.Valid {
		pos.LastUpdated = lastUpdated.String
	}
	if firstBoughtAt.Valid {
		pos.FirstBoughtAt = firstBoughtAt.String
	}
	if lastSoldAt.Valid {
		pos.LastSoldAt = lastSoldAt.String
	}
	if isin.Valid {
		pos.ISIN = isin.String
	}
	if bucketID.Valid {
		pos.BucketID = bucketID.String
	} else {
		pos.BucketID = "core"
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

	// Default bucket_id if empty
	if pos.BucketID == "" {
		pos.BucketID = "core"
	}

	return pos, nil
}

// Upsert inserts or updates a position
// Faithful translation of Python: async def upsert(self, position: Position) -> None
func (r *PositionRepository) Upsert(position Position) error {
	now := time.Now().Format(time.RFC3339)

	// Normalize symbol
	position.Symbol = strings.ToUpper(strings.TrimSpace(position.Symbol))

	// Set last_updated if not provided
	lastUpdated := position.LastUpdated
	if lastUpdated == "" {
		lastUpdated = now
	}

	// Begin transaction
	tx, err := r.stateDB.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	query := `
		INSERT OR REPLACE INTO positions
		(symbol, quantity, avg_price, current_price, currency,
		 currency_rate, market_value_eur, cost_basis_eur,
		 unrealized_pnl, unrealized_pnl_pct, last_updated,
		 first_bought_at, last_sold_at, isin, bucket_id)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	_, err = tx.Exec(query,
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
		lastUpdated,
		nullString(position.FirstBoughtAt),
		nullString(position.LastSoldAt),
		nullString(position.ISIN),
		position.BucketID,
	)
	if err != nil {
		return fmt.Errorf("failed to upsert position: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	r.log.Info().Str("symbol", position.Symbol).Msg("Position upserted")
	return nil
}

// Delete deletes a specific position
// Faithful translation of Python: async def delete(self, symbol: str) -> None
func (r *PositionRepository) Delete(symbol string) error {
	symbol = strings.ToUpper(strings.TrimSpace(symbol))

	// Begin transaction
	tx, err := r.stateDB.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	query := "DELETE FROM positions WHERE symbol = ?"
	result, err := tx.Exec(query, symbol)
	if err != nil {
		return fmt.Errorf("failed to delete position: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	r.log.Info().Str("symbol", symbol).Int64("rows_affected", rowsAffected).Msg("Position deleted")
	return nil
}

// DeleteAll deletes all positions (used during sync)
// Faithful translation of Python: async def delete_all(self) -> None
func (r *PositionRepository) DeleteAll() error {
	// Begin transaction
	tx, err := r.stateDB.Begin()
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

// UpdatePrice updates current price and recalculates market value and P&L
// Faithful translation of Python: async def update_price(self, symbol: str, price: float, currency_rate: float = 1.0)
func (r *PositionRepository) UpdatePrice(symbol string, price float64, currencyRate float64) error {
	symbol = strings.ToUpper(strings.TrimSpace(symbol))
	now := time.Now().Format(time.RFC3339)

	if currencyRate == 0 {
		currencyRate = 1.0
	}

	// Begin transaction
	tx, err := r.stateDB.Begin()
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
		WHERE symbol = ?
	`

	result, err := tx.Exec(query,
		price,        // current_price
		price,        // for market_value_eur calculation
		currencyRate, // for market_value_eur calculation
		price,        // for unrealized_pnl calculation
		currencyRate, // for unrealized_pnl calculation
		price,        // for unrealized_pnl_pct calculation
		now,          // last_updated
		symbol,       // WHERE symbol
	)
	if err != nil {
		return fmt.Errorf("failed to update price: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	r.log.Debug().
		Str("symbol", symbol).
		Float64("price", price).
		Float64("currency_rate", currencyRate).
		Int64("rows_affected", rowsAffected).
		Msg("Position price updated")

	return nil
}

// UpdateLastSoldAt updates the last_sold_at timestamp after a sell
// Faithful translation of Python: async def update_last_sold_at(self, symbol: str) -> None
func (r *PositionRepository) UpdateLastSoldAt(symbol string) error {
	symbol = strings.ToUpper(strings.TrimSpace(symbol))
	now := time.Now().Format(time.RFC3339)

	// Begin transaction
	tx, err := r.stateDB.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	query := "UPDATE positions SET last_sold_at = ? WHERE symbol = ?"
	result, err := tx.Exec(query, now, symbol)
	if err != nil {
		return fmt.Errorf("failed to update last_sold_at: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	r.log.Debug().Str("symbol", symbol).Int64("rows_affected", rowsAffected).Msg("Position last_sold_at updated")
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

func nullInt64(val int) sql.NullInt64 {
	if val == 0 {
		return sql.NullInt64{Valid: false}
	}
	return sql.NullInt64{Int64: int64(val), Valid: true}
}
