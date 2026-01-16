package portfolio

import (
	"database/sql"
	"fmt"
	"math"
	"sort"
	"strings"
	"time"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/utils"
	"github.com/rs/zerolog"
)

// SettingsServiceInterface defines the contract for settings operations needed by portfolio
type SettingsServiceInterface interface {
	Get(key string) (interface{}, error)
}

// SecuritySetupServiceInterface defines the contract for adding securities to the universe
// Using interface{} return type to avoid import cycle with universe package
// Note: User-configurable fields (min_lot, allow_buy, allow_sell, priority_multiplier)
// are stored in security_overrides table, not passed during creation.
type SecuritySetupServiceInterface interface {
	AddSecurityByIdentifier(identifier string) (interface{}, error)
}

// PortfolioService orchestrates portfolio operations and calculations.
//
// This is a module-specific service that encapsulates portfolio domain logic.
// It coordinates between repositories, external clients, and shared services
// to provide portfolio business functionality.
//
// Responsibilities:
//   - Calculate portfolio summaries (allocation vs targets)
//   - Aggregate position values by geography/industry
//   - Convert currencies for portfolio totals
//   - Provide portfolio state queries
//
// Dependencies:
//   - PositionRepositoryInterface: Position data access
//   - domain.AllocationTargetProvider: Target allocation configuration
//   - domain.CashManager: Cash balance queries
//   - domain.CurrencyExchangeServiceInterface: Currency conversion (shared service)
//   - domain.TradernetClientInterface: External API access
//
// See internal/services/README.md for service architecture documentation.
//
// Faithful translation from Python: app/modules/portfolio/services/portfolio_service.py

// ExchangeRateCacheServiceInterface defines the contract for exchange rate caching.
type ExchangeRateCacheServiceInterface interface {
	GetRate(fromCurrency, toCurrency string) (float64, error)
}

type PortfolioService struct {
	positionRepo             PositionRepositoryInterface
	allocRepo                domain.AllocationTargetProvider
	cashManager              domain.CashManager // Interface to break circular dependency
	universeDB               *sql.DB            // For querying securities (universe.db)
	securityProvider         SecurityProvider   // Optional: for override support
	brokerClient             domain.BrokerClient
	currencyExchangeService  domain.CurrencyExchangeServiceInterface
	exchangeRateCacheService ExchangeRateCacheServiceInterface // For cached exchange rates
	settingsService          SettingsServiceInterface          // For staleness threshold configuration
	securitySetupService     SecuritySetupServiceInterface     // For auto-adding missing securities
	log                      zerolog.Logger
}

// NewPortfolioService creates a new portfolio service
func NewPortfolioService(
	positionRepo PositionRepositoryInterface,
	allocRepo domain.AllocationTargetProvider,
	cashManager domain.CashManager,
	universeDB *sql.DB,
	securityProvider SecurityProvider,
	brokerClient domain.BrokerClient,
	currencyExchangeService domain.CurrencyExchangeServiceInterface,
	exchangeRateCacheService ExchangeRateCacheServiceInterface,
	settingsService SettingsServiceInterface,
	securitySetupService SecuritySetupServiceInterface,
	log zerolog.Logger,
) *PortfolioService {
	return &PortfolioService{
		positionRepo:             positionRepo,
		allocRepo:                allocRepo,
		cashManager:              cashManager,
		universeDB:               universeDB,
		securityProvider:         securityProvider,
		brokerClient:             brokerClient,
		currencyExchangeService:  currencyExchangeService,
		exchangeRateCacheService: exchangeRateCacheService,
		settingsService:          settingsService,
		securitySetupService:     securitySetupService,
		log:                      log.With().Str("service", "portfolio").Logger(),
	}
}

// GetPortfolioSummary calculates current portfolio allocation vs targets.
// This is the main method for portfolio analysis, aggregating positions by geography
// and industry, converting all values to EUR, and comparing against target allocations.
//
// The method:
// 1. Fetches allocation targets from the allocation repository
// 2. Gets all positions with security metadata (geography, industry)
// 3. Checks for stale price data (warns but doesn't block)
// 4. Aggregates position values by geography and industry (handles comma-separated values)
// 5. Converts cash balances from all currencies to EUR
// 6. Builds allocation status lists showing current vs target percentages
//
// Returns:
//   - PortfolioSummary: Complete portfolio summary with allocations and cash balance
//   - error: Error if data fetching or calculation fails
//
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

	// Check for stale price data (warn only, don't block)
	s.checkPriceStaleness(positions)

	// Get all geographies and industries from active securities in the universe
	// This must happen BEFORE aggregation so we can split securities without
	// geography/industry across ALL known categories
	allStockGeographies, allStockIndustries, err := s.getAllSecurityGeographiesAndIndustries()
	if err != nil {
		return PortfolioSummary{}, fmt.Errorf("failed to get securities: %w", err)
	}

	// Aggregate position values by geography and industry
	geographyValues, industryValues, totalValue := s.aggregatePositionValues(
		positions, allStockGeographies, allStockIndustries,
	)

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

	// Build allocations (using positions-only value for percentage calculations)
	geographyAllocations := s.buildGeographyAllocations(targets, geographyValues, totalValue, allStockGeographies)
	industryAllocations := s.buildIndustryAllocations(targets, industryValues, totalValue, allStockIndustries)

	// Total portfolio value includes cash
	totalPortfolioValue := totalValue + cashBalance

	return PortfolioSummary{
		TotalValue:           round(totalPortfolioValue, 2),
		CashBalance:          round(cashBalance, 2),
		GeographyAllocations: geographyAllocations,
		IndustryAllocations:  industryAllocations,
	}, nil
}

// aggregatePositionValues aggregates position values by geography and industry.
// Both geography and industry support comma-separated values for multiple assignments.
// Securities without a geography are split equally across ALL known geographies.
// Securities without an industry are split equally across ALL known industries.
func (s *PortfolioService) aggregatePositionValues(
	positions []PositionWithSecurity,
	allGeographies map[string]bool,
	allIndustries map[string]bool,
) (map[string]float64, map[string]float64, float64) {
	geographyValues := make(map[string]float64)
	industryValues := make(map[string]float64)
	totalValue := 0.0

	for _, pos := range positions {
		// Note: Cash positions should not exist in positions table after migration
		// If they do (during dual-write phase), they will be filtered out naturally
		// since they won't have matching securities in universe.db

		eurValue := s.calculatePositionValue(pos)
		totalValue += eurValue

		// Aggregate by geography (split if multiple geographies)
		// If no geography assigned, split equally across ALL known geographies
		geographies := utils.ParseCSV(pos.Geography)
		if len(geographies) == 0 && len(allGeographies) > 0 {
			// No geography assigned - split equally across ALL geographies
			splitValue := eurValue / float64(len(allGeographies))
			for geo := range allGeographies {
				geographyValues[geo] += splitValue
			}
		} else if len(geographies) > 0 {
			splitValue := eurValue / float64(len(geographies))
			for _, geo := range geographies {
				geographyValues[geo] += splitValue
			}
		}

		// Aggregate by industry (split if multiple industries)
		// If no industry assigned, split equally across ALL known industries
		industries := utils.ParseCSV(pos.Industry)
		if len(industries) == 0 && len(allIndustries) > 0 {
			// No industry assigned - split equally across ALL industries
			splitValue := eurValue / float64(len(allIndustries))
			for ind := range allIndustries {
				industryValues[ind] += splitValue
			}
		} else if len(industries) > 0 {
			splitValue := eurValue / float64(len(industries))
			for _, ind := range industries {
				industryValues[ind] += splitValue
			}
		}
	}

	return geographyValues, industryValues, totalValue
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

// buildGeographyAllocations builds geography allocation status list
func (s *PortfolioService) buildGeographyAllocations(
	targets map[string]float64,
	geographyValues map[string]float64,
	totalValue float64,
	allStockGeographies map[string]bool,
) []AllocationStatus {
	// Collect all geographies
	allGeographies := make(map[string]bool)
	for key := range targets {
		if strings.HasPrefix(key, "geography:") {
			geography := strings.TrimPrefix(key, "geography:")
			allGeographies[geography] = true
		}
	}
	for geography := range geographyValues {
		allGeographies[geography] = true
	}
	for geography := range allStockGeographies {
		allGeographies[geography] = true
	}

	// Build allocations
	var allocations []AllocationStatus
	for geography := range allGeographies {
		weight := targets[fmt.Sprintf("geography:%s", geography)]
		currentVal := geographyValues[geography]
		currentPct := 0.0
		if totalValue > 0 {
			currentPct = currentVal / totalValue
		}

		allocations = append(allocations, AllocationStatus{
			Category:     "geography",
			Name:         geography,
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

// getAllSecurityGeographiesAndIndustries gets all geographies and industries from active tradable securities (excludes indices)
// Both geography and industry fields can contain comma-separated values
func (s *PortfolioService) getAllSecurityGeographiesAndIndustries() (map[string]bool, map[string]bool, error) {
	geographies := make(map[string]bool)
	industries := make(map[string]bool)

	// SecurityProvider is required - no fallback
	securities, err := s.securityProvider.GetAllActiveTradable()
	if err != nil {
		return nil, nil, fmt.Errorf("failed to get securities: %w", err)
	}

	for _, sec := range securities {
		if sec.Geography != "" {
			geos := utils.ParseCSV(sec.Geography)
			for _, geo := range geos {
				geographies[geo] = true
			}
		}
		if sec.Industry != "" {
			inds := utils.ParseCSV(sec.Industry)
			for _, ind := range inds {
				industries[ind] = true
			}
		}
	}

	return geographies, industries, nil
}

// round rounds a float64 to n decimal places
func round(val float64, decimals int) float64 {
	multiplier := math.Pow(10, float64(decimals))
	return math.Round(val*multiplier) / multiplier
}

// SyncFromTradernet synchronizes positions and cash balances from Tradernet brokerage.
// This method performs a full sync of the portfolio state from the broker:
// 1. Fetches current positions from Tradernet
// 2. Upserts positions to database (auto-adds missing securities to universe)
// 3. Deletes stale positions (in DB but not in Tradernet)
// 4. Syncs cash balances to cash_balances table
//
// Currency conversion: All position values are converted to EUR before storage.
// This ensures the database always contains EUR-normalized values for planning.
//
// Auto-adding securities: If a position references a security not in the universe,
// it is automatically added via SecuritySetupService (full data pipeline).
//
// Returns:
//   - error: Error if broker connection fails or critical database operations fail
func (s *PortfolioService) SyncFromTradernet() error {
	s.log.Info().Msg("Starting portfolio sync from Tradernet")

	if s.brokerClient == nil {
		return fmt.Errorf("tradernet client not available")
	}

	// Step 1: Fetch current positions from Tradernet
	positions, err := s.brokerClient.GetPortfolio()
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

		// Lookup ISIN from securities via provider (required for Upsert)
		// Note: Cash positions should not come from Tradernet positions - they're synced separately
		if s.securityProvider == nil {
			s.log.Error().Msg("Security provider not available, cannot sync positions")
			return fmt.Errorf("security provider not available")
		}

		isin, err := s.securityProvider.GetISINBySymbol(tradernetPos.Symbol)
		if err != nil {
			// Security not in universe - auto-add it
			s.log.Info().
				Str("symbol", tradernetPos.Symbol).
				Msg("Security not found in universe, automatically adding it")

			// Use SecuritySetupService to add the security with full data pipeline
			// Note: User-configurable fields are set via security_overrides after creation
			if s.securitySetupService != nil {
				_, addErr := s.securitySetupService.AddSecurityByIdentifier(tradernetPos.Symbol)
				if addErr != nil {
					s.log.Error().
						Err(addErr).
						Str("symbol", tradernetPos.Symbol).
						Msg("Failed to auto-add security to universe, skipping position")
					continue
				}

				// Retry ISIN lookup after adding security
				isin, err = s.securityProvider.GetISINBySymbol(tradernetPos.Symbol)
				if err != nil {
					s.log.Error().
						Err(err).
						Str("symbol", tradernetPos.Symbol).
						Msg("Failed to lookup ISIN after auto-add, skipping position")
					continue
				}

				s.log.Info().
					Str("symbol", tradernetPos.Symbol).
					Str("isin", isin).
					Msg("Successfully auto-added security to universe")
			} else {
				s.log.Warn().
					Str("symbol", tradernetPos.Symbol).
					Msg("Security not found in universe and setup service not available, skipping position")
				continue
			}
		}
		if isin == "" {
			s.log.Warn().Str("symbol", tradernetPos.Symbol).Msg("Security has no ISIN, skipping position")
			continue
		}

		// Convert tradernet.Position to portfolio.Position
		// Use Tradernet data for position info, but preserve Yahoo prices
		now := time.Now().Unix()
		// Convert tradernet.Position to portfolio.Position
		// Use Tradernet data for all position info including current price
		dbPos := Position{
			ISIN:         isin, // Required for Upsert (PRIMARY KEY)
			Symbol:       tradernetPos.Symbol,
			Quantity:     tradernetPos.Quantity,     // From Tradernet
			AvgPrice:     tradernetPos.AvgPrice,     // From Tradernet (historical)
			CurrentPrice: tradernetPos.CurrentPrice, // From Tradernet (correct currency)
			Currency:     tradernetPos.Currency,     // From Tradernet
			CurrencyRate: 1.0,                       // Will be set below from cache
			LastUpdated:  &now,
		}

		// Fetch currency rate from cache service
		if dbPos.Currency != "" && dbPos.Currency != "EUR" {
			if s.exchangeRateCacheService != nil {
				rate, err := s.exchangeRateCacheService.GetRate(dbPos.Currency, "EUR")
				if err != nil {
					s.log.Warn().
						Err(err).
						Str("currency", dbPos.Currency).
						Str("symbol", dbPos.Symbol).
						Msg("Failed to get cached exchange rate, using fallback")
					// Use hardcoded fallback
					switch dbPos.Currency {
					case "USD":
						dbPos.CurrencyRate = 1.0 / 0.9 // EUR/USD ~= 1.11
					case "GBP":
						dbPos.CurrencyRate = 1.0 / 1.2 // EUR/GBP ~= 0.83
					case "HKD":
						dbPos.CurrencyRate = 1.0 / 0.11 // EUR/HKD ~= 9.09
					default:
						dbPos.CurrencyRate = 1.0
					}
				} else {
					// Convert {Currency}/EUR rate (from GetRate) to storage format
					// GetRate returns "1 USD = X EUR", we need "1 USD / X" for storage
					dbPos.CurrencyRate = 1.0 / rate
				}
			} else {
				// Service not available, use hardcoded fallback rates
				s.log.Warn().
					Str("symbol", dbPos.Symbol).
					Msg("ExchangeRateCacheService not available, using hardcoded fallback")
				// Use hardcoded fallback rates
				switch dbPos.Currency {
				case "USD":
					dbPos.CurrencyRate = 1.0 / 0.9 // EUR/USD ~= 1.11
				case "GBP":
					dbPos.CurrencyRate = 1.0 / 1.2 // EUR/GBP ~= 0.83
				case "HKD":
					dbPos.CurrencyRate = 1.0 / 0.11 // EUR/HKD ~= 9.09
				default:
					dbPos.CurrencyRate = 1.0
				}
			}
		} else {
			dbPos.CurrencyRate = 1.0 // EUR or no currency
		}

		// ===== CURRENCY CONVERSION BOUNDARY =====
		// Convert position market value from native currency to EUR before storing in DB.
		// This ensures the database always contains EUR-normalized values.
		// When planner reads from DB, it gets EUR values directly without needing conversion.
		if dbPos.CurrentPrice > 0 && dbPos.Quantity > 0 {
			valueInCurrency := dbPos.Quantity * dbPos.CurrentPrice
			if dbPos.CurrencyRate > 0 && dbPos.CurrencyRate != 1.0 {
				dbPos.MarketValueEUR = valueInCurrency / dbPos.CurrencyRate
			} else {
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
	balances, err := s.brokerClient.GetCashBalances()
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

// checkPriceStaleness checks if any position prices are stale and logs warnings.
// This is a soft check - it doesn't block operations, just provides visibility.
func (s *PortfolioService) checkPriceStaleness(positions []PositionWithSecurity) {
	// Get max price age from settings (default 48 hours)
	maxAgeHours := 48.0
	if s.settingsService != nil {
		if val, err := s.settingsService.Get("max_price_age_hours"); err == nil {
			if age, ok := val.(float64); ok {
				maxAgeHours = age
			}
		}
	}

	now := time.Now()
	staleCount := 0
	var staleSymbols []string

	for _, pos := range positions {
		if pos.LastUpdated == nil {
			// No update timestamp - warn about missing data
			s.log.Warn().
				Str("symbol", pos.Symbol).
				Msg("Position has no price update timestamp")
			staleCount++
			staleSymbols = append(staleSymbols, pos.Symbol)
			continue
		}

		// Calculate age in hours
		lastUpdatedTime := time.Unix(*pos.LastUpdated, 0)
		age := now.Sub(lastUpdatedTime).Hours()

		if age > maxAgeHours {
			s.log.Warn().
				Str("symbol", pos.Symbol).
				Float64("age_hours", age).
				Float64("max_hours", maxAgeHours).
				Time("last_updated", lastUpdatedTime).
				Msg("Position price data is stale")
			staleCount++
			staleSymbols = append(staleSymbols, pos.Symbol)
		}
	}

	if staleCount > 0 {
		s.log.Warn().
			Int("stale_count", staleCount).
			Int("total_positions", len(positions)).
			Strs("stale_symbols", staleSymbols).
			Float64("max_age_hours", maxAgeHours).
			Msg("Portfolio contains positions with stale price data - consider running price sync")
	} else if len(positions) > 0 {
		s.log.Debug().
			Int("positions", len(positions)).
			Float64("max_age_hours", maxAgeHours).
			Msg("All position prices are fresh")
	}
}
