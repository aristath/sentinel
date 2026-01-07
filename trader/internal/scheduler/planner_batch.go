package scheduler

import (
	"database/sql"
	"fmt"
	"math"
	"strings"
	"time"

	"github.com/aristath/portfolioManager/internal/clients/tradernet"
	"github.com/aristath/portfolioManager/internal/clients/yahoo"
	"github.com/aristath/portfolioManager/internal/domain"
	"github.com/aristath/portfolioManager/internal/modules/allocation"
	"github.com/aristath/portfolioManager/internal/modules/opportunities"
	"github.com/aristath/portfolioManager/internal/modules/optimization"
	"github.com/aristath/portfolioManager/internal/modules/planning"
	planningdomain "github.com/aristath/portfolioManager/internal/modules/planning/domain"
	"github.com/aristath/portfolioManager/internal/modules/planning/evaluation"
	"github.com/aristath/portfolioManager/internal/modules/planning/hash"
	"github.com/aristath/portfolioManager/internal/modules/planning/planner"
	"github.com/aristath/portfolioManager/internal/modules/planning/repository"
	"github.com/aristath/portfolioManager/internal/modules/portfolio"
	scoringdomain "github.com/aristath/portfolioManager/internal/modules/scoring/domain"
	"github.com/aristath/portfolioManager/internal/modules/sequences"
	"github.com/aristath/portfolioManager/internal/modules/settings"
	"github.com/aristath/portfolioManager/internal/modules/universe"
	"github.com/rs/zerolog"
)

// PlannerBatchJob processes planning in batches to generate trading recommendations
// Simplified version: Creates plan on-demand rather than batch processing sequences
type PlannerBatchJob struct {
	log                    zerolog.Logger
	positionRepo           *portfolio.PositionRepository
	securityRepo           *universe.SecurityRepository
	allocRepo              *allocation.Repository
	cashManager            domain.CashManager
	tradernetClient        *tradernet.Client
	yahooClient            yahoo.FullClientInterface
	optimizerService       *optimization.OptimizerService // Added for optimizer target weights
	opportunitiesService   *opportunities.Service
	sequencesService       *sequences.Service
	evaluationService      *evaluation.Service
	plannerService         *planner.Planner
	configRepo             *repository.ConfigRepository
	recommendationRepo     *planning.RecommendationRepository
	portfolioDB            *sql.DB                   // For querying scores and calculations
	configDB               *sql.DB                   // For querying settings
	scoreRepo              *universe.ScoreRepository // For querying quality scores
	lastPortfolioHash      string
	lastPlanTime           time.Time
	minPlanningIntervalMin int // Minimum minutes between planning cycles
}

// PlannerBatchConfig holds configuration for planner batch job
type PlannerBatchConfig struct {
	Log                    zerolog.Logger
	PositionRepo           *portfolio.PositionRepository
	SecurityRepo           *universe.SecurityRepository
	AllocRepo              *allocation.Repository
	CashManager            domain.CashManager
	TradernetClient        *tradernet.Client
	YahooClient            yahoo.FullClientInterface
	OptimizerService       *optimization.OptimizerService // Added for optimizer target weights
	OpportunitiesService   *opportunities.Service
	SequencesService       *sequences.Service
	EvaluationService      *evaluation.Service
	PlannerService         *planner.Planner
	ConfigRepo             *repository.ConfigRepository
	RecommendationRepo     *planning.RecommendationRepository
	PortfolioDB            *sql.DB                   // For querying scores and calculations
	ConfigDB               *sql.DB                   // For querying settings
	ScoreRepo              *universe.ScoreRepository // For querying quality scores
	MinPlanningIntervalMin int                       // Default: 15 minutes
}

// NewPlannerBatchJob creates a new planner batch job
func NewPlannerBatchJob(cfg PlannerBatchConfig) *PlannerBatchJob {
	minInterval := cfg.MinPlanningIntervalMin
	if minInterval == 0 {
		minInterval = 15 // Default: 15 minutes between planning cycles
	}

	return &PlannerBatchJob{
		log:                    cfg.Log.With().Str("job", "planner_batch").Logger(),
		positionRepo:           cfg.PositionRepo,
		securityRepo:           cfg.SecurityRepo,
		allocRepo:              cfg.AllocRepo,
		cashManager:            cfg.CashManager,
		tradernetClient:        cfg.TradernetClient,
		yahooClient:            cfg.YahooClient,
		optimizerService:       cfg.OptimizerService,
		opportunitiesService:   cfg.OpportunitiesService,
		sequencesService:       cfg.SequencesService,
		evaluationService:      cfg.EvaluationService,
		plannerService:         cfg.PlannerService,
		configRepo:             cfg.ConfigRepo,
		recommendationRepo:     cfg.RecommendationRepo,
		portfolioDB:            cfg.PortfolioDB,
		configDB:               cfg.ConfigDB,
		scoreRepo:              cfg.ScoreRepo,
		minPlanningIntervalMin: minInterval,
	}
}

// Name returns the job name
func (j *PlannerBatchJob) Name() string {
	return "planner_batch"
}

// Run executes the planner batch job
func (j *PlannerBatchJob) Run() error {
	j.log.Info().Msg("Starting planner batch generation")
	startTime := time.Now()

	// Check if enough time has passed since last planning
	timeSinceLastPlan := time.Since(j.lastPlanTime)
	minInterval := time.Duration(j.minPlanningIntervalMin) * time.Minute

	if timeSinceLastPlan < minInterval && j.lastPlanTime.Unix() > 0 {
		j.log.Info().
			Dur("time_since_last", timeSinceLastPlan).
			Dur("min_interval", minInterval).
			Msg("Skipping planning - too soon since last plan")
		return nil
	}

	// Step 1: Get current portfolio state
	positions, err := j.positionRepo.GetAll()
	if err != nil {
		j.log.Error().Err(err).Msg("Failed to get positions")
		return fmt.Errorf("failed to get positions: %w", err)
	}

	securities, err := j.securityRepo.GetAllActive()
	if err != nil {
		j.log.Error().Err(err).Msg("Failed to get securities")
		return fmt.Errorf("failed to get securities: %w", err)
	}

	allocations, err := j.allocRepo.GetAll()
	if err != nil {
		j.log.Error().Err(err).Msg("Failed to get allocations")
		return fmt.Errorf("failed to get allocations: %w", err)
	}

	// Step 2: Generate portfolio hash
	hashPositions := make([]hash.Position, 0, len(positions))
	for _, pos := range positions {
		hashPositions = append(hashPositions, hash.Position{
			Symbol:   pos.Symbol,
			Quantity: int(pos.Quantity),
		})
	}

	hashSecurities := make([]*universe.Security, 0, len(securities))
	for i := range securities {
		hashSecurities = append(hashSecurities, &securities[i])
	}

	// Get cash balances from CashManager
	cashBalances := make(map[string]float64)
	if j.cashManager != nil {
		balances, err := j.cashManager.GetAllCashBalances()
		if err != nil {
			j.log.Warn().Err(err).Msg("Failed to get cash balances from CashManager, using empty")
		} else {
			cashBalances = balances
		}
	}

	// Add virtual test cash if in research mode
	if err := j.addVirtualTestCash(cashBalances); err != nil {
		j.log.Warn().Err(err).Msg("Failed to add virtual test cash, continuing without it")
	}

	// Get pending orders from Tradernet if available
	pendingOrders := j.fetchPendingOrders()

	portfolioHash := hash.GeneratePortfolioHash(
		hashPositions,
		hashSecurities,
		cashBalances,
		pendingOrders,
	)

	// Check if portfolio has changed
	if portfolioHash == j.lastPortfolioHash && j.lastPortfolioHash != "" {
		j.log.Info().
			Str("portfolio_hash", portfolioHash).
			Msg("Portfolio unchanged, skipping planning")
		return nil
	}

	j.log.Info().
		Str("portfolio_hash", portfolioHash).
		Str("prev_hash", j.lastPortfolioHash).
		Msg("Portfolio changed, generating new plan")

	// Step 3: Get optimizer target weights (if optimizer service is available)
	var optimizerTargetWeights map[string]float64
	if j.optimizerService != nil {
		optimizerTargets, err := j.getOptimizerTargetWeights(positions, securities, cashBalances)
		if err != nil {
			j.log.Warn().Err(err).Msg("Failed to get optimizer target weights, continuing without them")
		} else {
			optimizerTargetWeights = optimizerTargets
			j.log.Info().
				Int("target_count", len(optimizerTargetWeights)).
				Msg("Retrieved optimizer target weights")
		}
	}

	// Step 4: Build opportunity context with complete PortfolioContext
	opportunityContext := j.buildOpportunityContext(positions, securities, allocations, cashBalances, optimizerTargetWeights)

	// Step 5: Get planner configuration
	config, err := j.loadPlannerConfig()
	if err != nil {
		j.log.Error().Err(err).Msg("Failed to load planner config")
		return fmt.Errorf("failed to load planner config: %w", err)
	}

	// Step 6: Create holistic plan
	plan, err := j.plannerService.CreatePlan(opportunityContext, config)
	if err != nil {
		j.log.Error().Err(err).Msg("Failed to create plan")
		return fmt.Errorf("failed to create plan: %w", err)
	}

	// Step 7: Store plan as recommendations
	if err := j.storePlan(plan, portfolioHash); err != nil {
		j.log.Error().Err(err).Msg("Failed to store plan")
		return fmt.Errorf("failed to store plan: %w", err)
	}
	j.log.Info().
		Int("steps", len(plan.Steps)).
		Float64("end_score", plan.EndStateScore).
		Float64("improvement", plan.Improvement).
		Bool("feasible", plan.Feasible).
		Msg("Plan generated and stored successfully")

	// Update state
	j.lastPortfolioHash = portfolioHash
	j.lastPlanTime = time.Now()

	duration := time.Since(startTime)
	j.log.Info().
		Dur("duration", duration).
		Str("portfolio_hash", portfolioHash).
		Msg("Planner batch completed")

	return nil
}

// getOptimizerTargetWeights calls the optimizer service to get target weights
func (j *PlannerBatchJob) getOptimizerTargetWeights(
	positions []portfolio.Position,
	securities []universe.Security,
	cashBalances map[string]float64,
) (map[string]float64, error) {
	if j.optimizerService == nil {
		return nil, fmt.Errorf("optimizer service not available")
	}

	// Fetch current prices
	currentPrices := j.fetchCurrentPrices(securities)

	// Calculate portfolio value
	portfolioValue := cashBalances["EUR"]
	for _, pos := range positions {
		if price, ok := currentPrices[pos.Symbol]; ok {
			portfolioValue += price * float64(pos.Quantity)
		}
	}

	// Get allocation targets
	allocations, err := j.allocRepo.GetAll()
	if err != nil {
		return nil, fmt.Errorf("failed to get allocations: %w", err)
	}

	// Extract country and industry targets
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

	// Convert positions to optimizer format
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

	// Convert securities to optimizer format
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

	// Build portfolio state
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

	// Get optimizer settings
	settings := optimization.Settings{
		Blend:              0.5,  // Default blend
		TargetReturn:       0.11, // 11% target
		MinCashReserve:     500.0,
		MinTradeAmount:     0.0,
		TransactionCostPct: 0.002,
		MaxConcentration:   0.25,
	}

	// Run optimization
	result, err := j.optimizerService.Optimize(state, settings)
	if err != nil {
		return nil, fmt.Errorf("optimizer failed: %w", err)
	}

	if !result.Success {
		return nil, fmt.Errorf("optimizer returned unsuccessful result")
	}

	return result.TargetWeights, nil
}

// buildOpportunityContext creates an opportunity context from current portfolio state
// with complete PortfolioContext including optimizer target weights
func (j *PlannerBatchJob) buildOpportunityContext(
	positions []portfolio.Position,
	securities []universe.Security,
	allocations map[string]float64,
	cashBalances map[string]float64,
	optimizerTargetWeights map[string]float64,
) *planningdomain.OpportunityContext {
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
			Country: sec.Country, // universe.Security.Country is string, domain.Security.Country is string
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

	// Build PortfolioContext (scoring domain)
	portfolioCtx := &scoringdomain.PortfolioContext{
		CountryWeights:     countryWeights,
		IndustryWeights:    industryWeights,
		Positions:          positionValues,
		SecurityCountries:  securityCountries,
		SecurityIndustries: securityIndustries,
		SecurityScores:     make(map[string]float64), // Could fetch from score repo if needed
		SecurityDividends:  make(map[string]float64), // Could fetch from dividend repo if needed
		CountryToGroup:     countryToGroup,
		IndustryToGroup:    industryToGroup,
		PositionAvgPrices:  positionAvgPrices,
		CurrentPrices:      currentPrices,
		TotalValue:         totalValue,
	}

	// Use optimizer target weights if available, otherwise fall back to allocations
	targetWeights := optimizerTargetWeights
	if len(targetWeights) == 0 {
		// Fall back to allocations (but these are country/industry level, not security level)
		targetWeights = make(map[string]float64)
		j.log.Warn().Msg("No optimizer target weights available, using empty map")
	}

	// Populate target return filtering data (CAGR, quality scores, settings)
	cagrs := j.populateCAGRs(securities)
	longTermScores, fundamentalsScores := j.populateQualityScores(securities)
	targetReturn, targetReturnThresholdPct := j.getTargetReturnSettings()

	return &planningdomain.OpportunityContext{
		PortfolioContext:         portfolioCtx,
		Positions:                domainPositions,
		Securities:               domainSecurities,
		StocksByISIN:             stocksByISIN,
		StocksBySymbol:           stocksBySymbol,
		AvailableCashEUR:         availableCashEUR,
		TotalPortfolioValueEUR:   totalValue,
		CurrentPrices:            currentPrices,
		TargetWeights:            targetWeights, // Optimizer target weights (security-level)
		CountryWeights:           countryWeights,
		CountryToGroup:           countryToGroup,
		CAGRs:                    cagrs,
		LongTermScores:           longTermScores,
		FundamentalsScores:       fundamentalsScores,
		TargetReturn:             targetReturn,
		TargetReturnThresholdPct: targetReturnThresholdPct,
	}
}

// populateCAGRs fetches CAGR values from calculations table for all securities
// Returns map keyed by both ISIN and symbol for flexible lookup
func (j *PlannerBatchJob) populateCAGRs(securities []universe.Security) map[string]float64 {
	cagrs := make(map[string]float64)

	if j.portfolioDB == nil {
		j.log.Debug().Msg("PortfolioDB not available, skipping CAGR population")
		return cagrs
	}

	// Build ISIN -> symbol map for securities
	isinToSymbol := make(map[string]string)
	isinList := make([]string, 0)
	for _, sec := range securities {
		if sec.ISIN != "" && sec.Symbol != "" {
			isinToSymbol[sec.ISIN] = sec.Symbol
			isinList = append(isinList, sec.ISIN)
		}
	}

	if len(isinList) == 0 {
		j.log.Debug().Msg("No ISINs available, skipping CAGR population")
		return cagrs
	}

	// Query scores table directly by ISIN (PRIMARY KEY - fastest)
	// Get all scores with valid CAGR, then filter to securities we care about
	query := `
		SELECT isin, cagr_score
		FROM scores
		WHERE cagr_score IS NOT NULL AND cagr_score > 0
		ORDER BY last_updated DESC
	`

	rows, err := j.portfolioDB.Query(query)
	if err != nil {
		j.log.Warn().Err(err).Msg("Failed to query CAGR from scores table")
		return cagrs
	}
	defer rows.Close()

	for rows.Next() {
		var isin string
		var cagrScore sql.NullFloat64
		if err := rows.Scan(&isin, &cagrScore); err != nil {
			j.log.Warn().Err(err).Str("isin", isin).Msg("Failed to scan CAGR")
			continue
		}

		// Only include CAGRs for securities we care about
		if _, ok := isinToSymbol[isin]; !ok {
			continue
		}

		if cagrScore.Valid && cagrScore.Float64 > 0 {
			// Convert normalized cagr_score (0-1) to approximate CAGR percentage
			cagrValue := convertCAGRScoreToCAGR(cagrScore.Float64)
			if cagrValue > 0 {
				cagrs[isin] = cagrValue
				// Also store by symbol if available
				if symbol, ok := isinToSymbol[isin]; ok {
					cagrs[symbol] = cagrValue
				}
			}
		}
	}

	j.log.Debug().Int("cagr_count", len(cagrs)).Msg("Populated CAGRs for target return filtering")
	return cagrs
}

// convertCAGRScoreToCAGR converts normalized cagr_score (0-1) back to approximate CAGR percentage.
// Reverse mapping based on scoreCAGRWithBubbleDetection logic:
// - cagr_score 1.0 → ~20% CAGR (excellent)
// - cagr_score 0.8 → ~11% CAGR (target)
// - cagr_score 0.5 → ~6-8% CAGR (below target)
// - cagr_score 0.15 → 0% CAGR (floor)
// Linear interpolation between key points
func convertCAGRScoreToCAGR(cagrScore float64) float64 {
	if cagrScore <= 0 {
		return 0.0
	}

	var cagrValue float64
	if cagrScore >= 0.8 {
		// Above target: 0.8 (11%) to 1.0 (20%)
		cagrValue = 0.11 + (cagrScore-0.8)*(0.20-0.11)/(1.0-0.8)
	} else if cagrScore >= 0.15 {
		// Below target: 0.15 (0%) to 0.8 (11%)
		cagrValue = 0.0 + (cagrScore-0.15)*(0.11-0.0)/(0.8-0.15)
	} else {
		// At or below floor
		cagrValue = 0.0
	}

	return cagrValue
}

// populateQualityScores fetches quality scores (long-term and fundamentals) from scores table
// Returns maps keyed by both ISIN and symbol for flexible lookup
func (j *PlannerBatchJob) populateQualityScores(securities []universe.Security) (map[string]float64, map[string]float64) {
	longTermScores := make(map[string]float64)
	fundamentalsScores := make(map[string]float64)

	if j.portfolioDB == nil {
		j.log.Debug().Msg("PortfolioDB not available, skipping quality scores population")
		return longTermScores, fundamentalsScores
	}

	// Build ISIN -> symbol map for securities
	isinToSymbol := make(map[string]string)
	isinList := make([]string, 0)
	for _, sec := range securities {
		if sec.ISIN != "" && sec.Symbol != "" {
			isinToSymbol[sec.ISIN] = sec.Symbol
			isinList = append(isinList, sec.ISIN)
		}
	}

	if len(isinList) == 0 {
		j.log.Debug().Msg("No ISINs available, skipping quality scores population")
		return longTermScores, fundamentalsScores
	}

	// Build query with IN clause (SQLite supports up to 999 parameters, but we'll use a simpler approach)
	// Query scores for all securities by ISIN
	query := `
		SELECT isin, cagr_score, fundamental_score
		FROM scores
		WHERE isin != '' AND isin IS NOT NULL
	`

	rows, err := j.portfolioDB.Query(query)
	if err != nil {
		j.log.Warn().Err(err).Msg("Failed to query quality scores from scores table")
		return longTermScores, fundamentalsScores
	}
	defer rows.Close()

	for rows.Next() {
		var isin string
		var cagrScore, fundamentalScore sql.NullFloat64
		if err := rows.Scan(&isin, &cagrScore, &fundamentalScore); err != nil {
			j.log.Warn().Err(err).Str("isin", isin).Msg("Failed to scan quality scores")
			continue
		}

		// Only include scores for securities we care about
		if _, ok := isinToSymbol[isin]; !ok {
			continue
		}

		// Use cagr_score as proxy for long-term (normalize to 0-1 range)
		if cagrScore.Valid {
			normalized := math.Max(0.0, math.Min(1.0, cagrScore.Float64))
			longTermScores[isin] = normalized
			// Also store by symbol if available
			if symbol, ok := isinToSymbol[isin]; ok {
				longTermScores[symbol] = normalized
			}
		}

		// Store fundamental_score
		if fundamentalScore.Valid {
			normalized := math.Max(0.0, math.Min(1.0, fundamentalScore.Float64))
			fundamentalsScores[isin] = normalized
			// Also store by symbol if available
			if symbol, ok := isinToSymbol[isin]; ok {
				fundamentalsScores[symbol] = normalized
			}
		}
	}

	j.log.Debug().
		Int("long_term_count", len(longTermScores)).
		Int("fundamentals_count", len(fundamentalsScores)).
		Msg("Populated quality scores for target return filtering")
	return longTermScores, fundamentalsScores
}

// getTargetReturnSettings fetches target return and threshold from settings table
// Returns defaults if not found: 0.11 (11%) target, 0.80 (80%) threshold
func (j *PlannerBatchJob) getTargetReturnSettings() (float64, float64) {
	targetReturn := 0.11 // Default: 11%
	thresholdPct := 0.80 // Default: 80%

	if j.configDB == nil {
		j.log.Debug().Msg("ConfigDB not available, using default target return settings")
		return targetReturn, thresholdPct
	}

	// Query target_annual_return
	var targetReturnStr string
	err := j.configDB.QueryRow("SELECT value FROM settings WHERE key = 'target_annual_return'").Scan(&targetReturnStr)
	if err == nil {
		if val, err := parseFloat(targetReturnStr); err == nil {
			targetReturn = val
		} else {
			// Fallback to SettingDefaults
			if val, ok := settings.SettingDefaults["target_annual_return"]; ok {
				if fval, ok := val.(float64); ok {
					targetReturn = fval
				}
			}
		}
	} else {
		// Fallback to SettingDefaults
		if val, ok := settings.SettingDefaults["target_annual_return"]; ok {
			if fval, ok := val.(float64); ok {
				targetReturn = fval
			}
		}
	}

	// Query target_return_threshold_pct
	var thresholdStr string
	err = j.configDB.QueryRow("SELECT value FROM settings WHERE key = 'target_return_threshold_pct'").Scan(&thresholdStr)
	if err == nil {
		if val, err := parseFloat(thresholdStr); err == nil {
			thresholdPct = val
		} else {
			// Fallback to SettingDefaults
			if val, ok := settings.SettingDefaults["target_return_threshold_pct"]; ok {
				if fval, ok := val.(float64); ok {
					thresholdPct = fval
				}
			}
		}
	} else {
		// Fallback to SettingDefaults
		if val, ok := settings.SettingDefaults["target_return_threshold_pct"]; ok {
			if fval, ok := val.(float64); ok {
				thresholdPct = fval
			}
		}
	}

	j.log.Debug().
		Float64("target_return", targetReturn).
		Float64("threshold_pct", thresholdPct).
		Msg("Retrieved target return settings")
	return targetReturn, thresholdPct
}

// parseFloat parses a string to float64, returns error if invalid
func parseFloat(s string) (float64, error) {
	var result float64
	_, err := fmt.Sscanf(s, "%f", &result)
	return result, err
}

// addVirtualTestCash adds virtual test cash to cash balances if in research mode
// TEST currency is added to cashBalances map, and also added to EUR for AvailableCashEUR calculation
func (j *PlannerBatchJob) addVirtualTestCash(cashBalances map[string]float64) error {
	if j.configDB == nil {
		return nil // No config DB available, skip
	}

	// Check trading mode - only add test cash in research mode
	var tradingMode string
	err := j.configDB.QueryRow("SELECT value FROM settings WHERE key = 'trading_mode'").Scan(&tradingMode)
	if err != nil {
		if err == sql.ErrNoRows {
			// Default to research mode if not set
			tradingMode = "research"
		} else {
			return fmt.Errorf("failed to get trading mode: %w", err)
		}
	}

	// Only add test cash in research mode
	if tradingMode != "research" {
		return nil
	}

	// Get virtual_test_cash setting
	var virtualTestCashStr string
	err = j.configDB.QueryRow("SELECT value FROM settings WHERE key = 'virtual_test_cash'").Scan(&virtualTestCashStr)
	if err != nil {
		if err == sql.ErrNoRows {
			// No virtual test cash set, that's fine
			return nil
		}
		return fmt.Errorf("failed to get virtual_test_cash: %w", err)
	}

	// Parse virtual test cash amount
	virtualTestCash, err := parseFloat(virtualTestCashStr)
	if err != nil {
		return fmt.Errorf("failed to parse virtual_test_cash: %w", err)
	}

	// Only add if > 0
	if virtualTestCash > 0 {
		// Add TEST currency to cashBalances
		cashBalances["TEST"] = virtualTestCash

		// Also add to EUR for AvailableCashEUR calculation (TEST is treated as EUR-equivalent)
		// Get current EUR balance (default to 0 if not present)
		currentEUR := cashBalances["EUR"]
		cashBalances["EUR"] = currentEUR + virtualTestCash

		j.log.Info().
			Float64("virtual_test_cash", virtualTestCash).
			Float64("eur_before", currentEUR).
			Float64("eur_after", cashBalances["EUR"]).
			Str("trading_mode", tradingMode).
			Msg("Added virtual test cash to opportunity context")
	}

	return nil
}

// fetchCurrentPrices fetches current prices for all securities from Yahoo Finance
func (j *PlannerBatchJob) fetchCurrentPrices(securities []universe.Security) map[string]float64 {
	prices := make(map[string]float64)

	// Skip if Yahoo client is not available
	if j.yahooClient == nil {
		j.log.Warn().Msg("Yahoo client not available, using empty prices")
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

	// Fetch batch quotes from Yahoo
	quotes, err := j.yahooClient.GetBatchQuotes(symbolMap)
	if err != nil {
		j.log.Warn().Err(err).Msg("Failed to fetch batch quotes from Yahoo, using empty prices")
		return prices
	}

	// Convert quotes map to prices map (convert *float64 to float64)
	successCount := 0
	for symbol, price := range quotes {
		if price != nil {
			prices[symbol] = *price
			successCount++
		}
	}

	j.log.Info().
		Int("total", len(securities)).
		Int("fetched", successCount).
		Msg("Fetched current prices from Yahoo")

	return prices
}

// fetchPendingOrders fetches pending orders from Tradernet for portfolio hash calculation
func (j *PlannerBatchJob) fetchPendingOrders() []hash.PendingOrder {
	var orders []hash.PendingOrder

	// Skip if Tradernet is not available
	if j.tradernetClient == nil || !j.tradernetClient.IsConnected() {
		j.log.Debug().Msg("Tradernet not available, using empty pending orders")
		return orders
	}

	// Fetch pending orders from Tradernet
	tradernetOrders, err := j.tradernetClient.GetPendingOrders()
	if err != nil {
		j.log.Warn().Err(err).Msg("Failed to fetch pending orders, using empty")
		return orders
	}

	// Convert to hash.PendingOrder format
	for _, order := range tradernetOrders {
		orders = append(orders, hash.PendingOrder{
			Symbol:   order.Symbol,
			Side:     order.Side,
			Quantity: int(order.Quantity),
			Price:    order.Price,
			Currency: order.Currency,
		})
	}

	j.log.Info().
		Int("count", len(orders)).
		Msg("Fetched pending orders for portfolio hash")

	return orders
}

// loadPlannerConfig loads the planner configuration from the repository or uses defaults
func (j *PlannerBatchJob) loadPlannerConfig() (*planningdomain.PlannerConfiguration, error) {
	// Try to load default config from repository
	if j.configRepo != nil {
		config, err := j.configRepo.GetDefaultConfig()
		if err != nil {
			j.log.Warn().Err(err).Msg("Failed to load default config from repository, using defaults")
		} else if config != nil {
			j.log.Debug().Str("config_name", config.Name).Msg("Loaded planner config from repository")
			return config, nil
		}
	}

	// Use default config
	j.log.Debug().Msg("Using default planner configuration")
	return planningdomain.NewDefaultConfiguration(), nil
}

// storePlan stores the generated plan as recommendations in the database
func (j *PlannerBatchJob) storePlan(plan *planningdomain.HolisticPlan, portfolioHash string) error {
	if plan == nil || len(plan.Steps) == 0 {
		j.log.Debug().Msg("No plan steps to store")
		return nil
	}

	// Extract recommendations from plan steps
	storedCount := 0
	for stepIdx, step := range plan.Steps {
		// Convert side to lowercase for database constraint (expects 'buy' or 'sell')
		side := strings.ToLower(step.Side)

		// Create recommendation from step
		rec := planning.Recommendation{
			Symbol:                step.Symbol,
			Name:                  step.Name,
			Side:                  side,
			Quantity:              float64(step.Quantity),
			EstimatedPrice:        step.EstimatedPrice,
			EstimatedValue:        step.EstimatedValue,
			Reason:                step.Reason,
			Currency:              step.Currency,
			Priority:              float64(stepIdx),
			CurrentPortfolioScore: plan.CurrentScore,
			NewPortfolioScore:     plan.EndStateScore,
			ScoreChange:           plan.Improvement,
			Status:                "pending",
			PortfolioHash:         portfolioHash,
		}

		uuid, err := j.recommendationRepo.CreateOrUpdate(rec)
		if err != nil {
			j.log.Error().
				Err(err).
				Str("symbol", step.Symbol).
				Str("side", step.Side).
				Msg("Failed to store recommendation")
			continue
		}

		j.log.Debug().
			Str("uuid", uuid).
			Str("symbol", step.Symbol).
			Str("side", step.Side).
			Int("quantity", step.Quantity).
			Msg("Stored recommendation")
		storedCount++
	}

	j.log.Info().
		Int("stored_count", storedCount).
		Int("total_steps", len(plan.Steps)).
		Msg("Stored plan recommendations")

	return nil
}
