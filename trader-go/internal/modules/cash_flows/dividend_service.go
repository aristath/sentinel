package cash_flows

import (
	"encoding/json"
	"fmt"
	"strings"

	"github.com/rs/zerolog"
)

// DividendService creates dividend records from cash flow transactions
type DividendService interface {
	CreateFromCashFlow(cashFlow *CashFlow) error
}

// DividendCreator handles dividend record creation
type DividendCreator struct {
	dividendService DividendService
	log             zerolog.Logger
}

// NewDividendCreator creates a new dividend creator
func NewDividendCreator(dividendService DividendService, log zerolog.Logger) *DividendCreator {
	return &DividendCreator{
		dividendService: dividendService,
		log:             log.With().Str("service", "dividend_creator").Logger(),
	}
}

// ShouldCreateDividend checks if cash flow is a dividend
func (d *DividendCreator) ShouldCreateDividend(cashFlow *CashFlow) bool {
	if cashFlow.TransactionType == nil {
		return false
	}

	txType := strings.ToLower(*cashFlow.TransactionType)
	return txType == "dividend" || strings.Contains(txType, "dividend")
}

// CreateDividendRecord creates a dividend record from cash flow
func (d *DividendCreator) CreateDividendRecord(cashFlow *CashFlow) error {
	// Extract symbol from params JSON
	symbol, err := d.extractSymbol(cashFlow)
	if err != nil {
		d.log.Warn().Err(err).Str("tx_id", cashFlow.TransactionID).Msg("Failed to extract symbol from params")
		return err
	}

	// Create dividend record via dividend service
	if err := d.dividendService.CreateFromCashFlow(cashFlow); err != nil {
		d.log.Error().Err(err).Str("symbol", symbol).Msg("Failed to create dividend record")
		return fmt.Errorf("failed to create dividend record: %w", err)
	}

	d.log.Info().
		Str("symbol", symbol).
		Float64("amount", cashFlow.AmountEUR).
		Str("date", cashFlow.Date).
		Msg("Dividend record created")

	return nil
}

// extractSymbol extracts stock symbol from params JSON
func (d *DividendCreator) extractSymbol(cashFlow *CashFlow) (string, error) {
	if cashFlow.ParamsJSON == nil {
		return "", fmt.Errorf("params_json is null")
	}

	var params map[string]interface{}
	if err := json.Unmarshal([]byte(*cashFlow.ParamsJSON), &params); err != nil {
		return "", fmt.Errorf("failed to parse params JSON: %w", err)
	}

	// Try multiple field names for symbol
	for _, key := range []string{"symbol", "ticker", "isin", "stock_symbol"} {
		if val, ok := params[key]; ok {
			if symbol, ok := val.(string); ok && symbol != "" {
				return symbol, nil
			}
		}
	}

	return "", fmt.Errorf("no symbol found in params")
}
