/**
 * Package services provides core business services shared across multiple modules.
 *
 * This file contains OpportunityContextBuilder which builds complete opportunity
 * context objects for opportunity calculators, planning, and rebalancing.
 */
package services

import (
	"fmt"
	"strings"

	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	scoringdomain "github.com/aristath/sentinel/internal/modules/scoring/domain"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/aristath/sentinel/internal/utils"
	"github.com/rs/zerolog"
)

/**
 * OpportunityContextBuilder builds complete OpportunityContext with all required data.
 *
 * This is the single source of truth for context building across all consumers.
 *
 * It consolidates logic from:
 * - scheduler/build_opportunity_context.go (most complete - scoring, weights, risk metrics)
 * - opportunities/handlers/handlers.go (cooloff from trades and pending orders)
 * - rebalancing/service.go (partial implementation)
 *
 * The builder fetches all required data (positions, securities, scores, cash, etc.)
 * and constructs a comprehensive context object that opportunity calculators,
 * planning, and rebalancing services can use.
 */
type OpportunityContextBuilder struct {
	positionRepo           PositionRepository              // Position repository
	securityRepo           SecurityRepository              // Security repository
	allocRepo              AllocationRepository            // Allocation repository
	tradeRepo              TradeRepository                 // Trade repository
	scoresRepo             ScoresRepository                // Scores repository
	settingsRepo           SettingsRepository              // Settings repository
	regimeRepo             RegimeRepository                // Regime repository
	cashManager            CashManager                     // Cash manager
	priceClient            PriceClient                     // Price client for current prices
	priceConversionService PriceConversionServiceInterface // Price conversion service
	brokerClient           BrokerClient                    // Broker client for pending orders
	returnsCalc            ExpectedReturnsCalculator       // Expected returns calculator (uses existing optimization logic)
	log                    zerolog.Logger                  // Structured logger
}

/**
 * NewOpportunityContextBuilder creates a new builder with all dependencies.
 *
 * @param positionRepo - Position repository
 * @param securityRepo - Security repository
 * @param allocRepo - Allocation repository
 * @param tradeRepo - Trade repository
 * @param scoresRepo - Scores repository
 * @param settingsRepo - Settings repository
 * @param regimeRepo - Regime repository
 * @param cashManager - Cash manager
 * @param priceClient - Price client for current prices
 * @param priceConversionService - Price conversion service
 * @param brokerClient - Broker client for pending orders
 * @param returnsCalc - Expected returns calculator (uses existing optimization logic)
 * @param log - Structured logger
 * @returns *OpportunityContextBuilder - New opportunity context builder instance
 */
func NewOpportunityContextBuilder(
	positionRepo PositionRepository,
	securityRepo SecurityRepository,
	allocRepo AllocationRepository,
	tradeRepo TradeRepository,
	scoresRepo ScoresRepository,
	settingsRepo SettingsRepository,
	regimeRepo RegimeRepository,
	cashManager CashManager,
	priceClient PriceClient,
	priceConversionService PriceConversionServiceInterface,
	brokerClient BrokerClient,
	returnsCalc ExpectedReturnsCalculator,
	log zerolog.Logger,
) *OpportunityContextBuilder {
	return &OpportunityContextBuilder{
		positionRepo:           positionRepo,
		securityRepo:           securityRepo,
		allocRepo:              allocRepo,
		tradeRepo:              tradeRepo,
		scoresRepo:             scoresRepo,
		settingsRepo:           settingsRepo,
		regimeRepo:             regimeRepo,
		cashManager:            cashManager,
		priceClient:            priceClient,
		priceConversionService: priceConversionService,
		brokerClient:           brokerClient,
		returnsCalc:            returnsCalc,
		log:                    log.With().Str("service", "opportunity_context_builder").Logger(),
	}
}

/**
 * Build creates a complete OpportunityContext with all fields populated.
 *
 * This method fetches all required data from repositories and builds a comprehensive
 * context object that includes:
 * - Positions and securities
 * - Allocation targets and current allocations
 * - Cash balances (including virtual test cash in research mode)
 * - Security scores (total, CAGR, quality, stability)
 * - Risk metrics (Sharpe, max drawdown)
 * - Value trap data (opportunity scores, momentum, volatility)
 * - Regime score
 * - Cooloff data (recently traded securities, pending orders)
 * - Current prices
 * - Target weights (from optimizer or allocation targets)
 *
 * Parameters:
 *   - optimizerWeights: ISIN-keyed target weights from optimizer (e.g., {"NL0010273215": 0.05})
 *     Pass nil to use allocation targets from database instead
 *
 * Returns error if critical data cannot be loaded.
 *
 * @param optimizerWeights - Optional optimizer weights (nil to use allocation targets)
 * @returns *planningdomain.OpportunityContext - Complete opportunity context
 * @returns error - Error if context building fails
 */
func (b *OpportunityContextBuilder) Build(optimizerWeights map[string]float64) (*planningdomain.OpportunityContext, error) {
	b.log.Debug().Msg("Building opportunity context")

	// Step 1: Get positions
	positions, err := b.positionRepo.GetAll()
	if err != nil {
		return nil, fmt.Errorf("failed to get positions: %w", err)
	}

	// Step 2: Get securities
	securities, err := b.securityRepo.GetAllActive()
	if err != nil {
		return nil, fmt.Errorf("failed to get securities: %w", err)
	}

	// Step 3: Get allocations
	allocations, err := b.allocRepo.GetAll()
	if err != nil {
		b.log.Warn().Err(err).Msg("Failed to get allocations, using empty")
		allocations = make(map[string]float64)
	}

	// Step 4: Get cash balances
	cashBalances := make(map[string]float64)
	if b.cashManager != nil {
		balances, err := b.cashManager.GetAllCashBalances()
		if err != nil {
			b.log.Warn().Err(err).Msg("Failed to get cash balances, using empty")
		} else {
			cashBalances = balances
		}
	}

	// Step 5: Add virtual test cash if configured (research mode)
	if b.settingsRepo != nil {
		virtualCash, err := b.settingsRepo.GetVirtualTestCash()
		if err == nil && virtualCash > 0 {
			cashBalances["EUR"] += virtualCash
			b.log.Debug().Float64("virtual_cash", virtualCash).Msg("Added virtual test cash")
		}
	}

	// Step 6: Build the context
	return b.buildContext(positions, securities, allocations, cashBalances, optimizerWeights)
}

// buildContext creates the OpportunityContext from the gathered data.
func (b *OpportunityContextBuilder) buildContext(
	positions []portfolio.Position,
	securities []universe.Security,
	allocations map[string]float64,
	cashBalances map[string]float64,
	optimizerWeights map[string]float64,
) (*planningdomain.OpportunityContext, error) {
	// Convert securities to domain format and build lookup maps
	domainSecurities := make([]universe.Security, 0, len(securities))
	stocksByISIN := make(map[string]universe.Security)
	symbolToISIN := make(map[string]string)

	for _, sec := range securities {
		domainSec := universe.Security{
			Symbol:    sec.Symbol,
			ISIN:      sec.ISIN,
			Geography: sec.Geography,
			Currency:  sec.Currency,
			Name:      sec.Name,
			AllowBuy:  sec.AllowBuy,
			AllowSell: sec.AllowSell,
			MinLot:    sec.MinLot,
		}
		domainSecurities = append(domainSecurities, domainSec)
		if sec.ISIN != "" {
			stocksByISIN[sec.ISIN] = domainSec
			if sec.Symbol != "" {
				symbolToISIN[sec.Symbol] = sec.ISIN
			}
		}
	}

	// Fetch current prices
	currentPrices := b.fetchCurrentPrices(securities, symbolToISIN)

	// Build enriched positions and calculate totals
	enrichedPositions, totalValue := b.buildEnrichedPositions(positions, stocksByISIN, currentPrices, cashBalances)

	// Get geography weights (CRITICAL - was missing from handler)
	// Pass securities to filter weights to only active geographies
	geographyWeights := b.populateGeographyWeights(securities)

	// Calculate geography allocations from positions
	// Pass geographyWeights so securities without geography can be split across ALL
	geographyAllocations := b.calculateGeographyAllocations(enrichedPositions, totalValue, geographyWeights)

	// Get industry weights (filter to only active industries)
	industryWeights := b.populateIndustryWeights(securities)

	// Calculate industry allocations from positions
	industryAllocations := b.calculateIndustryAllocations(enrichedPositions, totalValue, industryWeights)

	// Get security scores
	isinList := b.getISINList(securities)
	securityScores := b.populateSecurityScores(isinList)

	// Get CAGRs and target return settings
	cagrs := b.populateCAGRs(isinList)
	targetReturn, thresholdPct := b.getTargetReturnSettings()

	// Get regime score (needed for expected returns calculation)
	regimeScore := b.getRegimeScore()

	// Calculate expected returns using the unified optimization calculator
	// This applies multipliers, regime adjustment, and minimum return filter
	var expectedReturns map[string]float64
	if b.returnsCalc != nil {
		var err error
		expectedReturns, err = b.returnsCalc.CalculateExpectedReturnsForUniverse(
			securities,
			regimeScore,
			targetReturn,
			thresholdPct,
		)
		if err != nil {
			b.log.Warn().Err(err).Msg("Failed to calculate expected returns, using empty map")
			expectedReturns = make(map[string]float64)
		}
	} else {
		expectedReturns = make(map[string]float64)
	}

	// Get quality scores
	longTermScores, stabilityScores := b.populateQualityScores(isinList)

	// Get value trap data
	opportunityScores, momentumScores, volatility := b.populateValueTrapData(isinList)

	// Note: regimeScore already fetched above for expected returns calculation

	// Get risk metrics
	sharpe, maxDrawdown := b.populateRiskMetrics(isinList)

	// Get cooloff data from trades
	recentlySoldISINs, recentlyBoughtISINs := b.populateCooloffFromTrades()

	// Add pending orders to cooloff (CRITICAL - broker-assumed trades)
	b.addPendingOrdersToCooloff(recentlySoldISINs, recentlyBoughtISINs, symbolToISIN)

	// Get available cash in EUR
	availableCashEUR := cashBalances["EUR"]

	// Build PortfolioContext for scoring
	portfolioCtx := b.buildPortfolioContext(enrichedPositions, geographyWeights, industryWeights, currentPrices, totalValue)

	// Use optimizer weights if provided, otherwise fall back to allocations
	targetWeights := optimizerWeights
	if len(targetWeights) == 0 {
		targetWeights = allocations
	}

	return &planningdomain.OpportunityContext{
		PortfolioContext:         portfolioCtx,
		EnrichedPositions:        enrichedPositions,
		Securities:               domainSecurities,
		StocksByISIN:             stocksByISIN,
		AvailableCashEUR:         availableCashEUR,
		TotalPortfolioValueEUR:   totalValue,
		CurrentPrices:            currentPrices,
		SecurityScores:           securityScores,
		TargetWeights:            targetWeights,
		GeographyAllocations:     geographyAllocations,
		GeographyWeights:         geographyWeights,
		IndustryAllocations:      industryAllocations,
		IndustryWeights:          industryWeights,
		CAGRs:                    cagrs,
		ExpectedReturns:          expectedReturns,
		LongTermScores:           longTermScores,
		StabilityScores:          stabilityScores,
		TargetReturn:             targetReturn,
		TargetReturnThresholdPct: thresholdPct,
		OpportunityScores:        opportunityScores,
		MomentumScores:           momentumScores,
		Volatility:               volatility,
		RegimeScore:              regimeScore,
		Sharpe:                   sharpe,
		MaxDrawdown:              maxDrawdown,
		RecentlySoldISINs:        recentlySoldISINs,
		RecentlyBoughtISINs:      recentlyBoughtISINs,
		IneligibleISINs:          make(map[string]bool),
		TransactionCostFixed:     2.0,
		TransactionCostPercent:   0.002,
		AllowSell:                true,
		AllowBuy:                 true,
	}, nil
}

// fetchCurrentPrices fetches current prices for all securities and converts to EUR.
func (b *OpportunityContextBuilder) fetchCurrentPrices(securities []universe.Security, symbolToISIN map[string]string) map[string]float64 {
	prices := make(map[string]float64)

	if b.priceClient == nil {
		b.log.Warn().Msg("Price client not available, using empty prices")
		return prices
	}

	// Build symbol map for batch query
	symbolMap := make(map[string]*string)
	for _, sec := range securities {
		symbolMap[sec.Symbol] = nil
	}

	// Fetch prices
	rawPrices, err := b.priceClient.GetBatchQuotes(symbolMap)
	if err != nil {
		b.log.Warn().Err(err).Msg("Failed to fetch prices")
		return prices
	}

	// Convert to symbol -> price map
	symbolPrices := make(map[string]float64)
	for symbol, price := range rawPrices {
		if price != nil && *price > 0 {
			symbolPrices[symbol] = *price
		}
	}

	// Convert prices to EUR using PriceConversionService
	var eurPrices map[string]float64
	if b.priceConversionService != nil {
		eurPrices = b.priceConversionService.ConvertPricesToEUR(symbolPrices, securities)
	} else {
		eurPrices = symbolPrices
	}

	// Convert to ISIN-keyed map
	for symbol, price := range eurPrices {
		if isin, ok := symbolToISIN[symbol]; ok {
			prices[isin] = price
		}
	}

	return prices
}

// buildEnrichedPositions builds enriched positions and calculates total portfolio value.
func (b *OpportunityContextBuilder) buildEnrichedPositions(
	positions []portfolio.Position,
	stocksByISIN map[string]universe.Security,
	currentPrices map[string]float64,
	cashBalances map[string]float64,
) ([]planningdomain.EnrichedPosition, float64) {
	enrichedPositions := make([]planningdomain.EnrichedPosition, 0, len(positions))

	// Start with cash
	totalValue := cashBalances["EUR"]

	for _, pos := range positions {
		isin := pos.ISIN
		if isin == "" {
			continue
		}

		security, ok := stocksByISIN[isin]
		if !ok {
			continue
		}

		// Get current price
		currentPrice, hasPriceFromMap := currentPrices[isin]
		if !hasPriceFromMap || currentPrice <= 0 {
			// Use position's current price if available
			if pos.CurrentPrice > 0 {
				currentPrice = pos.CurrentPrice
			} else {
				continue
			}
		}

		// Calculate market value
		marketValueEUR := currentPrice * pos.Quantity
		totalValue += marketValueEUR

		// Get universe security for trading constraints
		var allowBuy, allowSell bool
		var minLot int
		if univSec, err := b.securityRepo.GetByISIN(isin); err == nil && univSec != nil {
			allowBuy = univSec.AllowBuy
			allowSell = univSec.AllowSell
			minLot = univSec.MinLot
		} else {
			allowBuy = security.AllowBuy
			allowSell = security.AllowSell
			minLot = security.MinLot
		}

		enriched := planningdomain.EnrichedPosition{
			ISIN:           isin,
			Symbol:         pos.Symbol,
			Quantity:       pos.Quantity,
			Currency:       pos.Currency,
			AverageCost:    pos.AvgPrice,
			MarketValueEUR: marketValueEUR,
			CurrentPrice:   currentPrice,
			SecurityName:   security.Name,
			Geography:      security.Geography,
			Industry:       security.Industry,
			AllowBuy:       allowBuy,
			AllowSell:      allowSell,
			MinLot:         minLot,
		}
		enrichedPositions = append(enrichedPositions, enriched)
	}

	// Calculate WeightInPortfolio for each position
	if totalValue > 0 {
		for i := range enrichedPositions {
			pos := &enrichedPositions[i]
			pos.WeightInPortfolio = pos.MarketValueEUR / totalValue
		}
	}

	return enrichedPositions, totalValue
}

// populateGeographyWeights gets geography weights from allocation targets.
// Filters weights to only include geographies that exist in the active securities
// (excluding index securities), then normalizes to sum to 1.0.
func (b *OpportunityContextBuilder) populateGeographyWeights(securities []universe.Security) map[string]float64 {
	if b.allocRepo == nil {
		return make(map[string]float64)
	}

	weights, err := b.allocRepo.GetGeographyTargets()
	if err != nil {
		b.log.Warn().Err(err).Msg("Failed to get geography weights")
		return make(map[string]float64)
	}

	// Extract unique geographies from active non-index securities
	activeGeographies := extractUniqueGeographies(securities)

	// Filter weights to only include geographies present in the universe
	filteredWeights := make(map[string]float64)
	for geo, weight := range weights {
		if activeGeographies[geo] {
			filteredWeights[geo] = weight
		}
	}

	if len(filteredWeights) == 0 {
		b.log.Warn().
			Int("configured_targets", len(weights)).
			Int("active_geographies", len(activeGeographies)).
			Msg("No matching geographies found between targets and universe")
		return make(map[string]float64)
	}

	b.log.Debug().
		Int("configured_targets", len(weights)).
		Int("active_geographies", len(activeGeographies)).
		Int("filtered_targets", len(filteredWeights)).
		Msg("Filtered geography weights to active geographies")

	// Normalize filtered weights to ensure they sum to 1.0
	return normalizeWeights(filteredWeights)
}

// calculateGeographyAllocations calculates current geography allocations from positions.
// Securities with multiple geographies have their value split proportionally.
// Securities without a geography are split equally across ALL known geographies.
func (b *OpportunityContextBuilder) calculateGeographyAllocations(
	positions []planningdomain.EnrichedPosition,
	totalValue float64,
	allGeographies map[string]float64,
) map[string]float64 {
	allocations := make(map[string]float64)

	if totalValue <= 0 {
		return allocations
	}

	// Sum values by geography (direct - no group mapping)
	geographyValues := make(map[string]float64)
	for _, pos := range positions {
		// Parse comma-separated geographies
		geographies := utils.ParseCSV(pos.Geography)

		if len(geographies) == 0 && len(allGeographies) > 0 {
			// No geography assigned - split equally across ALL known geographies
			valuePerGeo := pos.MarketValueEUR / float64(len(allGeographies))
			for geo := range allGeographies {
				geographyValues[geo] += valuePerGeo
			}
		} else if len(geographies) > 0 {
			// Split value proportionally across specified geographies
			valuePerGeo := pos.MarketValueEUR / float64(len(geographies))
			for _, geo := range geographies {
				geographyValues[geo] += valuePerGeo
			}
		}
	}

	// Convert to percentages
	for geo, value := range geographyValues {
		allocations[geo] = value / totalValue
	}

	return allocations
}

// populateIndustryWeights gets industry weights from allocation targets.
// Filters weights to only include industries that exist in the active securities
// (excluding index securities), then normalizes to sum to 1.0.
func (b *OpportunityContextBuilder) populateIndustryWeights(securities []universe.Security) map[string]float64 {
	if b.allocRepo == nil {
		return make(map[string]float64)
	}

	weights, err := b.allocRepo.GetIndustryTargets()
	if err != nil {
		b.log.Warn().Err(err).Msg("Failed to get industry weights")
		return make(map[string]float64)
	}

	// Extract unique industries from active non-index securities
	activeIndustries := extractUniqueIndustries(securities)

	// Filter weights to only include industries present in the universe
	filteredWeights := make(map[string]float64)
	for industry, weight := range weights {
		if activeIndustries[industry] {
			filteredWeights[industry] = weight
		}
	}

	if len(filteredWeights) == 0 {
		b.log.Warn().
			Int("configured_targets", len(weights)).
			Int("active_industries", len(activeIndustries)).
			Msg("No matching industries found between targets and universe")
		return make(map[string]float64)
	}

	b.log.Debug().
		Int("configured_targets", len(weights)).
		Int("active_industries", len(activeIndustries)).
		Int("filtered_targets", len(filteredWeights)).
		Msg("Filtered industry weights to active industries")

	// Normalize filtered weights to ensure they sum to 1.0
	return normalizeWeights(filteredWeights)
}

// calculateIndustryAllocations calculates current industry allocations from positions.
// Securities with multiple industries have their value split proportionally.
// Securities without an industry are split equally across ALL known industries.
func (b *OpportunityContextBuilder) calculateIndustryAllocations(
	positions []planningdomain.EnrichedPosition,
	totalValue float64,
	allIndustries map[string]float64,
) map[string]float64 {
	allocations := make(map[string]float64)

	if totalValue <= 0 {
		return allocations
	}

	// Sum values by industry (direct - no group mapping)
	industryValues := make(map[string]float64)
	for _, pos := range positions {
		// Parse comma-separated industries
		industries := utils.ParseCSV(pos.Industry)

		if len(industries) == 0 && len(allIndustries) > 0 {
			// No industry assigned - split equally across ALL known industries
			valuePerIndustry := pos.MarketValueEUR / float64(len(allIndustries))
			for industry := range allIndustries {
				industryValues[industry] += valuePerIndustry
			}
		} else if len(industries) > 0 {
			// Split value proportionally across specified industries
			valuePerIndustry := pos.MarketValueEUR / float64(len(industries))
			for _, industry := range industries {
				industryValues[industry] += valuePerIndustry
			}
		}
	}

	// Convert to percentages
	for industry, value := range industryValues {
		allocations[industry] = value / totalValue
	}

	return allocations
}

// getISINList extracts ISINs from securities.
func (b *OpportunityContextBuilder) getISINList(securities []universe.Security) []string {
	isins := make([]string, 0, len(securities))
	for _, sec := range securities {
		if sec.ISIN != "" {
			isins = append(isins, sec.ISIN)
		}
	}
	return isins
}

// populateSecurityScores gets total scores for securities.
func (b *OpportunityContextBuilder) populateSecurityScores(isinList []string) map[string]float64 {
	if b.scoresRepo == nil || len(isinList) == 0 {
		return make(map[string]float64)
	}

	scores, err := b.scoresRepo.GetTotalScores(isinList)
	if err != nil {
		b.log.Warn().Err(err).Msg("Failed to get security scores")
		return make(map[string]float64)
	}

	return scores
}

// populateCAGRs gets CAGR values for securities.
func (b *OpportunityContextBuilder) populateCAGRs(isinList []string) map[string]float64 {
	if b.scoresRepo == nil || len(isinList) == 0 {
		return make(map[string]float64)
	}

	cagrs, err := b.scoresRepo.GetCAGRs(isinList)
	if err != nil {
		b.log.Warn().Err(err).Msg("Failed to get CAGRs")
		return make(map[string]float64)
	}

	return cagrs
}

// getTargetReturnSettings gets target return settings.
func (b *OpportunityContextBuilder) getTargetReturnSettings() (float64, float64) {
	if b.settingsRepo == nil {
		return 0.11, 0.80 // Defaults
	}

	targetReturn, thresholdPct, err := b.settingsRepo.GetTargetReturnSettings()
	if err != nil {
		b.log.Warn().Err(err).Msg("Failed to get target return settings, using defaults")
		return 0.11, 0.80
	}

	return targetReturn, thresholdPct
}

// populateQualityScores gets long-term and stability scores.
func (b *OpportunityContextBuilder) populateQualityScores(isinList []string) (map[string]float64, map[string]float64) {
	if b.scoresRepo == nil || len(isinList) == 0 {
		return make(map[string]float64), make(map[string]float64)
	}

	longTerm, stability, err := b.scoresRepo.GetQualityScores(isinList)
	if err != nil {
		b.log.Warn().Err(err).Msg("Failed to get quality scores")
		return make(map[string]float64), make(map[string]float64)
	}

	return longTerm, stability
}

// populateValueTrapData gets value trap detection data.
func (b *OpportunityContextBuilder) populateValueTrapData(isinList []string) (map[string]float64, map[string]float64, map[string]float64) {
	if b.scoresRepo == nil || len(isinList) == 0 {
		return make(map[string]float64), make(map[string]float64), make(map[string]float64)
	}

	opportunity, momentum, volatility, err := b.scoresRepo.GetValueTrapData(isinList)
	if err != nil {
		b.log.Warn().Err(err).Msg("Failed to get value trap data")
		return make(map[string]float64), make(map[string]float64), make(map[string]float64)
	}

	return opportunity, momentum, volatility
}

// getRegimeScore gets the current market regime score.
func (b *OpportunityContextBuilder) getRegimeScore() float64 {
	if b.regimeRepo == nil {
		return 0.0
	}

	score, err := b.regimeRepo.GetCurrentRegimeScore()
	if err != nil {
		b.log.Warn().Err(err).Msg("Failed to get regime score")
		return 0.0
	}

	return score
}

// populateRiskMetrics gets Sharpe ratio and max drawdown.
func (b *OpportunityContextBuilder) populateRiskMetrics(isinList []string) (map[string]float64, map[string]float64) {
	if b.scoresRepo == nil || len(isinList) == 0 {
		return make(map[string]float64), make(map[string]float64)
	}

	sharpe, maxDrawdown, err := b.scoresRepo.GetRiskMetrics(isinList)
	if err != nil {
		b.log.Warn().Err(err).Msg("Failed to get risk metrics")
		return make(map[string]float64), make(map[string]float64)
	}

	return sharpe, maxDrawdown
}

// populateCooloffFromTrades gets recently traded ISINs from trade repository.
func (b *OpportunityContextBuilder) populateCooloffFromTrades() (map[string]bool, map[string]bool) {
	recentlySold := make(map[string]bool)
	recentlyBought := make(map[string]bool)

	if b.tradeRepo == nil {
		return recentlySold, recentlyBought
	}

	// Check if cooloff is disabled (only works in research mode)
	if b.settingsRepo != nil {
		if disabled, err := b.settingsRepo.IsCooloffDisabled(); err == nil && disabled {
			b.log.Info().Msg("Cooloff checks disabled - skipping trade-based cooloff")
			return recentlySold, recentlyBought
		}
	}

	// Get cooloff days from settings
	cooloffDays := 180 // Default
	if b.settingsRepo != nil {
		if days, err := b.settingsRepo.GetCooloffDays(); err == nil && days > 0 {
			cooloffDays = days
		}
	}

	// Get recently sold ISINs
	sold, err := b.tradeRepo.GetRecentlySoldISINs(cooloffDays)
	if err != nil {
		b.log.Warn().Err(err).Int("days", cooloffDays).Msg("Failed to get recently sold ISINs")
	} else {
		for isin := range sold {
			recentlySold[isin] = true
		}
		b.log.Debug().Int("count", len(sold)).Int("days", cooloffDays).Msg("Loaded recently sold ISINs")
	}

	// Get recently bought ISINs
	bought, err := b.tradeRepo.GetRecentlyBoughtISINs(cooloffDays)
	if err != nil {
		b.log.Warn().Err(err).Int("days", cooloffDays).Msg("Failed to get recently bought ISINs")
	} else {
		for isin := range bought {
			recentlyBought[isin] = true
		}
		b.log.Debug().Int("count", len(bought)).Int("days", cooloffDays).Msg("Loaded recently bought ISINs")
	}

	return recentlySold, recentlyBought
}

// addPendingOrdersToCooloff adds pending orders to cooloff maps.
// Assumes pending orders will complete successfully.
func (b *OpportunityContextBuilder) addPendingOrdersToCooloff(
	recentlySold map[string]bool,
	recentlyBought map[string]bool,
	symbolToISIN map[string]string,
) {
	// Check if cooloff is disabled (only works in research mode)
	if b.settingsRepo != nil {
		if disabled, err := b.settingsRepo.IsCooloffDisabled(); err == nil && disabled {
			b.log.Info().Msg("Cooloff checks disabled - skipping pending orders cooloff")
			return
		}
	}

	if b.brokerClient == nil || !b.brokerClient.IsConnected() {
		b.log.Debug().Msg("Broker not connected, skipping pending orders for cooloff")
		return
	}

	pendingOrders, err := b.brokerClient.GetPendingOrders()
	if err != nil {
		b.log.Warn().Err(err).Msg("Failed to get pending orders for cooloff")
		return
	}

	for _, order := range pendingOrders {
		// Look up ISIN from symbol
		isin, ok := symbolToISIN[order.Symbol]
		if !ok {
			// Try to look up from security repository
			if sec, err := b.securityRepo.GetBySymbol(order.Symbol); err == nil && sec != nil {
				isin = sec.ISIN
			} else {
				b.log.Debug().Str("symbol", order.Symbol).Msg("Could not find ISIN for pending order")
				continue
			}
		}

		// Add to appropriate cooloff map
		if order.Side == "BUY" {
			recentlyBought[isin] = true
			b.log.Debug().Str("symbol", order.Symbol).Str("isin", isin).Msg("Added pending BUY to cooloff")
		} else if order.Side == "SELL" {
			recentlySold[isin] = true
			b.log.Debug().Str("symbol", order.Symbol).Str("isin", isin).Msg("Added pending SELL to cooloff")
		}
	}

	if len(pendingOrders) > 0 {
		b.log.Info().Int("pending_orders", len(pendingOrders)).Msg("Added pending orders to cooloff")
	}
}

// buildPortfolioContext builds the scoring PortfolioContext.
func (b *OpportunityContextBuilder) buildPortfolioContext(
	positions []planningdomain.EnrichedPosition,
	geographyWeights map[string]float64,
	industryWeights map[string]float64,
	currentPrices map[string]float64,
	totalValue float64,
) *scoringdomain.PortfolioContext {
	// Build position values map
	positionValues := make(map[string]float64)
	positionAvgPrices := make(map[string]float64)
	securityGeographies := make(map[string]string)
	securityIndustries := make(map[string]string)

	for _, pos := range positions {
		positionValues[pos.ISIN] = pos.MarketValueEUR
		positionAvgPrices[pos.ISIN] = pos.AverageCost
		securityGeographies[pos.ISIN] = pos.Geography
		securityIndustries[pos.ISIN] = pos.Industry
	}

	return &scoringdomain.PortfolioContext{
		GeographyWeights:    geographyWeights,
		IndustryWeights:     industryWeights,
		Positions:           positionValues,
		SecurityGeographies: securityGeographies,
		SecurityIndustries:  securityIndustries,
		PositionAvgPrices:   positionAvgPrices,
		CurrentPrices:       currentPrices,
		TotalValue:          totalValue,
	}
}

// normalizeWeights normalizes a map of weights to sum to 1.0.
func normalizeWeights(weights map[string]float64) map[string]float64 {
	if len(weights) == 0 {
		return weights
	}

	total := 0.0
	for _, w := range weights {
		total += w
	}

	if total == 0 {
		return weights
	}

	normalized := make(map[string]float64, len(weights))
	for k, v := range weights {
		normalized[k] = v / total
	}

	return normalized
}

// extractUniqueGeographies extracts all unique geographies from non-index securities.
// Handles comma-separated geographies (e.g., "EU, US, AS") by splitting them.
// Excludes securities with symbols ending in ".IDX".
func extractUniqueGeographies(securities []universe.Security) map[string]bool {
	geographies := make(map[string]bool)

	for _, sec := range securities {
		// Skip index securities
		if strings.HasSuffix(sec.Symbol, ".IDX") {
			continue
		}

		// Skip if no geography assigned
		if sec.Geography == "" {
			continue
		}

		// Parse comma-separated geographies
		geos := utils.ParseCSV(sec.Geography)
		for _, geo := range geos {
			geographies[geo] = true
		}
	}

	return geographies
}

// extractUniqueIndustries extracts all unique industries from non-index securities.
// Handles comma-separated industries (e.g., "Finance, Technology") by splitting them.
// Excludes securities with symbols ending in ".IDX".
func extractUniqueIndustries(securities []universe.Security) map[string]bool {
	industries := make(map[string]bool)

	for _, sec := range securities {
		// Skip index securities
		if strings.HasSuffix(sec.Symbol, ".IDX") {
			continue
		}

		// Skip if no industry assigned
		if sec.Industry == "" {
			continue
		}

		// Parse comma-separated industries
		inds := utils.ParseCSV(sec.Industry)
		for _, ind := range inds {
			industries[ind] = true
		}
	}

	return industries
}
