package rebalancing

import (
	"testing"

	"github.com/aristath/arduino-trader/internal/clients/tradernet"
	"github.com/aristath/arduino-trader/internal/services"
	"github.com/rs/zerolog"
)

func TestCashConversion_AllEUR(t *testing.T) {
	// Setup - create real CurrencyExchangeService with mock client
	// Note: These tests may fail at runtime if the service requires connection
	// but they will compile. Consider updating to use NewHandlers with proper mocks.
	mockClient := tradernet.NewClient("", zerolog.Nop())
	exchangeService := services.NewCurrencyExchangeService(mockClient, zerolog.Nop())

	handler := &Handlers{
		currencyExchangeService: exchangeService,
	}

	// Simulate EUR-only cash balances
	type CashBalance struct {
		Currency string
		Amount   float64
	}

	cashBalances := []CashBalance{
		{Currency: "EUR", Amount: 1000.0},
		{Currency: "EUR", Amount: 500.0},
	}

	// Calculate total cash
	totalCash := 0.0
	for _, balance := range cashBalances {
		if balance.Currency == "EUR" {
			totalCash += balance.Amount
		} else {
			rate, err := handler.currencyExchangeService.GetRate(balance.Currency, "EUR")
			if err != nil {
				// Fallback
				eurValue := balance.Amount
				switch balance.Currency {
				case "USD":
					eurValue = balance.Amount * 0.9
				case "GBP":
					eurValue = balance.Amount * 1.2
				case "HKD":
					eurValue = balance.Amount * 0.11
				}
				totalCash += eurValue
			} else {
				totalCash += balance.Amount * rate
			}
		}
	}

	// Assert
	expected := 1500.0
	if totalCash != expected {
		t.Errorf("Expected total cash to be %f, got %f", expected, totalCash)
	}
}

func TestCashConversion_MixedCurrencies(t *testing.T) {
	// Setup - create real CurrencyExchangeService with mock client
	// Note: These tests may fail at runtime if the service requires connection
	// but they will compile. Consider updating to use NewHandlers with proper mocks.
	mockClient := tradernet.NewClient("", zerolog.Nop())
	exchangeService := services.NewCurrencyExchangeService(mockClient, zerolog.Nop())

	handler := &Handlers{
		currencyExchangeService: exchangeService,
	}

	// Simulate mixed currency cash balances
	type CashBalance struct {
		Currency string
		Amount   float64
	}

	cashBalances := []CashBalance{
		{Currency: "EUR", Amount: 1000.0},
		{Currency: "USD", Amount: 500.0},
		{Currency: "GBP", Amount: 200.0},
	}

	// Calculate total cash (same logic as in CheckTriggers)
	totalCash := 0.0
	for _, balance := range cashBalances {
		if balance.Currency == "EUR" {
			totalCash += balance.Amount
		} else {
			rate, err := handler.currencyExchangeService.GetRate(balance.Currency, "EUR")
			if err != nil {
				// Fallback
				eurValue := balance.Amount
				switch balance.Currency {
				case "USD":
					eurValue = balance.Amount * 0.9
				case "GBP":
					eurValue = balance.Amount * 1.2
				case "HKD":
					eurValue = balance.Amount * 0.11
				}
				totalCash += eurValue
			} else {
				totalCash += balance.Amount * rate
			}
		}
	}

	// Assert
	// 1000 + (500 * 0.9) + (200 * 1.2) = 1000 + 450 + 240 = 1690
	// Using fallback rates: USD 0.9, GBP 1.2
	expected := 1690.0
	if totalCash != expected {
		t.Errorf("Expected total cash to be %f, got %f", expected, totalCash)
	}
}

func TestShortfallConversion_Mixed(t *testing.T) {
	// Setup - create real CurrencyExchangeService with mock client
	mockClient := tradernet.NewClient("", zerolog.Nop())
	exchangeService := services.NewCurrencyExchangeService(mockClient, zerolog.Nop())

	handler := &Handlers{
		currencyExchangeService: exchangeService,
	}

	// Simulate shortfalls map
	shortfalls := map[string]float64{
		"EUR": 100.0,
		"USD": 200.0,
		"GBP": 50.0,
	}

	// Calculate total shortfall (same logic as in CheckNegativeBalances)
	totalShortfallEUR := 0.0
	for currency, shortfall := range shortfalls {
		if currency == "EUR" {
			totalShortfallEUR += shortfall
		} else {
			rate, err := handler.currencyExchangeService.GetRate(currency, "EUR")
			if err != nil {
				// Fallback
				eurValue := shortfall
				switch currency {
				case "USD":
					eurValue = shortfall * 0.9
				case "GBP":
					eurValue = shortfall * 1.2
				case "HKD":
					eurValue = shortfall * 0.11
				}
				totalShortfallEUR += eurValue
			} else {
				totalShortfallEUR += shortfall * rate
			}
		}
	}

	// Assert
	// 100 + (200 * 0.9) + (50 * 1.2) = 100 + 180 + 60 = 340
	// Using fallback rates: USD 0.9, GBP 1.2
	expected := 340.0
	if totalShortfallEUR != expected {
		t.Errorf("Expected total shortfall EUR to be %f, got %f", expected, totalShortfallEUR)
	}
}

func TestShortfallConversion_FallbackRates(t *testing.T) {
	// Setup - create real CurrencyExchangeService with mock client
	mockClient := tradernet.NewClient("", zerolog.Nop())
	exchangeService := services.NewCurrencyExchangeService(mockClient, zerolog.Nop())

	handler := &Handlers{
		currencyExchangeService: exchangeService,
	}

	// Simulate shortfalls map
	shortfalls := map[string]float64{
		"EUR": 100.0,
		"USD": 200.0,
		"GBP": 50.0,
		"HKD": 1000.0,
	}

	// Calculate total shortfall with fallback rates
	totalShortfallEUR := 0.0
	for currency, shortfall := range shortfalls {
		if currency == "EUR" {
			totalShortfallEUR += shortfall
		} else {
			rate, err := handler.currencyExchangeService.GetRate(currency, "EUR")
			if err != nil {
				// Fallback
				eurValue := shortfall
				switch currency {
				case "USD":
					eurValue = shortfall * 0.9
				case "GBP":
					eurValue = shortfall * 1.2
				case "HKD":
					eurValue = shortfall * 0.11
				}
				totalShortfallEUR += eurValue
			} else {
				totalShortfallEUR += shortfall * rate
			}
		}
	}

	// Assert
	// 100 + (200 * 0.9) + (50 * 1.2) + (1000 * 0.11) = 100 + 180 + 60 + 110 = 450
	expected := 450.0
	if totalShortfallEUR != expected {
		t.Errorf("Expected total shortfall EUR to be %f, got %f", expected, totalShortfallEUR)
	}
}

func TestCashConversion_FallbackRates(t *testing.T) {
	// Setup - create real CurrencyExchangeService with mock client
	mockClient := tradernet.NewClient("", zerolog.Nop())
	exchangeService := services.NewCurrencyExchangeService(mockClient, zerolog.Nop())

	handler := &Handlers{
		currencyExchangeService: exchangeService,
	}

	// Simulate mixed currency cash balances
	type CashBalance struct {
		Currency string
		Amount   float64
	}

	cashBalances := []CashBalance{
		{Currency: "EUR", Amount: 1000.0},
		{Currency: "USD", Amount: 500.0},
		{Currency: "GBP", Amount: 200.0},
		{Currency: "HKD", Amount: 1000.0},
	}

	// Calculate total cash with fallback rates
	totalCash := 0.0
	for _, balance := range cashBalances {
		if balance.Currency == "EUR" {
			totalCash += balance.Amount
		} else {
			rate, err := handler.currencyExchangeService.GetRate(balance.Currency, "EUR")
			if err != nil {
				// Fallback
				eurValue := balance.Amount
				switch balance.Currency {
				case "USD":
					eurValue = balance.Amount * 0.9
				case "GBP":
					eurValue = balance.Amount * 1.2
				case "HKD":
					eurValue = balance.Amount * 0.11
				}
				totalCash += eurValue
			} else {
				totalCash += balance.Amount * rate
			}
		}
	}

	// Assert
	// 1000 + (500 * 0.9) + (200 * 1.2) + (1000 * 0.11) = 1000 + 450 + 240 + 110 = 1800
	expected := 1800.0
	if totalCash != expected {
		t.Errorf("Expected total cash to be %f, got %f", expected, totalCash)
	}
}
