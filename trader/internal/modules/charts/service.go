package charts

import (
	"database/sql"
	"fmt"
	"path/filepath"
	"strings"
	"time"

	"github.com/aristath/arduino-trader/internal/modules/universe"
	_ "github.com/mattn/go-sqlite3"
	"github.com/rs/zerolog"
)

// ChartDataPoint represents a single point on a chart
type ChartDataPoint struct {
	Time  string  `json:"time"`  // YYYY-MM-DD format
	Value float64 `json:"value"` // Close price
}

// Service provides chart data operations
type Service struct {
	historyPath  string
	securityRepo *universe.SecurityRepository
	universeDB   *sql.DB // For querying securities (universe.db)
	log          zerolog.Logger
}

// NewService creates a new charts service
func NewService(
	historyPath string,
	securityRepo *universe.SecurityRepository,
	universeDB *sql.DB,
	log zerolog.Logger,
) *Service {
	return &Service{
		historyPath:  historyPath,
		securityRepo: securityRepo,
		universeDB:   universeDB,
		log:          log.With().Str("service", "charts").Logger(),
	}
}

// GetSparklines returns 1-year sparkline data for all active securities
// Faithful translation from Python: app/api/charts.py -> get_all_stock_sparklines()
func (s *Service) GetSparklines() (map[string][]ChartDataPoint, error) {
	startDate := time.Now().AddDate(-1, 0, 0).Format("2006-01-02")

	// Get all active securities
	rows, err := s.universeDB.Query("SELECT symbol FROM securities WHERE active = 1")
	if err != nil {
		return nil, fmt.Errorf("failed to get active securities: %w", err)
	}
	defer rows.Close()

	result := make(map[string][]ChartDataPoint)

	for rows.Next() {
		var symbol string
		if err := rows.Scan(&symbol); err != nil {
			s.log.Warn().Err(err).Msg("Failed to scan symbol")
			continue
		}

		// Get price data for this symbol
		prices, err := s.getPricesFromDB(symbol, startDate, "")
		if err != nil {
			s.log.Debug().
				Err(err).
				Str("symbol", symbol).
				Msg("Failed to get prices for symbol")
			continue
		}

		if len(prices) > 0 {
			result[symbol] = prices
		}
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating securities: %w", err)
	}

	return result, nil
}

// GetSecurityChart returns historical price data for a specific security
// Faithful translation from Python: app/api/charts.py -> get_security_chart()
func (s *Service) GetSecurityChart(isin string, dateRange string) ([]ChartDataPoint, error) {
	// Look up security by ISIN to get symbol
	security, err := s.securityRepo.GetByISIN(isin)
	if err != nil {
		return nil, fmt.Errorf("failed to get security: %w", err)
	}
	if security == nil {
		return nil, fmt.Errorf("security not found: %s", isin)
	}

	// Parse date range
	startDate := parseDateRange(dateRange)

	// Get prices from database
	prices, err := s.getPricesFromDB(security.Symbol, startDate, "")
	if err != nil {
		return nil, fmt.Errorf("failed to get prices: %w", err)
	}

	return prices, nil
}

// getPricesFromDB fetches price data from the history database
func (s *Service) getPricesFromDB(symbol string, startDate string, endDate string) ([]ChartDataPoint, error) {
	// Open the symbol's history database
	db, err := s.openHistoryDB(symbol)
	if err != nil {
		// Database doesn't exist - return empty
		s.log.Debug().
			Err(err).
			Str("symbol", symbol).
			Msg("History database not found")
		return []ChartDataPoint{}, nil
	}
	defer db.Close()

	// Build query
	var query string
	var args []interface{}

	if startDate != "" && endDate != "" {
		query = `
			SELECT date, close_price
			FROM daily_prices
			WHERE date >= ? AND date <= ?
			ORDER BY date ASC
		`
		args = []interface{}{startDate, endDate}
	} else if startDate != "" {
		query = `
			SELECT date, close_price
			FROM daily_prices
			WHERE date >= ?
			ORDER BY date ASC
		`
		args = []interface{}{startDate}
	} else {
		query = `
			SELECT date, close_price
			FROM daily_prices
			ORDER BY date ASC
		`
		args = []interface{}{}
	}

	rows, err := db.Query(query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to query daily prices: %w", err)
	}
	defer rows.Close()

	var prices []ChartDataPoint
	for rows.Next() {
		var date string
		var closePrice sql.NullFloat64

		if err := rows.Scan(&date, &closePrice); err != nil {
			s.log.Warn().Err(err).Msg("Failed to scan price row")
			continue
		}

		// Skip rows with null prices
		if !closePrice.Valid {
			continue
		}

		prices = append(prices, ChartDataPoint{
			Time:  date,
			Value: closePrice.Float64,
		})
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating prices: %w", err)
	}

	return prices, nil
}

// openHistoryDB opens the history database for a symbol
func (s *Service) openHistoryDB(symbol string) (*sql.DB, error) {
	// Use the same approach as HistoryDB in universe package
	// Convert symbol format: AAPL.US -> AAPL_US for database filename
	dbSymbol := strings.ReplaceAll(symbol, ".", "_")

	// History databases are in data/history/{SYMBOL}.db
	dbPath := filepath.Join(s.historyPath, dbSymbol+".db")

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

// parseDateRange converts a range string to a start date
// Faithful translation from Python: app/api/charts.py -> _parse_date_range()
func parseDateRange(rangeStr string) string {
	if rangeStr == "all" || rangeStr == "" {
		return ""
	}

	now := time.Now()
	var startDate time.Time

	switch rangeStr {
	case "1M":
		startDate = now.AddDate(0, -1, 0)
	case "3M":
		startDate = now.AddDate(0, -3, 0)
	case "6M":
		startDate = now.AddDate(0, -6, 0)
	case "1Y":
		startDate = now.AddDate(-1, 0, 0)
	case "5Y":
		startDate = now.AddDate(-5, 0, 0)
	case "10Y":
		startDate = now.AddDate(-10, 0, 0)
	default:
		return ""
	}

	return startDate.Format("2006-01-02")
}
