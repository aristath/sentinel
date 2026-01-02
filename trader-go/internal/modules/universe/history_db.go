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
