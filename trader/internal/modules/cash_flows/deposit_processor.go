package cash_flows

import (
	"fmt"
	"strings"

	"github.com/rs/zerolog"
)

// DepositProcessor processes deposits by allocating across satellite buckets
// Faithful translation from Python: app/modules/cash_flows/services/deposit_processor.py
type DepositProcessor struct {
	balanceService BalanceService
	log            zerolog.Logger
}

// BalanceService interface for dependency injection
type BalanceService interface {
	AllocateDeposit(amount float64, currency, description string) (map[string]interface{}, error)
}

// NewDepositProcessor creates a new deposit processor
func NewDepositProcessor(balanceService BalanceService, log zerolog.Logger) *DepositProcessor {
	return &DepositProcessor{
		balanceService: balanceService,
		log:            log.With().Str("service", "deposit_processor").Logger(),
	}
}

// ProcessDeposit processes a deposit and allocates across buckets
func (p *DepositProcessor) ProcessDeposit(
	amount float64,
	currency string,
	transactionID *string,
	description *string,
) (map[string]interface{}, error) {
	desc := ""
	if description != nil {
		desc = *description
	}

	result, err := p.balanceService.AllocateDeposit(amount, currency, desc)
	if err != nil {
		p.log.Error().Err(err).Msg("Failed to allocate deposit")
		return nil, fmt.Errorf("failed to allocate deposit: %w", err)
	}

	p.log.Info().
		Float64("amount", amount).
		Str("currency", currency).
		Interface("allocations", result).
		Msg("Deposit processed and allocated")

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
