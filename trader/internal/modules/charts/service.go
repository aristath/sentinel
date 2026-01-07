package charts

import (
	"database/sql"
	"fmt"
	"time"

	"github.com/aristath/portfolioManager/internal/modules/universe"
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
	historyDB    *sql.DB // Consolidated history.db connection
	securityRepo *universe.SecurityRepository
	universeDB   *sql.DB // For querying securities (universe.db)
	log          zerolog.Logger
}

// NewService creates a new charts service
func NewService(
	historyDB *sql.DB,
	securityRepo *universe.SecurityRepository,
	universeDB *sql.DB,
	log zerolog.Logger,
) *Service {
	return &Service{
		historyDB:    historyDB,
		securityRepo: securityRepo,
		universeDB:   universeDB,
		log:          log.With().Str("service", "charts").Logger(),
	}
}

// GetSparklines returns 1-year sparkline data for all active securities
// Faithful translation from Python: app/api/charts.py -> get_all_stock_sparklines()
func (s *Service) GetSparklines() (map[string][]ChartDataPoint, error) {
	startDate := time.Now().AddDate(-1, 0, 0).Format("2006-01-02")

	// Get all active securities with ISINs
	rows, err := s.universeDB.Query("SELECT symbol, isin FROM securities WHERE active = 1 AND isin != ''")
	if err != nil {
		return nil, fmt.Errorf("failed to get active securities: %w", err)
	}
	defer rows.Close()

	result := make(map[string][]ChartDataPoint)

	for rows.Next() {
		var symbol string
		var isin sql.NullString
		if err := rows.Scan(&symbol, &isin); err != nil {
			s.log.Warn().Err(err).Msg("Failed to scan symbol")
			continue
		}

		// Skip securities without ISIN
		if !isin.Valid || isin.String == "" {
			s.log.Debug().Str("symbol", symbol).Msg("Skipping security without ISIN")
			continue
		}

		// Get price data using ISIN
		prices, err := s.getPricesFromDB(isin.String, startDate, "")
		if err != nil {
			s.log.Debug().
				Err(err).
				Str("symbol", symbol).
				Str("isin", isin.String).
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
	// Validate ISIN is not empty
	if isin == "" {
		return nil, fmt.Errorf("ISIN cannot be empty")
	}

	// Parse date range
	startDate := parseDateRange(dateRange)

	// Get prices from database using ISIN directly
	prices, err := s.getPricesFromDB(isin, startDate, "")
	if err != nil {
		return nil, fmt.Errorf("failed to get prices: %w", err)
	}

	return prices, nil
}

// getPricesFromDB fetches price data from the consolidated history database using ISIN
func (s *Service) getPricesFromDB(isin string, startDate string, endDate string) ([]ChartDataPoint, error) {
	// Build query with ISIN filter
	var query string
	var args []interface{}

	if startDate != "" && endDate != "" {
		query = `
			SELECT date, close
			FROM daily_prices
			WHERE isin = ? AND date >= ? AND date <= ?
			ORDER BY date ASC
		`
		args = []interface{}{isin, startDate, endDate}
	} else if startDate != "" {
		query = `
			SELECT date, close
			FROM daily_prices
			WHERE isin = ? AND date >= ?
			ORDER BY date ASC
		`
		args = []interface{}{isin, startDate}
	} else {
		query = `
			SELECT date, close
			FROM daily_prices
			WHERE isin = ?
			ORDER BY date ASC
		`
		args = []interface{}{isin}
	}

	rows, err := s.historyDB.Query(query, args...)
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
