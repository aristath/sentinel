package services

import (
	"fmt"
	"testing"

	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/aristath/sentinel/pkg/logger"
	"github.com/stretchr/testify/assert"
)

// mockExchangeService for testing
type mockExchangeService struct {
	rates map[string]float64 // "CURRENCY:EUR" -> rate
}

func (m *mockExchangeService) GetRate(fromCurrency, toCurrency string) (float64, error) {
	if m.rates == nil {
		return 0, fmt.Errorf("no rates configured")
	}
	key := fromCurrency + ":" + toCurrency
	if rate, ok := m.rates[key]; ok {
		return rate, nil
	}
	return 0, fmt.Errorf("rate not found for %s", key)
}

func (m *mockExchangeService) EnsureBalance(currency string, minAmount float64, sourceCurrency string) (bool, error) {
	// Not needed for price conversion tests
	return true, nil
}

func TestConvertPricesToEUR_HKD(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	exchangeService := &mockExchangeService{
		rates: map[string]float64{
			"HKD:EUR": 0.11,
		},
	}

	service := NewPriceConversionService(exchangeService, log)

	prices := map[string]float64{
		"CAT.3750.AS": 497.4, // HKD
	}

	securities := []universe.Security{
		{Symbol: "CAT.3750.AS", Currency: "HKD"},
	}

	result := service.ConvertPricesToEUR(prices, securities)

	expected := 497.4 * 0.11 // ~54.71 EUR
	assert.InDelta(t, expected, result["CAT.3750.AS"], 0.01)
}

func TestConvertPricesToEUR_Mixed(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	exchangeService := &mockExchangeService{
		rates: map[string]float64{
			"USD:EUR": 0.93,
			"HKD:EUR": 0.11,
			"GBP:EUR": 1.17,
		},
	}

	service := NewPriceConversionService(exchangeService, log)

	prices := map[string]float64{
		"VWS.AS":  42.5,  // EUR
		"AAPL":    150.0, // USD
		"0700.HK": 90.0,  // HKD
		"BARC.L":  25.0,  // GBP
	}

	securities := []universe.Security{
		{Symbol: "VWS.AS", Currency: "EUR"},
		{Symbol: "AAPL", Currency: "USD"},
		{Symbol: "0700.HK", Currency: "HKD"},
		{Symbol: "BARC.L", Currency: "GBP"},
	}

	result := service.ConvertPricesToEUR(prices, securities)

	assert.Equal(t, 42.5, result["VWS.AS"])            // EUR unchanged
	assert.InDelta(t, 139.5, result["AAPL"], 0.01)     // USD converted
	assert.InDelta(t, 9.9, result["0700.HK"], 0.01)    // HKD converted
	assert.InDelta(t, 29.25, result["BARC.L"], 0.01)   // GBP converted
}

func TestConvertPricesToEUR_MissingRate(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	exchangeService := &mockExchangeService{
		rates: map[string]float64{}, // No rates
	}

	service := NewPriceConversionService(exchangeService, log)

	prices := map[string]float64{
		"CAT.3750.AS": 497.4,
	}

	securities := []universe.Security{
		{Symbol: "CAT.3750.AS", Currency: "HKD"},
	}

	result := service.ConvertPricesToEUR(prices, securities)

	// Should fall back to native price
	assert.Equal(t, 497.4, result["CAT.3750.AS"])
}

func TestConvertPricesToEUR_EUR_NoConversion(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	exchangeService := &mockExchangeService{
		rates: map[string]float64{},
	}

	service := NewPriceConversionService(exchangeService, log)

	prices := map[string]float64{
		"VWS.AS": 42.5,
	}

	securities := []universe.Security{
		{Symbol: "VWS.AS", Currency: "EUR"},
	}

	result := service.ConvertPricesToEUR(prices, securities)

	// EUR price should remain unchanged
	assert.Equal(t, 42.5, result["VWS.AS"])
}

func TestConvertPricesToEUR_NilExchangeService(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	service := NewPriceConversionService(nil, log)

	prices := map[string]float64{
		"CAT.3750.AS": 497.4,
	}

	securities := []universe.Security{
		{Symbol: "CAT.3750.AS", Currency: "HKD"},
	}

	result := service.ConvertPricesToEUR(prices, securities)

	// Should fall back to native price when exchange service is nil
	assert.Equal(t, 497.4, result["CAT.3750.AS"])
}

func TestConvertPricesToEUR_EmptyPrices(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	exchangeService := &mockExchangeService{
		rates: map[string]float64{},
	}

	service := NewPriceConversionService(exchangeService, log)

	prices := map[string]float64{}
	securities := []universe.Security{}

	result := service.ConvertPricesToEUR(prices, securities)

	assert.Empty(t, result)
}

func TestConvertPricesToEUR_MissingCurrencyInfo(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	exchangeService := &mockExchangeService{
		rates: map[string]float64{},
	}

	service := NewPriceConversionService(exchangeService, log)

	prices := map[string]float64{
		"UNKNOWN": 100.0,
	}

	securities := []universe.Security{
		{Symbol: "OTHER"}, // Different symbol, no currency info for UNKNOWN
	}

	result := service.ConvertPricesToEUR(prices, securities)

	// Should default to EUR (no conversion)
	assert.Equal(t, 100.0, result["UNKNOWN"])
}
