package portfolio

import (
	"database/sql"
	"fmt"
	"math"
	"strings"

	"github.com/rs/zerolog"
)

// AttributionCalculator calculates performance attribution by country and industry
// Faithful translation from Python: app/modules/analytics/domain/attribution/performance.py
type AttributionCalculator struct {
	tradeRepo   *TradeRepository
	configDB    *sql.DB // For securities query
	historyPath string  // Path to history databases
	log         zerolog.Logger
}

// NewAttributionCalculator creates a new attribution calculator
func NewAttributionCalculator(
	tradeRepo *TradeRepository,
	configDB *sql.DB,
	historyPath string,
	log zerolog.Logger,
) *AttributionCalculator {
	return &AttributionCalculator{
		tradeRepo:   tradeRepo,
		configDB:    configDB,
		historyPath: historyPath,
		log:         log.With().Str("service", "attribution").Logger(),
	}
}

// SecurityInfo holds security metadata for attribution
type SecurityInfo struct {
	Country  string
	Industry *string
}

// PositionValue holds position value and metadata for a date
type PositionValue struct {
	Value    float64
	Country  string
	Industry *string
}

// CalculatePerformanceAttribution calculates attribution by country and industry
// Faithful translation of Python: async def get_performance_attribution(...)
func (c *AttributionCalculator) CalculatePerformanceAttribution(
	returns []DailyReturn,
	startDate, endDate string,
) (AttributionData, error) {
	if len(returns) == 0 {
		return AttributionData{
			Country:  make(map[string]float64),
			Industry: make(map[string]float64),
		}, nil
	}

	// Get position history
	positions, err := c.tradeRepo.GetPositionHistory(startDate, endDate)
	if err != nil {
		return AttributionData{}, fmt.Errorf("failed to get position history: %w", err)
	}

	if len(positions) == 0 {
		return AttributionData{
			Country:  make(map[string]float64),
			Industry: make(map[string]float64),
		}, nil
	}

	// Get security info for country/industry
	stockInfo, err := c.getSecurityInfo()
	if err != nil {
		return AttributionData{}, fmt.Errorf("failed to get security info: %w", err)
	}

	// Calculate returns by geography and industry
	geoReturns := make(map[string][]float64)
	industryReturns := make(map[string][]float64)

	// Process each return date
	for _, dailyReturn := range returns {
		dateStr := dailyReturn.Date

		// Get positions up to this date
		latestPositions := c.getLatestPositions(positions, dateStr)
		if len(latestPositions) == 0 {
			continue
		}

		// Calculate position values
		totalValue, positionValues, err := c.calculatePositionValues(latestPositions, stockInfo, dateStr)
		if err != nil {
			c.log.Warn().Err(err).Str("date", dateStr).Msg("Failed to calculate position values")
			continue
		}

		if totalValue == 0 {
			continue
		}

		// Attribute return by category
		c.attributeReturnByCategory(positionValues, totalValue, dailyReturn.Return, geoReturns, industryReturns)
	}

	// Annualize contributions
	attribution := c.calculateAnnualizedAttribution(geoReturns, industryReturns)

	return attribution, nil
}

// getSecurityInfo retrieves country and industry for all securities
func (c *AttributionCalculator) getSecurityInfo() (map[string]SecurityInfo, error) {
	query := "SELECT symbol, country, industry FROM securities WHERE active = 1"

	rows, err := c.configDB.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query securities: %w", err)
	}
	defer rows.Close()

	stockInfo := make(map[string]SecurityInfo)
	for rows.Next() {
		var symbol, country string
		var industry sql.NullString

		if err := rows.Scan(&symbol, &country, &industry); err != nil {
			return nil, fmt.Errorf("failed to scan security: %w", err)
		}

		info := SecurityInfo{
			Country: country,
		}
		if industry.Valid && industry.String != "" {
			info.Industry = &industry.String
		}

		stockInfo[symbol] = info
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating securities: %w", err)
	}

	return stockInfo, nil
}

// getLatestPositions gets the latest position for each symbol up to the given date
func (c *AttributionCalculator) getLatestPositions(
	positions []PositionHistoryEntry,
	date string,
) map[string]float64 {
	latestPositions := make(map[string]float64)

	for _, pos := range positions {
		if pos.Date <= date {
			latestPositions[pos.Symbol] = pos.Quantity
		}
	}

	return latestPositions
}

// calculatePositionValues calculates position values and weights for a given date
// Faithful translation of Python: async def _calculate_position_values(...)
func (c *AttributionCalculator) calculatePositionValues(
	latestPositions map[string]float64,
	stockInfo map[string]SecurityInfo,
	dateStr string,
) (float64, map[string]PositionValue, error) {
	totalValue := 0.0
	positionValues := make(map[string]PositionValue)

	for symbol, quantity := range latestPositions {
		if quantity <= 0 {
			continue
		}

		info, exists := stockInfo[symbol]
		if !exists {
			info = SecurityInfo{Country: "UNKNOWN"}
		}

		// Get price for this date from history database
		histRepo := NewHistoryRepository(symbol, c.historyPath, c.log)
		priceData, err := histRepo.GetDailyRange(dateStr, dateStr)
		histRepo.Close()

		if err != nil {
			c.log.Warn().Err(err).Str("symbol", symbol).Str("date", dateStr).Msg("Failed to get price")
			continue
		}

		if len(priceData) == 0 {
			continue
		}

		price := priceData[0].ClosePrice
		value := quantity * price
		totalValue += value

		positionValues[symbol] = PositionValue{
			Value:    value,
			Country:  info.Country,
			Industry: info.Industry,
		}
	}

	return totalValue, positionValues, nil
}

// attributeReturnByCategory attributes daily return by geography and industry
// Faithful translation of Python: def _attribute_return_by_category(...)
func (c *AttributionCalculator) attributeReturnByCategory(
	positionValues map[string]PositionValue,
	totalValue float64,
	dailyReturn float64,
	geoReturns map[string][]float64,
	industryReturns map[string][]float64,
) {
	for symbol, data := range positionValues {
		weight := data.Value / totalValue
		country := data.Country
		contribution := dailyReturn * weight

		// Attribute by country
		if _, exists := geoReturns[country]; !exists {
			geoReturns[country] = []float64{}
		}
		geoReturns[country] = append(geoReturns[country], contribution)

		// Attribute by industry
		if data.Industry != nil && *data.Industry != "" {
			ind := *data.Industry
			if _, exists := industryReturns[ind]; !exists {
				industryReturns[ind] = []float64{}
			}
			industryReturns[ind] = append(industryReturns[ind], contribution)
		}

		c.log.Debug().
			Str("symbol", symbol).
			Str("country", country).
			Float64("weight", weight).
			Float64("contribution", contribution).
			Msg("Attributed return")
	}
}

// calculateAnnualizedAttribution calculates annualized attribution from daily contributions
// Faithful translation of Python: def _calculate_annualized_attribution(...)
func (c *AttributionCalculator) calculateAnnualizedAttribution(
	geoReturns map[string][]float64,
	industryReturns map[string][]float64,
) AttributionData {
	attribution := AttributionData{
		Country:  make(map[string]float64),
		Industry: make(map[string]float64),
	}

	// Annualize country attribution
	for country, contributions := range geoReturns {
		if len(contributions) == 0 {
			attribution.Country[country] = 0.0
			continue
		}

		totalReturn := sum(contributions)
		var annualized float64

		if totalReturn <= -1 {
			annualized = -1.0
		} else {
			// Annualize: (1 + total_return) ^ (252 / len(contributions)) - 1
			annualized = math.Pow(1+totalReturn, 252.0/float64(len(contributions))) - 1
		}

		// Check if finite (no NaN, no Inf)
		if math.IsInf(annualized, 0) || math.IsNaN(annualized) {
			attribution.Country[country] = 0.0
		} else {
			attribution.Country[country] = annualized
		}
	}

	// Annualize industry attribution
	for industry, contributions := range industryReturns {
		if len(contributions) == 0 {
			attribution.Industry[industry] = 0.0
			continue
		}

		totalReturn := sum(contributions)
		var annualized float64

		if totalReturn <= -1 {
			annualized = -1.0
		} else {
			// Annualize: (1 + total_return) ^ (252 / len(contributions)) - 1
			annualized = math.Pow(1+totalReturn, 252.0/float64(len(contributions))) - 1
		}

		// Check if finite (no NaN, no Inf)
		if math.IsInf(annualized, 0) || math.IsNaN(annualized) {
			attribution.Industry[industry] = 0.0
		} else {
			attribution.Industry[industry] = annualized
		}
	}

	return attribution
}

// sum calculates the sum of a slice of float64 values
func sum(values []float64) float64 {
	total := 0.0
	for _, v := range values {
		total += v
	}
	return total
}

// TradeRepository is needed for position history - defined in trade_repository.go
type TradeRepository struct {
	ledgerDB *sql.DB
	log      zerolog.Logger
}

// NewTradeRepository creates a new trade repository
func NewTradeRepository(ledgerDB *sql.DB, log zerolog.Logger) *TradeRepository {
	return &TradeRepository{
		ledgerDB: ledgerDB,
		log:      log.With().Str("repo", "trade").Logger(),
	}
}

// GetPositionHistory wrapper that converts from trading.PositionHistoryEntry to portfolio.PositionHistoryEntry
func (r *TradeRepository) GetPositionHistory(startDate, endDate string) ([]PositionHistoryEntry, error) {
	// This is a temporary bridge - ideally we'd import from trading module
	// But to avoid circular dependencies, we define our own type and query directly

	query := `
		SELECT symbol, side, quantity, executed_at
		FROM trades
		WHERE executed_at <= ?
		ORDER BY executed_at ASC
	`

	rows, err := r.ledgerDB.Query(query, endDate)
	if err != nil {
		return nil, fmt.Errorf("failed to get position history: %w", err)
	}
	defer rows.Close()

	// Collect all rows
	type tradeRow struct {
		Symbol     string
		Side       string
		Quantity   float64
		ExecutedAt string
	}

	var allTrades []tradeRow
	for rows.Next() {
		var row tradeRow
		if err := rows.Scan(&row.Symbol, &row.Side, &row.Quantity, &row.ExecutedAt); err != nil {
			return nil, fmt.Errorf("failed to scan trade row: %w", err)
		}
		allTrades = append(allTrades, row)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating trades: %w", err)
	}

	// Build position state up to start_date
	cumulativePositions := make(map[string]float64)
	var preStartTrades []tradeRow
	var inRangeTrades []tradeRow

	for _, row := range allTrades {
		date := row.ExecutedAt[:10] // Extract YYYY-MM-DD
		if date < startDate {
			preStartTrades = append(preStartTrades, row)
		} else {
			inRangeTrades = append(inRangeTrades, row)
		}
	}

	// Process trades before start_date
	for _, row := range preStartTrades {
		symbol := row.Symbol
		side := strings.ToUpper(row.Side)
		quantity := row.Quantity

		if side == "BUY" {
			cumulativePositions[symbol] += quantity
		} else if side == "SELL" {
			cumulativePositions[symbol] -= quantity
			if cumulativePositions[symbol] < 0 {
				cumulativePositions[symbol] = 0.0
			}
		}
	}

	// Build initial positions
	var result []PositionHistoryEntry
	for symbol, quantity := range cumulativePositions {
		if quantity > 0 {
			result = append(result, PositionHistoryEntry{
				Date:     startDate,
				Symbol:   symbol,
				Quantity: quantity,
			})
		}
	}

	// Process in-range trades
	positionsByDate := make(map[string]map[string]float64)
	for _, row := range inRangeTrades {
		date := row.ExecutedAt[:10]
		symbol := row.Symbol
		side := strings.ToUpper(row.Side)
		quantity := row.Quantity

		if _, exists := positionsByDate[date]; !exists {
			positionsByDate[date] = make(map[string]float64)
		}

		if side == "BUY" {
			positionsByDate[date][symbol] += quantity
		} else if side == "SELL" {
			positionsByDate[date][symbol] -= quantity
		}
	}

	// Get sorted dates
	var dates []string
	for date := range positionsByDate {
		dates = append(dates, date)
	}

	// Sort dates (simple bubble sort for small arrays)
	for i := 0; i < len(dates); i++ {
		for j := i + 1; j < len(dates); j++ {
			if dates[i] > dates[j] {
				dates[i], dates[j] = dates[j], dates[i]
			}
		}
	}

	for _, date := range dates {
		for symbol, delta := range positionsByDate[date] {
			cumulativePositions[symbol] += delta
			if cumulativePositions[symbol] < 0 {
				cumulativePositions[symbol] = 0.0
			}
		}

		for symbol, quantity := range cumulativePositions {
			if quantity > 0 {
				result = append(result, PositionHistoryEntry{
					Date:     date,
					Symbol:   symbol,
					Quantity: quantity,
				})
			}
		}
	}

	return result, nil
}

// PositionHistoryEntry represents a position at a specific date (portfolio package version)
type PositionHistoryEntry struct {
	Date     string  `json:"date"`
	Symbol   string  `json:"symbol"`
	Quantity float64 `json:"quantity"`
}
