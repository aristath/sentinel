package display

import (
	"database/sql"
	"fmt"
	"math"
	"time"

	"github.com/rs/zerolog"
)

// SecurityPerformanceService calculates individual security performance metrics for display
type SecurityPerformanceService struct {
	historyDB *sql.DB // Database for individual security price history (history/{isin}.db)
	log       zerolog.Logger
}

// NewSecurityPerformanceService creates a new security performance service
func NewSecurityPerformanceService(historyDB *sql.DB, log zerolog.Logger) *SecurityPerformanceService {
	return &SecurityPerformanceService{
		historyDB: historyDB,
		log:       log.With().Str("service", "security_performance").Logger(),
	}
}

// CalculateTrailing12MoCAGR calculates trailing 12-month CAGR for a specific security
// Uses the security's price history database
func (s *SecurityPerformanceService) CalculateTrailing12MoCAGR(symbol string) (*float64, error) {
	endDate := time.Now().Format("2006-01-02")
	startDate := time.Now().AddDate(-1, 0, 0).Format("2006-01-02")

	// Query price history for this security
	rows, err := s.historyDB.Query(`
		SELECT date, close_price
		FROM daily_prices
		WHERE date >= ? AND date <= ?
		ORDER BY date ASC
	`, startDate, endDate)
	if err != nil {
		return nil, fmt.Errorf("failed to query price history for %s: %w", symbol, err)
	}
	defer rows.Close()

	var prices []struct {
		Date  string
		Close float64
	}

	for rows.Next() {
		var p struct {
			Date  string
			Close float64
		}
		if err := rows.Scan(&p.Date, &p.Close); err != nil {
			return nil, err
		}
		prices = append(prices, p)
	}

	if len(prices) < 2 {
		s.log.Debug().Str("symbol", symbol).Msg("Insufficient price data for trailing 12mo calculation")
		return nil, nil
	}

	// Use first and last price
	startPrice := prices[0].Close
	endPrice := prices[len(prices)-1].Close

	if startPrice <= 0 {
		s.log.Warn().Str("symbol", symbol).Msg("Invalid start price for trailing 12mo calculation")
		return nil, nil
	}

	// Calculate days between first and last price
	startDt, _ := time.Parse("2006-01-02", prices[0].Date)
	endDt, _ := time.Parse("2006-01-02", prices[len(prices)-1].Date)
	days := endDt.Sub(startDt).Hours() / 24

	if days < 30 {
		s.log.Debug().Str("symbol", symbol).Msg("Insufficient time period for trailing 12mo calculation")
		return nil, nil
	}

	years := days / 365.0

	var cagr float64
	if years >= 0.25 {
		// Use CAGR formula for periods >= 3 months
		cagr = math.Pow(endPrice/startPrice, 1/years) - 1
	} else {
		// Simple return for very short periods
		cagr = (endPrice / startPrice) - 1
	}

	s.log.Debug().
		Str("symbol", symbol).
		Float64("cagr", cagr).
		Float64("start_price", startPrice).
		Float64("end_price", endPrice).
		Float64("days", days).
		Msg("Calculated trailing 12mo CAGR")

	return &cagr, nil
}

// GetPerformanceVsTarget gets security performance difference vs target
func (s *SecurityPerformanceService) GetPerformanceVsTarget(symbol string, target float64) (*float64, error) {
	cagr, err := s.CalculateTrailing12MoCAGR(symbol)
	if err != nil {
		return nil, err
	}

	if cagr == nil {
		return nil, nil
	}

	difference := *cagr - target

	s.log.Debug().
		Str("symbol", symbol).
		Float64("difference", difference).
		Float64("cagr", *cagr).
		Float64("target", target).
		Msg("Calculated performance vs target")

	return &difference, nil
}
