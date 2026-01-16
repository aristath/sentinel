// Package charts provides services for generating chart data from historical prices.
package charts

import (
	"fmt"
	"sort"
	"time"

	"github.com/aristath/sentinel/internal/modules/universe"
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
	historyDBClient universe.HistoryDBInterface // Filtered and cached price access
	securityRepo    *universe.SecurityRepository
	log             zerolog.Logger
}

// NewService creates a new charts service
func NewService(
	historyDBClient universe.HistoryDBInterface,
	securityRepo *universe.SecurityRepository,
	log zerolog.Logger,
) *Service {
	return &Service{
		historyDBClient: historyDBClient,
		securityRepo:    securityRepo,
		log:             log.With().Str("service", "charts").Logger(),
	}
}

// GetSparklinesAggregated returns sparkline data with specified aggregation
// Replaces the old GetSparklines() method - supports 1Y (weekly) or 5Y (monthly) periods
func (s *Service) GetSparklinesAggregated(period string) (map[string][]ChartDataPoint, error) {
	var startDate string
	var groupBy string

	switch period {
	case "1Y":
		startDate = time.Now().AddDate(-1, 0, 0).Format("2006-01-02")
		groupBy = "week" // Weekly aggregation
	case "5Y":
		startDate = time.Now().AddDate(-5, 0, 0).Format("2006-01-02")
		groupBy = "month" // Monthly aggregation
	default:
		return nil, fmt.Errorf("invalid period: %s (must be 1Y or 5Y)", period)
	}

	// Get all securities for charts (excludes indices, only those with ISINs)
	securities, err := s.securityRepo.GetSecuritiesForCharts()
	if err != nil {
		return nil, fmt.Errorf("failed to get securities for charts: %w", err)
	}

	result := make(map[string][]ChartDataPoint)

	for _, security := range securities {
		symbol := security.Symbol
		isin := security.ISIN

		// Skip securities without ISIN (defensive, should already be filtered)
		if isin == "" {
			s.log.Debug().Str("symbol", symbol).Msg("Skipping security without ISIN")
			continue
		}

		// Get aggregated prices
		prices, err := s.getAggregatedPrices(isin, startDate, groupBy)
		if err != nil {
			s.log.Debug().
				Err(err).
				Str("symbol", symbol).
				Str("isin", isin).
				Msg("Failed to get aggregated prices for symbol")
			continue
		}

		if len(prices) > 0 {
			result[symbol] = prices
		}
	}

	return result, nil
}

// getAggregatedPrices fetches filtered price data and aggregates by week or month
// Uses HistoryDB for filtered prices, then aggregates in memory
func (s *Service) getAggregatedPrices(isin string, startDate string, groupBy string) ([]ChartDataPoint, error) {
	// Get all filtered prices from HistoryDB
	dailyPrices, err := s.historyDBClient.GetDailyPrices(isin, 0) // 0 = no limit
	if err != nil {
		return nil, fmt.Errorf("failed to get daily prices: %w", err)
	}

	// Aggregate in memory
	aggregated := make(map[string][]float64) // period -> close prices

	for _, p := range dailyPrices {
		// Skip if before start date
		if p.Date < startDate {
			continue
		}

		var period string
		if groupBy == "week" {
			// Parse date and format as YYYY-W## (ISO week)
			t, err := time.Parse("2006-01-02", p.Date)
			if err != nil {
				continue
			}
			year, week := t.ISOWeek()
			period = fmt.Sprintf("%d-W%02d", year, week)
		} else {
			// Monthly: extract YYYY-MM
			if len(p.Date) >= 7 {
				period = p.Date[:7] // "2024-01-15" -> "2024-01"
			} else {
				continue
			}
		}

		aggregated[period] = append(aggregated[period], p.Close)
	}

	// Calculate averages and sort by period
	var periods []string
	for period := range aggregated {
		periods = append(periods, period)
	}
	sort.Strings(periods)

	var prices []ChartDataPoint
	for _, period := range periods {
		values := aggregated[period]
		if len(values) == 0 {
			continue
		}

		var sum float64
		for _, v := range values {
			sum += v
		}
		avg := sum / float64(len(values))

		prices = append(prices, ChartDataPoint{
			Time:  period,
			Value: avg,
		})
	}

	return prices, nil
}

// GetSecurityChart returns historical price data for a specific security
// Uses filtered price data from HistoryDB to exclude anomalies
func (s *Service) GetSecurityChart(isin string, dateRange string) ([]ChartDataPoint, error) {
	// Validate ISIN is not empty
	if isin == "" {
		return nil, fmt.Errorf("ISIN cannot be empty")
	}

	// Get filtered prices from HistoryDB (already cached and filtered)
	dailyPrices, err := s.historyDBClient.GetDailyPrices(isin, 0) // 0 = no limit
	if err != nil {
		return nil, fmt.Errorf("failed to get prices: %w", err)
	}

	// Parse date range to get start date
	startDate := parseDateRange(dateRange)

	// Convert to chart points, filtering by date range
	// dailyPrices comes in descending order (most recent first), we need ascending for charts
	var prices []ChartDataPoint
	for i := len(dailyPrices) - 1; i >= 0; i-- {
		p := dailyPrices[i]

		// Apply date filter if specified
		if startDate != "" && p.Date < startDate {
			continue
		}

		prices = append(prices, ChartDataPoint{
			Time:  p.Date,
			Value: p.Close,
		})
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
