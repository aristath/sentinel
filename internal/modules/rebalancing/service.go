// Package rebalancing provides portfolio rebalancing functionality.
package rebalancing

import (
	"database/sql"
	"fmt"
	"math"

	"github.com/aristath/sentinel/internal/clients/yahoo"
	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/modules/allocation"
	"github.com/aristath/sentinel/internal/modules/planning"
	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/planning/hash"
	planningrepo "github.com/aristath/sentinel/internal/modules/planning/repository"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/settings"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/aristath/sentinel/internal/services"
	"github.com/rs/zerolog"
)

// CalculateMinTradeAmount calculates minimum trade amount where transaction costs are acceptable
// Faithful translation from Python: app/modules/rebalancing/services/rebalancing_service.py
//
// With Freedom24's €2 + 0.2% fee structure:
// - €50 trade: €2.10 cost = 4.2% drag → not worthwhile
// - €200 trade: €2.40 cost = 1.2% drag → marginal
// - €400 trade: €2.80 cost = 0.7% drag → acceptable
//
// Args:
//
//	transactionCostFixed: Fixed cost per trade (e.g., €2.00)
//	transactionCostPercent: Variable cost as fraction (e.g., 0.002 = 0.2%)
//	maxCostRatio: Maximum acceptable cost-to-trade ratio (default 1%)
//
// Returns:
//
//	Minimum trade amount in EUR
func CalculateMinTradeAmount(
	transactionCostFixed float64,
	transactionCostPercent float64,
	maxCostRatio float64,
) float64 {
	// Solve for trade amount where: (fixed + trade * percent) / trade = max_ratio
	// fixed / trade + percent = max_ratio
	// trade = fixed / (max_ratio - percent)
	denominator := maxCostRatio - transactionCostPercent
	if denominator <= 0 {
		// If variable cost exceeds max ratio, return a high minimum
		return 1000.0
	}
	return transactionCostFixed / denominator
}

// Service orchestrates rebalancing operations
// Faithful translation from Python: app/modules/rebalancing/services/rebalancing_service.py
type Service struct {
	triggerChecker     *TriggerChecker
	negativeRebalancer *NegativeBalanceRebalancer

	// Planning integration
	planningService        *planning.Service
	positionRepo           *portfolio.PositionRepository
	securityRepo           *universe.SecurityRepository
	allocRepo              *allocation.Repository
	cashManager            domain.CashManager
	brokerClient           domain.BrokerClient
	yahooClient            yahoo.FullClientInterface
	priceConversionService *services.PriceConversionService
	configRepo             *planningrepo.ConfigRepository
	recommendationRepo     planning.RecommendationRepositoryInterface // Interface - can be DB or in-memory
	portfolioDB            *sql.DB                                    // For querying scores and calculations
	configDB               *sql.DB                                    // For querying settings

	log zerolog.Logger
}

// NewService creates a new rebalancing service
func NewService(
	triggerChecker *TriggerChecker,
	negativeRebalancer *NegativeBalanceRebalancer,
	planningService *planning.Service,
	positionRepo *portfolio.PositionRepository,
	securityRepo *universe.SecurityRepository,
	allocRepo *allocation.Repository,
	cashManager domain.CashManager,
	brokerClient domain.BrokerClient,
	yahooClient yahoo.FullClientInterface,
	priceConversionService *services.PriceConversionService,
	configRepo *planningrepo.ConfigRepository,
	recommendationRepo planning.RecommendationRepositoryInterface, // Interface - can be DB or in-memory
	portfolioDB *sql.DB, // For querying scores and calculations
	configDB *sql.DB, // For querying settings
	log zerolog.Logger,
) *Service {
	return &Service{
		triggerChecker:         triggerChecker,
		negativeRebalancer:     negativeRebalancer,
		planningService:        planningService,
		positionRepo:           positionRepo,
		securityRepo:           securityRepo,
		allocRepo:              allocRepo,
		cashManager:            cashManager,
		brokerClient:           brokerClient,
		yahooClient:            yahooClient,
		priceConversionService: priceConversionService,
		configRepo:             configRepo,
		recommendationRepo:     recommendationRepo,
		portfolioDB:            portfolioDB,
		configDB:               configDB,
		log:                    log.With().Str("service", "rebalancing").Logger(),
	}
}

// GetTriggerChecker returns the trigger checker
func (s *Service) GetTriggerChecker() *TriggerChecker {
	return s.triggerChecker
}

// GetNegativeBalanceRebalancer returns the negative balance rebalancer
func (s *Service) GetNegativeBalanceRebalancer() *NegativeBalanceRebalancer {
	return s.negativeRebalancer
}

// CalculateRebalanceTrades calculates optimal rebalancing trades
//
// This method integrates with the planning module to get trade recommendations
// and filters them based on available cash and transaction cost constraints.
//
// Args:
//
//	availableCash: Available cash for trading in EUR
//
// Returns:
//
//	List of trade recommendations
func (s *Service) CalculateRebalanceTrades(availableCash float64) ([]RebalanceRecommendation, error) {
	// Step 1: Check minimum trade amount
	minTradeAmount := CalculateMinTradeAmount(2.0, 0.002, 0.01)
	if availableCash < minTradeAmount {
		s.log.Info().
			Float64("available_cash", availableCash).
			Float64("min_trade_amount", minTradeAmount).
			Msg("Cash below minimum trade amount")
		return []RebalanceRecommendation{}, nil
	}

	// Step 2: Build OpportunityContext
	opportunityCtx, err := s.buildOpportunityContext(availableCash)
	if err != nil {
		return nil, fmt.Errorf("failed to build opportunity context: %w", err)
	}

	// Step 3: Load planner configuration
	config, err := s.loadPlannerConfig()
	if err != nil {
		return nil, fmt.Errorf("failed to load planner config: %w", err)
	}

	// Step 4: Call planning service
	plan, err := s.planningService.CreatePlan(opportunityCtx, config)
	if err != nil {
		return nil, fmt.Errorf("failed to create plan: %w", err)
	}

	if !plan.Feasible {
		s.log.Warn().Msg("Plan is not feasible")
		return []RebalanceRecommendation{}, nil
	}

	// Step 5: Filter for BUY steps within budget
	var buySteps []planningdomain.HolisticStep
	cashRemaining := availableCash

	for _, step := range plan.Steps {
		if step.Side != "BUY" {
			continue
		}

		estimatedCost := step.EstimatedValue
		if estimatedCost > cashRemaining {
			s.log.Debug().
				Str("symbol", step.Symbol).
				Float64("cost", estimatedCost).
				Float64("remaining", cashRemaining).
				Msg("Skipping step - insufficient cash")
			continue
		}

		buySteps = append(buySteps, step)
		cashRemaining -= estimatedCost
	}

	// Step 6: Convert to RebalanceRecommendation
	recommendations := make([]RebalanceRecommendation, 0, len(buySteps))
	for i, step := range buySteps {
		recommendations = append(recommendations, RebalanceRecommendation{
			Symbol:         step.Symbol,
			Name:           step.Name,
			Side:           step.Side,
			Quantity:       step.Quantity,
			EstimatedPrice: step.EstimatedPrice,
			EstimatedValue: step.EstimatedValue,
			Currency:       step.Currency,
			Reason:         step.Reason,
			Priority:       float64(i),
		})
	}

	s.log.Info().
		Int("total_steps", len(plan.Steps)).
		Int("buy_steps", len(buySteps)).
		Int("affordable_steps", len(recommendations)).
		Msg("Calculated rebalancing trades")

	return recommendations, nil
}

// buildOpportunityContext builds the opportunity context for planning
// Following pattern from scheduler/planner_batch.go:214-264
func (s *Service) buildOpportunityContext(availableCash float64) (*planningdomain.OpportunityContext, error) {
	// Get positions
	positions, err := s.positionRepo.GetAll()
	if err != nil {
		return nil, fmt.Errorf("failed to get positions: %w", err)
	}

	// Get securities
	securities, err := s.securityRepo.GetAllActive()
	if err != nil {
		return nil, fmt.Errorf("failed to get securities: %w", err)
	}

	// Get allocations
	allocations, err := s.allocRepo.GetAll()
	if err != nil {
		return nil, fmt.Errorf("failed to get allocations: %w", err)
	}

	// Convert positions to domain format
	domainPositions := make([]domain.Position, 0, len(positions))
	for _, pos := range positions {
		domainPositions = append(domainPositions, domain.Position{
			Symbol:   pos.Symbol,
			ISIN:     pos.ISIN, // Include ISIN (primary identifier)
			Quantity: float64(pos.Quantity),
			Currency: domain.Currency(pos.Currency),
		})
	}

	// Convert securities to domain format
	domainSecurities := make([]domain.Security, 0, len(securities))
	stocksByISIN := make(map[string]domain.Security)
	for _, sec := range securities {
		domainSec := domain.Security{
			Symbol:  sec.Symbol,
			ISIN:    sec.ISIN, // Include ISIN (primary identifier)
			Active:  sec.Active,
			Country: sec.Country,
			Name:    sec.Name,
		}
		domainSecurities = append(domainSecurities, domainSec)
		if sec.ISIN != "" {
			stocksByISIN[sec.ISIN] = domainSec // ISIN key only ✅
		}
	}

	// Fetch current prices
	currentPrices := s.fetchCurrentPrices(securities)

	// Calculate total portfolio value
	totalValue := availableCash
	for _, pos := range domainPositions {
		if pos.ISIN == "" {
			continue
		}
		if price, ok := currentPrices[pos.ISIN]; ok { // ISIN lookup ✅
			totalValue += price * pos.Quantity
		}
	}

	// Populate target return filtering data (CAGR, quality scores, settings)
	cagrs := s.populateCAGRs(securities)
	longTermScores, fundamentalsScores := s.populateQualityScores(securities)
	targetReturn, targetReturnThresholdPct := s.getTargetReturnSettings()

	// Create OpportunityContext
	ctx := &planningdomain.OpportunityContext{
		Positions:                domainPositions,
		Securities:               domainSecurities,
		StocksByISIN:             stocksByISIN, // ISIN-keyed only ✅
		AvailableCashEUR:         availableCash,
		TotalPortfolioValueEUR:   totalValue,
		CurrentPrices:            currentPrices, // ISIN-keyed ✅
		TargetWeights:            allocations,   // ISIN-keyed ✅
		IneligibleISINs:          make(map[string]bool),
		RecentlySoldISINs:        make(map[string]bool),
		RecentlyBoughtISINs:      make(map[string]bool),
		TransactionCostFixed:     2.0,
		TransactionCostPercent:   0.002,
		AllowSell:                false, // Rebalancing only buys
		AllowBuy:                 true,
		CAGRs:                    cagrs,                // ISIN-keyed ✅
		LongTermScores:           longTermScores,       // ISIN-keyed ✅
		FundamentalsScores:       fundamentalsScores,   // ISIN-keyed ✅
		TargetReturn:             targetReturn,
		TargetReturnThresholdPct: targetReturnThresholdPct,
	}

	s.log.Debug().
		Int("positions", len(domainPositions)).
		Int("securities", len(domainSecurities)).
		Float64("cash", availableCash).
		Float64("total_value", totalValue).
		Msg("Built opportunity context")

	return ctx, nil
}

// fetchCurrentPrices fetches current prices for all securities from Yahoo Finance and converts to EUR
// After migration: Returns map keyed by ISIN (internal identifier) with EUR-converted prices
func (s *Service) fetchCurrentPrices(securities []universe.Security) map[string]float64 {
	prices := make(map[string]float64)

	// Skip if Yahoo client is not available
	if s.yahooClient == nil {
		s.log.Warn().Msg("Yahoo client not available, using empty prices")
		return prices
	}

	if len(securities) == 0 {
		return prices
	}

	// Build symbol map (tradernet_symbol -> yahoo_symbol override) for Yahoo API
	symbolMap := make(map[string]*string)
	// Build symbol -> ISIN mapping to convert API response to ISIN keys
	symbolToISIN := make(map[string]string)
	for _, security := range securities {
		var yahooSymbolPtr *string
		if security.YahooSymbol != "" {
			// Create new string to avoid range variable issues
			yahooSymbol := security.YahooSymbol
			yahooSymbolPtr = &yahooSymbol
		}
		symbolMap[security.Symbol] = yahooSymbolPtr
		if security.ISIN != "" {
			symbolToISIN[security.Symbol] = security.ISIN
		}
	}

	// Fetch batch quotes from Yahoo (returns map keyed by Tradernet symbol, prices in native currencies)
	quotes, err := s.yahooClient.GetBatchQuotes(symbolMap)
	if err != nil {
		s.log.Warn().Err(err).Msg("Failed to fetch batch quotes from Yahoo, using empty prices")
		return prices
	}

	// Convert quotes map to native currency prices keyed by symbol
	nativePrices := make(map[string]float64)
	for symbol, price := range quotes {
		if price != nil {
			nativePrices[symbol] = *price
		}
	}

	// ===== CURRENCY CONVERSION BOUNDARY =====
	// Convert all prices from native currencies to EUR before passing to planner.
	// This mirrors the same conversion done in buildOpportunityContext.
	// The planner MUST receive EUR-normalized values for correct calculations.
	var eurPrices map[string]float64
	if s.priceConversionService != nil {
		eurPrices = s.priceConversionService.ConvertPricesToEUR(nativePrices, securities)
	} else {
		// Fallback: use native prices if service unavailable
		s.log.Warn().Msg("Price conversion service not available, using native currency prices (may cause valuation errors)")
		eurPrices = nativePrices
	}

	// Convert symbol-keyed EUR prices to ISIN-keyed prices
	successCount := 0
	for symbol, eurPrice := range eurPrices {
		// Convert symbol to ISIN for internal map key
		isin, hasISIN := symbolToISIN[symbol]
		if hasISIN && isin != "" {
			prices[isin] = eurPrice
			successCount++
		} else {
			// Fallback: use symbol as key if ISIN not found (shouldn't happen after migration)
			s.log.Warn().Str("symbol", symbol).Msg("No ISIN found for symbol in price map, using symbol as key")
			prices[symbol] = eurPrice
			successCount++
		}
	}

	s.log.Debug().
		Int("total", len(securities)).
		Int("fetched", successCount).
		Msg("Fetched and converted current prices to EUR")

	return prices
}

// populateCAGRs fetches CAGR values from calculations table for all securities
// Returns map keyed by ISIN only (internal identifier)
func (s *Service) populateCAGRs(securities []universe.Security) map[string]float64 {
	cagrs := make(map[string]float64)

	if s.portfolioDB == nil {
		s.log.Debug().Msg("PortfolioDB not available, skipping CAGR population")
		return cagrs
	}

	// Build ISIN set for securities we care about
	isinSet := make(map[string]bool)
	for _, sec := range securities {
		if sec.ISIN != "" {
			isinSet[sec.ISIN] = true
		}
	}

	if len(isinSet) == 0 {
		s.log.Debug().Msg("No ISINs available, skipping CAGR population")
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

	rows, err := s.portfolioDB.Query(query)
	if err != nil {
		s.log.Warn().Err(err).Msg("Failed to query CAGR from scores table")
		return cagrs
	}
	defer rows.Close()

	for rows.Next() {
		var isin string
		var cagrScore sql.NullFloat64
		if err := rows.Scan(&isin, &cagrScore); err != nil {
			s.log.Warn().Err(err).Str("isin", isin).Msg("Failed to scan CAGR")
			continue
		}

		// Only include CAGRs for securities we care about
		if !isinSet[isin] {
			continue
		}

		if cagrScore.Valid && cagrScore.Float64 > 0 {
			// Convert normalized cagr_score (0-1) to approximate CAGR percentage
			cagrValue := convertCAGRScoreToCAGR(cagrScore.Float64)
			if cagrValue > 0 {
				cagrs[isin] = cagrValue // ISIN key only ✅
			}
		}
	}

	s.log.Debug().Int("cagr_count", len(cagrs)).Msg("Populated CAGRs for target return filtering")
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
// Returns maps keyed by ISIN only (internal identifier)
func (s *Service) populateQualityScores(securities []universe.Security) (map[string]float64, map[string]float64) {
	longTermScores := make(map[string]float64)
	fundamentalsScores := make(map[string]float64)

	if s.portfolioDB == nil {
		s.log.Debug().Msg("PortfolioDB not available, skipping quality scores population")
		return longTermScores, fundamentalsScores
	}

	// Build ISIN set for securities we care about
	isinSet := make(map[string]bool)
	for _, sec := range securities {
		if sec.ISIN != "" {
			isinSet[sec.ISIN] = true
		}
	}

	if len(isinSet) == 0 {
		s.log.Debug().Msg("No ISINs available, skipping quality scores population")
		return longTermScores, fundamentalsScores
	}

	// Query scores for all securities by ISIN
	query := `
		SELECT isin, cagr_score, fundamental_score
		FROM scores
		WHERE isin != '' AND isin IS NOT NULL
	`

	rows, err := s.portfolioDB.Query(query)
	if err != nil {
		s.log.Warn().Err(err).Msg("Failed to query quality scores from scores table")
		return longTermScores, fundamentalsScores
	}
	defer rows.Close()

	for rows.Next() {
		var isin string
		var cagrScore, fundamentalScore sql.NullFloat64
		if err := rows.Scan(&isin, &cagrScore, &fundamentalScore); err != nil {
			s.log.Warn().Err(err).Str("isin", isin).Msg("Failed to scan quality scores")
			continue
		}

		// Only include scores for securities we care about
		if !isinSet[isin] {
			continue
		}

		// Use cagr_score as proxy for long-term (normalize to 0-1 range)
		if cagrScore.Valid {
			normalized := math.Max(0.0, math.Min(1.0, cagrScore.Float64))
			longTermScores[isin] = normalized // ISIN key only ✅
		}

		// Store fundamental_score
		if fundamentalScore.Valid {
			normalized := math.Max(0.0, math.Min(1.0, fundamentalScore.Float64))
			fundamentalsScores[isin] = normalized // ISIN key only ✅
		}
	}

	s.log.Debug().
		Int("long_term_count", len(longTermScores)).
		Int("fundamentals_count", len(fundamentalsScores)).
		Msg("Populated quality scores for target return filtering")
	return longTermScores, fundamentalsScores
}

// getTargetReturnSettings fetches target return and threshold from settings table
// Returns defaults if not found: 0.11 (11%) target, 0.80 (80%) threshold
func (s *Service) getTargetReturnSettings() (float64, float64) {
	targetReturn := 0.11 // Default: 11%
	thresholdPct := 0.80 // Default: 80%

	if s.configDB == nil {
		s.log.Debug().Msg("ConfigDB not available, using default target return settings")
		return targetReturn, thresholdPct
	}

	// Query target_annual_return
	var targetReturnStr string
	err := s.configDB.QueryRow("SELECT value FROM settings WHERE key = 'target_annual_return'").Scan(&targetReturnStr)
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
	err = s.configDB.QueryRow("SELECT value FROM settings WHERE key = 'target_return_threshold_pct'").Scan(&thresholdStr)
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

	s.log.Debug().
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

// loadPlannerConfig loads planner configuration from repository or uses defaults
// Following pattern from scheduler/planner_batch.go:335-351
func (s *Service) loadPlannerConfig() (*planningdomain.PlannerConfiguration, error) {
	if s.configRepo != nil {
		config, err := s.configRepo.GetDefaultConfig()
		if err != nil {
			s.log.Warn().Err(err).Msg("Failed to load config from repository")
		} else if config != nil {
			s.log.Debug().Str("config_name", config.Name).Msg("Loaded planner config")
			return config, nil
		}
	}

	s.log.Debug().Msg("Using default planner configuration")
	return planningdomain.NewDefaultConfiguration(), nil
}

// ExecuteRebalancing executes a full rebalancing cycle
//
// Steps:
// 1. Calculate trade recommendations
// 2. Store recommendations in database
//
// Note: Actual trade execution happens separately via event-based trading job
//
// Returns error if rebalancing fails
func (s *Service) ExecuteRebalancing(
	positions interface{},
	targetAllocations map[string]float64,
	totalPortfolioValue float64,
	cashBalance float64,
) error {
	s.log.Info().Msg("Starting rebalancing cycle")

	// Calculate trade recommendations
	recommendations, err := s.CalculateRebalanceTrades(cashBalance)
	if err != nil {
		return fmt.Errorf("failed to calculate rebalancing trades: %w", err)
	}

	if len(recommendations) == 0 {
		s.log.Info().Msg("No rebalancing trades recommended")
		return nil
	}

	// Store recommendations in database
	if s.recommendationRepo != nil {
		if err := s.storeRecommendations(recommendations); err != nil {
			s.log.Error().Err(err).Msg("Failed to store recommendations")
			return fmt.Errorf("failed to store recommendations: %w", err)
		}
	}

	s.log.Info().
		Int("recommendation_count", len(recommendations)).
		Msg("Rebalancing cycle completed - recommendations stored")

	return nil
}

// storeRecommendations stores recommendations in the database
// Following pattern from scheduler/planner_batch.go:353-406
func (s *Service) storeRecommendations(recommendations []RebalanceRecommendation) error {
	// Generate portfolio hash for grouping
	positions, _ := s.positionRepo.GetAll()
	securities, _ := s.securityRepo.GetAllActive()
	cashBalances := make(map[string]float64)

	if s.cashManager != nil {
		balances, err := s.cashManager.GetAllCashBalances()
		if err == nil {
			cashBalances = balances
			// Add virtual test cash if in research mode
			if err := s.addVirtualTestCash(cashBalances); err != nil {
				s.log.Warn().Err(err).Msg("Failed to add virtual test cash, continuing without it")
			}
		}
	}

	// Build portfolio hash
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

	pendingOrders := []hash.PendingOrder{} // Empty for now
	portfolioHash := hash.GeneratePortfolioHash(hashPositions, hashSecurities, cashBalances, pendingOrders)

	// Store each recommendation
	for _, rec := range recommendations {
		planningRec := planning.Recommendation{
			Symbol:         rec.Symbol,
			Name:           rec.Name,
			Side:           rec.Side,
			Quantity:       float64(rec.Quantity),
			EstimatedPrice: rec.EstimatedPrice,
			EstimatedValue: rec.EstimatedValue,
			Reason:         rec.Reason,
			Currency:       rec.Currency,
			Priority:       rec.Priority,
			Status:         "pending",
			PortfolioHash:  portfolioHash,
		}

		uuid, err := s.recommendationRepo.CreateOrUpdate(planningRec)
		if err != nil {
			s.log.Error().Err(err).Str("symbol", rec.Symbol).Msg("Failed to store recommendation")
			continue
		}

		s.log.Debug().
			Str("uuid", uuid).
			Str("symbol", rec.Symbol).
			Msg("Stored recommendation")
	}

	return nil
}

// addVirtualTestCash adds virtual test cash to cash balances if in research mode
// TEST currency is added to cashBalances map, and also added to EUR for AvailableCashEUR calculation
// This matches the implementation in scheduler/planner_batch.go
func (s *Service) addVirtualTestCash(cashBalances map[string]float64) error {
	if s.configDB == nil {
		return nil // No config DB available, skip
	}

	// Check trading mode - only add test cash in research mode
	var tradingMode string
	err := s.configDB.QueryRow("SELECT value FROM settings WHERE key = 'trading_mode'").Scan(&tradingMode)
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
	var virtualTestCash float64
	err = s.configDB.QueryRow("SELECT value FROM settings WHERE key = 'virtual_test_cash'").Scan(&virtualTestCashStr)
	if err != nil {
		if err == sql.ErrNoRows {
			// No virtual test cash set, default to 0 so it can be edited in UI
			virtualTestCash = 0
		} else {
			return fmt.Errorf("failed to get virtual_test_cash: %w", err)
		}
	} else {
		// Parse virtual test cash amount
		virtualTestCash, err = parseFloatRebalancing(virtualTestCashStr)
		if err != nil {
			return fmt.Errorf("failed to parse virtual_test_cash: %w", err)
		}
	}

	// Always add TEST currency to cashBalances, even if 0 (so it can be edited in UI)
	cashBalances["TEST"] = virtualTestCash

	// Also add to EUR for AvailableCashEUR calculation (TEST is treated as EUR-equivalent)
	// Only add to EUR if > 0 to avoid reducing EUR balance when TEST is 0
	if virtualTestCash > 0 {
		// Get current EUR balance (default to 0 if not present)
		currentEUR := cashBalances["EUR"]
		cashBalances["EUR"] = currentEUR + virtualTestCash

		s.log.Info().
			Float64("virtual_test_cash", virtualTestCash).
			Float64("eur_before", currentEUR).
			Float64("eur_after", cashBalances["EUR"]).
			Str("trading_mode", tradingMode).
			Msg("Added virtual test cash to cash balances")
	} else {
		s.log.Debug().
			Float64("virtual_test_cash", virtualTestCash).
			Str("trading_mode", tradingMode).
			Msg("Added virtual test cash (0) to cash balances for UI editing")
	}

	return nil
}

// parseFloatRebalancing parses a string to float64, returns error if invalid
func parseFloatRebalancing(s string) (float64, error) {
	var result float64
	_, err := fmt.Sscanf(s, "%f", &result)
	return result, err
}
