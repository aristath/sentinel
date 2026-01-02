package universe

import (
	"database/sql"
	"fmt"
	"path/filepath"
	"strings"

	_ "github.com/mattn/go-sqlite3" // SQLite driver
	"github.com/rs/zerolog"
)

// HistoryDB provides access to historical price data
type HistoryDB struct {
	historyDir string
	log        zerolog.Logger
}

// NewHistoryDB creates a new history database accessor
func NewHistoryDB(historyDir string, log zerolog.Logger) *HistoryDB {
	return &HistoryDB{
		historyDir: historyDir,
		log:        log.With().Str("component", "history_db").Logger(),
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

// GetDailyPrices fetches daily price data for a symbol
func (h *HistoryDB) GetDailyPrices(symbol string, limit int) ([]DailyPrice, error) {
	db, err := h.openHistoryDB(symbol)
	if err != nil {
		return nil, err
	}
	defer db.Close()

	query := `
		SELECT date, close_price as close, high_price as high, low_price as low, open_price as open, volume
		FROM daily_prices
		ORDER BY date DESC
		LIMIT ?
	`

	rows, err := db.Query(query, limit)
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

// GetMonthlyPrices fetches monthly price data for a symbol
func (h *HistoryDB) GetMonthlyPrices(symbol string, limit int) ([]MonthlyPrice, error) {
	db, err := h.openHistoryDB(symbol)
	if err != nil {
		return nil, err
	}
	defer db.Close()

	query := `
		SELECT year_month, avg_adj_close
		FROM monthly_prices
		ORDER BY year_month DESC
		LIMIT ?
	`

	rows, err := db.Query(query, limit)
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

// HasMonthlyData checks if the history database has monthly price data
// Used to determine if initial 10-year seed has been done
func (h *HistoryDB) HasMonthlyData(symbol string) (bool, error) {
	db, err := h.openHistoryDB(symbol)
	if err != nil {
		return false, err
	}
	defer db.Close()

	var count int
	err = db.QueryRow("SELECT COUNT(*) FROM monthly_prices").Scan(&count)
	if err != nil {
		return false, fmt.Errorf("failed to check monthly data: %w", err)
	}

	return count > 0, nil
}

// SyncHistoricalPrices writes historical price data to the database
// Faithful translation from Python: app/jobs/securities_data_sync.py -> _sync_historical_for_symbol()
//
// Inserts/replaces daily prices and aggregates to monthly prices in a single transaction
func (h *HistoryDB) SyncHistoricalPrices(symbol string, prices []DailyPrice) error {
	db, err := h.openHistoryDB(symbol)
	if err != nil {
		return err
	}
	defer db.Close()

	// Begin transaction
	tx, err := db.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback() // Will be no-op if Commit succeeds

	// Insert/replace daily prices
	stmt, err := tx.Prepare(`
		INSERT OR REPLACE INTO daily_prices
		(date, open_price, high_price, low_price, close_price, volume, source, created_at)
		VALUES (?, ?, ?, ?, ?, ?, 'yahoo', datetime('now'))
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

		_, err = stmt.Exec(
			price.Date,
			price.Open,
			price.High,
			price.Low,
			price.Close,
			volume,
		)
		if err != nil {
			return fmt.Errorf("failed to insert daily price for %s: %w", price.Date, err)
		}
	}

	// Aggregate to monthly prices
	// This matches the Python SQL exactly
	_, err = tx.Exec(`
		INSERT OR REPLACE INTO monthly_prices
		(year_month, avg_close, avg_adj_close, source, created_at)
		SELECT
			strftime('%Y-%m', date) as year_month,
			AVG(close_price) as avg_close,
			AVG(close_price) as avg_adj_close,
			'calculated',
			datetime('now')
		FROM daily_prices
		GROUP BY strftime('%Y-%m', date)
	`)
	if err != nil {
		return fmt.Errorf("failed to aggregate monthly prices: %w", err)
	}

	// Commit transaction
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	h.log.Info().
		Str("symbol", symbol).
		Int("count", len(prices)).
		Msg("Synced historical prices")

	return nil
}

// openHistoryDB opens the history database for a symbol
func (h *HistoryDB) openHistoryDB(symbol string) (*sql.DB, error) {
	// Convert symbol format: AAPL.US -> AAPL_US
	dbSymbol := strings.ReplaceAll(symbol, ".", "_")

	dbPath := filepath.Join(h.historyDir, dbSymbol+".db")

	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		return nil, fmt.Errorf("failed to open history database for %s: %w", symbol, err)
	}

	// Verify database is accessible
	if err := db.Ping(); err != nil {
		db.Close()
		return nil, fmt.Errorf("failed to ping history database for %s: %w", symbol, err)
	}

	return db, nil
}
