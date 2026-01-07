package portfolio

import (
	"database/sql"
	"fmt"

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

// HistoryRepository handles historical price data from consolidated history.db
// Uses ISINs as the canonical identifier
type HistoryRepository struct {
	isin string // ISIN identifier
	db   *sql.DB
	log  zerolog.Logger
}

// NewHistoryRepository creates a new history repository for an ISIN
// Uses the consolidated history.db database
func NewHistoryRepository(isin string, historyDB *sql.DB, log zerolog.Logger) *HistoryRepository {
	return &HistoryRepository{
		isin: isin,
		db:   historyDB,
		log:  log.With().Str("repo", "history").Str("isin", isin).Logger(),
	}
}

// GetDailyRange retrieves daily prices within a date range
// Faithful translation of Python: async def get_daily_range(self, start_date: str, end_date: str) -> List[DailyPrice]
func (r *HistoryRepository) GetDailyRange(startDate, endDate string) ([]DailyPrice, error) {
	query := `
		SELECT date, open, high, low, close, volume
		FROM daily_prices
		WHERE isin = ? AND date >= ? AND date <= ?
		ORDER BY date ASC
	`

	rows, err := r.db.Query(query, r.isin, startDate, endDate)
	if err != nil {
		return nil, fmt.Errorf("failed to query daily prices: %w", err)
	}
	defer rows.Close()

	var prices []DailyPrice
	for rows.Next() {
		var price DailyPrice
		var volume sql.NullInt64

		err := rows.Scan(
			&price.Date,
			&price.OpenPrice,
			&price.HighPrice,
			&price.LowPrice,
			&price.ClosePrice,
			&volume,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan daily price: %w", err)
		}

		if volume.Valid {
			price.Volume = volume.Int64
		}

		// Source is not stored in consolidated schema, default to yahoo
		price.Source = "yahoo"

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
	query := `
		SELECT date, open, high, low, close, volume
		FROM daily_prices
		WHERE isin = ?
		ORDER BY date DESC
		LIMIT 1
	`

	row := r.db.QueryRow(query, r.isin)

	var price DailyPrice
	var volume sql.NullInt64

	err := row.Scan(
		&price.Date,
		&price.OpenPrice,
		&price.HighPrice,
		&price.LowPrice,
		&price.ClosePrice,
		&volume,
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

	// Source is not stored in consolidated schema, default to yahoo
	price.Source = "yahoo"

	return &price, nil
}
