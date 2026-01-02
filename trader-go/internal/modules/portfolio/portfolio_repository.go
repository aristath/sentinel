package portfolio

import (
	"database/sql"
	"errors"
	"fmt"
	"time"

	"github.com/rs/zerolog"
)

// PortfolioRepository handles portfolio snapshot database operations
// Faithful translation from Python: app/modules/portfolio/database/portfolio_repository.py
// Note: This accesses snapshots database (snapshots.db)
type PortfolioRepository struct {
	db  *sql.DB
	log zerolog.Logger
}

// NewPortfolioRepository creates a new portfolio repository
func NewPortfolioRepository(db *sql.DB, log zerolog.Logger) *PortfolioRepository {
	return &PortfolioRepository{
		db:  db,
		log: log.With().Str("repo", "portfolio").Logger(),
	}
}

// GetLatestCashBalance returns cash balance from most recent snapshot
// Faithful translation of Python: async def get_latest_cash_balance(self) -> float
func (r *PortfolioRepository) GetLatestCashBalance() (float64, error) {
	query := "SELECT cash_balance FROM portfolio_snapshots ORDER BY date DESC LIMIT 1"

	var cashBalance sql.NullFloat64
	err := r.db.QueryRow(query).Scan(&cashBalance)
	if errors.Is(err, sql.ErrNoRows) {
		return 0.0, nil
	}
	if err != nil {
		return 0.0, fmt.Errorf("failed to get latest cash balance: %w", err)
	}

	if !cashBalance.Valid {
		return 0.0, nil
	}

	return cashBalance.Float64, nil
}

// GetHistory returns snapshot history for last N days
// Faithful translation of Python: async def get_history(self, days: int = 90) -> List[PortfolioSnapshot]
func (r *PortfolioRepository) GetHistory(days int) ([]PortfolioSnapshot, error) {
	query := `
		SELECT * FROM portfolio_snapshots
		ORDER BY date DESC
		LIMIT ?
	`

	rows, err := r.db.Query(query, days)
	if err != nil {
		return nil, fmt.Errorf("failed to query portfolio history: %w", err)
	}
	defer rows.Close()

	var snapshots []PortfolioSnapshot
	for rows.Next() {
		snapshot, err := r.scanSnapshot(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan snapshot: %w", err)
		}
		snapshots = append(snapshots, snapshot)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating snapshots: %w", err)
	}

	return snapshots, nil
}

// GetByDate returns snapshot for a specific date
// Faithful translation of Python: async def get_by_date(self, date: str) -> Optional[PortfolioSnapshot]
func (r *PortfolioRepository) GetByDate(date string) (*PortfolioSnapshot, error) {
	query := "SELECT * FROM portfolio_snapshots WHERE date = ?"

	rows, err := r.db.Query(query, date)
	if err != nil {
		return nil, fmt.Errorf("failed to query snapshot by date: %w", err)
	}
	defer rows.Close()

	if !rows.Next() {
		return nil, nil // Snapshot not found
	}

	snapshot, err := r.scanSnapshot(rows)
	if err != nil {
		return nil, fmt.Errorf("failed to scan snapshot: %w", err)
	}

	return &snapshot, nil
}

// GetLatest returns the most recent snapshot
// Faithful translation of Python: async def get_latest(self) -> Optional[PortfolioSnapshot]
func (r *PortfolioRepository) GetLatest() (*PortfolioSnapshot, error) {
	query := "SELECT * FROM portfolio_snapshots ORDER BY date DESC LIMIT 1"

	rows, err := r.db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query latest snapshot: %w", err)
	}
	defer rows.Close()

	if !rows.Next() {
		return nil, nil // No snapshots found
	}

	snapshot, err := r.scanSnapshot(rows)
	if err != nil {
		return nil, fmt.Errorf("failed to scan snapshot: %w", err)
	}

	return &snapshot, nil
}

// GetRange returns snapshots within a date range
// Faithful translation of Python: async def get_range(self, start_date: str, end_date: str) -> List[PortfolioSnapshot]
func (r *PortfolioRepository) GetRange(startDate, endDate string) ([]PortfolioSnapshot, error) {
	query := `
		SELECT * FROM portfolio_snapshots
		WHERE date >= ? AND date <= ?
		ORDER BY date ASC
	`

	rows, err := r.db.Query(query, startDate, endDate)
	if err != nil {
		return nil, fmt.Errorf("failed to query snapshot range: %w", err)
	}
	defer rows.Close()

	var snapshots []PortfolioSnapshot
	for rows.Next() {
		snapshot, err := r.scanSnapshot(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan snapshot: %w", err)
		}
		snapshots = append(snapshots, snapshot)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating snapshots: %w", err)
	}

	return snapshots, nil
}

// scanSnapshot scans a database row into a PortfolioSnapshot struct
func (r *PortfolioRepository) scanSnapshot(rows *sql.Rows) (PortfolioSnapshot, error) {
	var snapshot PortfolioSnapshot
	var investedValue, unrealizedPnL, geoEUPct, geoAsiaPct, geoUSPct sql.NullFloat64
	var positionCount sql.NullInt64
	var annualTurnover sql.NullFloat64
	var createdAt sql.NullString // Not in Go model, but in DB

	err := rows.Scan(
		&snapshot.Date,
		&snapshot.TotalValue,
		&snapshot.CashBalance,
		&investedValue,
		&unrealizedPnL,
		&geoEUPct,
		&geoAsiaPct,
		&geoUSPct,
		&positionCount,
		&annualTurnover,
		&createdAt, // Skip created_at field
	)
	if err != nil {
		return snapshot, err
	}

	// Handle nullable fields
	if investedValue.Valid {
		snapshot.InvestedValue = investedValue.Float64
	}
	if unrealizedPnL.Valid {
		snapshot.UnrealizedPnL = unrealizedPnL.Float64
	}
	if geoEUPct.Valid {
		snapshot.GeoEUPct = geoEUPct.Float64
	}
	if geoAsiaPct.Valid {
		snapshot.GeoAsiaPct = geoAsiaPct.Float64
	}
	if geoUSPct.Valid {
		snapshot.GeoUSPct = geoUSPct.Float64
	}
	if positionCount.Valid {
		snapshot.PositionCount = int(positionCount.Int64)
	}
	if annualTurnover.Valid {
		snapshot.AnnualTurnover = annualTurnover.Float64
	}

	return snapshot, nil
}

// ValueChange represents portfolio value change over time
type ValueChange struct {
	Change     float64 `json:"change"`
	ChangePct  float64 `json:"change_pct"`
	Days       int     `json:"days"`
	StartValue float64 `json:"start_value"`
	EndValue   float64 `json:"end_value"`
}

// GetValueChange calculates portfolio value change over N days
// Faithful translation of Python: async def get_value_change(self, days: int = 30) -> dict
func (r *PortfolioRepository) GetValueChange(days int) (ValueChange, error) {
	snapshots, err := r.GetHistory(days)
	if err != nil {
		return ValueChange{}, fmt.Errorf("failed to get history: %w", err)
	}

	if len(snapshots) < 2 {
		return ValueChange{
			Change:     0,
			ChangePct:  0,
			Days:       0,
			StartValue: 0,
			EndValue:   0,
		}, nil
	}

	// Snapshots are returned in DESC order, so [0] is latest, [-1] is oldest
	latest := snapshots[0]
	oldest := snapshots[len(snapshots)-1]

	change := latest.TotalValue - oldest.TotalValue
	changePct := 0.0
	if oldest.TotalValue > 0 {
		changePct = (change / oldest.TotalValue) * 100
	}

	return ValueChange{
		Change:     change,
		ChangePct:  changePct,
		Days:       len(snapshots),
		StartValue: oldest.TotalValue,
		EndValue:   latest.TotalValue,
	}, nil
}

// Upsert inserts or updates a portfolio snapshot
// Faithful translation of Python: async def upsert(self, snapshot: PortfolioSnapshot) -> None
func (r *PortfolioRepository) Upsert(snapshot PortfolioSnapshot) error {
	now := time.Now().Format(time.RFC3339)

	// Begin transaction
	tx, err := r.db.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	query := `
		INSERT OR REPLACE INTO portfolio_snapshots
		(date, total_value, cash_balance, invested_value,
		 unrealized_pnl, geo_eu_pct, geo_asia_pct, geo_us_pct,
		 position_count, annual_turnover, created_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	_, err = tx.Exec(query,
		snapshot.Date,
		snapshot.TotalValue,
		snapshot.CashBalance,
		nullFloat64(snapshot.InvestedValue),
		nullFloat64(snapshot.UnrealizedPnL),
		nullFloat64(snapshot.GeoEUPct),
		nullFloat64(snapshot.GeoAsiaPct),
		nullFloat64(snapshot.GeoUSPct),
		nullInt64(snapshot.PositionCount),
		nullFloat64(snapshot.AnnualTurnover),
		now,
	)
	if err != nil {
		return fmt.Errorf("failed to upsert snapshot: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	r.log.Info().Str("date", snapshot.Date).Msg("Portfolio snapshot upserted")
	return nil
}

// DeleteBefore deletes snapshots before a date
// Faithful translation of Python: async def delete_before(self, date: str) -> int
func (r *PortfolioRepository) DeleteBefore(date string) (int, error) {
	// First, count how many will be deleted
	var count int64
	err := r.db.QueryRow("SELECT COUNT(*) FROM portfolio_snapshots WHERE date < ?", date).Scan(&count)
	if err != nil {
		return 0, fmt.Errorf("failed to count snapshots: %w", err)
	}

	if count == 0 {
		return 0, nil
	}

	// Begin transaction
	tx, err := r.db.Begin()
	if err != nil {
		return 0, fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	query := "DELETE FROM portfolio_snapshots WHERE date < ?"
	_, err = tx.Exec(query, date)
	if err != nil {
		return 0, fmt.Errorf("failed to delete snapshots: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return 0, fmt.Errorf("failed to commit transaction: %w", err)
	}

	r.log.Info().Str("before_date", date).Int64("count", count).Msg("Portfolio snapshots deleted")
	return int(count), nil
}
