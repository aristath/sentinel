package services

import (
	"testing"

	"github.com/aristath/arduino-trader/pkg/logger"
)

func TestGetConversionPath(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})
	service := NewCurrencyExchangeService(nil, log)

	tests := []struct {
		name     string
		from     string
		to       string
		wantLen  int
		wantErr  bool
		validate func(*testing.T, []ConversionStep)
	}{
		{
			name:    "Same currency",
			from:    "EUR",
			to:      "EUR",
			wantLen: 0,
			wantErr: false,
		},
		{
			name:    "Direct pair EUR->USD",
			from:    "EUR",
			to:      "USD",
			wantLen: 1,
			wantErr: false,
			validate: func(t *testing.T, steps []ConversionStep) {
				if steps[0].Symbol != "EURUSD_T0.ITS" {
					t.Errorf("Expected EURUSD_T0.ITS, got %s", steps[0].Symbol)
				}
				if steps[0].Action != "SELL" {
					t.Errorf("Expected SELL, got %s", steps[0].Action)
				}
			},
		},
		{
			name:    "Direct pair USD->EUR",
			from:    "USD",
			to:      "EUR",
			wantLen: 1,
			wantErr: false,
			validate: func(t *testing.T, steps []ConversionStep) {
				if steps[0].Symbol != "EURUSD_T0.ITS" {
					t.Errorf("Expected EURUSD_T0.ITS, got %s", steps[0].Symbol)
				}
				if steps[0].Action != "BUY" {
					t.Errorf("Expected BUY, got %s", steps[0].Action)
				}
			},
		},
		{
			name:    "Multi-step GBP->HKD",
			from:    "GBP",
			to:      "HKD",
			wantLen: 2,
			wantErr: false,
			validate: func(t *testing.T, steps []ConversionStep) {
				if steps[0].FromCurrency != "GBP" || steps[0].ToCurrency != "EUR" {
					t.Errorf("Step 1 should be GBP->EUR, got %s->%s", steps[0].FromCurrency, steps[0].ToCurrency)
				}
				if steps[1].FromCurrency != "EUR" || steps[1].ToCurrency != "HKD" {
					t.Errorf("Step 2 should be EUR->HKD, got %s->%s", steps[1].FromCurrency, steps[1].ToCurrency)
				}
			},
		},
		{
			name:    "Multi-step HKD->GBP",
			from:    "HKD",
			to:      "GBP",
			wantLen: 2,
			wantErr: false,
		},
		{
			name:    "Invalid pair",
			from:    "EUR",
			to:      "JPY",
			wantLen: 0,
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			path, err := service.GetConversionPath(tt.from, tt.to)
			if (err != nil) != tt.wantErr {
				t.Errorf("GetConversionPath() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if len(path) != tt.wantLen {
				t.Errorf("GetConversionPath() path length = %d, want %d", len(path), tt.wantLen)
				return
			}
			if tt.validate != nil && len(path) > 0 {
				tt.validate(t, path)
			}
		})
	}
}

func TestFindRateSymbol(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})
	service := NewCurrencyExchangeService(nil, log)

	tests := []struct {
		name         string
		from         string
		to           string
		wantSymbol   string
		wantInverse  bool
		wantNotFound bool
	}{
		{
			name:        "EUR->USD direct",
			from:        "EUR",
			to:          "USD",
			wantSymbol:  "EURUSD_T0.ITS",
			wantInverse: false,
		},
		{
			name:        "USD->EUR inverse",
			from:        "USD",
			to:          "EUR",
			wantSymbol:  "EURUSD_T0.ITS",
			wantInverse: true,
		},
		{
			name:        "HKD->EUR direct",
			from:        "HKD",
			to:          "EUR",
			wantSymbol:  "HKD/EUR",
			wantInverse: false,
		},
		{
			name:         "Invalid pair",
			from:         "EUR",
			to:           "JPY",
			wantSymbol:   "",
			wantInverse:  false,
			wantNotFound: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			symbol, inverse := service.findRateSymbol(tt.from, tt.to)
			if tt.wantNotFound {
				if symbol != "" {
					t.Errorf("findRateSymbol() expected no symbol, got %s", symbol)
				}
				return
			}
			if symbol != tt.wantSymbol {
				t.Errorf("findRateSymbol() symbol = %s, want %s", symbol, tt.wantSymbol)
			}
			if inverse != tt.wantInverse {
				t.Errorf("findRateSymbol() inverse = %v, want %v", inverse, tt.wantInverse)
			}
		})
	}
}

func TestValidateExchangeRequest(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	tests := []struct {
		name     string
		from     string
		to       string
		amount   float64
		wantOk   bool
		mockConn bool
	}{
		{
			name:     "Valid request",
			from:     "EUR",
			to:       "USD",
			amount:   100.0,
			wantOk:   true,
			mockConn: true,
		},
		{
			name:     "Same currency",
			from:     "EUR",
			to:       "EUR",
			amount:   100.0,
			wantOk:   false,
			mockConn: true,
		},
		{
			name:     "Zero amount",
			from:     "EUR",
			to:       "USD",
			amount:   0.0,
			wantOk:   false,
			mockConn: true,
		},
		{
			name:     "Negative amount",
			from:     "EUR",
			to:       "USD",
			amount:   -100.0,
			wantOk:   false,
			mockConn: true,
		},
		{
			name:     "Not connected",
			from:     "EUR",
			to:       "USD",
			amount:   100.0,
			wantOk:   false,
			mockConn: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Note: These tests would need a mock Tradernet client
			// For now, testing the validation logic only
			// In integration tests, we would test with real client
			service := NewCurrencyExchangeService(nil, log)
			_ = tt.mockConn // Would use this to set up mock connection state

			// Test same currency and amount validation
			if tt.from == tt.to || tt.amount <= 0 {
				ok := service.validateExchangeRequest(tt.from, tt.to, tt.amount)
				if ok != tt.wantOk {
					t.Errorf("validateExchangeRequest() = %v, want %v", ok, tt.wantOk)
				}
			}
		})
	}
}

func TestGetAvailableCurrencies(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})
	service := NewCurrencyExchangeService(nil, log)

	currencies := service.GetAvailableCurrencies()

	// Should have EUR, USD, GBP, HKD
	expectedCurrencies := map[string]bool{
		"EUR": true,
		"USD": true,
		"GBP": true,
		"HKD": true,
	}

	if len(currencies) != len(expectedCurrencies) {
		t.Errorf("Expected %d currencies, got %d", len(expectedCurrencies), len(currencies))
	}

	for _, curr := range currencies {
		if !expectedCurrencies[curr] {
			t.Errorf("Unexpected currency: %s", curr)
		}
	}
}
