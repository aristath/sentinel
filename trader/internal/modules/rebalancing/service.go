package rebalancing

import (
	"fmt"

	"github.com/aristath/arduino-trader/internal/clients/tradernet"
	"github.com/aristath/arduino-trader/internal/domain"
	"github.com/aristath/arduino-trader/internal/modules/allocation"
	"github.com/aristath/arduino-trader/internal/modules/planning"
	planningdomain "github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/aristath/arduino-trader/internal/modules/planning/hash"
	planningrepo "github.com/aristath/arduino-trader/internal/modules/planning/repository"
	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/aristath/arduino-trader/internal/modules/universe"
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
	planningService    *planning.Service
	positionRepo       *portfolio.PositionRepository
	securityRepo       *universe.SecurityRepository
	allocRepo          *allocation.Repository
	tradernetClient    *tradernet.Client
	configRepo         *planningrepo.ConfigRepository
	recommendationRepo *planning.RecommendationRepository

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
	tradernetClient *tradernet.Client,
	configRepo *planningrepo.ConfigRepository,
	recommendationRepo *planning.RecommendationRepository,
	log zerolog.Logger,
) *Service {
	return &Service{
		triggerChecker:     triggerChecker,
		negativeRebalancer: negativeRebalancer,
		planningService:    planningService,
		positionRepo:       positionRepo,
		securityRepo:       securityRepo,
		allocRepo:          allocRepo,
		tradernetClient:    tradernetClient,
		configRepo:         configRepo,
		recommendationRepo: recommendationRepo,
		log:                log.With().Str("service", "rebalancing").Logger(),
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
			Quantity: float64(pos.Quantity),
			Currency: domain.Currency(pos.Currency),
		})
	}

	// Convert securities to domain format
	domainSecurities := make([]domain.Security, 0, len(securities))
	stocksBySymbol := make(map[string]domain.Security)
	for _, sec := range securities {
		domainSec := domain.Security{
			Symbol:  sec.Symbol,
			Active:  sec.Active,
			Country: sec.Country,
			Name:    sec.Name,
		}
		domainSecurities = append(domainSecurities, domainSec)
		stocksBySymbol[sec.Symbol] = domainSec
	}

	// Fetch current prices
	currentPrices := s.fetchCurrentPrices(securities)

	// Calculate total portfolio value
	totalValue := availableCash
	for symbol, price := range currentPrices {
		for _, pos := range domainPositions {
			if pos.Symbol == symbol {
				totalValue += price * pos.Quantity
				break
			}
		}
	}

	// Create OpportunityContext
	ctx := &planningdomain.OpportunityContext{
		Positions:              domainPositions,
		Securities:             domainSecurities,
		StocksBySymbol:         stocksBySymbol,
		AvailableCashEUR:       availableCash,
		TotalPortfolioValueEUR: totalValue,
		CurrentPrices:          currentPrices,
		TargetWeights:          allocations,
		IneligibleSymbols:      make(map[string]bool),
		RecentlySold:           make(map[string]bool),
		RecentlyBought:         make(map[string]bool),
		TransactionCostFixed:   2.0,
		TransactionCostPercent: 0.002,
		AllowSell:              false, // Rebalancing only buys
		AllowBuy:               true,
	}

	s.log.Debug().
		Int("positions", len(domainPositions)).
		Int("securities", len(domainSecurities)).
		Float64("cash", availableCash).
		Float64("total_value", totalValue).
		Msg("Built opportunity context")

	return ctx, nil
}

// fetchCurrentPrices fetches current prices for all securities
// Following pattern from scheduler/planner_batch.go:266-298
func (s *Service) fetchCurrentPrices(securities []universe.Security) map[string]float64 {
	prices := make(map[string]float64)

	if s.tradernetClient == nil || !s.tradernetClient.IsConnected() {
		s.log.Warn().Msg("Tradernet not available, using empty prices")
		return prices
	}

	successCount := 0
	for _, sec := range securities {
		quote, err := s.tradernetClient.GetQuote(sec.Symbol)
		if err != nil {
			s.log.Debug().Err(err).Str("symbol", sec.Symbol).Msg("Failed to fetch price")
			continue
		}
		prices[sec.Symbol] = quote.Price
		successCount++
	}

	s.log.Debug().
		Int("total", len(securities)).
		Int("fetched", successCount).
		Msg("Fetched current prices")

	return prices
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

	if s.tradernetClient != nil && s.tradernetClient.IsConnected() {
		balances, _ := s.tradernetClient.GetCashBalances()
		for _, bal := range balances {
			cashBalances[bal.Currency] = bal.Amount
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
