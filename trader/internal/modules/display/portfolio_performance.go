package display

import (
	"database/sql"
	"errors"
	"fmt"
	"math"
	"time"

	"github.com/aristath/arduino-trader/internal/modules/settings"
	"github.com/rs/zerolog"
)

// PortfolioPerformanceService calculates portfolio performance metrics for display visualization
type PortfolioPerformanceService struct {
	portfolioDB *sql.DB
	configDB    *sql.DB
	log         zerolog.Logger
}

// NewPortfolioPerformanceService creates a new portfolio performance service
func NewPortfolioPerformanceService(portfolioDB, configDB *sql.DB, log zerolog.Logger) *PortfolioPerformanceService {
	return &PortfolioPerformanceService{
		portfolioDB: portfolioDB,
		configDB:    configDB,
		log:         log.With().Str("service", "portfolio_performance").Logger(),
	}
}

// CalculateWeightedPerformance calculates weighted portfolio performance vs target
// Returns weighted combination of:
// - Trailing 12-month annualized return (70% default)
// - Since-inception CAGR (30% default)
func (s *PortfolioPerformanceService) CalculateWeightedPerformance() (float64, error) {
	// Get weights from settings
	trailingWeight := s.getSettingFloat("display_performance_trailing12mo_weight", 0.70)
	inceptionWeight := s.getSettingFloat("display_performance_inception_weight", 0.30)

	// Calculate both metrics
	trailing12mo, err := s.CalculateTrailing12MoReturn()
	if err != nil && !errors.Is(err, sql.ErrNoRows) {
		s.log.Warn().Err(err).Msg("Error calculating trailing 12mo return")
	}

	sinceInception, err := s.CalculateSinceInceptionCAGR()
	if err != nil && !errors.Is(err, sql.ErrNoRows) {
		s.log.Warn().Err(err).Msg("Error calculating since-inception CAGR")
	}

	// Handle cases where data is missing
	if trailing12mo == nil && sinceInception == nil {
		s.log.Warn().Msg("Insufficient data for performance calculation")
		return 0, fmt.Errorf("insufficient data")
	}

	if trailing12mo == nil {
		s.log.Debug().Msg("No trailing 12mo data, using inception CAGR only")
		return *sinceInception, nil
	}

	if sinceInception == nil {
		s.log.Debug().Msg("No inception data, using trailing 12mo only")
		return *trailing12mo, nil
	}

	// Weighted combination
	weighted := (*trailing12mo * trailingWeight) + (*sinceInception * inceptionWeight)
	s.log.Debug().
		Float64("weighted", weighted).
		Float64("trailing", *trailing12mo).
		Float64("trailing_weight", trailingWeight).
		Float64("inception", *sinceInception).
		Float64("inception_weight", inceptionWeight).
		Msg("Calculated weighted performance")

	return weighted, nil
}

// CalculateTrailing12MoReturn calculates trailing 12-month annualized return from portfolio snapshots
func (s *PortfolioPerformanceService) CalculateTrailing12MoReturn() (*float64, error) {
	endDate := time.Now().Format("2006-01-02")
	startDate := time.Now().AddDate(-1, 0, 0).Format("2006-01-02")

	// Get snapshots in range
	rows, err := s.portfolioDB.Query(`
		SELECT date, total_value
		FROM portfolio_snapshots
		WHERE date >= ? AND date <= ?
		ORDER BY date ASC
	`, startDate, endDate)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var snapshots []struct {
		Date       string
		TotalValue float64
	}

	for rows.Next() {
		var snap struct {
			Date       string
			TotalValue float64
		}
		if err := rows.Scan(&snap.Date, &snap.TotalValue); err != nil {
			return nil, err
		}
		snapshots = append(snapshots, snap)
	}

	if len(snapshots) < 2 {
		s.log.Debug().Msg("Insufficient snapshots for trailing 12mo calculation")
		return nil, nil
	}

	// Use first and last snapshot
	startSnapshot := snapshots[0]
	endSnapshot := snapshots[len(snapshots)-1]

	if startSnapshot.TotalValue <= 0 {
		s.log.Warn().Msg("Invalid start value for trailing 12mo calculation")
		return nil, nil
	}

	// Calculate days between snapshots
	startDt, _ := time.Parse("2006-01-02", startSnapshot.Date)
	endDt, _ := time.Parse("2006-01-02", endSnapshot.Date)
	days := endDt.Sub(startDt).Hours() / 24

	if days < 30 {
		s.log.Debug().Msg("Insufficient time period for trailing 12mo calculation")
		return nil, nil
	}

	years := days / 365.0

	var annualizedReturn float64
	if years >= 0.25 {
		// Use CAGR formula for periods >= 3 months
		annualizedReturn = math.Pow(endSnapshot.TotalValue/startSnapshot.TotalValue, 1/years) - 1
	} else {
		// Simple return for very short periods
		annualizedReturn = (endSnapshot.TotalValue / startSnapshot.TotalValue) - 1
	}

	s.log.Debug().
		Float64("return", annualizedReturn).
		Float64("start_value", startSnapshot.TotalValue).
		Float64("end_value", endSnapshot.TotalValue).
		Float64("days", days).
		Msg("Calculated trailing 12mo return")

	return &annualizedReturn, nil
}

// CalculateSinceInceptionCAGR calculates since-inception CAGR from first to latest portfolio snapshot
func (s *PortfolioPerformanceService) CalculateSinceInceptionCAGR() (*float64, error) {
	// Get first and last snapshot
	rows, err := s.portfolioDB.Query(`
		SELECT date, total_value
		FROM portfolio_snapshots
		WHERE date >= '2020-01-01'
		ORDER BY date ASC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var snapshots []struct {
		Date       string
		TotalValue float64
	}

	for rows.Next() {
		var snap struct {
			Date       string
			TotalValue float64
		}
		if err := rows.Scan(&snap.Date, &snap.TotalValue); err != nil {
			return nil, err
		}
		snapshots = append(snapshots, snap)
	}

	if len(snapshots) < 2 {
		s.log.Debug().Msg("Insufficient snapshots for inception CAGR calculation")
		return nil, nil
	}

	// Use first and last snapshot
	firstSnapshot := snapshots[0]
	latestSnapshot := snapshots[len(snapshots)-1]

	if firstSnapshot.TotalValue <= 0 {
		s.log.Warn().Msg("Invalid first value for inception CAGR calculation")
		return nil, nil
	}

	// Calculate years between snapshots
	firstDt, _ := time.Parse("2006-01-02", firstSnapshot.Date)
	latestDt, _ := time.Parse("2006-01-02", latestSnapshot.Date)
	days := latestDt.Sub(firstDt).Hours() / 24
	years := days / 365.0

	if years < 0.25 {
		s.log.Debug().Msg("Insufficient time period for inception CAGR calculation")
		return nil, nil
	}

	// Calculate CAGR: (ending/beginning)^(1/years) - 1
	cagr := math.Pow(latestSnapshot.TotalValue/firstSnapshot.TotalValue, 1/years) - 1

	s.log.Debug().
		Float64("cagr", cagr).
		Float64("first_value", firstSnapshot.TotalValue).
		Float64("latest_value", latestSnapshot.TotalValue).
		Float64("years", years).
		Msg("Calculated since-inception CAGR")

	return &cagr, nil
}

// GetPerformanceVsTarget gets performance difference vs target annual return
func (s *PortfolioPerformanceService) GetPerformanceVsTarget() (float64, error) {
	weightedPerf, err := s.CalculateWeightedPerformance()
	if err != nil {
		return 0, err
	}

	target := s.getSettingFloat("target_annual_return", 0.11)
	difference := weightedPerf - target

	s.log.Debug().
		Float64("difference", difference).
		Float64("weighted", weightedPerf).
		Float64("target", target).
		Msg("Calculated performance vs target")

	return difference, nil
}

// getSettingFloat retrieves a float setting with fallback to default
func (s *PortfolioPerformanceService) getSettingFloat(key string, defaultVal float64) float64 {
	var value float64
	err := s.configDB.QueryRow("SELECT value FROM settings WHERE key = ?", key).Scan(&value)
	if err != nil {
		// Fallback to SettingDefaults
		if val, ok := settings.SettingDefaults[key]; ok {
			if fval, ok := val.(float64); ok {
				return fval
			}
		}
		return defaultVal
	}
	return value
}
