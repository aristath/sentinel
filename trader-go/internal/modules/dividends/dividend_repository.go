package dividends

import (
	"database/sql"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/rs/zerolog"
)

// DividendRepository handles dividend database operations
// Faithful translation from Python: app/modules/dividends/database/dividend_repository.py
type DividendRepository struct {
	dividendsDB *sql.DB // dividends.db - dividend_history table
	log         zerolog.Logger
}

// NewDividendRepository creates a new dividend repository
func NewDividendRepository(dividendsDB *sql.DB, log zerolog.Logger) *DividendRepository {
	return &DividendRepository{
		dividendsDB: dividendsDB,
		log:         log.With().Str("repo", "dividend").Logger(),
	}
}

// Create creates a new dividend record
// Faithful translation of Python: async def create(self, dividend: DividendRecord) -> DividendRecord
func (r *DividendRepository) Create(dividend *DividendRecord) error {
	now := time.Now().Format(time.RFC3339)

	query := `
		INSERT INTO dividend_history
		(symbol, isin, cash_flow_id, amount, currency, amount_eur, payment_date,
		 reinvested, reinvested_at, reinvested_quantity, pending_bonus,
		 bonus_cleared, cleared_at, created_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	result, err := r.dividendsDB.Exec(query,
		strings.ToUpper(dividend.Symbol),
		dividend.ISIN,
		nullInt(dividend.CashFlowID),
		dividend.Amount,
		dividend.Currency,
		dividend.AmountEUR,
		dividend.PaymentDate,
		boolToInt(dividend.Reinvested),
		nullTime(dividend.ReinvestedAt),
		nullInt(dividend.ReinvestedQuantity),
		dividend.PendingBonus,
		boolToInt(dividend.BonusCleared),
		nullTime(dividend.ClearedAt),
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
	createdAt, _ := time.Parse(time.RFC3339, now)
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
	query := "SELECT * FROM dividend_history WHERE id = ?"

	row := r.dividendsDB.QueryRow(query, id)
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
	query := "SELECT * FROM dividend_history WHERE cash_flow_id = ?"

	row := r.dividendsDB.QueryRow(query, cashFlowID)
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
	err := r.dividendsDB.QueryRow(query, cashFlowID).Scan(&exists)
	if errors.Is(err, sql.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, fmt.Errorf("failed to check dividend existence: %w", err)
	}

	return true, nil
}

// GetBySymbol retrieves all dividend records for a symbol
// Faithful translation of Python: async def get_by_symbol(self, symbol: str) -> List[DividendRecord]
func (r *DividendRepository) GetBySymbol(symbol string) ([]DividendRecord, error) {
	query := `
		SELECT * FROM dividend_history
		WHERE symbol = ?
		ORDER BY payment_date DESC
	`

	rows, err := r.dividendsDB.Query(query, strings.ToUpper(symbol))
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

// GetByISIN retrieves all dividend records for an ISIN
// Faithful translation of Python: async def get_by_isin(self, isin: str) -> List[DividendRecord]
func (r *DividendRepository) GetByISIN(isin string) ([]DividendRecord, error) {
	query := `
		SELECT * FROM dividend_history
		WHERE isin = ?
		ORDER BY payment_date DESC
	`

	rows, err := r.dividendsDB.Query(query, strings.ToUpper(isin))
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
		query = "SELECT * FROM dividend_history ORDER BY payment_date DESC LIMIT ?"
		rows, err = r.dividendsDB.Query(query, limit)
	} else {
		query = "SELECT * FROM dividend_history ORDER BY payment_date DESC"
		rows, err = r.dividendsDB.Query(query)
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

// GetPendingBonuses retrieves all pending dividend bonuses by symbol
// Faithful translation of Python: async def get_pending_bonuses(self) -> Dict[str, float]
func (r *DividendRepository) GetPendingBonuses() (map[string]float64, error) {
	query := `
		SELECT symbol, SUM(pending_bonus) as total_bonus
		FROM dividend_history
		WHERE bonus_cleared = 0 AND pending_bonus > 0
		GROUP BY symbol
	`

	rows, err := r.dividendsDB.Query(query)
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
	err := r.dividendsDB.QueryRow(query, strings.ToUpper(symbol)).Scan(&total)
	if err != nil {
		return 0, fmt.Errorf("failed to get pending bonus: %w", err)
	}

	return total, nil
}

// MarkReinvested marks a dividend as reinvested (DRIP executed)
// Faithful translation of Python: async def mark_reinvested(self, dividend_id: int, quantity: int) -> None
func (r *DividendRepository) MarkReinvested(dividendID int, quantity int) error {
	now := time.Now().Format(time.RFC3339)

	query := `
		UPDATE dividend_history
		SET reinvested = 1,
			reinvested_at = ?,
			reinvested_quantity = ?,
			pending_bonus = 0
		WHERE id = ?
	`

	_, err := r.dividendsDB.Exec(query, now, quantity, dividendID)
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

	_, err := r.dividendsDB.Exec(query, bonus, dividendID)
	if err != nil {
		return fmt.Errorf("failed to set pending bonus: %w", err)
	}

	return nil
}

// ClearBonus clears pending bonuses for a symbol (after security is bought)
// Faithful translation of Python: async def clear_bonus(self, symbol: str) -> int
func (r *DividendRepository) ClearBonus(symbol string) (int, error) {
	now := time.Now().Format(time.RFC3339)

	query := `
		UPDATE dividend_history
		SET bonus_cleared = 1, cleared_at = ?, pending_bonus = 0
		WHERE symbol = ? AND bonus_cleared = 0 AND pending_bonus > 0
	`

	result, err := r.dividendsDB.Exec(query, now, strings.ToUpper(symbol))
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
		SELECT * FROM dividend_history
		WHERE reinvested = 0 AND amount_eur >= ?
		ORDER BY payment_date ASC
	`

	rows, err := r.dividendsDB.Query(query, minAmountEUR)
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

	rows, err := r.dividendsDB.Query(query)
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
	err := r.dividendsDB.QueryRow(query).Scan(&total)
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
	err := r.dividendsDB.QueryRow(query).Scan(&reinvested, &total)
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
	var isin, reinvestedAt, clearedAt, createdAt sql.NullString
	var cashFlowID, reinvestedQuantity sql.NullInt64

	err := row.Scan(
		&dividend.ID,
		&dividend.Symbol,
		&isin,
		&cashFlowID,
		&dividend.Amount,
		&dividend.Currency,
		&dividend.AmountEUR,
		&dividend.PaymentDate,
		&reinvested,
		&reinvestedAt,
		&reinvestedQuantity,
		&dividend.PendingBonus,
		&bonusCleared,
		&clearedAt,
		&createdAt,
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
	dividend.Reinvested = reinvested == 1
	if reinvestedAt.Valid {
		t, _ := time.Parse(time.RFC3339, reinvestedAt.String)
		dividend.ReinvestedAt = &t
	}
	if reinvestedQuantity.Valid {
		qty := int(reinvestedQuantity.Int64)
		dividend.ReinvestedQuantity = &qty
	}
	dividend.BonusCleared = bonusCleared == 1
	if clearedAt.Valid {
		t, _ := time.Parse(time.RFC3339, clearedAt.String)
		dividend.ClearedAt = &t
	}
	if createdAt.Valid {
		t, _ := time.Parse(time.RFC3339, createdAt.String)
		dividend.CreatedAt = &t
	}

	return dividend, nil
}

func (r *DividendRepository) scanDividendFromRows(rows *sql.Rows) (DividendRecord, error) {
	var dividend DividendRecord
	var reinvested, bonusCleared int
	var isin, reinvestedAt, clearedAt, createdAt sql.NullString
	var cashFlowID, reinvestedQuantity sql.NullInt64

	err := rows.Scan(
		&dividend.ID,
		&dividend.Symbol,
		&isin,
		&cashFlowID,
		&dividend.Amount,
		&dividend.Currency,
		&dividend.AmountEUR,
		&dividend.PaymentDate,
		&reinvested,
		&reinvestedAt,
		&reinvestedQuantity,
		&dividend.PendingBonus,
		&bonusCleared,
		&clearedAt,
		&createdAt,
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
	dividend.Reinvested = reinvested == 1
	if reinvestedAt.Valid {
		t, _ := time.Parse(time.RFC3339, reinvestedAt.String)
		dividend.ReinvestedAt = &t
	}
	if reinvestedQuantity.Valid {
		qty := int(reinvestedQuantity.Int64)
		dividend.ReinvestedQuantity = &qty
	}
	dividend.BonusCleared = bonusCleared == 1
	if clearedAt.Valid {
		t, _ := time.Parse(time.RFC3339, clearedAt.String)
		dividend.ClearedAt = &t
	}
	if createdAt.Valid {
		t, _ := time.Parse(time.RFC3339, createdAt.String)
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

func nullTime(t *time.Time) sql.NullString {
	if t == nil {
		return sql.NullString{Valid: false}
	}
	return sql.NullString{String: t.Format(time.RFC3339), Valid: true}
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
