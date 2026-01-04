package cash_flows

import (
	"encoding/json"
	"fmt"

	"github.com/aristath/arduino-trader/internal/modules/dividends"
	"github.com/rs/zerolog"
)

// DividendServiceImpl implements DividendService interface
// Adapter between DividendCreator (cash_flows module) and DividendRepository (dividends module)
type DividendServiceImpl struct {
	dividendRepo *dividends.DividendRepository
	log          zerolog.Logger
}

// NewDividendServiceImpl creates a new dividend service implementation
func NewDividendServiceImpl(dividendRepo *dividends.DividendRepository, log zerolog.Logger) *DividendServiceImpl {
	return &DividendServiceImpl{
		dividendRepo: dividendRepo,
		log:          log.With().Str("service", "dividend_service_impl").Logger(),
	}
}

// CreateFromCashFlow implements DividendService interface
// Creates a dividend record from a cash flow transaction
func (s *DividendServiceImpl) CreateFromCashFlow(cashFlow *CashFlow) error {
	// 1. Extract symbol from params JSON
	symbol, err := s.extractSymbol(cashFlow)
	if err != nil {
		return fmt.Errorf("failed to extract symbol: %w", err)
	}

	// 2. Check if dividend already exists for this cash flow
	exists, err := s.dividendRepo.ExistsForCashFlow(cashFlow.ID)
	if err != nil {
		return fmt.Errorf("failed to check existence: %w", err)
	}
	if exists {
		s.log.Debug().Int("cash_flow_id", cashFlow.ID).Msg("Dividend already exists, skipping")
		return nil
	}

	// 3. Create dividend record
	cashFlowID := cashFlow.ID
	dividend := &dividends.DividendRecord{
		Symbol:      symbol,
		CashFlowID:  &cashFlowID,
		Amount:      cashFlow.Amount,
		Currency:    cashFlow.Currency,
		AmountEUR:   cashFlow.AmountEUR,
		PaymentDate: cashFlow.Date,
		Reinvested:  false,
	}

	if err := s.dividendRepo.Create(dividend); err != nil {
		return fmt.Errorf("failed to create dividend: %w", err)
	}

	s.log.Info().
		Str("symbol", symbol).
		Float64("amount_eur", cashFlow.AmountEUR).
		Int("cash_flow_id", cashFlow.ID).
		Msg("Dividend record created")

	return nil
}

// extractSymbol extracts stock symbol from params JSON
func (s *DividendServiceImpl) extractSymbol(cashFlow *CashFlow) (string, error) {
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
