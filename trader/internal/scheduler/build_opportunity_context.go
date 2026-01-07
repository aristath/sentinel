package scheduler

import (
	"fmt"
	"strings"

	"github.com/aristath/sentinel/internal/domain"
	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/scoring"
	scoringdomain "github.com/aristath/sentinel/internal/modules/scoring/domain"
	"github.com/aristath/sentinel/internal/modules/settings"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
)

// BuildOpportunityContextJob builds the opportunity context from current portfolio state
type BuildOpportunityContextJob struct {
	log                    zerolog.Logger
	positionRepo           PositionRepositoryInterface
	securityRepo           SecurityRepositoryInterface
	allocRepo              AllocationRepositoryInterface
	cashManager            CashManagerInterface
	priceClient            PriceClientInterface
	scoresRepo             ScoresRepositoryInterface
	settingsRepo           SettingsRepositoryInterface
	regimeRepo             RegimeRepositoryInterface
	optimizerTargetWeights map[string]float64
	opportunityContext     *planningdomain.OpportunityContext
}

// NewBuildOpportunityContextJob creates a new BuildOpportunityContextJob
func NewBuildOpportunityContextJob(
	positionRepo PositionRepositoryInterface,
	securityRepo SecurityRepositoryInterface,
	allocRepo AllocationRepositoryInterface,
	cashManager CashManagerInterface,
	priceClient PriceClientInterface,
	scoresRepo ScoresRepositoryInterface,
	settingsRepo SettingsRepositoryInterface,
	regimeRepo RegimeRepositoryInterface,
) *BuildOpportunityContextJob {
	return &BuildOpportunityContextJob{
		log:          zerolog.Nop(),
		positionRepo: positionRepo,
		securityRepo: securityRepo,
		allocRepo:    allocRepo,
		cashManager:  cashManager,
		priceClient:  priceClient,
		scoresRepo:   scoresRepo,
		settingsRepo: settingsRepo,
		regimeRepo:   regimeRepo,
	}
}

// SetLogger sets the logger for the job
func (j *BuildOpportunityContextJob) SetLogger(log zerolog.Logger) {
	j.log = log
}

// SetOptimizerTargetWeights sets the optimizer target weights
func (j *BuildOpportunityContextJob) SetOptimizerTargetWeights(weights map[string]float64) {
	j.optimizerTargetWeights = weights
}

// GetOpportunityContext returns the built opportunity context
func (j *BuildOpportunityContextJob) GetOpportunityContext() *planningdomain.OpportunityContext {
	return j.opportunityContext
}

// Name returns the job name
func (j *BuildOpportunityContextJob) Name() string {
	return "build_opportunity_context"
}

// Run executes the build opportunity context job
func (j *BuildOpportunityContextJob) Run() error {
	// Step 1: Get positions
	positionsInterface, err := j.positionRepo.GetAll()
	if err != nil {
		j.log.Error().Err(err).Msg("Failed to get positions")
		return fmt.Errorf("failed to get positions: %w", err)
	}

	positions := make([]portfolio.Position, 0, len(positionsInterface))
	for _, p := range positionsInterface {
		if pos, ok := p.(portfolio.Position); ok {
			positions = append(positions, pos)
		} else if posPtr, ok := p.(*portfolio.Position); ok {
			positions = append(positions, *posPtr)
		}
	}

	// Step 2: Get securities
	securitiesInterface, err := j.securityRepo.GetAllActive()
	if err != nil {
		j.log.Error().Err(err).Msg("Failed to get securities")
		return fmt.Errorf("failed to get securities: %w", err)
	}

	securities := make([]universe.Security, 0, len(securitiesInterface))
	for _, s := range securitiesInterface {
		if sec, ok := s.(universe.Security); ok {
			securities = append(securities, sec)
		} else if secPtr, ok := s.(*universe.Security); ok {
			securities = append(securities, *secPtr)
		}
	}

	// Step 3: Get allocations
	allocations, err := j.allocRepo.GetAll()
	if err != nil {
		j.log.Error().Err(err).Msg("Failed to get allocations")
		return fmt.Errorf("failed to get allocations: %w", err)
	}

	// Step 4: Get cash balances
	cashBalances := make(map[string]float64)
	if j.cashManager != nil {
		balances, err := j.cashManager.GetAllCashBalances()
		if err != nil {
			j.log.Warn().Err(err).Msg("Failed to get cash balances, using empty")
		} else {
			cashBalances = balances
		}
	}

	// Step 5: Add virtual test cash if in research mode
	if err := j.addVirtualTestCash(cashBalances); err != nil {
		j.log.Warn().Err(err).Msg("Failed to add virtual test cash, continuing without it")
	}

	// Step 6: Build opportunity context
	ctx, err := j.buildOpportunityContext(positions, securities, allocations, cashBalances)
	if err != nil {
		j.log.Error().Err(err).Msg("Failed to build opportunity context")
		return fmt.Errorf("failed to build opportunity context: %w", err)
	}

	j.opportunityContext = ctx

	j.log.Info().
		Int("positions", len(positions)).
		Int("securities", len(securities)).
		Float64("total_value", ctx.TotalPortfolioValueEUR).
		Msg("Successfully built opportunity context")

	return nil
}

// buildOpportunityContext creates an opportunity context from current portfolio state
func (j *BuildOpportunityContextJob) buildOpportunityContext(
	positions []portfolio.Position,
	securities []universe.Security,
	allocations map[string]float64,
	cashBalances map[string]float64,
) (*planningdomain.OpportunityContext, error) {
	// Convert positions to domain format
	domainPositions := make([]domain.Position, 0, len(positions))
	positionValues := make(map[string]float64) // For PortfolioContext
	for _, pos := range positions {
		domainPositions = append(domainPositions, domain.Position{
			Symbol:   pos.Symbol,
			Quantity: float64(pos.Quantity),
			Currency: domain.Currency(pos.Currency),
		})
	}

	// Convert securities to domain format
	domainSecurities := make([]domain.Security, 0, len(securities))
	stocksBySymbol := make(map[string]domain.Security)
	stocksByISIN := make(map[string]domain.Security)
	securityCountries := make(map[string]string)
	securityIndustries := make(map[string]string)
	for _, sec := range securities {
		domainSec := domain.Security{
			Symbol:  sec.Symbol,
			ISIN:    sec.ISIN,
			Active:  sec.Active,
			Country: sec.Country,
			Name:    sec.Name,
		}
		domainSecurities = append(domainSecurities, domainSec)
		stocksBySymbol[sec.Symbol] = domainSec
		if sec.ISIN != "" {
			stocksByISIN[sec.ISIN] = domainSec
		}
		if sec.Country != "" {
			securityCountries[sec.Symbol] = sec.Country
		}
		if sec.Industry != "" {
			securityIndustries[sec.Symbol] = sec.Industry
		}
	}

	// Get available cash in EUR (primary currency)
	availableCashEUR := cashBalances["EUR"]

	// Fetch current prices for all securities
	currentPrices := j.fetchCurrentPrices(securities)

	// Calculate position values and total portfolio value
	totalValue := availableCashEUR
	positionAvgPrices := make(map[string]float64)
	for _, pos := range positions {
		if price, ok := currentPrices[pos.Symbol]; ok {
			valueEUR := price * float64(pos.Quantity)
			positionValues[pos.Symbol] = valueEUR
			totalValue += valueEUR
			// Use avg price from position if available, otherwise current price
			if pos.AvgPrice > 0 {
				positionAvgPrices[pos.Symbol] = pos.AvgPrice
			} else {
				positionAvgPrices[pos.Symbol] = price
			}
		}
	}

	// Build country and industry weights from allocations
	countryWeights := make(map[string]float64)
	industryWeights := make(map[string]float64)
	countryToGroup := make(map[string]string)
	industryToGroup := make(map[string]string)

	for key, value := range allocations {
		if strings.HasPrefix(key, "country_group:") {
			country := strings.TrimPrefix(key, "country_group:")
			countryWeights[country] = value
			// Map individual countries to groups (simplified - would need actual mapping)
			for _, sec := range securities {
				if sec.Country != "" {
					// Simple mapping: could be enhanced with actual country-to-group mapping
					countryToGroup[sec.Country] = country
				}
			}
		} else if strings.HasPrefix(key, "industry_group:") {
			industry := strings.TrimPrefix(key, "industry_group:")
			industryWeights[industry] = value
			// Map individual industries to groups (simplified)
			for _, sec := range securities {
				if sec.Industry != "" {
					industryToGroup[sec.Industry] = industry
				}
			}
		}
	}

	// Populate SecurityScores from scores repository
	securityScores := j.populateSecurityScores(securities)

	// Build PortfolioContext (scoring domain)
	portfolioCtx := &scoringdomain.PortfolioContext{
		CountryWeights:     countryWeights,
		IndustryWeights:    industryWeights,
		Positions:          positionValues,
		SecurityCountries:  securityCountries,
		SecurityIndustries: securityIndustries,
		SecurityScores:     securityScores,
		SecurityDividends:  make(map[string]float64), // Could fetch from dividend repo if needed
		CountryToGroup:     countryToGroup,
		IndustryToGroup:    industryToGroup,
		PositionAvgPrices:  positionAvgPrices,
		CurrentPrices:      currentPrices,
		TotalValue:         totalValue,
	}

	// Use optimizer target weights if available, otherwise fall back to allocations
	targetWeights := j.optimizerTargetWeights
	if len(targetWeights) == 0 {
		// Fall back to allocations (but these are country/industry level, not security level)
		targetWeights = make(map[string]float64)
		j.log.Warn().Msg("No optimizer target weights available, using empty map")
	}

	// Populate target return filtering data (CAGR, quality scores, settings)
	cagrs := j.populateCAGRs(securities)
	longTermScores, fundamentalsScores := j.populateQualityScores(securities)
	targetReturn, targetReturnThresholdPct := j.getTargetReturnSettings()

	// Populate value trap detection data
	valueTrapData := j.populateValueTrapData(securities)

	return &planningdomain.OpportunityContext{
		PortfolioContext:         portfolioCtx,
		Positions:                domainPositions,
		Securities:               domainSecurities,
		StocksByISIN:             stocksByISIN,
		StocksBySymbol:           stocksBySymbol,
		AvailableCashEUR:         availableCashEUR,
		TotalPortfolioValueEUR:   totalValue,
		CurrentPrices:            currentPrices,
		SecurityScores:           securityScores, // Total scores keyed by symbol (for calculators)
		TargetWeights:            targetWeights,  // Optimizer target weights (security-level)
		CountryWeights:           countryWeights,
		CountryToGroup:           countryToGroup,
		CAGRs:                    cagrs,
		LongTermScores:           longTermScores,
		FundamentalsScores:       fundamentalsScores,
		TargetReturn:             targetReturn,
		TargetReturnThresholdPct: targetReturnThresholdPct,
		OpportunityScores:        valueTrapData.OpportunityScores,
		PERatios:                 valueTrapData.PERatios,
		MarketAvgPE:              valueTrapData.MarketAvgPE,
		MomentumScores:           valueTrapData.MomentumScores,
		Volatility:               valueTrapData.Volatility,
		RegimeScore:              valueTrapData.RegimeScore,
	}, nil
}

// fetchCurrentPrices fetches current prices for all securities
func (j *BuildOpportunityContextJob) fetchCurrentPrices(securities []universe.Security) map[string]float64 {
	prices := make(map[string]float64)

	// Skip if price client is not available
	if j.priceClient == nil {
		j.log.Warn().Msg("Price client not available, using empty prices")
		return prices
	}

	if len(securities) == 0 {
		return prices
	}

	// Build symbol map (tradernet_symbol -> yahoo_symbol override)
	symbolMap := make(map[string]*string)
	for _, security := range securities {
		var yahooSymbolPtr *string
		if security.YahooSymbol != "" {
			// Create new string to avoid range variable issues
			yahooSymbol := security.YahooSymbol
			yahooSymbolPtr = &yahooSymbol
		}
		symbolMap[security.Symbol] = yahooSymbolPtr
	}

	// Fetch batch quotes
	quotes, err := j.priceClient.GetBatchQuotes(symbolMap)
	if err != nil {
		j.log.Warn().Err(err).Msg("Failed to fetch batch quotes, using empty prices")
		return prices
	}

	// Convert quotes to price map
	for symbol, pricePtr := range quotes {
		if pricePtr != nil {
			prices[symbol] = *pricePtr
		}
	}

	j.log.Info().
		Int("total", len(securities)).
		Int("fetched", len(prices)).
		Msg("Fetched current prices")

	return prices
}

// populateCAGRs fetches CAGR values from scores repository
func (j *BuildOpportunityContextJob) populateCAGRs(securities []universe.Security) map[string]float64 {
	cagrs := make(map[string]float64)

	if j.scoresRepo == nil {
		j.log.Debug().Msg("Scores repository not available, skipping CAGR population")
		return cagrs
	}

	// Build ISIN list for securities
	isinList := make([]string, 0)
	for _, sec := range securities {
		if sec.ISIN != "" && sec.Symbol != "" {
			isinList = append(isinList, sec.ISIN)
		}
	}

	if len(isinList) == 0 {
		j.log.Debug().Msg("No ISINs available, skipping CAGR population")
		return cagrs
	}

	// Get CAGRs from repository
	cagrsMap, err := j.scoresRepo.GetCAGRs(isinList)
	if err != nil {
		j.log.Warn().Err(err).Msg("Failed to get CAGRs from repository")
		return cagrs
	}

	// Build ISIN -> symbol map for adding symbol keys
	isinToSymbol := make(map[string]string)
	for _, sec := range securities {
		if sec.ISIN != "" && sec.Symbol != "" {
			isinToSymbol[sec.ISIN] = sec.Symbol
		}
	}

	// Copy CAGRs and add symbol keys
	for isin, cagr := range cagrsMap {
		cagrs[isin] = cagr
		// Also store by symbol if available
		if symbol, ok := isinToSymbol[isin]; ok {
			cagrs[symbol] = cagr
		}
	}

	j.log.Debug().Int("cagr_count", len(cagrs)).Msg("Populated CAGRs for target return filtering")
	return cagrs
}

// populateSecurityScores fetches total scores from scores repository
func (j *BuildOpportunityContextJob) populateSecurityScores(securities []universe.Security) map[string]float64 {
	securityScores := make(map[string]float64)

	if j.scoresRepo == nil {
		j.log.Debug().Msg("Scores repository not available, skipping security scores population")
		return securityScores
	}

	// Build ISIN list for securities
	isinList := make([]string, 0)
	isinToSymbol := make(map[string]string)
	for _, sec := range securities {
		if sec.ISIN != "" && sec.Symbol != "" {
			isinList = append(isinList, sec.ISIN)
			isinToSymbol[sec.ISIN] = sec.Symbol
		}
	}

	if len(isinList) == 0 {
		j.log.Debug().Msg("No ISINs available, skipping security scores population")
		return securityScores
	}

	// Get total scores from repository (keyed by ISIN)
	totalScoresByISIN, err := j.scoresRepo.GetTotalScores(isinList)
	if err != nil {
		j.log.Warn().Err(err).Msg("Failed to get total scores from repository")
		return securityScores
	}

	// Map scores by symbol (as calculators expect symbol keys)
	for isin, score := range totalScoresByISIN {
		if symbol, ok := isinToSymbol[isin]; ok {
			securityScores[symbol] = score
		}
		// Also keep ISIN key for compatibility
		securityScores[isin] = score
	}

	j.log.Debug().Int("score_count", len(securityScores)).Msg("Populated security scores")
	return securityScores
}

// populateQualityScores fetches quality scores (long-term and fundamentals) from scores repository
func (j *BuildOpportunityContextJob) populateQualityScores(securities []universe.Security) (map[string]float64, map[string]float64) {
	longTermScores := make(map[string]float64)
	fundamentalsScores := make(map[string]float64)

	if j.scoresRepo == nil {
		j.log.Debug().Msg("Scores repository not available, skipping quality scores population")
		return longTermScores, fundamentalsScores
	}

	// Build ISIN list for securities
	isinList := make([]string, 0)
	for _, sec := range securities {
		if sec.ISIN != "" && sec.Symbol != "" {
			isinList = append(isinList, sec.ISIN)
		}
	}

	if len(isinList) == 0 {
		j.log.Debug().Msg("No ISINs available, skipping quality scores population")
		return longTermScores, fundamentalsScores
	}

	// Get quality scores from repository
	longTerm, fundamentals, err := j.scoresRepo.GetQualityScores(isinList)
	if err != nil {
		j.log.Warn().Err(err).Msg("Failed to get quality scores from repository")
		return longTermScores, fundamentalsScores
	}

	// Build ISIN -> symbol map for adding symbol keys
	isinToSymbol := make(map[string]string)
	for _, sec := range securities {
		if sec.ISIN != "" && sec.Symbol != "" {
			isinToSymbol[sec.ISIN] = sec.Symbol
		}
	}

	// Copy long-term scores and add symbol keys
	for isin, score := range longTerm {
		longTermScores[isin] = score
		if symbol, ok := isinToSymbol[isin]; ok {
			longTermScores[symbol] = score
		}
	}

	// Copy fundamentals scores and add symbol keys
	for isin, score := range fundamentals {
		fundamentalsScores[isin] = score
		if symbol, ok := isinToSymbol[isin]; ok {
			fundamentalsScores[symbol] = score
		}
	}

	j.log.Debug().
		Int("long_term_count", len(longTermScores)).
		Int("fundamentals_count", len(fundamentalsScores)).
		Msg("Populated quality scores for target return filtering")
	return longTermScores, fundamentalsScores
}

// getTargetReturnSettings fetches target return and threshold from settings repository
func (j *BuildOpportunityContextJob) getTargetReturnSettings() (float64, float64) {
	targetReturn := 0.11 // Default: 11%
	thresholdPct := 0.80 // Default: 80%

	if j.settingsRepo == nil {
		j.log.Debug().Msg("Settings repository not available, using default target return settings")
		return targetReturn, thresholdPct
	}

	returnTarget, returnThreshold, err := j.settingsRepo.GetTargetReturnSettings()
	if err != nil {
		j.log.Warn().Err(err).Msg("Failed to get target return settings, using defaults")
		// Fallback to SettingDefaults
		if val, ok := settings.SettingDefaults["target_annual_return"]; ok {
			if fval, ok := val.(float64); ok {
				targetReturn = fval
			}
		}
		if val, ok := settings.SettingDefaults["target_return_threshold_pct"]; ok {
			if fval, ok := val.(float64); ok {
				thresholdPct = fval
			}
		}
		return targetReturn, thresholdPct
	}

	j.log.Debug().
		Float64("target_return", returnTarget).
		Float64("threshold_pct", returnThreshold).
		Msg("Retrieved target return settings")
	return returnTarget, returnThreshold
}

// buildOpportunityContextValueTrapData holds all data needed for value trap detection
type buildOpportunityContextValueTrapData struct {
	OpportunityScores map[string]float64
	PERatios          map[string]float64
	MarketAvgPE       float64
	MomentumScores    map[string]float64
	Volatility        map[string]float64
	RegimeScore       float64
}

// populateValueTrapData populates all data needed for classical and quantum value trap detection
func (j *BuildOpportunityContextJob) populateValueTrapData(securities []universe.Security) buildOpportunityContextValueTrapData {
	data := buildOpportunityContextValueTrapData{
		OpportunityScores: make(map[string]float64),
		PERatios:          make(map[string]float64),   // P/E ratios not stored in DB, leave empty for now
		MarketAvgPE:       scoring.DefaultMarketAvgPE, // Use constant default
		MomentumScores:    make(map[string]float64),
		Volatility:        make(map[string]float64),
		RegimeScore:       0.0, // Default to neutral
	}

	if j.scoresRepo == nil {
		j.log.Debug().Msg("Scores repository not available, skipping value trap data population")
		return data
	}

	// Build ISIN list for securities
	isinList := make([]string, 0)
	for _, sec := range securities {
		if sec.ISIN != "" && sec.Symbol != "" {
			isinList = append(isinList, sec.ISIN)
		}
	}

	if len(isinList) == 0 {
		j.log.Debug().Msg("No ISINs available, skipping value trap data population")
		return data
	}

	// Get value trap data from repository
	opportunityScores, momentumScores, volatility, err := j.scoresRepo.GetValueTrapData(isinList)
	if err != nil {
		j.log.Warn().Err(err).Msg("Failed to get value trap data from repository")
		return data
	}

	// Build ISIN -> symbol map for adding symbol keys
	isinToSymbol := make(map[string]string)
	for _, sec := range securities {
		if sec.ISIN != "" && sec.Symbol != "" {
			isinToSymbol[sec.ISIN] = sec.Symbol
		}
	}

	// Copy opportunity scores and add symbol keys
	for isin, score := range opportunityScores {
		data.OpportunityScores[isin] = score
		if symbol, ok := isinToSymbol[isin]; ok {
			data.OpportunityScores[symbol] = score
		}
	}

	// Copy momentum scores and add symbol keys
	for isin, score := range momentumScores {
		data.MomentumScores[isin] = score
		if symbol, ok := isinToSymbol[isin]; ok {
			data.MomentumScores[symbol] = score
		}
	}

	// Copy volatility and add symbol keys
	for isin, vol := range volatility {
		data.Volatility[isin] = vol
		if symbol, ok := isinToSymbol[isin]; ok {
			data.Volatility[symbol] = vol
		}
	}

	// Get regime score from regime repository
	if j.regimeRepo != nil {
		regimeScore, err := j.regimeRepo.GetCurrentRegimeScore()
		if err != nil {
			j.log.Warn().Err(err).Msg("Failed to get regime score, using default 0.0")
		} else {
			data.RegimeScore = regimeScore
		}
	}

	j.log.Debug().
		Int("opportunity_scores", len(data.OpportunityScores)).
		Int("momentum_scores", len(data.MomentumScores)).
		Int("volatility", len(data.Volatility)).
		Float64("market_avg_pe", data.MarketAvgPE).
		Float64("regime_score", data.RegimeScore).
		Msg("Populated value trap detection data")

	return data
}

// addVirtualTestCash adds virtual test cash to cash balances if in research mode
func (j *BuildOpportunityContextJob) addVirtualTestCash(cashBalances map[string]float64) error {
	if j.settingsRepo == nil {
		return nil // No settings repo available, skip
	}

	virtualTestCash, err := j.settingsRepo.GetVirtualTestCash()
	if err != nil {
		j.log.Warn().Err(err).Msg("Failed to get virtual test cash setting")
		return nil // Not an error, just skip
	}

	// Always add TEST currency to cashBalances, even if 0 (for consistency with UI)
	// GetVirtualTestCash returns 0 if not in research mode, so this will only add TEST in research mode
	cashBalances["TEST"] = virtualTestCash

	// Also add to EUR for AvailableCashEUR calculation (TEST is treated as EUR-equivalent)
	// Only add to EUR if > 0 to avoid reducing EUR balance when TEST is 0
	if virtualTestCash > 0 {
		// Get current EUR balance (default to 0 if not present)
		currentEUR := cashBalances["EUR"]
		cashBalances["EUR"] = currentEUR + virtualTestCash

		j.log.Info().
			Float64("virtual_test_cash", virtualTestCash).
			Float64("eur_before", currentEUR).
			Float64("eur_after", cashBalances["EUR"]).
			Msg("Added virtual test cash to opportunity context")
	} else {
		j.log.Debug().
			Float64("virtual_test_cash", virtualTestCash).
			Msg("Added virtual test cash (0) to opportunity context for consistency")
	}

	return nil
}
