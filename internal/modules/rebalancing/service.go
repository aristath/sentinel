// Package rebalancing provides portfolio rebalancing functionality.
package rebalancing

import (
	"database/sql"
	"fmt"
	"strconv"
	"strings"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/modules/allocation"
	"github.com/aristath/sentinel/internal/modules/planning"
	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/planning/hash"
	planningrepo "github.com/aristath/sentinel/internal/modules/planning/repository"
	"github.com/aristath/sentinel/internal/modules/portfolio"
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

// parseFloat parses a string to float64, returns error if invalid
func parseFloat(s string) (float64, error) {
	return strconv.ParseFloat(s, 64)
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
	cashManager        domain.CashManager
	brokerClient       domain.BrokerClient
	configRepo         *planningrepo.ConfigRepository
	recommendationRepo planning.RecommendationRepositoryInterface // Interface - can be DB or in-memory
	contextBuilder     *services.OpportunityContextBuilder
	configDB           *sql.DB // For querying settings

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
	configRepo *planningrepo.ConfigRepository,
	recommendationRepo planning.RecommendationRepositoryInterface, // Interface - can be DB or in-memory
	contextBuilder *services.OpportunityContextBuilder,
	configDB *sql.DB, // For querying settings
	log zerolog.Logger,
) *Service {
	return &Service{
		triggerChecker:     triggerChecker,
		negativeRebalancer: negativeRebalancer,
		planningService:    planningService,
		positionRepo:       positionRepo,
		securityRepo:       securityRepo,
		allocRepo:          allocRepo,
		cashManager:        cashManager,
		brokerClient:       brokerClient,
		configRepo:         configRepo,
		recommendationRepo: recommendationRepo,
		contextBuilder:     contextBuilder,
		configDB:           configDB,
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

// SimulatedPortfolio represents the simulated portfolio state after trades
type SimulatedPortfolio struct {
	Positions     map[string]float64 // ISIN -> quantity
	CashBalances  map[string]float64 // Currency -> balance
	TotalValue    float64            // Total portfolio value in EUR
	TotalCost     float64            // Total cost of trades
	TradesApplied int                // Number of trades successfully applied
}

// SimulateTrade represents a trade to simulate
type SimulateTrade struct {
	ISIN     string
	Symbol   string
	Side     string
	Quantity float64
	Price    float64
	Currency string
}

// SimulateRebalance simulates the portfolio state after executing a set of trades
// Returns the simulated portfolio state with new positions and cash balances
func (s *Service) SimulateRebalance(trades []SimulateTrade) (*SimulatedPortfolio, error) {
	// Step 1: Validate required dependencies
	if s.positionRepo == nil {
		return nil, fmt.Errorf("position repository is required")
	}

	// Step 2: Get current positions
	currentPositions, err := s.positionRepo.GetAll()
	if err != nil {
		return nil, fmt.Errorf("failed to get current positions: %w", err)
	}

	// Step 3: Get current cash balances
	cashBalances := make(map[string]float64)
	if s.cashManager != nil {
		balances, err := s.cashManager.GetAllCashBalances()
		if err == nil {
			cashBalances = balances
		}
	}

	// Step 4: Build position map (ISIN -> quantity)
	positions := make(map[string]float64)
	for _, pos := range currentPositions {
		if pos.ISIN != "" {
			positions[pos.ISIN] = pos.Quantity
		}
	}

	// Step 5: Build price lookup map for efficiency
	priceByISIN := make(map[string]float64)
	for _, pos := range currentPositions {
		if pos.ISIN != "" {
			priceByISIN[pos.ISIN] = pos.CurrentPrice
		}
	}

	// Step 6: Simulate each trade
	totalCost := 0.0
	tradesApplied := 0

	for _, trade := range trades {
		// Calculate trade value
		tradeValue := trade.Quantity * trade.Price

		// Calculate commission (€2 fixed + 0.2% variable)
		commission := 2.0 + (tradeValue * 0.002)

		// Ensure currency exists in cash balances
		if trade.Currency == "" {
			trade.Currency = "EUR" // Default
		}
		if _, exists := cashBalances[trade.Currency]; !exists {
			cashBalances[trade.Currency] = 0.0
		}

		// Apply trade
		if trade.Side == "BUY" {
			// Deduct cost from cash
			totalTradeCost := tradeValue + commission
			cashBalances[trade.Currency] -= totalTradeCost
			totalCost += totalTradeCost

			// Add to position
			if trade.ISIN != "" {
				positions[trade.ISIN] += trade.Quantity
				// Store trade price for newly purchased securities
				if _, exists := priceByISIN[trade.ISIN]; !exists {
					priceByISIN[trade.ISIN] = trade.Price
				}
			}

			tradesApplied++
		} else if trade.Side == "SELL" {
			// Add proceeds to cash
			proceeds := tradeValue - commission
			cashBalances[trade.Currency] += proceeds
			totalCost += commission // Only commission counts as cost for sells

			// Subtract from position
			if trade.ISIN != "" {
				positions[trade.ISIN] -= trade.Quantity
				// Remove position if quantity becomes 0 or negative
				if positions[trade.ISIN] <= 0 {
					delete(positions, trade.ISIN)
				}
			}

			tradesApplied++
		}
	}

	// Step 7: Calculate total value (positions + cash)
	totalValue := 0.0
	for _, balance := range cashBalances {
		totalValue += balance
	}

	// Add position values using price lookup map
	for isin, qty := range positions {
		if price, exists := priceByISIN[isin]; exists {
			totalValue += qty * price
		}
	}

	return &SimulatedPortfolio{
		Positions:     positions,
		CashBalances:  cashBalances,
		TotalValue:    totalValue,
		TotalCost:     totalCost,
		TradesApplied: tradesApplied,
	}, nil
}

// CheckTriggers checks if rebalancing should be triggered based on current portfolio state
// Returns trigger result with should_rebalance flag and reason
func (s *Service) CheckTriggers() (*TriggerResult, error) {
	// Step 1: Validate required dependencies
	if s.positionRepo == nil {
		return nil, fmt.Errorf("position repository is required")
	}
	if s.allocRepo == nil {
		return nil, fmt.Errorf("allocation repository is required")
	}
	if s.triggerChecker == nil {
		return nil, fmt.Errorf("trigger checker is required")
	}

	// Step 2: Get positions
	positions, err := s.positionRepo.GetAll()
	if err != nil {
		return nil, fmt.Errorf("failed to get positions: %w", err)
	}

	// Step 3: Get target allocations
	targetAllocations, err := s.allocRepo.GetAll()
	if err != nil {
		return nil, fmt.Errorf("failed to get target allocations: %w", err)
	}

	// Step 4: Calculate total portfolio value and get cash balance
	var totalValue float64
	var cashBalance float64

	// Calculate portfolio value from positions
	for _, pos := range positions {
		totalValue += pos.MarketValueEUR
	}

	// Get cash balances
	if s.cashManager != nil {
		balances, err := s.cashManager.GetAllCashBalances()
		if err == nil {
			for _, balance := range balances {
				cashBalance += balance
			}
		}
	}

	// Add cash to total value
	totalValue += cashBalance

	// Step 5: Get settings from config DB
	enabled := true                // Default
	driftThreshold := 0.05         // Default 5%
	cashThresholdMultiplier := 2.0 // Default 2x
	minTradeSize := CalculateMinTradeAmount(2.0, 0.002, 0.01)

	if s.configDB != nil {
		// Get rebalancing_enabled
		var enabledStr string
		err := s.configDB.QueryRow("SELECT value FROM settings WHERE key = 'rebalancing_enabled'").Scan(&enabledStr)
		if err == nil {
			lowered := strings.ToLower(strings.TrimSpace(enabledStr))
			enabled = (lowered == "true" || lowered == "1" || lowered == "yes")
		}

		// Get drift_threshold
		var driftStr string
		err = s.configDB.QueryRow("SELECT value FROM settings WHERE key = 'drift_threshold'").Scan(&driftStr)
		if err == nil {
			if val, parseErr := parseFloat(driftStr); parseErr == nil {
				driftThreshold = val
			}
		}

		// Get cash_threshold_multiplier
		var cashMultStr string
		err = s.configDB.QueryRow("SELECT value FROM settings WHERE key = 'cash_threshold_multiplier'").Scan(&cashMultStr)
		if err == nil {
			if val, parseErr := parseFloat(cashMultStr); parseErr == nil {
				cashThresholdMultiplier = val
			}
		}
	}

	// Step 6: Convert positions to portfolio.Position pointers for trigger checker
	positionPtrs := make([]*portfolio.Position, len(positions))
	for i := range positions {
		positionPtrs[i] = &positions[i]
	}

	// Step 7: Check triggers
	result := s.triggerChecker.CheckRebalanceTriggers(
		positionPtrs,
		targetAllocations,
		totalValue,
		cashBalance,
		enabled,
		driftThreshold,
		cashThresholdMultiplier,
		minTradeSize,
	)

	return result, nil
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
	// Step 1: Validate required dependencies
	if s.positionRepo == nil {
		return nil, fmt.Errorf("position repository is required")
	}
	if s.securityRepo == nil {
		return nil, fmt.Errorf("security repository is required")
	}
	if s.allocRepo == nil {
		return nil, fmt.Errorf("allocation repository is required")
	}
	if s.planningService == nil {
		return nil, fmt.Errorf("planning service is required")
	}
	if s.configRepo == nil {
		return nil, fmt.Errorf("config repository is required")
	}

	// Step 2: Check minimum trade amount
	minTradeAmount := CalculateMinTradeAmount(2.0, 0.002, 0.01)
	if availableCash < minTradeAmount {
		s.log.Info().
			Float64("available_cash", availableCash).
			Float64("min_trade_amount", minTradeAmount).
			Msg("Cash below minimum trade amount")
		return []RebalanceRecommendation{}, nil
	}

	// Step 2: Build OpportunityContext using unified builder
	opportunityCtx, err := s.contextBuilder.Build()
	if err != nil {
		return nil, fmt.Errorf("failed to build opportunity context: %w", err)
	}

	// Step 3: Load planner configuration
	config, err := s.loadPlannerConfig()
	if err != nil {
		return nil, fmt.Errorf("failed to load planner config: %w", err)
	}

	// Step 4: Call planning service with rejection tracking (nil progress callback)
	planResult, err := s.planningService.CreatePlanWithRejections(opportunityCtx, config, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create plan: %w", err)
	}

	plan := planResult.Plan
	if !plan.Feasible {
		s.log.Warn().Msg("Plan is not feasible")
		return []RebalanceRecommendation{}, nil
	}

	// Store rejected opportunities if available (will be stored again when recommendations are stored,
	// but we store here to ensure they're available even if recommendation storage fails)
	if s.recommendationRepo != nil && len(planResult.RejectedOpportunities) > 0 {
		portfolioHash := s.generatePortfolioHash()
		if portfolioHash != "" {
			// Store rejected opportunities
			if err := s.recommendationRepo.StoreRejectedOpportunities(planResult.RejectedOpportunities, portfolioHash); err != nil {
				s.log.Warn().Err(err).Msg("Failed to store rejected opportunities")
				// Don't fail the whole operation if rejected opportunities can't be stored
			} else {
				s.log.Info().
					Int("rejected_count", len(planResult.RejectedOpportunities)).
					Str("portfolio_hash", portfolioHash).
					Msg("Stored rejected opportunities")
			}
		}
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

// generatePortfolioHash generates a portfolio hash from current portfolio state
// This ensures consistent hash generation across all operations
func (s *Service) generatePortfolioHash() string {
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
	return hash.GeneratePortfolioHash(hashPositions, hashSecurities, cashBalances, pendingOrders)
}

// storeRecommendations stores recommendations in the database
// Following pattern from scheduler/planner_batch.go:353-406
// This also clears old rejected opportunities for the portfolio hash to ensure consistency
func (s *Service) storeRecommendations(recommendations []RebalanceRecommendation) error {
	portfolioHash := s.generatePortfolioHash()

	// Note: Rejected opportunities are already stored in CalculateRebalanceTrades with the same hash
	// They will be cleared automatically when StorePlan is called (which clears for the portfolio hash)
	// For this path (storeRecommendations via CreateOrUpdate), we rely on the fact that
	// rejected opportunities were stored with the same hash in CalculateRebalanceTrades

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
