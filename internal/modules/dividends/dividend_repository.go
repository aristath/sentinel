// Package dividends provides repository implementations for managing dividend records.
// This file implements the DividendRepository, which handles dividend records stored in ledger.db.
// Dividends represent dividend payments received and their reinvestment status (DRIP).
package dividends

import (
	"database/sql"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/rs/zerolog"
)

// SecurityProvider defines the interface for getting security information.
// This interface is used to avoid circular dependencies with the universe module.
// It provides symbol-to-ISIN lookups for dividend records.
type SecurityProvider interface {
	GetISINBySymbol(symbol string) (string, error) // Resolve symbol to ISIN
}

// DividendRepository handles dividend database operations for the immutable audit trail.
// Dividends are stored in ledger.db and represent dividend payments received from securities.
// The repository tracks reinvestment status (DRIP), pending bonuses, and bonus clearing.
// After migration 030, ISIN is the primary identifier (replacing symbol).
//
// The repository can optionally use a SecurityProvider to resolve symbols to ISINs
// for backward compatibility.
//
// Faithful translation from Python: app/modules/dividends/database/dividend_repository.py
type DividendRepository struct {
	ledgerDB         *sql.DB          // ledger.db - dividend_history table (immutable audit trail)
	securityProvider SecurityProvider // Optional provider for symbol -> ISIN lookup
	log              zerolog.Logger   // Structured logger
}

// dividendHistoryColumns is the list of columns for the dividend_history table
// Used to avoid SELECT * which can break when schema changes
// Column order must match scanDividend() and scanDividendFromRows() function expectations
const dividendHistoryColumns = `id, symbol, isin, cash_flow_id, amount, currency, amount_eur, payment_date,
reinvested, reinvested_at, reinvested_quantity, pending_bonus, bonus_cleared, cleared_at, created_at`

// NewDividendRepository creates a new dividend repository
func NewDividendRepository(ledgerDB *sql.DB, securityProvider SecurityProvider, log zerolog.Logger) *DividendRepository {
	return &DividendRepository{
		ledgerDB:         ledgerDB,
		securityProvider: securityProvider,
		log:              log.With().Str("repo", "dividend").Logger(),
	}
}

// Create creates a new dividend record in the immutable audit trail.
// This method automatically resolves ISIN from symbol if not provided (via securityProvider).
// Payment date is required and stored as a Unix timestamp.
//
// Parameters:
//   - dividend: DividendRecord object to create (ID and CreatedAt will be populated)
//
// Returns:
//   - error: Error if payment_date is missing or database operation fails
func (r *DividendRepository) Create(dividend *DividendRecord) error {
	now := time.Now().Unix()

	// Ensure ISIN is populated (required after migration)
	// If not provided, try to lookup from securities via provider
	if dividend.ISIN == "" && r.securityProvider != nil {
		isin, err := r.securityProvider.GetISINBySymbol(dividend.Symbol)
		if err == nil {
			dividend.ISIN = isin
		}
	}

	// Use Unix timestamp directly - no string parsing needed
	if dividend.PaymentDate == nil {
		return fmt.Errorf("payment_date is required")
	}
	paymentDateUnix := *dividend.PaymentDate

	query := `
		INSERT INTO dividend_history
		(symbol, isin, cash_flow_id, amount, currency, amount_eur, payment_date,
		 reinvested, reinvested_at, reinvested_quantity, pending_bonus,
		 bonus_cleared, cleared_at, created_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	result, err := r.ledgerDB.Exec(query,
		strings.ToUpper(dividend.Symbol),
		dividend.ISIN,
		nullInt(dividend.CashFlowID),
		dividend.Amount,
		dividend.Currency,
		dividend.AmountEUR,
		paymentDateUnix,
		boolToInt(dividend.Reinvested),
		nullTimeUnix(dividend.ReinvestedAt),
		nullInt(dividend.ReinvestedQuantity),
		dividend.PendingBonus,
		boolToInt(dividend.BonusCleared),
		nullTimeUnix(dividend.ClearedAt),
		now,
	)

	if err != nil {
		return fmt.Errorf("failed to create dividend: %w", err)
	}

	id, err := result.LastInsertId()
	if err != nil {
		return fmt.Errorf("failed to get insert ID: %w", err)
	}

	dividend.ID = int(id)
	createdAt := time.Unix(now, 0).UTC()
	dividend.CreatedAt = &createdAt

	r.log.Info().
		Str("symbol", dividend.Symbol).
		Float64("amount", dividend.Amount).
		Msg("Dividend record created")

	return nil
}

// GetByID retrieves a dividend record by ID
// Faithful translation of Python: async def get_by_id(self, dividend_id: int) -> Optional[DividendRecord]
func (r *DividendRepository) GetByID(id int) (*DividendRecord, error) {
	query := "SELECT " + dividendHistoryColumns + " FROM dividend_history WHERE id = ?"

	row := r.ledgerDB.QueryRow(query, id)
	dividend, err := r.scanDividend(row)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get dividend by ID: %w", err)
	}

	return &dividend, nil
}

// GetByCashFlowID retrieves a dividend record linked to a cash flow
// Faithful translation of Python: async def get_by_cash_flow_id(self, cash_flow_id: int) -> Optional[DividendRecord]
func (r *DividendRepository) GetByCashFlowID(cashFlowID int) (*DividendRecord, error) {
	query := "SELECT " + dividendHistoryColumns + " FROM dividend_history WHERE cash_flow_id = ?"

	row := r.ledgerDB.QueryRow(query, cashFlowID)
	dividend, err := r.scanDividend(row)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get dividend by cash_flow_id: %w", err)
	}

	return &dividend, nil
}

// ExistsForCashFlow checks if a dividend record already exists for a cash flow
// Faithful translation of Python: async def exists_for_cash_flow(self, cash_flow_id: int) -> bool
func (r *DividendRepository) ExistsForCashFlow(cashFlowID int) (bool, error) {
	query := "SELECT 1 FROM dividend_history WHERE cash_flow_id = ? LIMIT 1"

	var exists int
	err := r.ledgerDB.QueryRow(query, cashFlowID).Scan(&exists)
	if errors.Is(err, sql.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, fmt.Errorf("failed to check dividend existence: %w", err)
	}

	return true, nil
}

// GetBySymbol retrieves all dividend records for a symbol (helper method - looks up ISIN first)
// This requires securityProvider to lookup ISIN from securities table
// After migration: prefer GetByISIN for internal operations
func (r *DividendRepository) GetBySymbol(symbol string) ([]DividendRecord, error) {
	// If security provider is available, lookup ISIN first, then query by ISIN
	if r.securityProvider != nil {
		isin, err := r.securityProvider.GetISINBySymbol(symbol)
		if err == nil && isin != "" {
			// Query by ISIN (preferred after migration)
			return r.GetByISIN(isin)
		}
	}

	// Fallback to symbol lookup (for backward compatibility)
	query := `
		SELECT ` + dividendHistoryColumns + ` FROM dividend_history
		WHERE symbol = ?
		ORDER BY payment_date DESC
	`

	rows, err := r.ledgerDB.Query(query, strings.ToUpper(symbol))
	if err != nil {
		return nil, fmt.Errorf("failed to get dividends by symbol: %w", err)
	}
	defer rows.Close()

	var dividends []DividendRecord
	for rows.Next() {
		dividend, err := r.scanDividendFromRows(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan dividend: %w", err)
		}
		dividends = append(dividends, dividend)
	}

	return dividends, nil
}

// GetByISIN retrieves all dividend records for an ISIN.
// This is the preferred method after migration 030 (ISIN is the primary identifier).
// Results are ordered by payment_date descending (most recent first).
//
// Parameters:
//   - isin: Security ISIN
//
// Returns:
//   - []DividendRecord: List of dividend records (ordered by payment_date DESC)
//   - error: Error if query fails
//
// Faithful translation of Python: async def get_by_isin(self, isin: str) -> List[DividendRecord]
func (r *DividendRepository) GetByISIN(isin string) ([]DividendRecord, error) {
	query := `
		SELECT ` + dividendHistoryColumns + ` FROM dividend_history
		WHERE isin = ?
		ORDER BY payment_date DESC
	`

	rows, err := r.ledgerDB.Query(query, strings.ToUpper(isin))
	if err != nil {
		return nil, fmt.Errorf("failed to get dividends by ISIN: %w", err)
	}
	defer rows.Close()

	var dividends []DividendRecord
	for rows.Next() {
		dividend, err := r.scanDividendFromRows(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan dividend: %w", err)
		}
		dividends = append(dividends, dividend)
	}

	return dividends, nil
}

// GetByIdentifier retrieves dividend records by symbol or ISIN
// Faithful translation of Python: async def get_by_identifier(self, identifier: str) -> List[DividendRecord]
func (r *DividendRepository) GetByIdentifier(identifier string) ([]DividendRecord, error) {
	identifier = strings.ToUpper(strings.TrimSpace(identifier))

	// Check if it looks like an ISIN (12 chars, country code + alphanumeric)
	if len(identifier) == 12 && isAlpha(identifier[:2]) {
		dividends, err := r.GetByISIN(identifier)
		if err == nil && len(dividends) > 0 {
			return dividends, nil
		}
	}

	// Try symbol lookup
	return r.GetBySymbol(identifier)
}

// GetAll retrieves all dividend records, optionally limited
// Faithful translation of Python: async def get_all(self, limit: Optional[int] = None) -> List[DividendRecord]
func (r *DividendRepository) GetAll(limit int) ([]DividendRecord, error) {
	var query string
	var rows *sql.Rows
	var err error

	if limit > 0 {
		query = "SELECT " + dividendHistoryColumns + " FROM dividend_history ORDER BY payment_date DESC LIMIT ?"
		rows, err = r.ledgerDB.Query(query, limit)
	} else {
		query = "SELECT " + dividendHistoryColumns + " FROM dividend_history ORDER BY payment_date DESC"
		rows, err = r.ledgerDB.Query(query)
	}

	if err != nil {
		return nil, fmt.Errorf("failed to get all dividends: %w", err)
	}
	defer rows.Close()

	var dividends []DividendRecord
	for rows.Next() {
		dividend, err := r.scanDividendFromRows(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan dividend: %w", err)
		}
		dividends = append(dividends, dividend)
	}

	return dividends, nil
}

// GetPendingBonuses retrieves all pending dividend bonuses by symbol.
// Pending bonuses are dividends that couldn't be fully reinvested (e.g., insufficient amount
// to buy a full share). These accumulate until the security is bought again, at which point
// they are cleared via ClearBonus().
//
// Returns:
//   - map[string]float64: Map of symbol -> total pending bonus amount
//   - error: Error if query fails
//
// Faithful translation of Python: async def get_pending_bonuses(self) -> Dict[str, float]
func (r *DividendRepository) GetPendingBonuses() (map[string]float64, error) {
	query := `
		SELECT symbol, SUM(pending_bonus) as total_bonus
		FROM dividend_history
		WHERE bonus_cleared = 0 AND pending_bonus > 0
		GROUP BY symbol
	`

	rows, err := r.ledgerDB.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to get pending bonuses: %w", err)
	}
	defer rows.Close()

	bonuses := make(map[string]float64)
	for rows.Next() {
		var symbol string
		var totalBonus float64
		if err := rows.Scan(&symbol, &totalBonus); err != nil {
			return nil, fmt.Errorf("failed to scan bonus: %w", err)
		}
		bonuses[symbol] = totalBonus
	}

	return bonuses, nil
}

// GetPendingBonus retrieves pending dividend bonus for a specific symbol
// Faithful translation of Python: async def get_pending_bonus(self, symbol: str) -> float
func (r *DividendRepository) GetPendingBonus(symbol string) (float64, error) {
	query := `
		SELECT COALESCE(SUM(pending_bonus), 0) as total
		FROM dividend_history
		WHERE symbol = ? AND bonus_cleared = 0 AND pending_bonus > 0
	`

	var total float64
	err := r.ledgerDB.QueryRow(query, strings.ToUpper(symbol)).Scan(&total)
	if err != nil {
		return 0, fmt.Errorf("failed to get pending bonus: %w", err)
	}

	return total, nil
}

// MarkReinvested marks a dividend as reinvested (DRIP executed).
// This updates the dividend record to indicate it was used to purchase shares via DRIP.
// The pending_bonus is cleared when a dividend is marked as reinvested.
//
// Parameters:
//   - dividendID: Dividend record ID
//   - quantity: Number of shares purchased with the dividend
//
// Returns:
//   - error: Error if database operation fails
//
// Faithful translation of Python: async def mark_reinvested(self, dividend_id: int, quantity: int) -> None
func (r *DividendRepository) MarkReinvested(dividendID int, quantity int) error {
	now := time.Now().Unix()

	query := `
		UPDATE dividend_history
		SET reinvested = 1,
			reinvested_at = ?,
			reinvested_quantity = ?,
			pending_bonus = 0
		WHERE id = ?
	`

	_, err := r.ledgerDB.Exec(query, now, quantity, dividendID)
	if err != nil {
		return fmt.Errorf("failed to mark dividend as reinvested: %w", err)
	}

	r.log.Info().
		Int("dividend_id", dividendID).
		Int("quantity", quantity).
		Msg("Dividend marked as reinvested")

	return nil
}

// SetPendingBonus sets pending bonus for a dividend that couldn't be reinvested
// Faithful translation of Python: async def set_pending_bonus(self, dividend_id: int, bonus: float) -> None
func (r *DividendRepository) SetPendingBonus(dividendID int, bonus float64) error {
	query := `
		UPDATE dividend_history
		SET pending_bonus = ?
		WHERE id = ?
	`

	_, err := r.ledgerDB.Exec(query, bonus, dividendID)
	if err != nil {
		return fmt.Errorf("failed to set pending bonus: %w", err)
	}

	return nil
}

// ClearBonus clears pending bonuses for a symbol (after security is bought).
// When a security is purchased, any accumulated pending bonuses are cleared.
// This prevents double-counting of bonuses that were already used in the purchase.
//
// Parameters:
//   - symbol: Security symbol
//
// Returns:
//   - int: Number of dividend records updated
//   - error: Error if database operation fails
//
// Faithful translation of Python: async def clear_bonus(self, symbol: str) -> int
func (r *DividendRepository) ClearBonus(symbol string) (int, error) {
	now := time.Now().Unix()

	query := `
		UPDATE dividend_history
		SET bonus_cleared = 1, cleared_at = ?, pending_bonus = 0
		WHERE symbol = ? AND bonus_cleared = 0 AND pending_bonus > 0
	`

	result, err := r.ledgerDB.Exec(query, now, strings.ToUpper(symbol))
	if err != nil {
		return 0, fmt.Errorf("failed to clear bonus: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return 0, fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected > 0 {
		r.log.Info().
			Str("symbol", symbol).
			Int64("records", rowsAffected).
			Msg("Pending bonuses cleared")
	}

	return int(rowsAffected), nil
}

// GetUnreinvestedDividends retrieves dividends that haven't been reinvested yet
// Faithful translation of Python: async def get_unreinvested_dividends(self, min_amount_eur: float = 0.0) -> List[DividendRecord]
func (r *DividendRepository) GetUnreinvestedDividends(minAmountEUR float64) ([]DividendRecord, error) {
	query := `
		SELECT ` + dividendHistoryColumns + ` FROM dividend_history
		WHERE reinvested = 0 AND amount_eur >= ?
		ORDER BY payment_date ASC
	`

	rows, err := r.ledgerDB.Query(query, minAmountEUR)
	if err != nil {
		return nil, fmt.Errorf("failed to get unreinvested dividends: %w", err)
	}
	defer rows.Close()

	var dividends []DividendRecord
	for rows.Next() {
		dividend, err := r.scanDividendFromRows(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan dividend: %w", err)
		}
		dividends = append(dividends, dividend)
	}

	return dividends, nil
}

// GetTotalDividendsBySymbol retrieves total dividends received per symbol (in EUR)
// Faithful translation of Python: async def get_total_dividends_by_symbol(self) -> Dict[str, float]
func (r *DividendRepository) GetTotalDividendsBySymbol() (map[string]float64, error) {
	query := `
		SELECT symbol, SUM(amount_eur) as total
		FROM dividend_history
		GROUP BY symbol
		ORDER BY total DESC
	`

	rows, err := r.ledgerDB.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to get total dividends by symbol: %w", err)
	}
	defer rows.Close()

	totals := make(map[string]float64)
	for rows.Next() {
		var symbol string
		var total float64
		if err := rows.Scan(&symbol, &total); err != nil {
			return nil, fmt.Errorf("failed to scan total: %w", err)
		}
		totals[symbol] = total
	}

	return totals, nil
}

// GetTotalReinvested retrieves total amount of dividends that were reinvested (in EUR)
// Faithful translation of Python: async def get_total_reinvested(self) -> float
func (r *DividendRepository) GetTotalReinvested() (float64, error) {
	query := `
		SELECT COALESCE(SUM(amount_eur), 0) as total
		FROM dividend_history
		WHERE reinvested = 1
	`

	var total float64
	err := r.ledgerDB.QueryRow(query).Scan(&total)
	if err != nil {
		return 0, fmt.Errorf("failed to get total reinvested: %w", err)
	}

	return total, nil
}

// GetReinvestmentRate retrieves dividend reinvestment rate (0.0 to 1.0)
// Faithful translation of Python: async def get_reinvestment_rate(self) -> float
func (r *DividendRepository) GetReinvestmentRate() (float64, error) {
	query := `
		SELECT
			COALESCE(SUM(CASE WHEN reinvested = 1 THEN amount_eur ELSE 0 END), 0) as reinvested,
			COALESCE(SUM(amount_eur), 0) as total
		FROM dividend_history
	`

	var reinvested, total float64
	err := r.ledgerDB.QueryRow(query).Scan(&reinvested, &total)
	if err != nil {
		return 0, fmt.Errorf("failed to get reinvestment rate: %w", err)
	}

	if total == 0 {
		return 0, nil
	}

	return reinvested / total, nil
}

// Helper methods

func (r *DividendRepository) scanDividend(row *sql.Row) (DividendRecord, error) {
	var dividend DividendRecord
	var reinvested, bonusCleared int
	var isin sql.NullString
	var paymentDateUnix, reinvestedAtUnix, clearedAtUnix, createdAtUnix sql.NullInt64
	var cashFlowID, reinvestedQuantity sql.NullInt64

	err := row.Scan(
		&dividend.ID,
		&dividend.Symbol,
		&isin,
		&cashFlowID,
		&dividend.Amount,
		&dividend.Currency,
		&dividend.AmountEUR,
		&paymentDateUnix,
		&reinvested,
		&reinvestedAtUnix,
		&reinvestedQuantity,
		&dividend.PendingBonus,
		&bonusCleared,
		&clearedAtUnix,
		&createdAtUnix,
	)

	if err != nil {
		return dividend, err
	}

	// Convert nullable fields
	if isin.Valid {
		dividend.ISIN = isin.String
	}
	if cashFlowID.Valid {
		id := int(cashFlowID.Int64)
		dividend.CashFlowID = &id
	}
	if paymentDateUnix.Valid {
		dividend.PaymentDate = &paymentDateUnix.Int64
	}
	dividend.Reinvested = reinvested == 1
	if reinvestedAtUnix.Valid {
		t := time.Unix(reinvestedAtUnix.Int64, 0).UTC()
		dividend.ReinvestedAt = &t
	}
	if reinvestedQuantity.Valid {
		qty := int(reinvestedQuantity.Int64)
		dividend.ReinvestedQuantity = &qty
	}
	dividend.BonusCleared = bonusCleared == 1
	if clearedAtUnix.Valid {
		t := time.Unix(clearedAtUnix.Int64, 0).UTC()
		dividend.ClearedAt = &t
	}
	if createdAtUnix.Valid {
		t := time.Unix(createdAtUnix.Int64, 0).UTC()
		dividend.CreatedAt = &t
	}

	return dividend, nil
}

func (r *DividendRepository) scanDividendFromRows(rows *sql.Rows) (DividendRecord, error) {
	var dividend DividendRecord
	var reinvested, bonusCleared int
	var isin sql.NullString
	var paymentDateUnix, reinvestedAtUnix, clearedAtUnix, createdAtUnix sql.NullInt64
	var cashFlowID, reinvestedQuantity sql.NullInt64

	err := rows.Scan(
		&dividend.ID,
		&dividend.Symbol,
		&isin,
		&cashFlowID,
		&dividend.Amount,
		&dividend.Currency,
		&dividend.AmountEUR,
		&paymentDateUnix,
		&reinvested,
		&reinvestedAtUnix,
		&reinvestedQuantity,
		&dividend.PendingBonus,
		&bonusCleared,
		&clearedAtUnix,
		&createdAtUnix,
	)

	if err != nil {
		return dividend, err
	}

	// Convert nullable fields
	if isin.Valid {
		dividend.ISIN = isin.String
	}
	if cashFlowID.Valid {
		id := int(cashFlowID.Int64)
		dividend.CashFlowID = &id
	}
	if paymentDateUnix.Valid {
		dividend.PaymentDate = &paymentDateUnix.Int64
	}
	dividend.Reinvested = reinvested == 1
	if reinvestedAtUnix.Valid {
		t := time.Unix(reinvestedAtUnix.Int64, 0).UTC()
		dividend.ReinvestedAt = &t
	}
	if reinvestedQuantity.Valid {
		qty := int(reinvestedQuantity.Int64)
		dividend.ReinvestedQuantity = &qty
	}
	dividend.BonusCleared = bonusCleared == 1
	if clearedAtUnix.Valid {
		t := time.Unix(clearedAtUnix.Int64, 0).UTC()
		dividend.ClearedAt = &t
	}
	if createdAtUnix.Valid {
		t := time.Unix(createdAtUnix.Int64, 0).UTC()
		dividend.CreatedAt = &t
	}

	return dividend, nil
}

// Helper functions

func nullInt(i *int) sql.NullInt64 {
	if i == nil {
		return sql.NullInt64{Valid: false}
	}
	return sql.NullInt64{Int64: int64(*i), Valid: true}
}

func nullTimeUnix(t *time.Time) sql.NullInt64 {
	if t == nil {
		return sql.NullInt64{Valid: false}
	}
	return sql.NullInt64{Int64: t.Unix(), Valid: true}
}

func boolToInt(b bool) int {
	if b {
		return 1
	}
	return 0
}

func isAlpha(s string) bool {
	for _, r := range s {
		if (r < 'A' || r > 'Z') && (r < 'a' || r > 'z') {
			return false
		}
	}
	return true
}
