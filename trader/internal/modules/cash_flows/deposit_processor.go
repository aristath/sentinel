package cash_flows

import (
	"fmt"
	"strings"

	"github.com/rs/zerolog"
)

// DepositProcessor processes deposits by updating cash balances
// Uses CashManager to update cash balances in the cash_balances table
type DepositProcessor struct {
	cashManager *CashManager
	log         zerolog.Logger
}

// NewDepositProcessor creates a new deposit processor
func NewDepositProcessor(cashManager *CashManager, log zerolog.Logger) *DepositProcessor {
	return &DepositProcessor{
		cashManager: cashManager,
		log:         log.With().Str("service", "deposit_processor").Logger(),
	}
}

// ProcessDeposit processes a deposit by updating the cash position
// Returns a simple map with the total amount for backward compatibility
func (p *DepositProcessor) ProcessDeposit(
	amount float64,
	currency string,
	transactionID *string,
	description *string,
) (map[string]interface{}, error) {
	if p.cashManager == nil {
		p.log.Warn().Msg("CashManager not available, skipping deposit processing")
		return map[string]interface{}{"total": amount}, nil
	}

	// Get current balance
	currentBalance, err := p.cashManager.GetCashBalance(currency)
	if err != nil {
		p.log.Error().Err(err).Msg("Failed to get current cash balance")
		return nil, fmt.Errorf("failed to get current cash balance: %w", err)
	}

	// Update cash position with new total
	newBalance := currentBalance + amount
	err = p.cashManager.UpdateCashPosition(currency, newBalance)
	if err != nil {
		p.log.Error().Err(err).Msg("Failed to update cash position")
		return nil, fmt.Errorf("failed to update cash position: %w", err)
	}

	result := map[string]interface{}{
		"total": newBalance,
	}

	p.log.Info().
		Float64("amount", amount).
		Str("currency", currency).
		Float64("previous_balance", currentBalance).
		Float64("new_balance", newBalance).
		Msg("Deposit processed and cash balance updated")

	return result, nil
}

// ShouldProcessCashFlow determines if a cash flow should trigger deposit processing
func (p *DepositProcessor) ShouldProcessCashFlow(cashFlow *CashFlow) bool {
	if cashFlow.TransactionType == nil {
		return false
	}

	txType := strings.ToLower(*cashFlow.TransactionType)

	// Match deposit types
	return txType == "deposit" ||
		txType == "refill" ||
		txType == "transfer_in"
}
