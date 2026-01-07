package universe

import (
	"database/sql"
	"fmt"

	_ "github.com/mattn/go-sqlite3" // SQLite driver
	"github.com/rs/zerolog"
)

// HistoryDB provides access to historical price data
type HistoryDB struct {
	db  *sql.DB
	log zerolog.Logger
}

// NewHistoryDB creates a new history database accessor
func NewHistoryDB(db *sql.DB, log zerolog.Logger) *HistoryDB {
	return &HistoryDB{
		db:  db,
		log: log.With().Str("component", "history_db").Logger(),
	}
}

// DailyPrice represents a daily OHLCV price point
type DailyPrice struct {
	Date   string  `json:"date"`
	Open   float64 `json:"open"`
	High   float64 `json:"high"`
	Low    float64 `json:"low"`
	Close  float64 `json:"close"`
	Volume *int64  `json:"volume,omitempty"`
}

// MonthlyPrice represents a monthly average price
type MonthlyPrice struct {
	YearMonth   string  `json:"year_month"`
	AvgAdjClose float64 `json:"avg_adj_close"`
}

// GetDailyPrices fetches daily price data for an ISIN
func (h *HistoryDB) GetDailyPrices(isin string, limit int) ([]DailyPrice, error) {
	query := `
		SELECT date, close, high, low, open, volume
		FROM daily_prices
		WHERE isin = ?
		ORDER BY date DESC
		LIMIT ?
	`

	rows, err := h.db.Query(query, isin, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to query daily prices: %w", err)
	}
	defer rows.Close()

	var prices []DailyPrice
	for rows.Next() {
		var p DailyPrice
		var volume sql.NullInt64

		err := rows.Scan(&p.Date, &p.Close, &p.High, &p.Low, &p.Open, &volume)
		if err != nil {
			return nil, fmt.Errorf("failed to scan daily price: %w", err)
		}

		if volume.Valid {
			p.Volume = &volume.Int64
		}

		prices = append(prices, p)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating daily prices: %w", err)
	}

	return prices, nil
}

// GetMonthlyPrices fetches monthly price data for an ISIN
func (h *HistoryDB) GetMonthlyPrices(isin string, limit int) ([]MonthlyPrice, error) {
	query := `
		SELECT year_month, avg_adj_close
		FROM monthly_prices
		WHERE isin = ?
		ORDER BY year_month DESC
		LIMIT ?
	`

	rows, err := h.db.Query(query, isin, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to query monthly prices: %w", err)
	}
	defer rows.Close()

	var prices []MonthlyPrice
	for rows.Next() {
		var p MonthlyPrice

		err := rows.Scan(&p.YearMonth, &p.AvgAdjClose)
		if err != nil {
			return nil, fmt.Errorf("failed to scan monthly price: %w", err)
		}

		prices = append(prices, p)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating monthly prices: %w", err)
	}

	return prices, nil
}

// HasMonthlyData checks if the history database has monthly price data for an ISIN
// Used to determine if initial 10-year seed has been done
func (h *HistoryDB) HasMonthlyData(isin string) (bool, error) {
	var count int
	err := h.db.QueryRow("SELECT COUNT(*) FROM monthly_prices WHERE isin = ?", isin).Scan(&count)
	if err != nil {
		return false, fmt.Errorf("failed to check monthly data: %w", err)
	}

	return count > 0, nil
}

// SyncHistoricalPrices writes historical price data to the database
// Faithful translation from Python: app/jobs/securities_data_sync.py -> _sync_historical_for_symbol()
//
// Inserts/replaces daily prices and aggregates to monthly prices in a single transaction
// The isin parameter is the ISIN (e.g., US0378331005), not the Tradernet symbol
func (h *HistoryDB) SyncHistoricalPrices(isin string, prices []DailyPrice) error {
	// Begin transaction
	tx, err := h.db.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback() // Will be no-op if Commit succeeds

	// Insert/replace daily prices with ISIN
	stmt, err := tx.Prepare(`
		INSERT OR REPLACE INTO daily_prices
		(isin, date, open, high, low, close, volume, adjusted_close)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?)
	`)
	if err != nil {
		return fmt.Errorf("failed to prepare statement: %w", err)
	}
	defer stmt.Close()

	for _, price := range prices {
		volume := sql.NullInt64{}
		if price.Volume != nil {
			volume.Int64 = *price.Volume
			volume.Valid = true
		}

		adjustedClose := price.Close // Use close as adjusted_close if not provided

		_, err = stmt.Exec(
			isin,
			price.Date,
			price.Open,
			price.High,
			price.Low,
			price.Close,
			volume,
			adjustedClose,
		)
		if err != nil {
			return fmt.Errorf("failed to insert daily price for %s: %w", price.Date, err)
		}
	}

	// Aggregate to monthly prices with ISIN filter
	_, err = tx.Exec(`
		INSERT OR REPLACE INTO monthly_prices
		(isin, year_month, avg_close, avg_adj_close, source, created_at)
		SELECT
			? as isin,
			strftime('%Y-%m', date) as year_month,
			AVG(close) as avg_close,
			AVG(adjusted_close) as avg_adj_close,
			'calculated',
			datetime('now')
		FROM daily_prices
		WHERE isin = ?
		GROUP BY strftime('%Y-%m', date)
	`, isin, isin)
	if err != nil {
		return fmt.Errorf("failed to aggregate monthly prices: %w", err)
	}

	// Commit transaction
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	h.log.Info().
		Str("isin", isin).
		Int("count", len(prices)).
		Msg("Synced historical prices")

	return nil
}
