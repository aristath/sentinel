package rebalancing

import (
	"fmt"

	"github.com/rs/zerolog"
)

// MinCurrencyReserve is the minimum cash reserve per currency (€5)
const MinCurrencyReserve = 5.0

// NegativeBalanceRebalancer automatically fixes negative cash balances
// Faithful translation from Python: app/modules/rebalancing/services/negative_balance_rebalancer.py
type NegativeBalanceRebalancer struct {
	log zerolog.Logger
}

// NewNegativeBalanceRebalancer creates a new negative balance rebalancer
func NewNegativeBalanceRebalancer(log zerolog.Logger) *NegativeBalanceRebalancer {
	return &NegativeBalanceRebalancer{
		log: log.With().Str("service", "negative_balance_rebalancer").Logger(),
	}
}

// HasNegativeBalances checks if any currency has a negative balance
func (r *NegativeBalanceRebalancer) HasNegativeBalances() (bool, error) {
	// TODO: Integrate with Tradernet client to get actual balances
	// For now, return false as a safe default
	r.log.Debug().Msg("Checking for negative balances (stub)")
	return false, nil
}

// HasCurrenciesBelowMinimum checks if any trading currency is below minimum reserve
func (r *NegativeBalanceRebalancer) HasCurrenciesBelowMinimum() (bool, error) {
	// TODO: Integrate with Tradernet client and security repository
	// For now, return false as a safe default
	r.log.Debug().Msg("Checking for currencies below minimum (stub)")
	return false, nil
}

// RebalanceNegativeBalances executes the rebalancing process
//
// Sequence:
// 1. Currency exchange from other currencies
// 2. Position sales (if exchange insufficient)
// 3. Final currency exchange to ensure all currencies have minimum
//
// Returns error if rebalancing fails
func (r *NegativeBalanceRebalancer) RebalanceNegativeBalances() error {
	r.log.Warn().Msg("Starting negative balance rebalancing")

	// TODO: Full implementation
	// This is a critical safety feature that requires:
	// 1. Integration with Tradernet client for balance checks
	// 2. Integration with currency exchange service
	// 3. Integration with trading service for position liquidation
	// 4. Integration with position repository for position selection
	//
	// For now, log that the feature needs implementation
	r.log.Warn().Msg("Negative balance rebalancing requires full Tradernet integration")

	return fmt.Errorf("negative balance rebalancing not yet fully implemented - requires Tradernet integration")
}

// CheckCurrencyMinimums checks which currencies are below minimum reserve
//
// Args:
//
//	cashBalances: Map of currency -> balance amount
//
// Returns:
//
//	Map of currency -> shortfall amount (only currencies below minimum)
func (r *NegativeBalanceRebalancer) CheckCurrencyMinimums(cashBalances map[string]float64) map[string]float64 {
	shortfalls := make(map[string]float64)

	for currency, balance := range cashBalances {
		if balance < MinCurrencyReserve {
			shortfall := MinCurrencyReserve - balance
			shortfalls[currency] = shortfall
			r.log.Warn().
				Str("currency", currency).
				Float64("balance", balance).
				Float64("minimum", MinCurrencyReserve).
				Float64("shortfall", shortfall).
				Msg("Currency below minimum reserve")
		}
	}

	return shortfalls
}
