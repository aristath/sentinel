package rebalancing

import (
	"fmt"

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
	log                zerolog.Logger
}

// NewService creates a new rebalancing service
func NewService(
	triggerChecker *TriggerChecker,
	negativeRebalancer *NegativeBalanceRebalancer,
	log zerolog.Logger,
) *Service {
	return &Service{
		triggerChecker:     triggerChecker,
		negativeRebalancer: negativeRebalancer,
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
func (s *Service) CalculateRebalanceTrades(availableCash float64) ([]interface{}, error) {
	// Calculate minimum trade amount using Freedom24 costs
	minTradeAmount := CalculateMinTradeAmount(
		2.0,   // €2 fixed cost
		0.002, // 0.2% variable cost
		0.01,  // 1% max cost ratio
	)

	if availableCash < minTradeAmount {
		s.log.Info().
			Float64("available_cash", availableCash).
			Float64("min_trade_amount", minTradeAmount).
			Msg("Cash below minimum trade amount")
		return []interface{}{}, nil
	}

	// TODO: Integration with planning module required
	// This should call the planning module's holistic planner to get
	// a sequence of trade recommendations, then filter to buys that
	// fit within the available cash budget.
	//
	// For now, return empty list
	s.log.Info().Msg("Rebalancing trade calculation requires planning module integration")

	return []interface{}{}, fmt.Errorf("rebalancing requires full planning module integration")
}

// ExecuteRebalancing executes a full rebalancing cycle
//
// Steps:
// 1. Check if rebalancing should be triggered (event-driven)
// 2. Calculate trade recommendations
// 3. Execute trades
// 4. Handle negative balances if needed
//
// Returns error if rebalancing fails
func (s *Service) ExecuteRebalancing(
	positions interface{},
	targetAllocations map[string]float64,
	totalPortfolioValue float64,
	cashBalance float64,
) error {
	s.log.Info().Msg("Starting rebalancing cycle")

	// TODO: Full implementation requires:
	// 1. Integration with portfolio module for position data
	// 2. Integration with planning module for trade generation
	// 3. Integration with trading module for execution
	// 4. Integration with Tradernet for balance checks
	//
	// The core logic (opportunity calculators) is already implemented
	// in the opportunities module. This service provides orchestration.

	s.log.Info().Msg("Rebalancing orchestration requires full module integration")
	return fmt.Errorf("rebalancing orchestration not yet fully implemented - requires module integration")
}
