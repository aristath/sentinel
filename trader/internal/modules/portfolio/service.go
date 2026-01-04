package portfolio

import (
	"database/sql"
	"fmt"
	"math"
	"sort"
	"strings"
	"time"

	"github.com/aristath/arduino-trader/internal/modules/cash_utils"
	"github.com/aristath/arduino-trader/pkg/formulas"
	"github.com/rs/zerolog"
)

// AllocationTargetProvider provides access to allocation targets
// This interface breaks the circular dependency between portfolio and allocation packages
type AllocationTargetProvider interface {
	GetAll() (map[string]float64, error)
}

// CashManager interface defines operations for managing cash as securities and positions
// This interface breaks the circular dependency between portfolio and cash_flows packages
type CashManager interface {
	UpdateCashPosition(currency string, balance float64) error
}

// PortfolioService orchestrates portfolio operations
// Faithful translation from Python: app/modules/portfolio/services/portfolio_service.py
type PortfolioService struct {
	portfolioRepo           *PortfolioRepository
	positionRepo            PositionRepositoryInterface
	allocRepo               AllocationTargetProvider
	turnoverTracker         *TurnoverTracker
	attributionCalc         *AttributionCalculator
	cashManager             CashManager // Interface to break circular dependency
	universeDB              *sql.DB     // For querying securities (universe.db)
	tradernetClient         TradernetClientInterface
	currencyExchangeService CurrencyExchangeServiceInterface
	log                     zerolog.Logger
}

// NewPortfolioService creates a new portfolio service
func NewPortfolioService(
	portfolioRepo *PortfolioRepository,
	positionRepo PositionRepositoryInterface,
	allocRepo AllocationTargetProvider,
	turnoverTracker *TurnoverTracker,
	attributionCalc *AttributionCalculator,
	cashManager CashManager,
	universeDB *sql.DB,
	tradernetClient TradernetClientInterface,
	currencyExchangeService CurrencyExchangeServiceInterface,
	log zerolog.Logger,
) *PortfolioService {
	return &PortfolioService{
		portfolioRepo:           portfolioRepo,
		positionRepo:            positionRepo,
		allocRepo:               allocRepo,
		turnoverTracker:         turnoverTracker,
		attributionCalc:         attributionCalc,
		cashManager:             cashManager,
		universeDB:              universeDB,
		tradernetClient:         tradernetClient,
		currencyExchangeService: currencyExchangeService,
		log:                     log.With().Str("service", "portfolio").Logger(),
	}
}

// GetPortfolioSummary calculates current portfolio allocation vs targets
// Faithful translation of Python: async def get_portfolio_summary(self) -> PortfolioSummary
func (s *PortfolioService) GetPortfolioSummary() (PortfolioSummary, error) {
	// Get allocation targets
	targets, err := s.allocRepo.GetAll()
	if err != nil {
		return PortfolioSummary{}, fmt.Errorf("failed to get allocation targets: %w", err)
	}

	// Get positions with security info
	positions, err := s.positionRepo.GetWithSecurityInfo()
	if err != nil {
		return PortfolioSummary{}, fmt.Errorf("failed to get positions: %w", err)
	}

	// Aggregate position values by country and industry
	countryValues, industryValues, totalValue := s.aggregatePositionValues(positions)

	// Get all countries and industries from active securities in the universe
	allStockCountries, allStockIndustries, err := s.getAllSecurityCountriesAndIndustries()
	if err != nil {
		return PortfolioSummary{}, fmt.Errorf("failed to get securities: %w", err)
	}

	// Get cash balance from actual Tradernet balances (more accurate than snapshot)
	// Fallback to snapshot if Tradernet is not connected (matches Python behavior)
	cashBalance := 0.0
	if s.tradernetClient != nil {
		balances, err := s.tradernetClient.GetCashBalances()
		if err == nil && len(balances) > 0 {
			// Convert all currencies to EUR
			var totalEUR float64
			for _, balance := range balances {
				if balance.Currency == "EUR" {
					totalEUR += balance.Amount
					s.log.Debug().
						Str("currency", "EUR").
						Float64("amount", balance.Amount).
						Msg("Added EUR balance")
				} else {
					// Convert non-EUR currency to EUR
					if s.currencyExchangeService != nil {
						rate, err := s.currencyExchangeService.GetRate(balance.Currency, "EUR")
						if err != nil {
							s.log.Warn().
								Err(err).
								Str("currency", balance.Currency).
								Float64("amount", balance.Amount).
								Msg("Failed to get exchange rate, using fallback")

							// Fallback rates for autonomous operation
							eurValue := balance.Amount
							switch balance.Currency {
							case "USD":
								eurValue = balance.Amount * 0.9
							case "GBP":
								eurValue = balance.Amount * 1.2
							case "HKD":
								eurValue = balance.Amount * 0.11
							default:
								s.log.Warn().
									Str("currency", balance.Currency).
									Msg("Unknown currency, assuming 1:1 with EUR")
							}
							totalEUR += eurValue

							s.log.Info().
								Str("currency", balance.Currency).
								Float64("amount", balance.Amount).
								Float64("eur_value", eurValue).
								Msg("Converted to EUR using fallback rate")
						} else {
							eurValue := balance.Amount * rate
							totalEUR += eurValue

							s.log.Debug().
								Str("currency", balance.Currency).
								Float64("rate", rate).
								Float64("amount", balance.Amount).
								Float64("eur_value", eurValue).
								Msg("Converted to EUR using live rate")
						}
					} else {
						// No exchange service available, use fallback rates
						eurValue := balance.Amount
						switch balance.Currency {
						case "USD":
							eurValue = balance.Amount * 0.9
						case "GBP":
							eurValue = balance.Amount * 1.2
						case "HKD":
							eurValue = balance.Amount * 0.11
						default:
							s.log.Warn().
								Str("currency", balance.Currency).
								Msg("Exchange service not available, assuming 1:1 with EUR")
						}
						totalEUR += eurValue
					}
				}
			}
			cashBalance = totalEUR
			s.log.Debug().Float64("cash_balance", cashBalance).Msg("Got cash balance from Tradernet")
		} else {
			s.log.Warn().Err(err).Msg("Failed to get cash balances from Tradernet, falling back to snapshot")
		}
	}

	// Fallback to snapshot if Tradernet unavailable or failed
	if cashBalance == 0.0 {
		snapshotBalance, err := s.portfolioRepo.GetLatestCashBalance()
		if err != nil {
			s.log.Warn().Err(err).Msg("Failed to get cash balance from snapshot, using 0")
			cashBalance = 0.0
		} else {
			cashBalance = snapshotBalance
			s.log.Debug().Float64("cash_balance", cashBalance).Msg("Got cash balance from snapshot")
		}
	}

	// Build allocations
	countryAllocations := s.buildCountryAllocations(targets, countryValues, totalValue, allStockCountries)
	industryAllocations := s.buildIndustryAllocations(targets, industryValues, totalValue, allStockIndustries)

	return PortfolioSummary{
		TotalValue:          round(totalValue, 2),
		CashBalance:         round(cashBalance, 2),
		CountryAllocations:  countryAllocations,
		IndustryAllocations: industryAllocations,
	}, nil
}

// aggregatePositionValues aggregates position values by country and industry
// Faithful translation of Python: def _aggregate_position_values(self, positions)
func (s *PortfolioService) aggregatePositionValues(positions []PositionWithSecurity) (
	map[string]float64, map[string]float64, float64,
) {
	countryValues := make(map[string]float64)
	industryValues := make(map[string]float64)
	totalValue := 0.0

	for _, pos := range positions {
		// Skip cash positions - they don't participate in allocation targets
		// Cash is managed separately via BalanceService
		if cash_utils.IsCashSymbol(pos.Symbol) {
			continue
		}

		eurValue := s.calculatePositionValue(pos)
		totalValue += eurValue

		// Aggregate by country
		if pos.Country != "" {
			countryValues[pos.Country] += eurValue
		}

		// Aggregate by industry (split if multiple industries)
		industries := parseIndustries(pos.Industry)
		if len(industries) > 0 {
			splitValue := eurValue / float64(len(industries))
			for _, ind := range industries {
				industryValues[ind] += splitValue
			}
		}
	}

	return countryValues, industryValues, totalValue
}

// calculatePositionValue calculates EUR value for a position
// Faithful translation of Python: def _calculate_position_value(self, pos: dict) -> float
func (s *PortfolioService) calculatePositionValue(pos PositionWithSecurity) float64 {
	eurValue := pos.MarketValueEUR

	// If market_value_eur is 0 or currency is not EUR, calculate from quantity and price
	if eurValue == 0 || pos.Currency != "EUR" {
		price := pos.CurrentPrice
		if price == 0 {
			price = pos.AvgPrice
		}

		if price == 0 {
			// Fallback to market_value_eur even if it might be in wrong currency
			return eurValue
		}

		// Calculate value in position's currency
		valueInCurrency := pos.Quantity * price

		// If already EUR or no currency conversion needed
		if pos.Currency == "EUR" || pos.Currency == "" {
			return valueInCurrency
		}

		// Convert to EUR using currency_rate if available
		if pos.CurrencyRate > 0 && pos.CurrencyRate != 1.0 {
			eurValue = valueInCurrency / pos.CurrencyRate
		} else {
			// Try to get exchange rate from service
			if s.currencyExchangeService != nil {
				rate, err := s.currencyExchangeService.GetRate(pos.Currency, "EUR")
				if err == nil && rate > 0 {
					eurValue = valueInCurrency * rate
				} else {
					// Use fallback rates
					switch pos.Currency {
					case "USD":
						eurValue = valueInCurrency * 0.9
					case "GBP":
						eurValue = valueInCurrency * 1.2
					case "HKD":
						eurValue = valueInCurrency * 0.11
					default:
						s.log.Warn().
							Str("currency", pos.Currency).
							Str("symbol", pos.Symbol).
							Msg("Unknown currency, using market_value_eur as-is (may be incorrect)")
						// Use stored market_value_eur if available, otherwise assume same as calculated
						if eurValue == 0 {
							eurValue = valueInCurrency
						}
					}
				}
			} else {
				// No exchange service, use fallback rates
				switch pos.Currency {
				case "USD":
					eurValue = valueInCurrency * 0.9
				case "GBP":
					eurValue = valueInCurrency * 1.2
				case "HKD":
					eurValue = valueInCurrency * 0.11
				default:
					s.log.Warn().
						Str("currency", pos.Currency).
						Str("symbol", pos.Symbol).
						Msg("Unknown currency, using market_value_eur as-is (may be incorrect)")
					if eurValue == 0 {
						eurValue = valueInCurrency
					}
				}
			}
		}
	} else if pos.Currency != "EUR" && pos.Currency != "" {
		// market_value_eur exists but position is not EUR - need to convert
		// This handles the case where market_value_eur is stored in wrong currency
		if s.currencyExchangeService != nil {
			rate, err := s.currencyExchangeService.GetRate(pos.Currency, "EUR")
			if err == nil && rate > 0 {
				eurValue = eurValue * rate
			} else {
				// Use fallback rates
				switch pos.Currency {
				case "USD":
					eurValue = eurValue * 0.9
				case "GBP":
					eurValue = eurValue * 1.2
				case "HKD":
					eurValue = eurValue * 0.11
				default:
					s.log.Warn().
						Str("currency", pos.Currency).
						Str("symbol", pos.Symbol).
						Float64("market_value_eur", eurValue).
						Msg("Unknown currency, using market_value_eur as-is (may be incorrect)")
				}
			}
		} else {
			// No exchange service, use fallback rates
			switch pos.Currency {
			case "USD":
				eurValue = eurValue * 0.9
			case "GBP":
				eurValue = eurValue * 1.2
			case "HKD":
				eurValue = eurValue * 0.11
			default:
				s.log.Warn().
					Str("currency", pos.Currency).
					Str("symbol", pos.Symbol).
					Float64("market_value_eur", eurValue).
					Msg("Unknown currency, using market_value_eur as-is (may be incorrect)")
			}
		}
	}

	return eurValue
}

// buildCountryAllocations builds country allocation status list
// Faithful translation of Python: def _build_country_allocations(...)
func (s *PortfolioService) buildCountryAllocations(
	targets map[string]float64,
	countryValues map[string]float64,
	totalValue float64,
	allStockCountries map[string]bool,
) []AllocationStatus {
	// Collect all countries
	allCountries := make(map[string]bool)
	for key := range targets {
		if strings.HasPrefix(key, "country:") {
			country := strings.TrimPrefix(key, "country:")
			allCountries[country] = true
		}
	}
	for country := range countryValues {
		allCountries[country] = true
	}
	for country := range allStockCountries {
		allCountries[country] = true
	}

	// Build allocations
	var allocations []AllocationStatus
	for country := range allCountries {
		weight := targets[fmt.Sprintf("country:%s", country)]
		currentVal := countryValues[country]
		currentPct := 0.0
		if totalValue > 0 {
			currentPct = currentVal / totalValue
		}

		allocations = append(allocations, AllocationStatus{
			Category:     "country",
			Name:         country,
			TargetPct:    weight,
			CurrentPct:   round(currentPct, 4),
			CurrentValue: round(currentVal, 2),
			Deviation:    round(currentPct-weight, 4),
		})
	}

	// Sort by name
	sort.Slice(allocations, func(i, j int) bool {
		return allocations[i].Name < allocations[j].Name
	})

	return allocations
}

// buildIndustryAllocations builds industry allocation status list
// Faithful translation of Python: def _build_industry_allocations(...)
func (s *PortfolioService) buildIndustryAllocations(
	targets map[string]float64,
	industryValues map[string]float64,
	totalValue float64,
	allStockIndustries map[string]bool,
) []AllocationStatus {
	// Collect all industries
	allIndustries := make(map[string]bool)
	for key := range targets {
		if strings.HasPrefix(key, "industry:") {
			industry := strings.TrimPrefix(key, "industry:")
			allIndustries[industry] = true
		}
	}
	for industry := range industryValues {
		allIndustries[industry] = true
	}
	for industry := range allStockIndustries {
		allIndustries[industry] = true
	}

	// Build allocations
	var allocations []AllocationStatus
	for industry := range allIndustries {
		weight := targets[fmt.Sprintf("industry:%s", industry)]
		currentVal := industryValues[industry]
		currentPct := 0.0
		if totalValue > 0 {
			currentPct = currentVal / totalValue
		}

		allocations = append(allocations, AllocationStatus{
			Category:     "industry",
			Name:         industry,
			TargetPct:    weight,
			CurrentPct:   round(currentPct, 4),
			CurrentValue: round(currentVal, 2),
			Deviation:    round(currentPct-weight, 4),
		})
	}

	// Sort by name
	sort.Slice(allocations, func(i, j int) bool {
		return allocations[i].Name < allocations[j].Name
	})

	return allocations
}

// getAllSecurityCountriesAndIndustries gets all countries and industries from active securities
func (s *PortfolioService) getAllSecurityCountriesAndIndustries() (map[string]bool, map[string]bool, error) {
	query := "SELECT country, industry FROM securities WHERE active = 1"

	rows, err := s.universeDB.Query(query)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to query securities: %w", err)
	}
	defer rows.Close()

	countries := make(map[string]bool)
	industries := make(map[string]bool)

	for rows.Next() {
		var country, industry sql.NullString
		if err := rows.Scan(&country, &industry); err != nil {
			return nil, nil, fmt.Errorf("failed to scan security: %w", err)
		}

		if country.Valid && country.String != "" {
			countries[country.String] = true
		}

		if industry.Valid && industry.String != "" {
			inds := parseIndustries(industry.String)
			for _, ind := range inds {
				industries[ind] = true
			}
		}
	}

	if err := rows.Err(); err != nil {
		return nil, nil, fmt.Errorf("error iterating securities: %w", err)
	}

	return countries, industries, nil
}

// parseIndustries parses comma-separated industry string into list
// Faithful translation of Python: def parse_industries(industry_str: str) -> list[str]
func parseIndustries(industryStr string) []string {
	if industryStr == "" {
		return []string{}
	}

	var result []string
	for _, ind := range strings.Split(industryStr, ",") {
		trimmed := strings.TrimSpace(ind)
		if trimmed != "" {
			result = append(result, trimmed)
		}
	}
	return result
}

// round rounds a float64 to n decimal places
func round(val float64, decimals int) float64 {
	multiplier := math.Pow(10, float64(decimals))
	return math.Round(val*multiplier) / multiplier
}

// GetAnalytics calculates portfolio analytics for the specified period
// Faithful translation from Python: app/modules/portfolio/api/portfolio.py -> get_portfolio_analytics()
func (s *PortfolioService) GetAnalytics(days int) (PortfolioAnalyticsResponse, error) {
	// 1. Load risk parameters (use defaults for main portfolio)
	riskParams := NewDefaultRiskParameters()
	// TODO: Load from configuration if custom risk parameters are needed for main portfolio

	// 2. Calculate date range
	endDate := time.Now()
	startDate := endDate.AddDate(0, 0, -days)
	startDateStr := startDate.Format("2006-01-02")
	endDateStr := endDate.Format("2006-01-02")

	// 3. Get portfolio value series from snapshots
	snapshots, err := s.portfolioRepo.GetRange(startDateStr, endDateStr)
	if err != nil {
		return s.buildErrorResponse("Failed to get portfolio history", startDateStr, endDateStr, days), fmt.Errorf("failed to get snapshots: %w", err)
	}

	if len(snapshots) < 2 {
		return s.buildErrorResponse("Insufficient data", startDateStr, endDateStr, days), nil
	}

	// 4. Extract values and calculate returns
	values := make([]float64, len(snapshots))
	for i, snap := range snapshots {
		values[i] = snap.TotalValue
	}

	returns := formulas.CalculateReturns(values)
	if len(returns) == 0 {
		return s.buildErrorResponse("Could not calculate returns", startDateStr, endDateStr, days), nil
	}

	// 5. Calculate annual return and metrics (with parameterized risk calculations)
	annualReturn := formulas.CalculateAnnualReturn(returns)
	metrics := s.calculateMetrics(returns, annualReturn, riskParams)

	// 5. Format returns data (daily, monthly, annual)
	returnsData := s.formatReturnsData(returns, snapshots, annualReturn)

	// 6. Calculate turnover
	var turnoverInfo *TurnoverInfo
	if s.turnoverTracker != nil {
		turnover, err := s.turnoverTracker.CalculateAnnualTurnover(endDateStr)
		if err != nil {
			s.log.Warn().Err(err).Msg("Failed to calculate turnover, continuing without it")
		} else {
			info := s.turnoverTracker.GetTurnoverStatus(turnover)
			turnoverInfo = &info
		}
	}

	// 7. Calculate performance attribution
	var attribution AttributionData
	if s.attributionCalc != nil {
		dailyReturns := returnsData.Daily
		attr, err := s.attributionCalc.CalculatePerformanceAttribution(dailyReturns, startDateStr, endDateStr)
		if err != nil {
			s.log.Warn().Err(err).Msg("Failed to calculate attribution, continuing with empty attribution")
			attribution = AttributionData{
				Country:  make(map[string]float64),
				Industry: make(map[string]float64),
			}
		} else {
			attribution = attr
		}
	} else {
		attribution = AttributionData{
			Country:  make(map[string]float64),
			Industry: make(map[string]float64),
		}
	}

	// 8. Build response
	return PortfolioAnalyticsResponse{
		Returns:     returnsData,
		RiskMetrics: metrics,
		Attribution: attribution,
		Period: PeriodInfo{
			StartDate: startDateStr,
			EndDate:   endDateStr,
			Days:      days,
		},
		Turnover: turnoverInfo,
	}, nil
}

// calculateMetrics computes all risk metrics from returns
// Faithful translation from Python: app/modules/analytics/domain/metrics/portfolio.py -> get_portfolio_metrics()
func (s *PortfolioService) calculateMetrics(returns []float64, annualReturn float64, riskParams RiskParameters) RiskMetrics {
	// Volatility (annualized)
	volatility := formulas.AnnualizedVolatility(returns)
	if math.IsInf(volatility, 0) || math.IsNaN(volatility) {
		volatility = 0.0
	}

	// Sharpe ratio - uses risk-free rate from parameters
	sharpe := formulas.CalculateSharpeRatio(returns, riskParams.RiskFreeRate, 252)
	sharpeVal := 0.0
	if sharpe != nil {
		sharpeVal = *sharpe
		if math.IsInf(sharpeVal, 0) || math.IsNaN(sharpeVal) {
			sharpeVal = 0.0
		}
	}

	// Sortino ratio - uses risk-free rate and MAR from parameters
	sortino := formulas.CalculateSortinoRatio(returns, riskParams.RiskFreeRate, riskParams.SortinoMAR, 252)
	sortinoVal := 0.0
	if sortino != nil {
		sortinoVal = *sortino
		if math.IsInf(sortinoVal, 0) || math.IsNaN(sortinoVal) {
			sortinoVal = 0.0
		}
	}

	// Max drawdown (need to reconstruct prices from returns)
	prices := reconstructPricesFromReturns(returns)
	maxDD := formulas.CalculateMaxDrawdown(prices)
	maxDDVal := 0.0
	if maxDD != nil {
		maxDDVal = *maxDD
		if math.IsInf(maxDDVal, 0) || math.IsNaN(maxDDVal) {
			maxDDVal = 0.0
		}
	}

	// Calmar ratio = annual_return / abs(max_drawdown)
	calmarVal := 0.0
	if maxDDVal != 0 {
		calmarVal = annualReturn / math.Abs(maxDDVal)
		if math.IsInf(calmarVal, 0) || math.IsNaN(calmarVal) {
			calmarVal = 0.0
		}
	}

	// Check annualReturn itself for infinite values
	if math.IsInf(annualReturn, 0) || math.IsNaN(annualReturn) {
		annualReturn = 0.0
	}

	return RiskMetrics{
		SharpeRatio:  sharpeVal,
		SortinoRatio: sortinoVal,
		CalmarRatio:  calmarVal,
		Volatility:   volatility,
		MaxDrawdown:  maxDDVal,
	}
}

// reconstructPricesFromReturns converts returns back to price series
// This is needed because CalculateMaxDrawdown works on prices, not returns
func reconstructPricesFromReturns(returns []float64) []float64 {
	if len(returns) == 0 {
		return []float64{}
	}

	prices := make([]float64, len(returns)+1)
	prices[0] = 100.0 // Start at 100 (arbitrary base value)

	for i, r := range returns {
		prices[i+1] = prices[i] * (1 + r)
	}

	return prices
}

// formatReturnsData formats returns for API response
// Faithful translation from Python: app/modules/portfolio/api/portfolio.py -> _format_returns_data()
func (s *PortfolioService) formatReturnsData(
	returns []float64,
	snapshots []PortfolioSnapshot,
	annualReturn float64,
) ReturnsData {
	// Daily returns
	daily := make([]DailyReturn, len(returns))
	for i, r := range returns {
		// snapshots[i+1] because returns[i] = change from snapshots[i] to snapshots[i+1]
		daily[i] = DailyReturn{
			Date:   snapshots[i+1].Date,
			Return: r,
		}
	}

	// Monthly returns (aggregate by month)
	monthly := aggregateMonthlyReturns(daily)

	return ReturnsData{
		Daily:   daily,
		Monthly: monthly,
		Annual:  annualReturn,
	}
}

// aggregateMonthlyReturns groups daily returns into monthly compound returns
// Faithful translation from Python monthly resampling logic
func aggregateMonthlyReturns(daily []DailyReturn) []MonthlyReturn {
	// Group by year-month
	monthlyMap := make(map[string][]float64)

	for _, d := range daily {
		month := d.Date[:7] // Extract YYYY-MM
		monthlyMap[month] = append(monthlyMap[month], d.Return)
	}

	// Calculate compound return for each month
	var monthly []MonthlyReturn
	for month, rets := range monthlyMap {
		// Compound: (1+r1)*(1+r2)*...*(1+rN) - 1
		compound := 1.0
		for _, r := range rets {
			compound *= (1 + r)
		}
		monthly = append(monthly, MonthlyReturn{
			Month:  month,
			Return: compound - 1,
		})
	}

	// Sort by month
	sort.Slice(monthly, func(i, j int) bool {
		return monthly[i].Month < monthly[j].Month
	})

	return monthly
}

// buildErrorResponse creates an error response with empty metrics
func (s *PortfolioService) buildErrorResponse(
	errorMsg, startDate, endDate string,
	days int,
) PortfolioAnalyticsResponse {
	s.log.Warn().Str("error", errorMsg).Msg("Analytics error")

	return PortfolioAnalyticsResponse{
		Returns: ReturnsData{
			Daily:   []DailyReturn{},
			Monthly: []MonthlyReturn{},
			Annual:  0.0,
		},
		RiskMetrics: RiskMetrics{},
		Attribution: AttributionData{
			Country:  make(map[string]float64),
			Industry: make(map[string]float64),
		},
		Period: PeriodInfo{
			StartDate: startDate,
			EndDate:   endDate,
			Days:      days,
		},
		Turnover: nil,
	}
}

// SyncFromTradernet synchronizes positions and cash balances from Tradernet brokerage
func (s *PortfolioService) SyncFromTradernet() error {
	s.log.Info().Msg("Starting portfolio sync from Tradernet")

	if s.tradernetClient == nil {
		return fmt.Errorf("tradernet client not available")
	}

	// Step 1: Fetch current positions from Tradernet
	positions, err := s.tradernetClient.GetPortfolio()
	if err != nil {
		return fmt.Errorf("failed to fetch portfolio from Tradernet: %w", err)
	}

	s.log.Info().Int("positions", len(positions)).Msg("Fetched positions from Tradernet")

	// Step 2: Get current positions from database for cleanup
	currentPositions, err := s.positionRepo.GetAll()
	if err != nil {
		return fmt.Errorf("failed to get current positions: %w", err)
	}

	// Step 3: Build map of Tradernet symbols
	tradernetSymbols := make(map[string]bool)
	for _, pos := range positions {
		tradernetSymbols[pos.Symbol] = true
	}

	// Step 4: Upsert positions from Tradernet
	upserted := 0
	for _, tradernetPos := range positions {
		// Skip positions with zero quantity
		if tradernetPos.Quantity == 0 {
			continue
		}

		// Convert tradernet.Position to portfolio.Position
		dbPos := Position{
			Symbol:         tradernetPos.Symbol,
			Quantity:       tradernetPos.Quantity,
			AvgPrice:       tradernetPos.AvgPrice,
			CurrentPrice:   tradernetPos.CurrentPrice,
			Currency:       tradernetPos.Currency,
			CurrencyRate:   tradernetPos.CurrencyRate,
			MarketValueEUR: tradernetPos.MarketValueEUR,
			LastUpdated:    time.Now().Format(time.RFC3339),
		}

		if err := s.positionRepo.Upsert(dbPos); err != nil {
			s.log.Error().Err(err).Str("symbol", dbPos.Symbol).Msg("Failed to upsert position")
			continue
		}
		upserted++
	}

	// Step 5: Delete stale positions (in DB but not in Tradernet)
	deleted := 0
	for _, currentPos := range currentPositions {
		if !tradernetSymbols[currentPos.Symbol] {
			if err := s.positionRepo.Delete(currentPos.Symbol); err != nil {
				s.log.Error().Err(err).Str("symbol", currentPos.Symbol).Msg("Failed to delete stale position")
				continue
			}
			s.log.Info().Str("symbol", currentPos.Symbol).Msg("Deleted stale position not in Tradernet")
			deleted++
		}
	}

	// Step 6: Sync cash balances as positions (cash-as-securities architecture)
	balances, err := s.tradernetClient.GetCashBalances()
	if err != nil {
		s.log.Warn().Err(err).Msg("Failed to fetch cash balances from Tradernet")
	} else {
		// Update cash positions for each currency balance in the core bucket
		cashUpdated := 0
		for _, cashBalance := range balances {
			if err := s.cashManager.UpdateCashPosition(cashBalance.Currency, cashBalance.Amount); err != nil {
				s.log.Error().
					Err(err).
					Str("currency", cashBalance.Currency).
					Float64("amount", cashBalance.Amount).
					Msg("Failed to update cash position")
				continue
			}
			cashUpdated++
		}
		s.log.Info().
			Int("currencies", len(balances)).
			Int("updated", cashUpdated).
			Msg("Cash balances synced as positions")
	}

	s.log.Info().
		Int("upserted", upserted).
		Int("deleted", deleted).
		Int("total", len(positions)).
		Msg("Portfolio sync from Tradernet completed")

	return nil
}
