package portfolio

import (
	"database/sql"
	"fmt"
	"math"
	"sort"
	"strings"
	"time"

	"github.com/rs/zerolog"
)

// AllocationTargetProvider provides access to allocation targets
// This interface breaks the circular dependency between portfolio and allocation packages
type AllocationTargetProvider interface {
	GetAll() (map[string]float64, error)
}

// CashManager interface defines operations for managing cash balances
// This interface breaks the circular dependency between portfolio and cash_flows packages
type CashManager interface {
	UpdateCashPosition(currency string, balance float64) error
	GetAllCashBalances() (map[string]float64, error)
}

// PortfolioService orchestrates portfolio operations
// Faithful translation from Python: app/modules/portfolio/services/portfolio_service.py
type PortfolioService struct {
	positionRepo            PositionRepositoryInterface
	allocRepo               AllocationTargetProvider
	cashManager             CashManager // Interface to break circular dependency
	universeDB              *sql.DB     // For querying securities (universe.db)
	tradernetClient         TradernetClientInterface
	currencyExchangeService CurrencyExchangeServiceInterface
	log                     zerolog.Logger
}

// NewPortfolioService creates a new portfolio service
func NewPortfolioService(
	positionRepo PositionRepositoryInterface,
	allocRepo AllocationTargetProvider,
	cashManager CashManager,
	universeDB *sql.DB,
	tradernetClient TradernetClientInterface,
	currencyExchangeService CurrencyExchangeServiceInterface,
	log zerolog.Logger,
) *PortfolioService {
	return &PortfolioService{
		positionRepo:            positionRepo,
		allocRepo:               allocRepo,
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

	// Get cash balance from CashManager
	cashBalance := 0.0
	if s.cashManager != nil {
		balances, err := s.cashManager.GetAllCashBalances()
		if err == nil && len(balances) > 0 {
			// Convert all currencies to EUR
			var totalEUR float64
			for currency, amount := range balances {
				if currency == "EUR" {
					totalEUR += amount
					s.log.Debug().
						Str("currency", "EUR").
						Float64("amount", amount).
						Msg("Added EUR balance")
				} else {
					// Convert non-EUR currency to EUR
					if s.currencyExchangeService != nil {
						rate, err := s.currencyExchangeService.GetRate(currency, "EUR")
						if err != nil {
							s.log.Warn().
								Err(err).
								Str("currency", currency).
								Float64("amount", amount).
								Msg("Failed to get exchange rate, using fallback")

							// Fallback rates for autonomous operation
							eurValue := amount
							switch currency {
							case "USD":
								eurValue = amount * 0.9
							case "GBP":
								eurValue = amount * 1.2
							case "HKD":
								eurValue = amount * 0.11
							default:
								s.log.Warn().
									Str("currency", currency).
									Msg("Unknown currency, assuming 1:1 with EUR")
							}
							totalEUR += eurValue

							s.log.Info().
								Str("currency", currency).
								Float64("amount", amount).
								Float64("eur_value", eurValue).
								Msg("Converted to EUR using fallback rate")
						} else {
							eurValue := amount * rate
							totalEUR += eurValue

							s.log.Debug().
								Str("currency", currency).
								Float64("rate", rate).
								Float64("amount", amount).
								Float64("eur_value", eurValue).
								Msg("Converted to EUR using live rate")
						}
					} else {
						// No exchange service available, use fallback rates
						eurValue := amount
						switch currency {
						case "USD":
							eurValue = amount * 0.9
						case "GBP":
							eurValue = amount * 1.2
						case "HKD":
							eurValue = amount * 0.11
						default:
							s.log.Warn().
								Str("currency", currency).
								Msg("Exchange service not available, assuming 1:1 with EUR")
						}
						totalEUR += eurValue
					}
				}
			}
			cashBalance = totalEUR
			s.log.Debug().Float64("cash_balance", cashBalance).Msg("Got cash balance from CashManager")
		} else if err != nil {
			s.log.Warn().Err(err).Msg("Failed to get cash balances from CashManager, using 0")
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
		// Note: Cash positions should not exist in positions table after migration
		// If they do (during dual-write phase), they will be filtered out naturally
		// since they won't have matching securities in universe.db

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

		// Before upserting, get existing position to preserve Yahoo prices
		// GetBySymbol looks up ISIN first, then queries by ISIN
		existingPos, _ := s.positionRepo.GetBySymbol(tradernetPos.Symbol)

		// Lookup ISIN from securities table (required for Upsert)
		// Note: Cash positions should not come from Tradernet positions - they're synced separately
		var isin string
		query := "SELECT isin FROM securities WHERE symbol = ?"
		row := s.universeDB.QueryRow(query, strings.ToUpper(strings.TrimSpace(tradernetPos.Symbol)))
		if err := row.Scan(&isin); err != nil {
			s.log.Warn().Err(err).Str("symbol", tradernetPos.Symbol).Msg("Failed to lookup ISIN, position may not save correctly")
		}

		// Convert tradernet.Position to portfolio.Position
		// Use Tradernet data for position info, but preserve Yahoo prices
		dbPos := Position{
			ISIN:         isin, // Required for Upsert (PRIMARY KEY)
			Symbol:       tradernetPos.Symbol,
			Quantity:     tradernetPos.Quantity,     // From Tradernet
			AvgPrice:     tradernetPos.AvgPrice,     // From Tradernet (historical)
			Currency:     tradernetPos.Currency,     // From Tradernet
			CurrencyRate: tradernetPos.CurrencyRate, // From Tradernet
			LastUpdated:  time.Now().Format(time.RFC3339),
		}

		// Preserve Yahoo prices - DO NOT use Tradernet prices
		if existingPos != nil {
			dbPos.CurrentPrice = existingPos.CurrentPrice     // Keep Yahoo price
			dbPos.MarketValueEUR = existingPos.MarketValueEUR // Keep Yahoo-calculated value
		}

		// If we have a current price, recalculate market value
		if dbPos.CurrentPrice > 0 && dbPos.Quantity > 0 {
			valueInCurrency := dbPos.Quantity * dbPos.CurrentPrice
			if dbPos.CurrencyRate > 0 {
				dbPos.MarketValueEUR = valueInCurrency / dbPos.CurrencyRate
			} else if dbPos.Currency == "EUR" || dbPos.Currency == "" {
				dbPos.MarketValueEUR = valueInCurrency
			}
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
			// Delete by ISIN (primary identifier)
			// Note: Cash positions should not be in positions table after migration
			if currentPos.ISIN == "" {
				s.log.Warn().Str("symbol", currentPos.Symbol).Msg("Position has no ISIN, skipping deletion")
				continue
			}
			if err := s.positionRepo.Delete(currentPos.ISIN); err != nil {
				s.log.Error().Err(err).Str("isin", currentPos.ISIN).Str("symbol", currentPos.Symbol).Msg("Failed to delete stale position")
				continue
			}
			s.log.Info().Str("symbol", currentPos.Symbol).Str("isin", currentPos.ISIN).Msg("Deleted stale position not in Tradernet")
			deleted++
		}
	}

	// Step 6: Sync cash balances to cash_balances table
	balances, err := s.tradernetClient.GetCashBalances()
	if err != nil {
		s.log.Warn().Err(err).Msg("Failed to fetch cash balances from Tradernet")
	} else {
		// Update cash balances for each currency
		cashUpdated := 0
		for _, cashBalance := range balances {
			if err := s.cashManager.UpdateCashPosition(cashBalance.Currency, cashBalance.Amount); err != nil {
				s.log.Error().
					Err(err).
					Str("currency", cashBalance.Currency).
					Float64("amount", cashBalance.Amount).
					Msg("Failed to update cash balance")
				continue
			}
			cashUpdated++
		}
		s.log.Info().
			Int("currencies", len(balances)).
			Int("updated", cashUpdated).
			Msg("Cash balances synced")
	}

	s.log.Info().
		Int("upserted", upserted).
		Int("deleted", deleted).
		Int("total", len(positions)).
		Msg("Portfolio sync from Tradernet completed")

	return nil
}
