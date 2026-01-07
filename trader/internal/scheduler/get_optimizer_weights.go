package scheduler

import (
	"fmt"
	"strings"

	"github.com/aristath/sentinel/internal/modules/optimization"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
)

// GetOptimizerWeightsJob fetches optimizer target weights for the current portfolio
type GetOptimizerWeightsJob struct {
	log              zerolog.Logger
	positionRepo     PositionRepositoryInterface
	securityRepo     SecurityRepositoryInterface
	allocRepo        AllocationRepositoryInterface
	cashManager      CashManagerInterface
	priceClient      PriceClientInterface
	optimizerService OptimizerServiceInterface
	targetWeights    map[string]float64 // Store computed weights
}

// NewGetOptimizerWeightsJob creates a new GetOptimizerWeightsJob
func NewGetOptimizerWeightsJob(
	positionRepo PositionRepositoryInterface,
	securityRepo SecurityRepositoryInterface,
	allocRepo AllocationRepositoryInterface,
	cashManager CashManagerInterface,
	priceClient PriceClientInterface,
	optimizerService OptimizerServiceInterface,
) *GetOptimizerWeightsJob {
	return &GetOptimizerWeightsJob{
		log:              zerolog.Nop(),
		positionRepo:     positionRepo,
		securityRepo:     securityRepo,
		allocRepo:        allocRepo,
		cashManager:      cashManager,
		priceClient:      priceClient,
		optimizerService: optimizerService,
		targetWeights:    make(map[string]float64),
	}
}

// SetLogger sets the logger for the job
func (j *GetOptimizerWeightsJob) SetLogger(log zerolog.Logger) {
	j.log = log
}

// Name returns the job name
func (j *GetOptimizerWeightsJob) Name() string {
	return "get_optimizer_weights"
}

// Run executes the get optimizer weights job
func (j *GetOptimizerWeightsJob) Run() error {
	if j.optimizerService == nil {
		return fmt.Errorf("optimizer service not available")
	}

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

	// Step 3: Get cash balances
	cashBalances := make(map[string]float64)
	if j.cashManager != nil {
		balances, err := j.cashManager.GetAllCashBalances()
		if err != nil {
			j.log.Warn().Err(err).Msg("Failed to get cash balances, using empty")
		} else {
			cashBalances = balances
		}
	}

	// Step 4: Fetch current prices
	currentPrices := j.fetchCurrentPrices(securities)

	// Step 5: Calculate portfolio value
	portfolioValue := cashBalances["EUR"]
	for _, pos := range positions {
		if price, ok := currentPrices[pos.Symbol]; ok {
			portfolioValue += price * float64(pos.Quantity)
		}
	}

	// Step 6: Get allocation targets
	allocations, err := j.allocRepo.GetAll()
	if err != nil {
		j.log.Error().Err(err).Msg("Failed to get allocations")
		return fmt.Errorf("failed to get allocations: %w", err)
	}

	// Step 7: Extract country and industry targets
	countryTargets := make(map[string]float64)
	industryTargets := make(map[string]float64)
	for key, value := range allocations {
		if strings.HasPrefix(key, "country_group:") {
			country := strings.TrimPrefix(key, "country_group:")
			countryTargets[country] = value
		} else if strings.HasPrefix(key, "industry_group:") {
			industry := strings.TrimPrefix(key, "industry_group:")
			industryTargets[industry] = value
		}
	}

	// Step 8: Convert positions to optimizer format
	optimizerPositions := make(map[string]optimization.Position)
	for _, pos := range positions {
		valueEUR := 0.0
		if price, ok := currentPrices[pos.Symbol]; ok {
			valueEUR = price * float64(pos.Quantity)
		}
		optimizerPositions[pos.Symbol] = optimization.Position{
			Symbol:   pos.Symbol,
			Quantity: float64(pos.Quantity),
			ValueEUR: valueEUR,
		}
	}

	// Step 9: Convert securities to optimizer format
	optimizerSecurities := make([]optimization.Security, 0, len(securities))
	for _, sec := range securities {
		optimizerSecurities = append(optimizerSecurities, optimization.Security{
			Symbol:             sec.Symbol,
			Country:            sec.Country,
			Industry:           sec.Industry,
			MinPortfolioTarget: 0.0, // Could be from security settings
			MaxPortfolioTarget: 1.0, // Could be from security settings
			AllowBuy:           sec.Active,
			AllowSell:          true, // Default to true
			MinLot:             1.0,
			PriorityMultiplier: 1.0,
			TargetPriceEUR:     0.0, // Not used
		})
	}

	// Step 10: Build portfolio state
	state := optimization.PortfolioState{
		Securities:      optimizerSecurities,
		Positions:       optimizerPositions,
		PortfolioValue:  portfolioValue,
		CurrentPrices:   currentPrices,
		CashBalance:     cashBalances["EUR"],
		CountryTargets:  countryTargets,
		IndustryTargets: industryTargets,
		DividendBonuses: make(map[string]float64), // Could fetch from dividend repo if needed
	}

	// Step 11: Get optimizer settings
	settings := optimization.Settings{
		Blend:              0.5,  // Default blend
		TargetReturn:       0.11, // 11% target
		MinCashReserve:     500.0,
		MinTradeAmount:     0.0,
		TransactionCostPct: 0.002,
		MaxConcentration:   0.25,
	}

	// Step 12: Run optimization
	resultInterface, err := j.optimizerService.Optimize(state, settings)
	if err != nil {
		j.log.Error().Err(err).Msg("Optimizer failed")
		return fmt.Errorf("optimizer failed: %w", err)
	}

	// Type assert the result
	result, ok := resultInterface.(*optimization.Result)
	if !ok {
		j.log.Error().Msg("Optimizer returned invalid result type")
		return fmt.Errorf("optimizer returned invalid result type")
	}

	if !result.Success {
		j.log.Error().Msg("Optimizer returned unsuccessful result")
		return fmt.Errorf("optimizer returned unsuccessful result")
	}

	// Store target weights for retrieval
	j.targetWeights = result.TargetWeights

	j.log.Info().
		Int("target_count", len(result.TargetWeights)).
		Msg("Successfully retrieved optimizer target weights")

	return nil
}

// GetTargetWeights returns the computed optimizer target weights
func (j *GetOptimizerWeightsJob) GetTargetWeights() map[string]float64 {
	if j.targetWeights == nil {
		return make(map[string]float64)
	}
	return j.targetWeights
}

// fetchCurrentPrices fetches current prices for all securities
func (j *GetOptimizerWeightsJob) fetchCurrentPrices(securities []universe.Security) map[string]float64 {
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

	return prices
}
