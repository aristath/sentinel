package services

import (
	"fmt"

	"github.com/aristath/arduino-trader/internal/clients/tradernet"
	"github.com/rs/zerolog"
)

// ConversionStep represents a single step in a currency conversion path
type ConversionStep struct {
	FromCurrency string
	ToCurrency   string
	Symbol       string
	Action       string // "BUY" or "SELL"
}

// ExchangeRate holds exchange rate information
type ExchangeRate struct {
	FromCurrency string
	ToCurrency   string
	Rate         float64
	Bid          float64
	Ask          float64
	Symbol       string
}

// CurrencyExchangeService handles currency conversions via Tradernet FX pairs
//
// Supports direct conversions between EUR, USD, HKD, and GBP.
// For pairs without direct instruments (GBP<->HKD), routes via EUR.
//
// Faithful translation from Python: app/shared/services/currency_exchange_service.py
type CurrencyExchangeService struct {
	client *tradernet.Client
	log    zerolog.Logger
}

// Direct currency pairs available on Tradernet
// Format: (from_currency, to_currency) -> (symbol, action)
var DirectPairs = map[string]struct {
	Symbol string
	Action string
}{
	// EUR <-> USD (ITS_MONEY market)
	"EUR:USD": {"EURUSD_T0.ITS", "SELL"},
	"USD:EUR": {"EURUSD_T0.ITS", "BUY"},
	// EUR <-> GBP (ITS_MONEY market)
	"EUR:GBP": {"EURGBP_T0.ITS", "SELL"},
	"GBP:EUR": {"EURGBP_T0.ITS", "BUY"},
	// GBP <-> USD (ITS_MONEY market)
	"GBP:USD": {"GBPUSD_T0.ITS", "SELL"},
	"USD:GBP": {"GBPUSD_T0.ITS", "BUY"},
	// HKD <-> EUR (MONEY market, EXANTE)
	"EUR:HKD": {"HKD/EUR", "BUY"},
	"HKD:EUR": {"HKD/EUR", "SELL"},
	// HKD <-> USD (MONEY market, EXANTE)
	"USD:HKD": {"HKD/USD", "BUY"},
	"HKD:USD": {"HKD/USD", "SELL"},
}

// Symbols for rate lookups (base_currency -> quote_currency)
var RateSymbols = map[string]string{
	"EUR:USD": "EURUSD_T0.ITS",
	"EUR:GBP": "EURGBP_T0.ITS",
	"GBP:USD": "GBPUSD_T0.ITS",
	"HKD:EUR": "HKD/EUR",
	"HKD:USD": "HKD/USD",
}

// NewCurrencyExchangeService creates a new currency exchange service
func NewCurrencyExchangeService(client *tradernet.Client, log zerolog.Logger) *CurrencyExchangeService {
	return &CurrencyExchangeService{
		client: client,
		log:    log.With().Str("service", "currency_exchange").Logger(),
	}
}

// GetConversionPath returns the conversion path between two currencies
func (s *CurrencyExchangeService) GetConversionPath(fromCurrency, toCurrency string) ([]ConversionStep, error) {
	if fromCurrency == toCurrency {
		return []ConversionStep{}, nil
	}

	// Check for direct pair
	pairKey := fromCurrency + ":" + toCurrency
	if pair, ok := DirectPairs[pairKey]; ok {
		return []ConversionStep{
			{
				FromCurrency: fromCurrency,
				ToCurrency:   toCurrency,
				Symbol:       pair.Symbol,
				Action:       pair.Action,
			},
		}, nil
	}

	// GBP <-> HKD requires routing via EUR
	if (fromCurrency == "GBP" && toCurrency == "HKD") || (fromCurrency == "HKD" && toCurrency == "GBP") {
		steps := []ConversionStep{}

		// Step 1: from_currency -> EUR
		step1Key := fromCurrency + ":EUR"
		if pair1, ok := DirectPairs[step1Key]; ok {
			steps = append(steps, ConversionStep{
				FromCurrency: fromCurrency,
				ToCurrency:   "EUR",
				Symbol:       pair1.Symbol,
				Action:       pair1.Action,
			})
		}

		// Step 2: EUR -> to_currency
		step2Key := "EUR:" + toCurrency
		if pair2, ok := DirectPairs[step2Key]; ok {
			steps = append(steps, ConversionStep{
				FromCurrency: "EUR",
				ToCurrency:   toCurrency,
				Symbol:       pair2.Symbol,
				Action:       pair2.Action,
			})
		}

		if len(steps) == 2 {
			return steps, nil
		}
	}

	return nil, fmt.Errorf("no conversion path from %s to %s", fromCurrency, toCurrency)
}

// GetRate returns the current exchange rate between two currencies
//
// Returns how many units of toCurrency per 1 fromCurrency
func (s *CurrencyExchangeService) GetRate(fromCurrency, toCurrency string) (float64, error) {
	if fromCurrency == toCurrency {
		return 1.0, nil
	}

	if !s.client.IsConnected() {
		return 0, fmt.Errorf("tradernet not connected")
	}

	// Find rate symbol
	symbol, inverse := s.findRateSymbol(fromCurrency, toCurrency)
	if symbol == "" {
		// Try to get rate via path
		return s.getRateViaPath(fromCurrency, toCurrency)
	}

	// Get quote
	quote, err := s.client.GetQuote(symbol)
	if err != nil {
		s.log.Warn().Err(err).Str("symbol", symbol).Msg("Failed to get quote")
		return 0, err
	}

	if quote.Price <= 0 {
		return 0, fmt.Errorf("invalid quote price: %f", quote.Price)
	}

	if inverse {
		return 1.0 / quote.Price, nil
	}
	return quote.Price, nil
}

// findRateSymbol finds the exchange rate symbol and whether it's inverse
func (s *CurrencyExchangeService) findRateSymbol(fromCurrency, toCurrency string) (string, bool) {
	key := fromCurrency + ":" + toCurrency
	if symbol, ok := RateSymbols[key]; ok {
		return symbol, false
	}

	// Try inverse
	inverseKey := toCurrency + ":" + fromCurrency
	if symbol, ok := RateSymbols[inverseKey]; ok {
		return symbol, true
	}

	return "", false
}

// getRateViaPath gets exchange rate via conversion path
func (s *CurrencyExchangeService) getRateViaPath(fromCurrency, toCurrency string) (float64, error) {
	path, err := s.GetConversionPath(fromCurrency, toCurrency)
	if err != nil {
		return 0, err
	}

	if len(path) == 1 {
		quote, err := s.client.GetQuote(path[0].Symbol)
		if err != nil || quote.Price <= 0 {
			return 0, fmt.Errorf("failed to get quote for %s", path[0].Symbol)
		}
		return quote.Price, nil
	} else if len(path) == 2 {
		rate1, err := s.GetRate(path[0].FromCurrency, path[0].ToCurrency)
		if err != nil {
			return 0, err
		}
		rate2, err := s.GetRate(path[1].FromCurrency, path[1].ToCurrency)
		if err != nil {
			return 0, err
		}
		return rate1 * rate2, nil
	}

	return 0, fmt.Errorf("no conversion path found")
}

// Exchange executes a currency exchange
func (s *CurrencyExchangeService) Exchange(fromCurrency, toCurrency string, amount float64) error {
	if !s.validateExchangeRequest(fromCurrency, toCurrency, amount) {
		return fmt.Errorf("invalid exchange request")
	}

	path, err := s.GetConversionPath(fromCurrency, toCurrency)
	if err != nil {
		return err
	}

	if len(path) == 0 {
		return fmt.Errorf("no conversion path")
	} else if len(path) == 1 {
		return s.executeStep(path[0], amount)
	} else {
		return s.executeMultiStepConversion(path, amount)
	}
}

// validateExchangeRequest validates exchange request parameters
func (s *CurrencyExchangeService) validateExchangeRequest(fromCurrency, toCurrency string, amount float64) bool {
	if fromCurrency == toCurrency {
		s.log.Warn().Str("currency", fromCurrency).Msg("Same currency exchange requested")
		return false
	}

	if amount <= 0 {
		s.log.Error().Float64("amount", amount).Msg("Invalid exchange amount")
		return false
	}

	if !s.client.IsConnected() {
		s.log.Error().Msg("Tradernet not connected for exchange")
		return false
	}

	return true
}

// executeMultiStepConversion executes multi-step currency conversion
func (s *CurrencyExchangeService) executeMultiStepConversion(path []ConversionStep, amount float64) error {
	currentAmount := amount

	for _, step := range path {
		if err := s.executeStep(step, currentAmount); err != nil {
			s.log.Error().
				Err(err).
				Str("from", step.FromCurrency).
				Str("to", step.ToCurrency).
				Msg("Failed at conversion step")
			return err
		}

		// Update amount for next step
		rate, err := s.GetRate(step.FromCurrency, step.ToCurrency)
		if err == nil {
			currentAmount = currentAmount * rate
		}
	}

	return nil
}

// executeStep executes a single conversion step
func (s *CurrencyExchangeService) executeStep(step ConversionStep, amount float64) error {
	s.log.Info().
		Str("action", step.Action).
		Str("symbol", step.Symbol).
		Float64("amount", amount).
		Str("from", step.FromCurrency).
		Str("to", step.ToCurrency).
		Msg("Executing FX conversion")

	_, err := s.client.PlaceOrder(step.Symbol, step.Action, amount)
	return err
}

// EnsureBalance ensures we have at least minAmount in the target currency
//
// If insufficient balance, converts from sourceCurrency.
func (s *CurrencyExchangeService) EnsureBalance(currency string, minAmount float64, sourceCurrency string) (bool, error) {
	if currency == sourceCurrency {
		return true, nil
	}

	if !s.client.IsConnected() {
		return false, fmt.Errorf("tradernet not connected")
	}

	// Get balances
	currentBalance, sourceBalance, err := s.getBalances(currency, sourceCurrency)
	if err != nil {
		return false, err
	}

	// Block conversion if source balance is negative
	if sourceBalance < 0 {
		s.log.Error().
			Str("source_currency", sourceCurrency).
			Float64("source_balance", sourceBalance).
			Msg("Cannot ensure balance: source currency has negative balance")
		return false, fmt.Errorf("source currency %s has negative balance: %.2f", sourceCurrency, sourceBalance)
	}

	if currentBalance >= minAmount {
		s.log.Info().
			Str("currency", currency).
			Float64("balance", currentBalance).
			Float64("min_amount", minAmount).
			Msg("Sufficient balance")
		return true, nil
	}

	needed := minAmount - currentBalance
	return s.convertForBalance(currency, sourceCurrency, needed, sourceBalance)
}

// getBalances returns current and source currency balances
func (s *CurrencyExchangeService) getBalances(currency, sourceCurrency string) (float64, float64, error) {
	balances, err := s.client.GetCashBalances()
	if err != nil {
		return 0, 0, err
	}

	var currentBalance, sourceBalance float64

	for _, bal := range balances {
		if bal.Currency == currency {
			currentBalance = bal.Amount
			if currentBalance < 0 {
				s.log.Warn().
					Str("currency", currency).
					Float64("balance", currentBalance).
					Msg("Negative balance detected")
			}
		} else if bal.Currency == sourceCurrency {
			sourceBalance = bal.Amount
			if sourceBalance < 0 {
				s.log.Warn().
					Str("currency", sourceCurrency).
					Float64("balance", sourceBalance).
					Msg("Negative balance detected")
			}
		}
	}

	return currentBalance, sourceBalance, nil
}

// convertForBalance converts source currency to target currency to meet balance requirement
func (s *CurrencyExchangeService) convertForBalance(currency, sourceCurrency string, needed, sourceBalance float64) (bool, error) {
	// Safety check: block conversion if source balance is negative
	if sourceBalance < 0 {
		s.log.Error().
			Str("source_currency", sourceCurrency).
			Float64("source_balance", sourceBalance).
			Msg("Cannot convert: source balance is negative")
		return false, fmt.Errorf("source balance is negative")
	}

	// Add 2% buffer
	neededWithBuffer := needed * 1.02

	rate, err := s.GetRate(sourceCurrency, currency)
	if err != nil {
		s.log.Error().Err(err).Msgf("Could not get rate for %s/%s", sourceCurrency, currency)
		return false, err
	}

	sourceAmountNeeded := neededWithBuffer / rate

	if sourceBalance < sourceAmountNeeded {
		s.log.Warn().
			Str("source_currency", sourceCurrency).
			Float64("need", sourceAmountNeeded).
			Float64("have", sourceBalance).
			Msg("Insufficient source currency to convert")
		return false, fmt.Errorf("insufficient %s to convert", sourceCurrency)
	}

	s.log.Info().
		Float64("amount", sourceAmountNeeded).
		Str("from", sourceCurrency).
		Str("to", currency).
		Float64("needed", needed).
		Msg("Converting currency")

	if err := s.Exchange(sourceCurrency, currency, sourceAmountNeeded); err != nil {
		s.log.Error().Err(err).Msgf("Failed to convert %s to %s", sourceCurrency, currency)
		return false, err
	}

	s.log.Info().Msg("Currency exchange completed")
	return true, nil
}

// GetAvailableCurrencies returns list of currencies that can be exchanged
func (s *CurrencyExchangeService) GetAvailableCurrencies() []string {
	currencies := make(map[string]bool)
	for key := range DirectPairs {
		// Split "FROM:TO" into currencies
		from := key[:3]
		to := key[4:]
		currencies[from] = true
		currencies[to] = true
	}

	result := make([]string, 0, len(currencies))
	for curr := range currencies {
		result = append(result, curr)
	}
	return result
}
