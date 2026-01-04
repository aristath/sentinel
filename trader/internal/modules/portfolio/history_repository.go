package portfolio

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	_ "github.com/mattn/go-sqlite3"
	"github.com/rs/zerolog"
)

// DailyPrice represents a single day's price data
// Faithful translation from Python: app/modules/portfolio/domain/models.py -> DailyPrice
type DailyPrice struct {
	Date       string  `json:"date"`
	ClosePrice float64 `json:"close_price"`
	OpenPrice  float64 `json:"open_price"`
	HighPrice  float64 `json:"high_price"`
	LowPrice   float64 `json:"low_price"`
	Volume     int64   `json:"volume"`
	Source     string  `json:"source"`
}

// HistoryRepository handles per-symbol historical price data
// Faithful translation from Python: app/modules/portfolio/database/history_repository.py
// TODO: Migrate to use consolidated history.db instead of per-symbol databases
// Database: Currently history/{SYMBOL}.db, will be consolidated to history.db
type HistoryRepository struct {
	symbol      string
	historyPath string // Base path for history databases
	db          *sql.DB
	log         zerolog.Logger
}

// NewHistoryRepository creates a new history repository for a symbol
// historyPath is the directory where per-symbol .history.db files are stored
// TODO: Update to use consolidated history.db with symbol column
func NewHistoryRepository(symbol, historyPath string, log zerolog.Logger) *HistoryRepository {
	return &HistoryRepository{
		symbol:      strings.ToUpper(strings.TrimSpace(symbol)),
		historyPath: historyPath,
		log:         log.With().Str("repo", "history").Str("symbol", symbol).Logger(),
	}
}

// getDB lazily initializes the symbol's history database connection
func (r *HistoryRepository) getDB() (*sql.DB, error) {
	if r.db != nil {
		return r.db, nil
	}

	// Path: {historyPath}/{SYMBOL}.history.db
	dbPath := filepath.Join(r.historyPath, fmt.Sprintf("%s.history.db", r.symbol))

	// Check if database exists
	if _, err := os.Stat(dbPath); os.IsNotExist(err) {
		return nil, fmt.Errorf("history database does not exist for %s: %s", r.symbol, dbPath)
	}

	// Open database
	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		return nil, fmt.Errorf("failed to open history database for %s: %w", r.symbol, err)
	}

	r.db = db
	return db, nil
}

// Close closes the database connection
func (r *HistoryRepository) Close() error {
	if r.db != nil {
		return r.db.Close()
	}
	return nil
}

// GetDailyRange retrieves daily prices within a date range
// Faithful translation of Python: async def get_daily_range(self, start_date: str, end_date: str) -> List[DailyPrice]
func (r *HistoryRepository) GetDailyRange(startDate, endDate string) ([]DailyPrice, error) {
	db, err := r.getDB()
	if err != nil {
		// Database doesn't exist - return empty list (graceful degradation)
		r.log.Debug().Err(err).Msg("History database not found, returning empty price list")
		return []DailyPrice{}, nil
	}

	query := `
		SELECT date, open_price, high_price, low_price, close_price, volume, source
		FROM daily_prices
		WHERE date >= ? AND date <= ?
		ORDER BY date ASC
	`

	rows, err := db.Query(query, startDate, endDate)
	if err != nil {
		return nil, fmt.Errorf("failed to query daily prices: %w", err)
	}
	defer rows.Close()

	var prices []DailyPrice
	for rows.Next() {
		var price DailyPrice
		var source sql.NullString
		var volume sql.NullInt64

		err := rows.Scan(
			&price.Date,
			&price.OpenPrice,
			&price.HighPrice,
			&price.LowPrice,
			&price.ClosePrice,
			&volume,
			&source,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan daily price: %w", err)
		}

		if volume.Valid {
			price.Volume = volume.Int64
		}

		if source.Valid {
			price.Source = source.String
		} else {
			price.Source = "yahoo"
		}

		prices = append(prices, price)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating prices: %w", err)
	}

	return prices, nil
}

// GetLatestPrice retrieves the most recent price
// Faithful translation of Python: async def get_latest_price(self) -> Optional[DailyPrice]
func (r *HistoryRepository) GetLatestPrice() (*DailyPrice, error) {
	db, err := r.getDB()
	if err != nil {
		return nil, err
	}

	query := `
		SELECT date, open_price, high_price, low_price, close_price, volume, source
		FROM daily_prices
		ORDER BY date DESC
		LIMIT 1
	`

	row := db.QueryRow(query)

	var price DailyPrice
	var source sql.NullString
	var volume sql.NullInt64

	err = row.Scan(
		&price.Date,
		&price.OpenPrice,
		&price.HighPrice,
		&price.LowPrice,
		&price.ClosePrice,
		&volume,
		&source,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get latest price: %w", err)
	}

	if volume.Valid {
		price.Volume = volume.Int64
	}

	if source.Valid {
		price.Source = source.String
	} else {
		price.Source = "yahoo"
	}

	return &price, nil
}
